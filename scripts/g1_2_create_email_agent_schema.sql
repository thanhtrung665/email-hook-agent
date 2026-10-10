-- ============================================
-- G1.2 — TẠO BẢNG EMAIL-AGENT TRÊN DB ĐÍCH (project webapp)
-- Chạy THỦ CÔNG trong Supabase Dashboard → SQL Editor
-- Không đụng bất kỳ bảng Prisma nào (AiConfig/Client/RFQ/...)
-- IDEMPOTENT: chạy lại nhiều lần an toàn (IF NOT EXISTS + DO $$)
-- ============================================

-- 1) Bảng tra cứu nhãn
CREATE TABLE IF NOT EXISTS labels (
    id_label SERIAL PRIMARY KEY,
    label_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    priority SMALLINT NOT NULL DEFAULT 50,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- 2) Bảng liên lạc (người gửi)
CREATE TABLE IF NOT EXISTS contacts (
    id_contact UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_address VARCHAR(320) UNIQUE NOT NULL,
    sender_name VARCHAR(255),
    company VARCHAR(255),
    phone VARCHAR(50),
    is_internal BOOLEAN NOT NULL DEFAULT FALSE,
    is_known_customer BOOLEAN NOT NULL DEFAULT FALSE,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    email_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_contacts_email_address ON contacts (email_address);

-- 3) Hộp thư
CREATE TABLE IF NOT EXISTS mailboxes (
    id_mailbox UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_address VARCHAR(255) UNIQUE NOT NULL,
    provider VARCHAR(50) NOT NULL,
    oauth_access_token BYTEA,
    oauth_refresh_token BYTEA,
    token_expires_at TIMESTAMPTZ,
    webhook_subscription_id VARCHAR(255),
    webhook_expires_at TIMESTAMPTZ,
    sync_cursor TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4) Email
CREATE TABLE IF NOT EXISTS emails (
    id_email UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_mailbox UUID NOT NULL REFERENCES mailboxes (id_mailbox) ON DELETE CASCADE,
    id_sender UUID REFERENCES contacts (id_contact),
    message_id VARCHAR(998) NOT NULL,
    thread_id VARCHAR(998),
    in_reply_to VARCHAR(998),
    subject TEXT,
    sent_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    body_text TEXT,
    body_clean TEXT,
    language VARCHAR(10),
    has_attachments BOOLEAN NOT NULL DEFAULT FALSE,
    cc_emails JSONB,
    bcc_emails JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING_ROUTING',
    assigned_agent VARCHAR(100),
    security_flags JSONB,
    raw_storage_key VARCHAR(1024),
    html_storage_key VARCHAR(1024),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_mailbox_message UNIQUE (id_mailbox, message_id)
);
CREATE INDEX IF NOT EXISTS ix_emails_id_mailbox ON emails (id_mailbox);
CREATE INDEX IF NOT EXISTS ix_emails_id_sender ON emails (id_sender);
CREATE INDEX IF NOT EXISTS ix_emails_message_id ON emails (message_id);
CREATE INDEX IF NOT EXISTS ix_emails_thread_id ON emails (thread_id);
CREATE INDEX IF NOT EXISTS ix_emails_received_at ON emails (received_at);
CREATE INDEX IF NOT EXISTS ix_emails_status ON emails (status);
CREATE INDEX IF NOT EXISTS ix_emails_assigned_agent ON emails (assigned_agent);

-- 5) Nhãn của email (PK composite email+label+source)
CREATE TABLE IF NOT EXISTS email_labels (
    id_email UUID NOT NULL REFERENCES emails (id_email) ON DELETE CASCADE,
    id_label INTEGER NOT NULL REFERENCES labels (id_label),
    source VARCHAR(20) NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_email_labels PRIMARY KEY (id_email, id_label, source)
);

-- 6) Attachment
CREATE TABLE IF NOT EXISTS attachments (
    id_attachment UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_email UUID NOT NULL REFERENCES emails (id_email) ON DELETE CASCADE,
    file_name VARCHAR(1024) NOT NULL,
    mime_type VARCHAR(255),
    size_bytes BIGINT NOT NULL DEFAULT 0,
    sha256 VARCHAR(64),
    storage_key VARCHAR(1024) NOT NULL,
    is_inline BOOLEAN NOT NULL DEFAULT FALSE,
    process_status VARCHAR(50) NOT NULL DEFAULT 'pending'
);
CREATE INDEX IF NOT EXISTS ix_attachments_id_email ON attachments (id_email);
CREATE INDEX IF NOT EXISTS ix_attachments_sha256 ON attachments (sha256);

-- 7) Summary
CREATE TABLE IF NOT EXISTS email_summaries (
    id_summary UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_email UUID UNIQUE NOT NULL REFERENCES emails (id_email) ON DELETE CASCADE,
    content_summarized TEXT,
    key_points JSONB,
    model VARCHAR(128),
    prompt_version VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 8) Card (dữ liệu UI)
CREATE TABLE IF NOT EXISTS email_cards (
    id_email UUID PRIMARY KEY REFERENCES emails (id_email) ON DELETE CASCADE,
    card_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 9) BẢNG THEO DÕI AGENT (agent_runs) — mới cho Platform
CREATE TABLE IF NOT EXISTS agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_email UUID REFERENCES emails (id_email) ON DELETE CASCADE,
    rfq_id TEXT,
    agent_name VARCHAR(100) NOT NULL,
    label_name VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'QUEUED',
    input_json JSONB,
    output_json JSONB,
    error TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_agent_runs_status CHECK (status IN ('QUEUED','RUNNING','DONE','FAILED','ESCALATED'))
);
CREATE INDEX IF NOT EXISTS ix_agent_runs_status ON agent_runs (status);
CREATE INDEX IF NOT EXISTS ix_agent_runs_agent ON agent_runs (agent_name);
CREATE INDEX IF NOT EXISTS ix_agent_runs_email ON agent_runs (id_email);

-- 10) FK nối email ↔ RFQ (webapp) — ghi chú: FK cross-tool, tạo sau khi xác nhận kiểu cột RFQ.id (TEXT/UUID)
-- ALTER TABLE emails ADD COLUMN IF NOT EXISTS rfq_id TEXT;
-- CREATE INDEX IF NOT EXISTS ix_emails_rfq_id ON emails (rfq_id);

-- ============================================
-- KIỂM CHỨNG SAU KHI CHẠY (paste thêm đoạn này):
-- select table_name from information_schema.tables
--   where table_schema='public'
--     and table_name in ('labels','contacts','mailboxes','emails','email_labels',
--                        'attachments','email_summaries','email_cards','agent_runs')
--   order by 1;
-- -- kỳ vọng: 9 bảng
-- select count(*) from "RFQ";  -- kỳ vọng: 36 (DỮ LIỆU CŨ CÒN NGUYÊN)
-- ============================================
