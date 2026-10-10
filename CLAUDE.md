# CLAUDE.md — PSBV Agent Platform (Hợp nhất 2 Repo)

> **File này là CLAUDE.md DUY NHẤT của dự án** — hợp nhất nội dung của 2 repo:
> 1. `email-hook-agent` (repo hiện tại) — ingestion email + AI phân tích + nhãn + HITL
> 2. `psbv-sale-admin-webapp` (clone tại `psbv-saleadmin-app/`) — CRM RFQ + CBU + gửi mail
>
> **Cấu trúc file:** Phần I = thông tin hiện tại cần biết khi làm việc (đã tổng hợp); Phần II/III = bản lưu trữ nguyên văn của CLAUDE.md từng repo.
>
> **Liên quan:** kế hoạch triển khai ở [`SPEC.md`](SPEC.md) · nhật ký ở [`PROGRESS.md`](PROGRESS.md).

---

# PHẦN I — HỢP NHẤT

## 1. Tổng quan

**PSBV Agent Platform** — hệ thống agent nghiệp vụ cho team Sale Admin (PSBV Trading & Service Co., Ltd.): email đến được **ingest + phân tích + gán nhãn**, sau đó chuyển thành **RFQ** đi qua vòng đời bán hàng (RFO → Quote → CBU → Quotation → Gửi khách), mỗi bước có agent AI phụ trách và **con người luôn giữ quyền duyệt (HITL)**.

Mục tiêu hợp nhất: **2 repo → 1 hệ thống thống nhất**, 1 database, 1 UI, mọi agent định tuyến theo nhãn.

### Bảng so sánh 2 repo

| | **email-agent** (repo này) | **psbv-sale-admin-webapp** |
|---|---|---|
| Đường dẫn | `E:\AI_LEARNING\email-agent` | `psbv-saleadmin-app/` (clone, gitignore) |
| GitHub | `thanhtrung665/email-hook-agent` | `thanhtrung665/psbv-sale-admin-webapp` |
| Vai trò | Ingest + phân tích + nhãn + HITL | CRM: RFQ, CBU, PDF, gửi mail, dashboard |
| Backend | FastAPI + SQLAlchemy 2.x + Alembic | Next.js API Routes (server) |
| Frontend | Next.js 16 + React 19 + Tailwind 4 (`frontend/`) | Next.js 14 + React 18 + shadcn/ui (17 trang) |
| ORM | SQLAlchemy + Alembic | Prisma 7 |
| DB | Supabase PostgreSQL (`db.dmllfbsrnoprdhwltxic`) | Supabase PostgreSQL (**project ref khác** — cần chốt) |
| Auth | Không (API mở nội bộ) | NextAuth v4 + bcrypt, role `ADMIN`/`SALE_ADMIN` |
| AI | LangChain + `langchain-google-genai`, `gemini-2.5-flash` | `@google/generative-ai`, config trong bảng `AiConfig` |
| Email nhận | MS Graph webhook + delta poll | Chưa có (chỉ gửi) |
| Email gửi | Có sẵn `sendEmailViaGraph` (chưa dùng nhiều) | `src/lib/ms-graph.ts` — transport duy nhất, `drilling@psbvn.com` |
| Kiểm thử | `app/tests/*` (script) | Jest 23 suite / 382 test + GitHub Actions CI |

### Mục tiêu kiến trúc sau hợp nhất

```
Outlook (drilling@psbvn.com)
   │  Graph webhook / delta poll
   ▼
[ email-agent · FastAPI · Python ]
   ingestion → preprocess → AI phân tích → labels (14) → HITL
   │
   │  POST /api/email/inbound (service-role, MỚI)
   │  POST /api/rfq/{id}/ingest-supplier-email (MỚI)
   ▼
[ webapp · Next.js · TypeScript ]  ← dashboard duy nhất người dùng mở
   RFQ lifecycle (7 trạng thái) · CBU v2 · PDF · Email Review Agent · MS Graph gửi mail
   │
   ▼
[ 1 database PostgreSQL (Supabase) ]  ← schema hợp nhất, có FK emails.rfq_id
```

**Nguyên tắc thiết kế (giữ nguyên tinh thần "mở" của 2 repo):** mọi component hoán đổi được; agent định tuyến theo nhãn; AI **không bao giờ tự gửi email** — luôn qua duyệt của Sale Admin; server là nguồn quyết định giá.

## 2. Kiến trúc hợp nhất

### 2.1 Tầng ingestion & nhãn (email-agent — đã chạy thật)

- **2 đường vào hội tụ** ở `app/services/email_processing_pipeline.py::EmailPipeline.process_and_save`:
  - **Webhook (push):** `app/api/webhooks.py::outlook_webhook` → echo `validationToken` → check `schedule.is_active()` → `get_worker().submit(message_id)` → trả 202 (fire-and-forget).
  - **Poll nền:** `app/main.py::lifespan` → `app/services/ingestion_worker.py::_run` → `MSGraphService.get_messages_delta()` (cursor = `mailboxes.sync_cursor`) → `_process_message` (dedupe `id_mailbox + message_id`).
- **Pipeline:** `get_email_content` → `EmailPreprocessor.process()` (`app/utils/email_preprocessing.py`: BS4 → talon → `_strip_outlook_quotes()` → regex SĐT) → `EmailAnalyzerAgent.analyze()` (`gemini-2.5-flash`, structured output Pydantic) → ghi `Contact` / `Email` / `EmailSummary` / `EmailLabel(source=ai)` / `Attachment` (`get_storage()`) → `status = PENDING_ROUTING`.
- **14 nhãn** (`app/scripts/seed_labels.py::INITIAL_LABELS`): `INQUIRY(10)`, `QUOTE(20)`, `PO(30)`, `PROFORMA_INVOICE(40)`, `MISA_MVPO(50)`, `SOA(60)`, `CIPL_CERTIFICATES(70)`, `ORDER_PICTURE(80)`, `AWB_BOL(90)`, `SED(100)`, `SHIPMENT_DOCUMENT(110)`, `DELIVERY_TICKET(120)`, `EXCEPTION(900)`, `SPAM_ADS(999)`.
- **Gán agent DUY NHẤT** ở `app/api/emails_render.py::assign_email_label`:
  | Nhãn | status | assigned_agent |
  |---|---|---|
  | `SPAM_ADS` | `IGNORED` | `NONE` |
  | `EXCEPTION`, `SED` | `ESCALATED` | `HUMAN_MANAGER` |
  | còn lại | `PROCESSING` | `{LABEL}_AGENT` |
- **Trạng thái `emails.status`:** `PROCESSING` → `PENDING_ROUTING` → (HITL) → `IGNORED` / `ESCALATED` / `PROCESSING`.
- **Chưa có:** worker thực thi agent (`assigned_agent` hiện chỉ là chuỗi), không có `DONE`/`REPLIED`.

### 2.2 Tầng nghiệp vụ RFQ (webapp — đã chạy thật)

Vòng đời `OrderStatus` (`prisma/schema.prisma`):

| # | Trạng thái | Agent / AI phụ trách |
|---|---|---|
| 1 | `INQUIRY_RECEIVED` | `src/lib/gemini-inquiry.ts` → `POST /api/rfq/parse-inquiry` (tạo `Client`+`RFQ`+`RFQItem`) |
| 2 | `RFO_PENDING_ADMIN` | **người duyệt**; `src/lib/email-builder.ts` dựng HTML RFO (không lộ client) |
| 3 | `RFO_SENT_TO_SUPPLIER` | `POST /api/rfq/[id]/send-rfo` → `sendEmailViaGraph` |
| 4 | `SUPPLIER_QUOTED` | `src/lib/gemini-quote.ts` → `POST /api/rfq/[id]/parse-supplier-quote` |
| 5 | `CBU_PENDING_ADMIN` | engine `src/lib/cbu/` (không phải AI) — server quyết định giá |
| 6 | `QUOTATION_DRAFTED` | **Email Review Agent v1** `src/lib/agent/draft-quotation-email.ts` → `POST /api/rfq/[id]/agent/draft-quotation-email` |
| 7 | `QUOTED_TO_CLIENT` | `POST /api/rfq/[id]/send-quote` / `send-dispatch` → MS Graph |

- **Email Review Agent v1 (đã xong):** Gemini soạn nháp subject/body từ dữ liệu RFQ thật (≤10 dòng hàng, rfqCode/incoterm/paymentTerm/totalRevenue), validate qua Zod (`src/lib/schemas/agent.schemas.ts`), route chỉ đọc DB + rate-limit, UI `quote-preview` có nút "Soạn lại bằng AI", **human duyệt bắt buộc** qua `send-quote`.
- Module Gemini khác: `gemini-po.ts` (PO khách), `gemini-cipl.ts` (CIPL hải quan).
- **MS Graph là transport duy nhất** (`src/lib/ms-graph.ts`): `ClientSecretCredential` → `POST /users/{MS_GRAPH_MAILBOX}/sendMail`, `saveToSentItems: true`, mailbox `drilling@psbvn.com`. 4 route gửi: `send-rfo`, `send-quote`, `send-dispatch`, `email/send-rfq`.

### 2.3 Database schema hợp nhất (mục tiêu)

**Cùng 1 database PostgreSQL.** Hiện 2 repo trỏ 2 project-ref Supabase khác nhau → **việc đầu tiên phải chốt: gộp vào 1 project.**

Cụm bảng của mỗi bên **giữ nguyên** (không đổi tên, không đổi PK), chỉ thêm bảng liên kết:

```
── email-agent (SQLAlchemy / Alembic) ──────────────
mailboxes · contacts · emails · labels · email_labels
attachments · email_summaries · email_cards

── webapp (Prisma) ────────────────────────────────
User · Client · RFQ · RFQItem · Document · CiplRecord
CiplItem · Task · AiConfig · MasterPart · Supplier

── BẢNG LIÊN KẾT (MỚI) ───────────────────────────
emails.rfq_id      UUID NULL → RFQ.id   (FK, index)
email_threads      (tùy chọn) id, rfq_id, thread_id, last_message_at
agent_runs         (MỚI — bắt buộc cho Platform)
                   id, email_id/rfq_id, agent_name, label_id,
                   status(queued|running|done|failed|escalated),
                   input_json, output_json, error, started_at, finished_at
agent_configs      (MỚI) name, enabled, prompt, model, rate_limit
```

**Quy tắc migration (bắt buộc theo convention webapp):**
- **Không** chạy `npx prisma migrate dev` trên DB dùng chung (Prisma sẽ đề nghị reset → mất dữ liệu).
- Migration mới viết **SQL tay, idempotent** (`CREATE TABLE IF NOT EXISTS`, `DO $$ … EXCEPTION WHEN duplicate_object`), có script `node scripts/verify-*.mjs` kiểm chứng bằng Postgres nhúng.
- Alembic (phía email-agent) chỉ thêm cột/FK mới, **không** đụng bảng Prisma.
- **Luôn** đọc `information_schema` trước khi áp; backup trước; áp khi người dùng cho phép.

### 2.4 Điểm nối 2 hệ thống (3 điểm, theo thứ tự ưu tiên)

| # | Điểm nối | Việc làm | Vì sao ưu tiên |
|---|---|---|---|
| **1** | `POST /api/email/inbound` (mới, xác thực service-role) | email-agent webhook/poll → nhãn AI `INQUIRY` → gọi route này → `parseInquiryWithGemini` + `Client.upsert` + `RFQ.create` → `RFO_PENDING_ADMIN` | Ít xâm lấn nhất, tái dùng toàn bộ parsing + lifecycle sẵn có |
| **2** | `POST /api/rfq/{id}/ingest-supplier-email` (mới) | email-agent bóc PDF Quote từ mailbox → `parseSupplierQuoteWithGemini` → cập nhật `RFQItem.supplierUnitPrice`/`extWeightLbs` → `SUPPLIER_QUOTED` | Tự động hóa bước chờ hãng |
| **3** | Enrich-only | Gắn nhãn/thread/metadata vào `email_threads` (FK `rfqId`) hoặc `RFQ.extractionError`/`isProcessing` | An toàn — không tự đổi `status`, Sale Admin quyết định |

### 2.5 Danh mục Agent theo nhãn (danh sách mục tiêu)

| Nhãn | Agent | Hành động | Chạm vào |
|---|---|---|---|
| `INQUIRY` | `INQUIRY_AGENT` | Tạo RFQ từ email khách | Điểm nối 1 |
| `QUOTE` | `QUOTE_AGENT` | Bóc quote hãng → RFQItem | Điểm nối 2 |
| `PO` | `PO_AGENT` | `gemini-po` + `/api/rfq/save-customer-po` | webapp |
| `PROFORMA_INVOICE` | `PROFORMA_AGENT` | Bóc PI → cập nhật RFQ terms | webapp |
| `MISA_MVPO` | `MVPO_AGENT` | Tạo MVPO | `/api/rfq/generate-document` |
| `CIPL_CERTIFICATES` | `CIPL_AGENT` | Bóc CIPL → `CiplRecord` | `gemini-cipl` + `/api/cipl/*` |
| `AWB_BOL` | `DOCUMENT_AGENT` | Giải nghĩa vận đơn | mới |
| `SHIPMENT_DOCUMENT` / `DELIVERY_TICKET` / `ORDER_PICTURE` / `SOA` | `DOCUMENT_AGENT` | Phân loại + lưu trữ | enrich-only |
| `SED`, `EXCEPTION` | `HUMAN_MANAGER` | Báo escalat cho người | HITL (đã có) |
| `SPAM_ADS` | `NONE` | Bỏ qua | đã có |
| (RFQ `QUOTATION_DRAFTED`) | `EMAIL_REVIEW_AGENT` | Soạn nháp gửi khách | webapp v1 — **đã xong** |

### 2.6 Co che kich hoat agent: NGUOI DUYET NHAN truoc (P5, quyet dinh 2026-10-10)

```
Email vao -> AI goi y nhan (source=ai, co confidence)
   -> NGUOI DUNG CHON NHAN trong dropdown 14 nhan + DUYET (Email Gateway)
   -> chi khi DUYET moi set assigned_agent = {NHAN}_AGENT + status=PROCESSING
   -> worker chi duoc chay agent nay (khong poll tren nhan AI)
   -> moi agent = MULTI-AGENT, checkpoint moi node vao agent_runs
   -> moi diem GUI EMAIL ra ngoai dung cho nguoi xac nhan truoc khi gui
```

**2 quy trinh multi-agent (danh sach sau, chi tiet SPEC P6/P7):**

| Agent | Nhạn | Node quy trinh |
|---|---|---|
| `INQUIRY_AGENT` (P6) | `INQUIRY` | I1 phat hien file (khong file/body, pdf/docx/xlsx/anh) -> I2 boc tung cong cu -> I3 luu DB + tao RFQ -> I4 tao Quotation hang (APITemplate) -> I5 soạn mail hoi hang kem chu ky + logo -> I6 MAN DUYET (kiem chinh/sua/dien To-CC) -> GUI toi hang -> `RFO_SENT_TO_SUPPLIER` |
| `QUOTATION_AGENT` (P7) | `QUOTE` | Q1 match inquiry (thread_id/in_reply_to) -> Q2 boc file bao gia -> Q3 man nhap tham so (Payment/Delivery/IncoTerm + input CBU) -> Q4 tinh CBU (`src/lib/cbu/`) -> Q5 tao Quotation PDF (APITemplate) -> Q6 MAN DUYET email khach + PDF -> REPLY dung thread cong khach -> `QUOTED_TO_CLIENT` |

**Ten nhan:** seed 14 nhan dung `QUOTE` cho ca 2 huong (hiep + hang). Luc lam P7 chon 1 trong 2: dung chung `QUOTE` (phan biet bang Supplier.email) hoac them `QUOTATION` moi.

### 2.7 Email Gateway (P8) — 1 module trong webapp PSBV, khong phai UI rieng nua

- **Webapp `psbv-saleadmin-app`** la UI duy nhat nguoi dung mo. Email Agent khong co UI rieng — `frontend/` (email-agent) chuyen sang LEGACY sau khi Gateway live.
- **Cau truc trang:**
  ```
  src/app/(dashboard)/email-gateway/
    page.tsx           Inbox — card email sau xu ly (loc theo nhan/status/thread)
    [id]/page.tsx      Chi tiet — noi dung + summary + labels + thread + attachments
    [id]/review/       MAN DUYET nhan: dropdown 14 nhan + DUYET -> kich hoat agent
    [id]/agent/        Timeline agent_runs: node xong/dang chay/loi + retry
  ```
- **BFF (proxy nguoc email-agent qua `EMAIL_AGENT_API_URL`, auth NextAuth):** `src/app/api/email-gateway/{route, [id]/route, [id]/labels, [id]/approve, [id]/thread}`.
- **Sidebar:** muc "Email Gateway" trong `src/components/shared/sidebar.tsx::navLinks`, ngay SAU "Don hang RFQ". `adminOnly: false`, badge so email chua duyet.
- **Design:** dung shadcn/ui + Tailwind cua webapp (slate-900/blue/indigo nhu sidebar), **khong copy CSS demo tu `frontend/`** — chi copy noi dung layout 70/30 + thu tu truong (SPEC Giai doan 5 cua email-agent).

## 3. Lệnh thường dùng

```powershell
# ── email-agent (Python, Windows) ──
.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload              # backend :8000
cd frontend; npm run dev                              # UI demo :3000

# Alembic (cần PYTHONPATH)
$env:PYTHONPATH="E:\AI_LEARNING\email-agent"; alembic revision --autogenerate -m "ten"
$env:PYTHONPATH="E:\AI_LEARNING\email-agent"; alembic upgrade head

# Chất lượng code
uv run ruff check . ; uv run mypy app
python -X utf8 -m app.tests.test_db                   # test nhanh (tránh lỗi encoding)

# Docker
docker compose up -d --build
curl http://127.0.0.1:8000/api/ingestion/status

# ── webapp (Node) ──
cd psbv-saleadmin-app
npm install ; npm run dev                             # :3000
npx tsc --noEmit                                      # PHẢI 0 lỗi
npm test -- --runInBand                               # 23 suite / 382 test
npx jest __tests__/cbu                                # chỉ test CBU
```

## 4. Lưu ý quan trọng khi làm việc

### 4.1 Thuộc email-agent (Python / Windows)

- **Encoding:** terminal Windows dùng cp1258 → luôn chạy Python với `python -X utf8` khi in tiếng Việt.
- **Driver DB:** `app/db/base.py` tự đổi `postgresql://` → `postgresql+psycopg://` (psycopg3). Tạo `create_engine` mới **bắt buộc** dùng scheme này.
- **Talon/sklearn:** `email_preprocessing.py` alias `sys.modules['sklearn.svm.classes']`; shim `sklearn.externals.joblib` phải set **trước** `from talon import ...` (bug Docker từng gặp).
- **Không xóa lại các field `AGENT_*` / `INGESTION_*` trong `app/core/config.py`** — chúng đã bị xóa nhầm 1 lần (2026-10-10) làm `main.py`/`ingestion_worker.py`/`schedule.py` crash; đã khôi phục từ HEAD.
- **`.env` là file secrets** — không commit, không đưa vào git (`.gitignore` đã chặn); `.env` từng bị commit ở lịch sử cũ → **khuyến nghị rotate Supabase keys + DB password**.
- **Frontend `frontend/`** là bản demo riêng của email-agent — sẽ **gộp vào webapp** làm trang `inbox`, không phát triển thêm độc lập.

### 4.2 Thuộc webapp (Node / Prisma)

- **Không** `npx prisma migrate dev` trên DB dùng chung — sẽ reset + mất dữ liệu. Migration viết tay idempotent, có `scripts/verify-*.mjs`.
- **CBU có quy tắc bắt buộc:** đơn vị `%` luôn là số phần trăm (3 = 3%), server là nguồn quyết định giá, golden test lấy số từ file md không sửa fixture. Chi tiết: Phần III §11 (SPEC webapp).
- **Không** thêm đường ghi giá/tổng trực tiếp từ body client.
- **Email transport chỉ MS Graph** — Resend/nodemailer đã gỡ (Sprint 2), cấm dùng lại.
- **`npx tsc --noEmit` phải 0 lỗi** trước khi nhận thay đổi.
- **Path alias:** `@/*` → `src/*` (đã gỡ webpack alias; **không** import `@/lib` cũ).
- **⚠️ Bản lưu trữ có mục lỗi thời:** §4 "Common Tasks → Email Review Agent (chưa bắt đầu)" và các chỗ ghi "`POST /api/agent` mock" là bản **trước khi v1 hoàn thành**. Thực tế v1 đã xong (§13). Khi đọc Phần III, lấy ngày tháng ở header §13 làm mốc.

### 4.3 Quy tắc chung cho cả 2

1. **HITL bất biến:** AI không bao giờ tự gửi email cho khách/hãng — luôn qua duyệt.
2. **Định tuyến theo nhãn:** mọi agent mới = thêm nhãn (`seed_labels.py`) + nhánh trong `assign_email_label` + `app/services/agents/<label>_agent.py` + worker gọi nó + UI sidebar.
3. **Không commit secrets** (`.env`, `*.key`, `*.pem`, `*.bot`).
4. **Ghi nhật ký `PROGRESS.md`** mỗi task; **cập nhật `SPEC.md`** khi có task mới (mới nhất lên đầu, ở Phần I).
5. Đọc Phần II/III khi cần chi tiết nguyên văn của từng repo.

---

# PHẦN II — BẢN LƯU TRỮ: CLAUDE.md GỐC CỦA EMAIL-AGENT

> Nguyên văn `CLAUDE.md` của repo `email-hook-agent` trước khi hợp nhất (2026-10-10).

<!-- BEGIN:CLAUDE.email-agent.md -->
# CLAUDE.md

## Tổng quan dự án

**Email Hook Agent** — hệ thống multi-agent xử lý email tự động: nhận email mới từ Outlook qua Microsoft Graph webhook, phân tích bằng Gemini (LangChain), lưu vào Supabase PostgreSQL, hiển thị trên dashboard Next.js. Triết lý thiết kế "mở" — mọi component hoán đổi được mà không refactor lớn.

- **Backend:** FastAPI + SQLAlchemy 2.x + Alembic + psycopg3 (`postgresql+psycopg://`)
- **DB:** Supabase (PostgreSQL 16)
- **AI:** LangChain + `langchain-google-genai` (Gemini 1.5 Pro, `with_structured_output` trả về Pydantic)
- **Email Ingestion:** Microsoft Graph + MSAL (client credentials flow)
- **Storage:** Abstraction `StorageProvider` (LocalStorage / SupabaseStorage), DI qua `get_storage()`
- **Frontend:** Next.js 16 + React 19 + Tailwind CSS 4 (`frontend/`)
- **Package manager:** `uv` (venv tại `.venv/`)

## Cấu trúc thư mục

```
app/
  main.py                      # FastAPI app, CORS, health check
  core/
    config.py                  # Settings (pydantic-settings), đọc .env
    supabase.py                # create_client admin/anon
  db/
    base.py                    # engine, SessionLocal, Base, get_db() — retry driver psycopg3
    session.py                 # (cũ, trùng chức năng với base.py)
    models.py                  # Mailbox, Contact, Email, Label, EmailLabel, Attachment, EmailSummary, EmailCard
    database_schema.md, db_schema.mmd
  api/
    webhooks.py                # POST /api/webhooks/outlook (Microsoft Graph notification)
    emails_render.py           # GET /api/emails, GET /api/emails/{id}, POST /api/emails/{id}/labels
  services/
    email_processing_pipeline.py # EmailPipeline: get → preprocess → AI analyze → DB
    ms_graph.py                # MSGraphService: token, send, get content/attachments, webhook subscription
    email_analyzer_agent.py    # EmailAnalyzerAgent (LangChain + Gemini structured output)
    storage.py                 # StorageProvider interface + LocalStorage + SupabaseStorage + get_storage()
  utils/
    email_preprocessing.py     # EmailPreprocessor (BeautifulSoup + talon + regex)
  scripts/seed_labels.py       # Seed danh mục labels
  tests/
    test_db.py, test_msgraph.py, subscribe_webhook.py
alembic/
  env.py, versions/            # init_schema + ten_migration
frontend/
  app/page.tsx                 # Smart Inbox (mock data)
  app/emails/[id]/page.tsx     # Trang chi tiết email (Giai đoạn 5 sẽ chỉnh)
  lib/data.ts                  # LABELS + MOCK_EMAILS
  .env.local                   # NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

## Lệnh thường dùng

```powershell
# Kích hoạt venv (Windows)
.venv\Scripts\Activate.ps1

# Chạy backend
python -m uvicorn app.main:app --reload

# Chạy frontend
cd frontend; npm run dev

# Alembic (cần PYTHONPATH)
$env:PYTHONPATH="E:\AI_LEARNING\email-agent"; alembic revision --autogenerate -m "ten"
$env:PYTHONPATH="E:\AI_LEARNING\email-agent"; alembic upgrade head

# Chạy test nhanh (tránh lỗi encoding)
python -X utf8 -m app.tests.test_db
```

## Lưu ý quan trọng

- **Encoding:** Terminal Windows dùng cp1258 → luôn chạy Python với `python -X utf8` khi in tiếng Việt.
- **Driver DB:** `app/db/base.py` tự đổi `postgresql://` → `postgresql+psycopg://` (psycopg3). Nếu tạo `create_engine` mới, phải dùng scheme này.
- **Talon/sklearn:** `email_preprocessing.py` cần alias `sys.modules['sklearn.svm.classes']` vì talon dùng API sklearn cũ.
- **`EmailAnalyzerAgent.analyze()`** trả về `EmailAnalysisResult` Pydantic — pipeline dùng `ai_result.contact_info`, `ai_result.security`, `ai_result.key_points.model_dump()`.
- **Lỗi hiện tại (Giai đoạn 5):** `extract() got an unexpected keyword argument 'sender_email'` trong `EmailPreprocessor.process` → do `signature.extract(text, sender_email=...)` gọi sai API talon (bản mới dùng tham số khác, thường là `sender` hoặc không nhận sender_email).
- **Giai đoạn 5 cần làm:** cải tiến UI `frontend/app/emails/[id]/page.tsx` (70/30 layout, hiển thị theo schema), fix lỗi pipeline trên, xử lý luồng email dài (thread), kiểm tra kết nối DB, test 30 email/7 ngày.
- **Frontend** dùng mock data (`MOCK_EMAILS`), chưa nối với API thật (`NEXT_PUBLIC_API_URL` đã đặt sẵn).
- `.env` chứa secrets (SUPABASE_*, MS_CLIENT_SECRET, GEMINI_API_KEY) — không commit.

@AGENTS.md

<!-- END:CLAUDE.email-agent.md -->

---

# PHẦN III — BẢN LƯU TRỮ: CLAUDE.md GỐC CỦA WEBAPP

> Nguyên văn `CLAUDE.md` của repo `psbv-sale-admin-webapp` trước khi hợp nhất (2026-10-10).

<!-- BEGIN:CLAUDE.webapp.md -->
# CLAUDE.md — PSBV Sales Agent Platform

## Project Context

Bạn đang làm việc trên **PSBV Sales Agent Platform** — một hệ thống CRM B2B nội bộ cho team Sale Admin của công ty PSBV Trading & Service Co., Ltd. Hệ thống tự động hóa vòng đời giao dịch xuất nhập khẩu: từ tiếp nhận Inquiry → gửi RFO cho hãng → AI bóc tách Quote → tính CBU → sinh Quotation PDF → gửi email qua MS Graph.

## Quick Start

```bash
# Development
npm run dev

# Check TypeScript
npx tsc --noEmit

# Check Lint
npm run lint

# Database migrations
npx prisma migrate dev

# Generate Prisma client
npx prisma generate
```

---

## Architecture

### Tech Stack
- **Frontend:** Next.js 14 (App Router) + React 18 + TypeScript
- **Styling:** Tailwind CSS + shadcn/ui
- **Database:** PostgreSQL + Prisma ORM 7
- **Auth:** NextAuth.js v4 + bcrypt
- **AI:** Google Gemini API (document parsing)
- **Documents:** APITemplate.io (PDF generation)
- **Email:** Microsoft Graph API (Outlook)
- **Storage:** Supabase Storage

### Project Structure
```
src/
├── app/                    # Next.js App Router
│   ├── (auth)/           # Login page
│   ├── (dashboard)/      # Auth-gated pages
│   │   ├── layout.tsx   # Dashboard shell + Sidebar
│   │   ├── rfq/         # RFQ management
│   │   │   ├── [id]/
│   │   │   │   ├── rfo-review/    # RFO review page
│   │   │   │   ├── cbu-calc/     # CBU calculation page
│   │   │   │   ├── mvpo/         # MVPO creation page
│   │   │   │   └── quote-preview/ # Quotation preview page
│   │   │   ├── page.tsx  # RFQ list
│   │   │   └── new/      # Create new RFQ
│   │   ├── clients/      # Client management
│   │   ├── tasks/        # Task management
│   │   └── system-users/ # User management (Admin)
│   └── api/              # API Routes (server-side)
│       ├── rfq/          # RFQ CRUD + operations
│       ├── email/        # Email endpoints
│       └── auth/         # NextAuth
├── components/
│   ├── ui/              # shadcn/ui components
│   ├── rfq/             # RFQ-specific components
│   └── shared/          # Sidebar, etc.
└── lib/                 # DUY NHẤT (thư mục gốc lib/ đã hợp nhất vào đây ở Sprint 2 — không còn webpack alias @/lib, @/* chỉ trỏ src/*)
    ├── ms-graph.ts      # MS Graph API client — transport email duy nhất (Resend/nodemailer đã gỡ)
    ├── email-builder.ts  # Email HTML templates (RFO — "no client info")
    ├── auth.ts, prisma.ts, gemini-*.ts, catalog-matcher.ts, rfq-code.ts, supabase/, schemas/  # phần còn lại của lib cũ, giữ nguyên hành vi
    ├── cbu/             # CBU engine v2 (SPEC §11.8): calculateCbu(), pools, pricing, checks, profiles/
    └── utils.ts         # Utilities (cn() helper)
```

---

## Key Domain Concepts

| Term | Description |
|------|-------------|
| **RFQ** | Request for Quotation — Đơn yêu cầu báo giá |
| **RFO** | Request for Offer — Phiếu gửi hãng hỏi giá |
| **CBU** | Cost Build Up — Tính giá thành bao gồm tất cả chi phí |
| **DDP** | Delivered Duty Paid — Giá đã bao gồm thuế, vận chuyển |
| **MVPO** | Manufacturer's Vendor Purchase Order — Đơn đặt hàng |
| **CI/PL** | Commercial Invoice / Packing List — Chứng từ hải quan |

---

## RFQ Status Lifecycle

```
INQUIRY_RECEIVED → RFO_PENDING_ADMIN → RFO_SENT_TO_SUPPLIER →
SUPPLIER_QUOTED → CBU_PENDING_ADMIN → QUOTATION_DRAFTED → QUOTED_TO_CLIENT
```

1. **INQUIRY_RECEIVED**: Khách gửi yêu cầu (AI bóc tách)
2. **RFO_PENDING_ADMIN**: Chờ Sale Admin duyệt RFO
3. **RFO_SENT_TO_SUPPLIER**: Đã gửi RFO cho hãng
4. **SUPPLIER_QUOTED**: Hãng đã báo giá (AI bóc tách Quote)
5. **CBU_PENDING_ADMIN**: Chờ Sale Admin tính CBU
6. **QUOTATION_DRAFTED**: Đã sinh PDF Quotation nháp
7. **QUOTED_TO_CLIENT**: Đã gửi báo giá cho khách

---

## CBU Module (đang tái cấu trúc — CBU v2)

**Trạng thái (22/09/2026):** Phase C0–C5 **xong** (C4 = profile `FCA_DAP` Baker Hughes: `src/lib/cbu/profiles/fca-dap.ts`, kịch bản = điều khoản thanh toán, `quoteBasis` FCA/DAP, bỏ chặn "Nước ngoài" ở modal; C5 = sửa payload Quotation PDF, xoá trang legacy + adapter cũ) — engine v2 khớp Excel từng dòng; lưu/đọc + API v2 (`src/lib/cbu/db/`, `/api/rfq/[id]/cbu`) tính lại phía server; giao diện mới ở `src/components/cbu/` (logic thuần ở `src/lib/cbu/ui/`) là **duy nhất** (trang cũ `?legacy=1`, adapter `calculateCBU()`, route `calculate-cbu`, và `lib/cbu-engine.ts` đã bị xoá); **có kịch bản Air/Sea + so sánh** (kịch bản đầu = nền ở cột phẳng RFQ, kịch bản được chọn quyết định giá lưu và tổng — SPEC §11.3). 314 test pass. **Migration bước 1 đã áp lên DB thật (22/09); bước 2 (backfill `marginPercent`) CHỈ áp sau khi deploy code.** Đặc tả: `SPEC.md` §11 · Theo dõi: `PROGRESS.md` §6.

### Nguồn sự thật nghiệp vụ
`documents/CBU_docx/` — 4 file `.md` do đội nghiệp vụ chuyển từ Excel:
- `CBU_Margin_Input/…AC0084_DDP_VN_MARGIN_INPUT.md` · `CBU_DDPPrice_Input/…PRICE_INPUT.md` — profile `DDP_IMPORT` (Hoàng Sơn, Air/Sea)
- `CBU_BakerHughes_MarginnInput/…` · `CBU_BakerHughes_PriceInput/…` — profile `FCA_DAP` (Baker Hughes, FCA/DAP, Payment/Net 60)
- `CBU_ANALYSIS_REPORT.md` — **LỖI THỜI (27/08), đừng làm theo**: 3 "lỗi" nó nêu không phải lỗi, bản sửa logistics của nó chưa đúng.

### Quy tắc bắt buộc khi đụng vào CBU
1. **Đơn vị %**: mọi `…Percent` / `…Rate` / `…Pct` là số phần trăm (3 = 3%). Engine chia 100 (`pctToFrac`). **Không** khôi phục kiểu auto-detect "≤ 1 là phân số" (`pct()` cũ — đó là lỗi P0-6).
2. **Trọng lượng chuẩn** của engine v2 = tổng trọng lượng của dòng (lb) = `RFQItem.extWeightLbs` (`totalWeightLb`). Trọng lượng/đơn vị = `ext ÷ qty`. Riêng adapter cũ, `netWeightLbs` = **một đơn vị** (đúng nghĩa DB) — đừng trộn hai nghĩa (đó là lỗi P0-5).
3. **Công thức lõi** (đã kiểm chứng khớp Excel — SPEC §11.4): pool logistics = freight + thông quan + nội địa + **insurance**, phân bổ theo trọng lượng; bank fee = phí NH phân bổ theo Material + chi phí vốn; `DDP = ROUNDUP(base ÷ (1 − margin − q·(1+c)), 2)`; Commission/CIT tính **sau** khi có giá bán. **Duty base (profile `DDP_IMPORT`) = `Material + Freight phân bổ + Insurance phân bổ`** (CIF thực — **không** dùng công thức Excel col L `Material + toàn bộ Logistics`, vì Logistics còn gồm thông quan/nội địa/other không thuộc trị giá tính thuế; quyết định SPEC §11.12 Q2, áp dụng 22/09/2026). Profile `FCA_DAP` (Baker) không có khái niệm Duty.
4. **Chi phí theo lô hàng mặc định = 0**; chỉ tham số chính sách (biểu phí NH, bảo hiểm, days/year, lb→kg, bước làm tròn VND) mới có mặc định, và đặt ở **một** file.
5. **Server là nguồn quyết định giá**: API tính lại từ input; không ghi số client gửi lên. Đã thực hiện ở `src/lib/cbu/db/service.ts` — route chỉ validate (Zod) rồi gọi service; đừng thêm đường ghi giá/tổng trực tiếp từ body.
6. **Mỗi phiên tính phải qua các check** C1–C4 (SPEC §11.4); finalize bị chặn khi check lỗi.
7. **Golden test lấy số từ file md**, không sửa fixture cho khớp code. Bug này từng bị che vì hai lỗi triệt tiêu ở mức tổng — luôn so **từng dòng**, không chỉ tổng.
8. **Tên chỉ số trên giao diện CBU dùng đúng tiếng Anh của workbook** (cột, tham số, KPI, hàng tổng hợp: `Material Cost`, `Unit Cost`, `DDP Price (USD)`, `Sales Price`, `% Margin`, `TOTAL BANK FEE`, `Incoterm 1 — FCA`, `Freight per Logistic (reference)`…). Lấy từ 4 file md trước, giữ nguyên chữ hoa/viết tắt; tiếng Việt chỉ cho giải thích (hint), thông báo, nút. Không tự đặt tên tiếng Việt cho thuật ngữ đã có trong workbook. Nhãn nằm ở `src/lib/cbu/ui/draft.ts` (`PARAM_FIELDS`, `FCA_DAP_TEXT`) và các component trong `src/components/cbu/`.

### Cảnh báo migration
DB đang **lệch migration cả ở mức cột** so với `prisma/migrations`. **Không chạy `npx prisma migrate dev`** — Prisma sẽ đề nghị reset và xoá dữ liệu. Migration CBU được viết **SQL tay, idempotent** (`prisma/migrations/20260921120000_cbu_v2/migration.sql`); kiểm chứng bằng `node scripts/verify-cbu-migration.mjs` (Postgres nhúng, không đụng DB thật). Migration tách 2 bước: `20260921120000_cbu_v2` (chỉ thêm cột/default — an toàn với code cũ) và `20260921120100_cbu_v2_margin_cleanup` (backfill `marginPercent` — **chỉ sau khi code mới đã deploy**, vì `GET /api/rfq/[id]` bản cũ ép `null → 0` và trang cũ coi đó là override 0%). Thứ tự bắt buộc: **backup → bước 1 → deploy code → bước 2** (deploy mà chưa áp bước 1 thì mọi truy vấn `RFQ` lỗi). **Trạng thái: bước 1 ĐÃ áp lên Supabase (22/09/2026), bước 2 chưa.** Máy dev chạy nhánh này với .env trỏ Supabase cần bước 1 (nếu thiếu, mọi truy vấn RFQ lỗi và trang CBU không tải được). Đừng ghi vào DB dùng chung (Supabase) khi chưa được người dùng cho phép rõ ràng. Migration Prisma mới cho phần CBU cũng nên viết tay và có script kiểm chứng tương tự. Xem SPEC §11.8.

Cùng lý do lệch migration: `prisma/migrations` trước đây chưa từng tạo 6 model `Task`/`AiConfig`/`MasterPart`/`Supplier`/`CiplRecord`/`CiplItem` (+ enum `TaskStatus`) dù `schema.prisma` đã khai báo từ lâu và code production đang dùng — soạn ở `prisma/migrations/20260922130000_missing_models/migration.sql`, cùng phong cách hand-written/idempotent (`CREATE TABLE IF NOT EXISTS`, `CREATE TYPE`/`ADD CONSTRAINT` bọc trong `DO $$ … EXCEPTION WHEN duplicate_object`); kiểm chứng bằng `node scripts/verify-missing-models-migration.mjs` (Postgres nhúng, gồm cả kịch bản bảng đã tồn tại sẵn ngoài migration — trường hợp thực tế của DB production). **Trạng thái: ĐÃ áp lên Supabase thật (22/09/2026)**, có sự đồng ý rõ ràng của người dùng — đọc `information_schema` trước khi áp xác nhận cả 6 bảng đã tồn tại và khớp 100% `schema.prisma`, nên đây là no-op thật sự trên schema, chỉ đồng bộ sổ sách `_prisma_migrations`. Xem PROGRESS.md §4 SPRINT 1 để biết chi tiết quy trình.

### Lệnh hữu ích
```bash
npm test -- --runInBand          # 21 suite / 366 test phải xanh (--runInBand: worker song song có thể hết RAM trên máy yếu)
node scripts/verify-cbu-migration.mjs  # kiểm chứng migration SQL tay (không cần DB)
node scripts/verify-missing-models-migration.mjs  # kiểm chứng migration 6 model thiếu (không cần DB)
node scripts/verify-fk-indexes-migration.mjs  # kiểm chứng migration index cho 7 cột FK (không cần DB)
npx tsx scripts/cbu-audit.ts --help    # audit giá đã lưu vs engine v2 (chỉ đọc, cần DATABASE_URL)
npx tsx scripts/dev-cbu-sandbox.ts     # sandbox: Postgres nhúng + dữ liệu AC0084 + next dev (localhost:3100), KHÔNG dùng DB thật
node scripts/e2e-cbu-sandbox.cjs       # 48 kiểm tra API end-to-end trên sandbox, gồm Baker (đổi dữ liệu — khởi động lại sandbox trước mỗi lần chạy lại)
npx jest __tests__/cbu            # chỉ test CBU (golden AC0084 + AC0481, tích hợp, render)
node scripts/gen-cbu-fixture.mjs  # sinh lại fixture từ file md (không sửa tay fixture)
npx tsc --noEmit                  # phải 0 lỗi
```

---

## Important Patterns

### 1. API Routes
- Tất cả API routes nằm trong `src/app/api/`
- Dùng Next.js App Router conventions
- Import `authOptions` từ `@/lib/auth` để get session
- Prisma client từ `@/lib/prisma`

```typescript
import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth/next";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  // ... handler
}
```

### 2. Auth Guards
- Dashboard layout đã có auth check (`@/components/shared/sidebar`)
- API routes cần check session manually
- Role-based access: `ADMIN` và `SALE_ADMIN`

### 3. Email Sending
- **MS Graph — transport duy nhất** (Sprint 2, 22/09/2026: gỡ bỏ Resend/nodemailer khỏi `send-rfo`, `send-rfq`/`quick-email-modal`; trước đó 2 route này gửi thật qua sandbox domain `onboarding@resend.dev`, không phải domain công ty). Dùng `sendEmailViaGraph()` từ `@/lib/ms-graph`
  - Auto lấy token từ Azure AD credentials
  - Hỗ trợ PDF attachments (tham số `attachmentUrl`/`fileName` optional — email không đính kèm vẫn gửi được)
  - Email gửi từ `drilling@psbvn.com`

```typescript
import { sendEmailViaGraph } from "@/lib/ms-graph";

await sendEmailViaGraph({
  to: "recipient@example.com",
  subject: "Subject",
  bodyHtml: "<p>HTML content</p>",
  attachmentUrl: "https://...", // Optional
  fileName: "document.pdf"      // Optional
});
```

### 4. AI Document Parsing
- Dùng Gemini API qua `src/lib/gemini-inquiry.ts`, `gemini-quote.ts`, `gemini-po.ts`, `gemini-cipl.ts`
- AI config lưu trong database (`AiConfig` model)

### 5. PDF Generation
- Dùng APITemplate.io qua `/api/rfq/generate-document`
- Templates: Quotation, MVPO

---

## Environment Variables

**Critical** (phải có trên Vercel):
```bash
DATABASE_URL
NEXTAUTH_SECRET
NEXTAUTH_URL
NEXT_PUBLIC_SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
GOOGLE_GEMINI_API_KEY
APITEMPLATE_API_KEY
APITEMPLATE_QUOTATION_TEMPLATE_ID
APITEMPLATE_MVPO_TEMPLATE_ID
AZURE_TENANT_ID
AZURE_CLIENT_ID
AZURE_CLIENT_SECRET
MS_GRAPH_MAILBOX=drilling@psbvn.com
```

(Không còn `RESEND_API_KEY` — Sprint 2 đã gỡ Resend/nodemailer, MS Graph là transport email duy nhất. Cột `AiConfig.resendApiKey` trong DB vẫn còn nhưng không còn được code đọc/ghi.)

---

## Common Tasks

### Add new API endpoint
1. Tạo file trong `src/app/api/[module]/[action]/route.ts`
2. Dùng template pattern ở trên
3. Test với Postman/curl

### Add new component
1. Đặt trong folder phù hợp (`components/ui/`, `components/rfq/`)
2. Nếu cần UI primitives, kiểm tra shadcn/ui trước
3. Dùng `cn()` từ `@/lib/utils` cho className

### Modify CBU calculation
- **Đọc mục "CBU Module" bên dưới trước.** Đổi công thức = sửa golden test trước, rồi mới sửa engine.
- Engine v2: `src/lib/cbu/` — dùng `import { calculateCbu } from "@/lib/cbu"`. Adapter cũ `calculateCBU()` và shim `lib/cbu-engine.ts` đã bị xoá ở Phase C5 — không còn tồn tại, đừng import.
- Trang `cbu-calc/page.tsx` **chỉ hiển thị và gọi engine** — không chứa công thức.

### Add new email template
- Email builder trong `src/lib/email-builder.ts`
- Các functions hiện có: `buildRfoEmailHtml()`, `buildOrderTableHtml()` (dùng cho RFO gửi hãng — ràng buộc "không chứa thông tin khách hàng"). Không còn `buildQuotationEmailHtml()` — đã xoá ở Sprint 2 vì mồ côi (không ai import) và tự ký sai domain

### Dashboard Analytics (Phase 2 — v1 xong 22/09)
- Chi tiết: `SPEC.md` §12. Theo dõi: `PROGRESS.md` §7.
- `/overview` đã có biểu đồ xu hướng doanh thu/margin theo tháng, phễu trạng thái, top khách hàng — dùng `recharts`. Tầng gộp số thuần ở `src/lib/analytics/aggregate.ts` (`revenueByMonth`, `statusBreakdown`, `topClients` — không phụ thuộc Prisma, có test). Component biểu đồ ở `src/components/analytics/`.

### Email Review Agent (Phase 2 — chưa bắt đầu)
- Kế hoạch chi tiết: `SPEC.md` §13. Theo dõi: `PROGRESS.md` §8.
- `POST /api/agent` hiện là **mock hoàn toàn** (tự ghi chú "placeholder", trả cứng dữ liệu giả); `src/components/agent/email-review-card.tsx` đã dựng UI đầy đủ nhưng **mồ côi, không ai render**. Chưa có logic AI thật ở đâu. v1: chỉ soạn nháp email Quotation gửi khách bằng Gemini, con người luôn phải duyệt trước khi gửi (route gửi thật không đổi, vẫn `send-quote` qua MS Graph).

---

## Testing

### Test Email System
```bash
node scripts/test-ms-graph.mjs
```

### Test MS Graph Connection
```bash
# Gửi test email
curl -X POST http://localhost:3000/api/email/test-ms \
  -H "Content-Type: application/json" \
  -d '{"to":"test@example.com","subject":"Test","body":"<p>Test</p>"}'
```

---

## Deployment

- **Platform:** Vercel
- **Trigger:** Auto-deploy on GitHub push to `main`
- **Build:** `npm run build`

Sau khi push lên GitHub, Vercel sẽ tự động build và deploy.

---

## Code Style

- **TypeScript:** Strict mode, avoid `any`
- **Naming:** camelCase for variables/functions, PascalCase for components
- **Imports:** Use path aliases (`@/...`)
- **API Routes:** REST conventions, return JSON with appropriate HTTP status
- **Error Handling:** Always wrap in try/catch, log errors, return user-friendly messages

---

## Troubleshooting

### Build fails on Vercel but works locally
1. Kiểm tra tất cả imports có resolve không
2. Kiểm tra environment variables trên Vercel
3. Chạy `npm run build` locally để xem lỗi

### Email not sending
1. Kiểm tra MS Graph credentials
2. Chạy `node scripts/test-ms-graph.mjs` để test
3. Kiểm tra `MS_GRAPH_MAILBOX` đúng email

### Prisma errors
1. Chạy `npx prisma generate` để regenerate client
2. Chạy `npx prisma migrate deploy` để apply migrations

---

## Resources

- [Next.js 14 Docs](https://nextjs.org/docs)
- [Prisma Docs](https://prisma.io/docs)
- [shadcn/ui](https://ui.shadcn.com)
- [Microsoft Graph API](https://docs.microsoft.com/en-us/graph/api/)
- [Gemini API](https://ai.google.dev/docs)

<!-- END:CLAUDE.webapp.md -->
