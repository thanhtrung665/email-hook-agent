-- ============================================================================
--  G1.2 — GỘP SCHEMA HỆ THỐNG: webapp (Prisma) + email-agent (SQLAlchemy)
--  DB đích: nvcanmdfdmyllvopxdst (Supabase, webapp production)
--
--  QUY TẮC:
--   • CHỈ THÊM — không DROP / không DELETE / không ALTER bảng Prisma đang có.
--   • Toàn bộ câu lệnh idempotent (IF NOT EXISTS / DO $$) → chạy lại nhiều lần an toàn.
--   • Dữ liệu webapp (User=5, RFQ=36, RFQItem=168, Client=19, Document=45,
--     Task=8, Supplier=3, AiConfig=1) được giữ nguyên.
--
--  CÁCH CHẠY: Supabase Dashboard → SQL Editor → dán toàn bộ file này → Run.
--  Sau đó chạy phần KIỂM CHỨNG ở cuối file.
-- ============================================================================


-- ############################################################################
--  PHẦN A — SCHEMA EMAIL-AGENT (8 bảng, từ app/db/models.py)
-- ############################################################################

-- A1. Hộp thư
CREATE TABLE IF NOT EXISTS "mailboxes" (
    "id_mailbox"                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "email_address"              VARCHAR(255) NOT NULL UNIQUE,
    "provider"                   VARCHAR(50)  NOT NULL,
    "oauth_access_token"         BYTEA,
    "oauth_refresh_token"        BYTEA,
    "token_expires_at"           TIMESTAMPTZ,
    "webhook_subscription_id"    VARCHAR(255),
    "webhook_expires_at"         TIMESTAMPTZ,
    "sync_cursor"                TEXT,
    "created_at"                 TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS "ix_mailboxes_email_address" ON "mailboxes" ("email_address");

-- A2. Liên lạc (người gửi)
CREATE TABLE IF NOT EXISTS "contacts" (
    "id_contact"             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "email_address"          VARCHAR(320) NOT NULL UNIQUE,
    "sender_name"            VARCHAR(255),
    "company"                VARCHAR(255),
    "phone"                  VARCHAR(50),
    "is_internal"            BOOLEAN NOT NULL DEFAULT FALSE,
    "is_known_customer"      BOOLEAN NOT NULL DEFAULT FALSE,
    "first_seen_at"          TIMESTAMPTZ NOT NULL DEFAULT now(),
    "last_seen_at"           TIMESTAMPTZ NOT NULL DEFAULT now(),
    "email_count"            INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS "ix_contacts_email_address" ON "contacts" ("email_address");

-- A3. Nhãn nghiệp vụ
CREATE TABLE IF NOT EXISTS "labels" (
    "id_label"       SERIAL PRIMARY KEY,
    "label_name"     VARCHAR(100) NOT NULL UNIQUE,
    "description"    TEXT,
    "priority"       SMALLINT NOT NULL DEFAULT 50,
    "is_active"      BOOLEAN NOT NULL DEFAULT TRUE
);

-- A4. Email
CREATE TABLE IF NOT EXISTS "emails" (
    "id_email"            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "id_mailbox"          UUID NOT NULL REFERENCES "mailboxes"("id_mailbox"),
    "id_sender"           UUID REFERENCES "contacts"("id_contact"),
    "message_id"          VARCHAR(998) NOT NULL,
    "thread_id"           VARCHAR(998),
    "in_reply_to"         VARCHAR(998),
    "subject"             TEXT,
    "sent_at"             TIMESTAMPTZ,
    "received_at"         TIMESTAMPTZ NOT NULL DEFAULT now(),
    "body_text"           TEXT,
    "body_clean"          TEXT,
    "language"            VARCHAR(10),
    "has_attachments"     BOOLEAN NOT NULL DEFAULT FALSE,
    "cc_emails"           JSONB,
    "bcc_emails"          JSONB,
    "status"              VARCHAR(50) NOT NULL DEFAULT 'PENDING_ROUTING',
    "assigned_agent"      VARCHAR(100),
    "security_flags"      JSONB,
    "raw_storage_key"     VARCHAR(1024),
    "html_storage_key"    VARCHAR(1024),
    "created_at"          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT "uq_mailbox_message" UNIQUE ("id_mailbox", "message_id")
);
CREATE INDEX IF NOT EXISTS "ix_emails_id_mailbox"     ON "emails" ("id_mailbox");
CREATE INDEX IF NOT EXISTS "ix_emails_id_sender"      ON "emails" ("id_sender");
CREATE INDEX IF NOT EXISTS "ix_emails_message_id"     ON "emails" ("message_id");
CREATE INDEX IF NOT EXISTS "ix_emails_thread_id"      ON "emails" ("thread_id");
CREATE INDEX IF NOT EXISTS "ix_emails_received_at"    ON "emails" ("received_at");
CREATE INDEX IF NOT EXISTS "ix_emails_status"         ON "emails" ("status");
CREATE INDEX IF NOT EXISTS "ix_emails_assigned_agent" ON "emails" ("assigned_agent");

-- A5. Nhãn của email (PK composite: email + label + source)
CREATE TABLE IF NOT EXISTS "email_labels" (
    "id_email"      UUID    NOT NULL REFERENCES "emails"("id_email") ON DELETE CASCADE,
    "id_label"      INTEGER NOT NULL REFERENCES "labels"("id_label"),
    "source"        VARCHAR(20) NOT NULL,   -- ai | rule | user
    "is_primary"    BOOLEAN NOT NULL DEFAULT FALSE,
    "confidence"    DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    "reason"        TEXT,
    "created_at"    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT "pk_email_labels" PRIMARY KEY ("id_email", "id_label", "source")
);

-- A6. File đính kèm
CREATE TABLE IF NOT EXISTS "attachments" (
    "id_attachment" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "id_email"      UUID NOT NULL REFERENCES "emails"("id_email") ON DELETE CASCADE,
    "file_name"     VARCHAR(1024) NOT NULL,
    "mime_type"     VARCHAR(255),
    "size_bytes"    BIGINT NOT NULL DEFAULT 0,
    "sha256"        VARCHAR(64),
    "storage_key"   VARCHAR(1024) NOT NULL,
    "is_inline"     BOOLEAN NOT NULL DEFAULT FALSE,
    "process_status" VARCHAR(50) NOT NULL DEFAULT 'pending'
);
CREATE INDEX IF NOT EXISTS "ix_attachments_id_email" ON "attachments" ("id_email");
CREATE INDEX IF NOT EXISTS "ix_attachments_sha256"  ON "attachments" ("sha256");

-- A7. Tóm tắt AI
CREATE TABLE IF NOT EXISTS "email_summaries" (
    "id_summary"          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "id_email"            UUID NOT NULL UNIQUE REFERENCES "emails"("id_email") ON DELETE CASCADE,
    "content_summarized"  TEXT,
    "key_points"          JSONB,
    "model"               VARCHAR(128),
    "prompt_version"      VARCHAR(50),
    "created_at"          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A8. Card dữ liệu cho UI
CREATE TABLE IF NOT EXISTS "email_cards" (
    "id_email"    UUID PRIMARY KEY REFERENCES "emails"("id_email") ON DELETE CASCADE,
    "card_json"   JSONB NOT NULL DEFAULT '{}'::jsonb,
    "version"     INTEGER NOT NULL DEFAULT 1,
    "updated_at"  TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ############################################################################
--  PHẦN B — BẢNG NỐI 2 HỆ THỐNG (định nghĩa cho SPEC §2.3)
-- ############################################################################

-- B1. emails.rfq_id — email này sinh ra RFQ nào (FK → "RFQ"."id")
--     Prisma dùng String @id @default(uuid()) → kiểu TEXT trong Postgres.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='emails' AND column_name='rfq_id'
    ) THEN
        ALTER TABLE "emails" ADD COLUMN "rfq_id" TEXT;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS "ix_emails_rfq_id" ON "emails" ("rfq_id");

-- B2. Bảng theo dõi agent (bắt buộc cho Agent Platform — SPEC G4)
CREATE TABLE IF NOT EXISTS "agent_runs" (
    "id"          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "id_email"    UUID REFERENCES "emails"("id_email") ON DELETE CASCADE,
    "rfq_id"      TEXT,                                   -- trỏ "RFQ"."id" (TEXT)
    "agent_name"  VARCHAR(100) NOT NULL,
    "label_name"  VARCHAR(100),
    "status"      VARCHAR(20) NOT NULL DEFAULT 'QUEUED',
    "input_json"  JSONB,
    "output_json" JSONB,
    "error"       TEXT,
    "started_at"  TIMESTAMPTZ NOT NULL DEFAULT now(),
    "finished_at" TIMESTAMPTZ,
    "created_at"  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT "ck_agent_runs_status"
        CHECK ("status" IN ('QUEUED','RUNNING','DONE','FAILED','ESCALATED'))
);
CREATE INDEX IF NOT EXISTS "ix_agent_runs_status" ON "agent_runs" ("status");
CREATE INDEX IF NOT EXISTS "ix_agent_runs_agent"  ON "agent_runs" ("agent_name");
CREATE INDEX IF NOT EXISTS "ix_agent_runs_email"  ON "agent_runs" ("id_email");

-- B3. Cấu hình agent (prompt/model/rate-limit quản lý từ DB)
CREATE TABLE IF NOT EXISTS "agent_configs" (
    "id"          SERIAL PRIMARY KEY,
    "name"        VARCHAR(100) NOT NULL UNIQUE,
    "enabled"     BOOLEAN NOT NULL DEFAULT TRUE,
    "label_name"  VARCHAR(100),
    "prompt"      TEXT,
    "model"       VARCHAR(128),
    "rate_limit"  INTEGER,
    "created_at"  TIMESTAMPTZ NOT NULL DEFAULT now(),
    "updated_at"  TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ############################################################################
--  PHẦN C — NẠP DANH MỤC NHÃN (14 nhãn từ app/scripts/seed_labels.py)
--  Idempotent: ON CONFLICT DO NOTHING theo label_name
-- ############################################################################
INSERT INTO "labels" ("label_name", "description", "priority", "is_active") VALUES
    ('INQUIRY',            'Hỏi đáp, tìm hiểu thông tin chung',                                10,  TRUE),
    ('QUOTE',              'Yêu cầu báo giá (Quote)',                                           20,  TRUE),
    ('PO',                 'Purchase Order - Đơn đặt hàng',                                       30,  TRUE),
    ('PROFORMA_INVOICE',   'Hóa đơn thanh toán -> Nhận Bank Slip -> Kế toán xác nhận',           40,  TRUE),
    ('MISA_MVPO',          'Chứng từ Misa MVPO',                                                  50,  TRUE),
    ('SOA',                'Sales Order Acknowledgement -> Báo hàng ready kèm thời gian',        60,  TRUE),
    ('CIPL_CERTIFICATES',  'Commercial Invoice Packing List / Certificates',                      70,  TRUE),
    ('ORDER_PICTURE',      'Hình ảnh đơn hàng',                                                   80,  TRUE),
    ('AWB_BOL',            'Vận đơn AWB/BOL - Cần giải nghĩa',                                  90,  TRUE),
    ('SED',                'Tờ khai xuất khẩu Mỹ',                                                100, TRUE),
    ('SHIPMENT_DOCUMENT',  'Chứng từ từ Hãng tàu/bay -> Báo về shipment cho khách',             110, TRUE),
    ('DELIVERY_TICKET',    'Phiếu giao hàng -> Chờ khách gửi lại bản đã ký',                     120, TRUE),
    ('EXCEPTION',          'Ngoại lệ - Trường hợp hiếm gặp, phức tạp',                          900, TRUE),
    ('SPAM_ADS',           'Quảng cáo, Spam -> Bỏ qua',                                          999, TRUE)
ON CONFLICT ("label_name") DO NOTHING;


-- ============================================================================
--  KIỂM CHỨNG — chạy SAU khi dán & Run phần trên
-- ============================================================================

-- C1. Kỳ vọng: 23 bảng (13 cũ + 10 mới: 8 email-agent + agent_runs + agent_configs)
--     Kiểm tra các bảng MỚI đã tạo đủ chưa:
SELECT 'BANG MOI' AS kiem_tra, table_name
FROM information_schema.tables
WHERE table_schema='public'
  AND table_name IN ('mailboxes','contacts','labels','emails','email_labels',
                     'attachments','email_summaries','email_cards',
                     'agent_runs','agent_configs')
ORDER BY table_name;
-- => phải trả về ĐÚNG 10 dòng

-- C2. DỮ LIỆU WEBAPP CÒN NGUYÊN? (so với baseline đã chụp)
SELECT 'RFQ' AS bang, count(*) AS so_dong FROM "RFQ"        -- kỳ vọng 36
UNION ALL SELECT 'RFQItem',    count(*) FROM "RFQItem"        -- kỳ vọng 168
UNION ALL SELECT 'Client',     count(*) FROM "Client"         -- kỳ vọng 19
UNION ALL SELECT 'Document',   count(*) FROM "Document"       -- kỳ vọng 45
UNION ALL SELECT 'User',       count(*) FROM "User"           -- kỳ vọng 5
UNION ALL SELECT 'Task',       count(*) FROM "Task"           -- kỳ vọng 8
UNION ALL SELECT 'Supplier',   count(*) FROM "Supplier"       -- kỳ vọng 3
UNION ALL SELECT 'AiConfig',   count(*) FROM "AiConfig"       -- kỳ vọng 1
UNION ALL SELECT 'labels',     count(*) FROM "labels"         -- kỳ vọng 14 (mới)
UNION ALL SELECT 'mailboxes',  count(*) FROM "mailboxes"      -- kỳ vọng 0 (mới)
UNION ALL SELECT 'emails',     count(*) FROM "emails";        -- kỳ vọng 0 (mới)

-- C3. 14 nhãn đã nạp đủ chưa?
SELECT count(*) AS so_nhan, min(priority) AS p_min, max(priority) AS p_max FROM "labels";
-- => 14 | 10 | 999

-- C4. Cột liên kết email ↔ RFQ đã có chưa?
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema='public' AND table_name='emails' AND column_name='rfq_id';
-- => 1 dòng: rfq_id | text

-- C5. Bảng webapp KHÔNG bị ảnh hưởng (vẫn đủ 5 migration)
SELECT migration_name, finished_at IS NOT NULL AS applied
FROM _prisma_migrations ORDER BY finished_at;
-- => 5 dòng, applied = true hết


-- ============================================================================
--  NẾU CẦN HOÀN TÁC (chỉ khi chưa có email nào và muốn gỡ bảng mới):
--    DROP TABLE IF EXISTS "agent_configs", "agent_runs", "email_cards",
--                         "email_summaries", "attachments", "email_labels",
--                         "emails", "labels", "contacts", "mailboxes";
--    (KHÔNG đụng bảng Prisma — dữ liệu webapp luôn an toàn.)
-- ============================================================================