# SPEC — Kế hoạch làm việc (Hợp nhất 2 Repo)

> **File này là SPEC DUY NHẤT của dự án.** Cấu trúc:
> - **Phần I** — Kế hoạch hợp nhất thành PSBV Agent Platform (mới nhất, 2026-10-10) — *mọi task mới thêm vào đây, mới nhất lên đầu*.
> - **Phần II** — Bản lưu trữ SPEC gốc của `email-hook-agent` (nguyên văn).
> - **Phần III** — Bản lưu trữ SPEC gốc của `psbv-sale-admin-webapp` (nguyên văn, §1–§13 — chi tiết CBU/Analytics/Email Review).
>
> Tổng quan kiến trúc & quy tắc: [`CLAUDE.md`](CLAUDE.md) · Nhật ký: [`PROGRESS.md`](PROGRESS.md).

---

# PHẦN I — KẾ HOẠCH HỢP NHẤT THÀNH AGENT PLATFORM

## P1. Bối cảnh & mục tiêu

**Tình trạng hiện tại:** 2 repo tách biệt, cả 2 đều chạy thật và có giá trị:

- `email-hook-agent` — đã ingest được 30 email/7 ngày, phân tích bằng Gemini, gán 14 nhãn, HITL gán nhãn từ UI, gắn nhãn `assigned_agent`.
- `psbv-sale-admin-webapp` — CRM đầy đủ: RFQ 7 trạng thái, CBU v2 (314 test), sinh PDF, Email Review Agent v1, MS Graph gửi mail, dashboard 17 trang, CI/CD.

**Khoảng trống khiến 2 repo chưa thành 1 hệ thống:**

| # | Khoảng trống | Hậu quả |
|---|---|---|
| G1 | 2 project-ref Supabase **khác nhau** | Dữ liệu email và RFQ nằm 2 nơi, không join được |
| G2 | Không có API nối từ ingestion → RFQ | Email INQUIRY phải bóc tay, mất lợi thế tự động |
| G3 | `assigned_agent` là chuỗi, **không có worker thực thi** | Thêm agent = thêm tên chuỗi, không chạy gì cả |
| G4 | Không có bảng theo dõi agent (`agent_runs`) | Không biết agent nào chạy, chạy gì, lỗi gì |
| G5 | Email-agent `frontend/` là demo (17 trang của webapp mới là UI thật) | 2 UI song song, người dùng không biết mở cái nào |
| G6 | Bug hồi quy `config.py` mất `AGENT_*`/`INGESTION_*` (đã khôi phục) + `.env` thiếu `SUPABASE_URL`, `WEBHOOK_BASE_URL` | Backend chưa start lại được |
| G7 | `seed_labels.py` import sai (`app.models` → `app.db.models`), `db.merge()` tạo bản ghi `EmailLabel` trùng | Chạy seed / gán lại nhãn là lỗi |
| G8 | Prompt AI **cấm** phân loại nhãn → `label_prediction` luôn `None` → `email_labels` source=`ai` rỗng | Không có nhãn tự động để agent tự chạy |

**Mục tiêu:** 1 database, 1 dashboard, mọi email được định tuyến theo nhãn đến đúng agent, mọi agent chạy thật và được theo dõi, con người giữ quyền duyệt ở mọi bước.

**Định nghĩa "Xong" chung:** từ lúc email vào Inbox → hệ thống tự gán nhãn → tự gọi đúng agent → RFQ được tạo/cập nhật → Sale Admin thấy trên 1 dashboard → bấm duyệt → gửi mail. Không có bước nào AI tự gửi mà không qua con người. Không lỗi `tsc`/`ruff`/`mypy`.

**Bốn nguyên tắc không đổi (kế thừa 2 repo):**
1. AI **không bao giờ tự gửi email** — HITL bắt buộc.
2. **Server quyết định** mọi con số nghiệp vụ (giá, CBU) — không tin body client.
3. **Migration viết tay, idempotent, có script verify** — không `prisma migrate dev` trên DB dùng chung.
4. Mọi component **hoán đổi được** — tôn trọng triết lý "mở" gốc.

---

## P2. Lộ trình tổng thể (6 Giai đoạn)

| Giai đoạn | Tên | Kết quả thấy được | Phụ thuộc |
|---|---|---|---|
| **G0** | Hồi phục & chuẩn hoá | Backend chạy lại, 2 doc hợp nhất, không còn bug chặn | — |
| **G1** | Thống nhất Database | 1 project Supabase, schema hợp nhất, FK `emails.rfq_id` | G0 |
| **G2** | Điểm nối Inbound (Inquiry) | Email khách → RFQ tự động | G1 |
| **G3** | Hợp nhất UI | 1 dashboard, trang Inbox trong webapp | G2 |
| **G4** | Agent theo nhãn chạy thật | Worker + `agent_runs` + 3 agent đầu | G2 |
| **G5** | Các agent còn lại & nâng cao | PO/CIPL/MVPO/Quote + SSE + follow-up | G4 |
| **G6** | Vận hành & mở rộng | VPS deploy, monitoring, monorepo (tùy chọn) | G5 |

Ước lượng: G0–G1 ≈ 3–4 ngày · G2 ≈ 3 ngày · G3 ≈ 4 ngày · G4 ≈ 5 ngày · G5 ≈ 6 ngày · G6 ≈ 2 ngày.

---

## G0 — Hồi phục & chuẩn hoá (1–2 ngày)

**Mục tiêu:** hệ thống chạy lại được, tài liệu đã hợp nhất, xoá các bug đã biết trước khi chồng feature.

### G0.1 — Hồi phục backend email-agent

- [x] Khôi phục `app/core/config.py` từ HEAD (mất toàn bộ `AGENT_*`/`INGESTION_*` → `main.py`, `ingestion_worker.py`, `schedule.py` crash) — *đã làm 2026-10-10*.
- [x] **Dọn `.env`** — gộp 2 khối cấu hình rời rạc thành 1 file nhất quán (39 dòng, chú thích rõ phần email-agent / webapp), chuẩn hoá tên biến theo `config.py` (`SUPABASE_SERVICE_ROLE_KEY`; `MS_*` lấy giá trị từ `AZURE_*`; thêm `SUPABASE_URL`, `WEBHOOK_BASE_URL`, `MS_TARGET_MAILBOX`), để mặc định `AGENT_*`/`INGESTION_*` ở dạng comment — *đã làm 2026-10-10*.
- [x] Đổi `DATABASE_URL` + `SUPABASE_URL` sang **project webapp `nvcanmdfdmyllvopxdst`** (theo Q1) — *đã làm 2026-10-10*.
- [x] `Settings` import OK; SQLAlchemy kết nối DB đích thành công (`app.tests.test_db` bước 1 xanh).
- [x] **2 key Supabase đã được người dùng cập nhật** (`SUPABASE_ANON_KEY` + `SUPABASE_SERVICE_ROLE_KEY` của project `nvcan…`) — *đã làm 2026-10-10*.
- [x] `python -X utf8 -m app.tests.test_db` → **2/2 xanh** (SQLAlchemy + Supabase REST API).
- [x] `python -X utf8 -m app.tests.test_msgraph` → lấy token OK (2158 ký tự), **gửi mail thật thành công** từ `drilling@psbvn.com`.
- [x] Backend `python -m uvicorn app.main:app` → `GET /` 200, `GET /api/ingestion/status` 200 (`running:true`, `within_active_window:true`, `last_error:null`).
- [x] Xác nhận DB đích = **webapp production**: PostgreSQL 17.6, 13 bảng public, 5 migration đã áp, `User`=5, `RFQ`=36. Supabase REST đọc đúng (`admin@psbv.com`/ADMIN…).
- [ ] Nếu test webhook: `python -X utf8 app/tests/subscribe_webhook.py` với `WEBHOOK_BASE_URL` public (ngrok). Nếu chỉ chạy poll thì giữ `INGESTION_ENABLED=true`, bỏ qua webhook.

### G0.2 — Sửa bug đã biết (email-agent)

| ID | Bug | File cần sửa | Tiêu chí |
|---|---|---|---|
| B1 ✅ | `seed_labels.py` import sai → crash | ĐÃ SỬA (2026-10-10): `from app.db.models import Label`, `from app.db.base import SessionLocal`; thứ tự import theo ruff. LƯU Ý: chưa chạy seed được trên DB đích vì 8 bảng email-agent **chưa tồn tại** (chờ G1 bên dưới) | Chạy sau khi có schema G1 |
| B2 ✅ (code) | `db.merge()` với PK composite → bản ghi trùng | ĐÃ SỬA (2026-10-10): bỏ `merge` → lookup-existing → update/add; bỏ `is_primary=True` trên **mọi** nhãn cũ trước khi thêm nhãn mới (HITL thắng). Ruff + mypy các file đổi: sạch | Test thật chờ DB schema (G1) — hoặc chạy trên SQLite nếu bỏ BYTEA test |
| B3 ✅ | Prompt AI cấm phân loại → `label_prediction=None` | ĐÃ SỬA + TEST THẬT (2026-10-10): viết lại prompt yêu cầu chọn 1/14 nhãn + confidence/reason. Test với Gemini thật: QUOTE/SPAM_ADS/DELIVERY_TICKET, 3/3 đúng, confidence 1.0. `pipeline` đã có sẵn code ghi `EmailLabel(source="ai")` — chỉ chờ nhãn ra khỏi None | ✅ |
| B4 | `assigned_agent` không ai thực thi | Xem G4.1 — đánh dấu "ở G4" | — |
| B5 | `EmailSummary.model` hardcode, `sent_at` lấy từ `createdDateTime`, `email_count` tăng cả email trùng, không dedupe race webhook↔worker | `email_processing_pipeline.py`, `ingestion_worker.py`: thêm retry/backoff LLM, dedupe theo unique constraint trước khi tăng `email_count` | — |

### G0.3 — Hợp nhất tài liệu

- [x] Tạo `CLAUDE.md` hợp nhất (Phần I tổng hợp + Phần II/III lưu trữ) — *đã làm 2026-10-10*.
- [x] Tạo `SPEC.md` hợp nhất (Phần I kế hoạch + Phần II/III lưu trữ) — *đã làm 2026-10-10*.
- [x] Tạo `PROGRESS.md` hợp nhất (Phần I nhật ký + Phần II/III lưu trữ) — *đã làm 2026-10-10*.
- [ ] Ghi vào `CLAUDE.md` Phần I cảnh báo: các mục `§4 Common Tasks → Email Review Agent (chưa bắt đầu)` và `POST /api/agent mock` trong **bản lưu trữ** webapp đã **lỗi thời** — tính năng thật đã xong (§13).
- [ ] Quy ước sau này: **mọi task mới** → thêm mục vào `SPEC.md` Phần I (mới nhất lên đầu) + ghi `PROGRESS.md` Phần I; không sửa phần lưu trữ.

**Hoàn thành G0 khi:** backend chạy 200, `ruff`/`mypy`/`tsc` xanh, không còn bug B1–B3, 3 file doc hợp nhất được team dùng.

---

## G1 — Thống nhất Database (2 ngày)

**Mục tiêu:** 1 database duy nhất cho cả hệ thống; 2 ORM cùng tồn tại không xung đột.

### G1.1 — Chốt dự án Supabase

- [x] **ĐÃ CHỐT (Q1, 2026-10-10): chọn (A) project webapp `nvcanmdfdmyllvopxdst`** (production đang chạy, Vercel đã cấu hình). `DATABASE_URL` + `SUPABASE_URL` của email-agent **đã đổi** sang project này.
- [ ] Chụp `information_schema.tables` của **cả hai** project (đích + cũ `dmllfbsrnoprdhwltxic`) để so sánh; nếu trùng tên bảng thì dừng và báo lại (không bao giờ ghi đè).
- [ ] **Export dữ liệu project cũ** (`dmllfbs…` — nơi có ~30 email + attachments đã ingest) ra ngoài repo, **trước khi** áp schema mới lên project đích và trước khi đóng project cũ. Ghi tên file export vào `PROGRESS.md`.

### G1.2 — Gộp schema

- [ ] **Phía webapp (Prisma):** thêm model `AgentRun` (bảng `agent_runs`) — `id`, `rfqId?`, `emailId?` (String, không FK vì UUID của bên kia), `agentName`, `labelName?`, `status` enum(`QUEUED|RUNNING|DONE|FAILED|ESCALATED`), `input Json?`, `output Json?`, `error Text?`, `startedAt`, `finishedAt?`, `createdAt`. Thêm enum `AgentRunStatus`.
- [ ] **Phía email-agent (Alembic):** thêm cột `emails.rfq_id UUID NULL` + index; thêm bảng `agent_runs` (bảng này **do email-agent quản lý**, ghi theo email) — thống nhất 1 trong 2 bên giữ bảng này, **khuyến nghị: email-agent giữ**, webapp chỉ đọc.
- [ ] Kiểm tra không có tên bảng/cột trùng giữa 2 ORM; `alembic` chỉ đụng bảng email-agent, `prisma` chỉ đụng bảng webapp.
- [ ] Viết migration **SQL tay idempotent** + `scripts/verify-merge-schema.mjs` (Postgres nhúng) theo đúng khuôn có sẵn.

### G1.3 — Áp dụng (cẩn thận)

- [ ] **Backup** toàn bộ DB đích (Supabase export / `pg_dump`) → lưu ngoài repo, ghi tên file vào `PROGRESS.md`.
- [ ] Đọc `information_schema` xác nhận trạng thái trước.
- [ ] Áp `alembic upgrade head` (chỉ thêm cột/bảng) → chạy lại `node scripts/verify-merge-schema.mjs`.
- [ ] Cập nhật `.env`/Vercel: `DATABASE_URL` 2 bên cùng trỏ 1 DB.
- [ ] Chạy smoke test: `GET /api/emails` 200 · `GET /api/rfq` 200 (webapp đăng nhập) · 30 email cũ vẫn đọc được · RFQ cũ vẫn mở được.

**Hoàn thành G1 khi:** 2 app cùng 1 DB, backup đã có, verify script xanh, smoke test 2 phía OK.

---

## G2 — Điểm nối Inbound: Email → RFQ (3 ngày)

**Mục tiêu:** email khách (nhãn `INQUIRY`) tự động thành RFQ; email hãng (nhãn `QUOTE`) tự cập nhật báo giá.

### G2.1 — Route `POST /api/email/inbound` (webapp)

- [ ] File: `psbv-saleadmin-app/src/app/api/email/inbound/route.ts`.
- [ ] **Xác thực:** header `Authorization: Bearer <SERVICE_ROLE_SECRET>` — so sánh với biến môi trường webapp (không dùng session NextAuth vì đây là service-to-service). Rate-limit bằng `src/lib/rate-limit.ts` có sẵn.
- [ ] **Nhận payload:** `{ messageId, threadId, from{email,name}, to[], cc[], bcc[], subject, bodyClean, receivedAt, attachments[{fileName, mimeType, url}], labels[{name, confidence}] }` — schema Zod mới ở `src/lib/schemas/inbound.schemas.ts` (theo đúng khuôn `gemini.schemas.ts`: **validate input từ AI/email, không tin thẳng**).
- [ ] **Chỉ xử lý khi** có nhãn `INQUIRY` (nếu payload có); nếu không có, trả `{action:"ignored"}`.
- [ ] **Chạy:** `parseInquiryWithGemini(bodyClean)` → upsert `Client` theo email → tạo `RFQ` (status `RFO_PENDING_ADMIN`, `extractionError` nếu AI fail) → trả `{ rfqId, rfqCode }`.
- [ ] **Không** tự gửi mail, **không** đổi trạng thái sang `RFO_SENT_TO_SUPPLIER`.
- [ ] Test: mock Gemini + mock Prisma, gọi thẳng handler (khuôn `__tests__/api/*.route.test.ts`).

### G2.2 — Gửi từ email-agent

- [ ] `app/services/email_processing_pipeline.py`: sau khi commit, nếu nhãn primary ∈ {`INQUIRY`} → `asyncio`/worker gửi `POST {WEBAPP_BASE_URL}/api/email/inbound` với `SERVICE_ROLE_SECRET` (thêm vào `Settings`).
- [ ] Retry + log; nếu webapp down → ghi `agent_runs` trạng thái `QUEUED`, worker G4 sẽ gửi lại.
- [ ] Đặt trong worker nền (G4), **không** trong webhook handler (webhook phải trả 202 ngay).

### G2.3 — Điểm nối Quote (mở rộng, làm ngay nếu trơn tru)

- [ ] Route `POST /api/rfq/{id}/ingest-supplier-email` (webapp): nhận kết quả đã bóc từ email-agent → `parseSupplierQuoteWithGemini` → cập nhật `RFQItem.supplierUnitPrice`/`extWeightLbs` → đổi status sang `SUPPLIER_QUOTED`.
- [ ] Matching RFQ: theo `supplierEmail` + `rfqCode` có trong subject; nếu không match chắc → lưu chờ, **không** tự đổi status (enrich-only).

**Hoàn thành G2 khi:** 1 email Inquiry thật từ Inbox → RFQ mới xuất hiện trên dashboard webapp, `npx tsc --noEmit` 0 lỗi, test route xanh.

---

## G3 — Hợp nhất Giao diện: 1 Dashboard (4 ngày)

**Mục tiêu:** người dùng chỉ mở **webapp**; trang Inbox nằm trong dashboard, dữ liệu lấy từ API email-agent.

### G3.1 — BFF trung gian trong webapp

- [ ] `src/app/api/inbox/route.ts` (GET list), `src/app/api/inbox/[id]/route.ts` (GET chi tiết), `src/app/api/inbox/[id]/labels/route.ts` (POST gán nhãn), `src/app/api/inbox/[id]/thread/route.ts`.
- [ ] BFF gọi `EMAIL_AGENT_API_URL` (env mới) — cache ngắn (revalidate 5s), **auth NextAuth** phía client, không lộ URL backend ra browser.
- [ ] Gộp response: thêm `rfqId`/`rfqCode` (từ G1) để hiển thị liên kết email ↔ RFQ.

### G3.2 — Trang Inbox trong webapp

- [ ] Route: `psbv-saleadmin-app/src/app/(dashboard)/inbox/page.tsx` + `[id]/page.tsx`.
- [ ] **Đổi hướng sidebar** `components/shared/*`: thêm mục "Inbox" (icon thư) vào menu chính.
- [ ] Lấy lại layout/content từ `frontend/app/page.tsx` (grid thẻ) và `frontend/app/emails/[id]/page.tsx` (70/30 + `ThreadHistory` + `AttachmentViewer`) của email-agent, chuyển sang **shadcn/ui + Tailwind của webapp** (không copy CSS riêng).
- [ ] Gán nhãn HITL: gọi BFF ở G3.1 → backend email-agent `POST /api/emails/{id}/labels`.
- [ ] Component hiển thị gắn nhãn: chip màu theo `priority`, badge `assigned_agent`, nút "Mở RFQ" (khi có `rfqId`).

### G3.3 — Bỏ / hạ cấp UI demo

- [ ] Sau khi Inbox webapp xong + smoke test: đánh dấu `frontend/` của email-agent là **legacy** (đọc ở `README.md`), không phát triển thêm; hoặc xoá hẳn nếu bạn xác nhận.
- [ ] Cập nhật `CLAUDE.md` mục 2.4 / ghi chú `frontend/`.

**Hoàn thành G3 khi:** 1 người dùng mở 1 URL, xem được email + gắn nhãn + nhảy sang RFQ liên quan; `frontend/` không còn là nơi dùng thật.

---

## G4 — Agent chạy thật (5 ngày)

**Mục tiêu:** `assigned_agent` không còn là chuỗi vô hồn — có worker, có bảng theo dõi, 3 agent đầu chạy thật.

### G4.1 — Worker thực thi agent (email-agent)

- [ ] Bảng `agent_runs` (G1.2) + model `AgentRun` trong `app/db/models.py`.
- [ ] `app/services/agent_runner.py`: `run_agent_for_email(email_id)` — đọc nhãn primary → map `label → agent_name` → tìm module agent (`app/services/agents/<label>_agent.py`) → gọi → ghi `agent_runs` (`RUNNING` → `DONE`/`FAILED`) → nếu là điểm nối inbound (G2) thì gọi webapp.
- [ ] Worker: `IngestionWorker` thêm nhánh poll `emails.status='PROCESSING' AND assigned_agent IS NOT NULL` (chu kỳ 30s), gọi `run_agent_for_email`. Tách hẳn luồng này khỏi luồng ingest (đừng chặn Graph delta).
- [ ] **Retry/timeout:** tối đa 3 lần, backoff; LLM lỗi → `FAILED` + log; không bao giờ để `RUNNING` treo (timeout 120s).
- [ ] **Quy tắc HITL:** agent **không bao giờ** gửi mail; nếu cần người duyệt → set `status='ESCALATED'` + `assigned_agent='HUMAN_MANAGER'`.

### G4.2 — 3 agent đầu tiên

| Agent | Nhãn | Việc làm | File |
|---|---|---|---|
| `INQUIRY_AGENT` | `INQUIRY` | Gọi điểm nối G2.1 → tạo RFQ | `app/services/agents/inquiry_agent.py` |
| `QUOTE_AGENT` | `QUOTE` | Bóc PDF Quote (webapp `parseSupplierQuoteWithGemini` qua điểm nối G2.3) | `app/services/agents/quote_agent.py` |
| `DOCUMENT_AGENT` | `AWB_BOL`, `SHIPMENT_DOCUMENT`, `DELIVERY_TICKET`, `ORDER_PICTURE`, `SOA` | Đọc nội dung/OCR, lưu metadata, **không** đổi status (enrich-only) | `app/services/agents/document_agent.py` |

### G4.3 — Bảng theo dõi & API

- [ ] `GET /api/agents/runs` (FastAPI): list `agent_runs` lọc theo `status`/`agent_name`.
- [ ] Webapp (tùy chọn, G5): trang `/agents` hiển thị — bảng chạy gần đây, lỗi, tỉ lệ thành công.
- [ ] Log structured (JSON) cho mọi lần chạy; `last_error` trong `/api/ingestion/status` mở rộng cho agent.

### G4.4 — Test

- [ ] Unit: `agent_runner` với DB giả (fixture email + nhãn) → `agent_runs` đúng trạng thái.
- [ ] Test retry: mock LLM fail 2 lần → lần 3 thành công.
- [ ] Test HITL: agent không bao giờ gọi route gửi mail (khẳng định bằng spy).

**Hoàn thành G4 khi:** 1 email nhãn `INQUIRY` thật → `agent_runs` có dòng `DONE` + RFQ xuất hiện; kill webapp → agent ghi `FAILED`/`QUEUED` và tự thử lại; test xanh.

---

## G5 — Mở rộng agent & nâng cao (6 ngày)

**Mục tiêu:** đủ mọi nhãn có agent; có realtime; nền tảng cho Phase 3.

### G5.1 — Thêm agent theo nhãn

| Agent | Nhãn | Việc làm | File |
|---|---|---|---|
| `PO_AGENT` | `PO` | `gemini-po` + `/api/rfq/parse-customer-po` → `save-customer-po` | `app/services/agents/po_agent.py` |
| `PROFORMA_AGENT` | `PROFORMA_INVOICE` | Bóc PI → cập nhật RFQ terms | `.../proforma_agent.py` |
| `CIPL_AGENT` | `CIPL_CERTIFICATES` | `gemini-cipl` + `/api/cipl/*` → `CiplRecord` | `.../cipl_agent.py` |
| `MVPO_AGENT` | `MISA_MVPO` | `generate-document` (MVPO) | `.../mvpo_agent.py` |
| `EXCEPTION_AGENT` (mới) | `EXCEPTION`, `SED` | Chỉ tạo Task trong webapp (`/api/tasks`) báo Sale Admin — **không tự xử lý** | `.../exception_agent.py` |

- [ ] Thêm nhãn mới (nếu có) vào `seed_labels.py` + `frontend/lib/data.ts::LABELS` (hoặc bảng label của webapp nếu đã gộp UI).
- [ ] Map `label → agent_name` đặt ở **một chỗ duy nhất** (dict trong `agent_runner.py`) — đừng rải if/elif.

### G5.2 — Realtime

- [ ] `GET /api/stream` (SSE) của email-agent — đã ghi trong SPEC Giai đoạn 3 nhưng **chưa hiện thực**: push event `email.new`, `agent.done`, `agent.failed`.
- [ ] Webapp trang Inbox subscribe SSE để không cần F5 (fallback: poll 10s).

### G5.3 — Email Review Agent mở rộng (tuỳ chọn, theo M1 SPEC §13.6)

- [ ] Soạn nháp cho **RFO gửi hãng** (không chỉ Quotation): gọi lại `draftQuotationEmailWithGemini` với context RFO, hiển thị ở `rfo-review`.
- [ ] `quick-email-modal.tsx` `EMAIL_ACTIONS` (3 template tĩnh) → gọi AI soạn (vẫn qua duyệt).

### G5.4 — Nâng cao (không chặn)

- [ ] Tự động **follow-up email** khi RFQ quá hạn (Phase 3) — vẫn chỉ soạn nháp, người duyệt.
- [ ] LangGraph: chuyển pipeline Python sang `StateGraph` (đã dự kiến từ Giai đoạn 2 SPEC gốc) — checkpoint vào chính DB này.
- [ ] MCP server cho Python CRUD (`GET/PATCH /api/emails`) → Claude Desktop thao tác inbox.

**Hoàn thành G5 khi:** ≥8 nhãn có agent chạy thật; inbox realtime; không còn nhãn nào rơi vào nhánh `else` mặc định mà không có agent.

---

## G6 — Vận hành & mở rộng (2 ngày + liên tục)

- [ ] Deploy webapp (Vercel, đã cấu hình) + email-agent (`deploy.sh` → VPS Ubuntu 24.04) — **cùng `DATABASE_URL`**.
- [ ] `.env`/Vercel env: bổ biến `SERVICE_ROLE_SECRET` (2 bên), `EMAIL_AGENT_API_URL`, `WEBHOOK_BASE_URL`.
- [ ] Healthcheck: `GET /api/ingestion/status` (email-agent) + `GET /api/rfq` (webapp) trong 1 script giám sát.
- [ ] **Monorepo (tùy chọn, làm cuối cùng):** gộp thành thư mục gốc:
  ```
  apps/api/      ← email-agent FastAPI
  apps/web/      ← webapp Next.js
  packages/      ← schema chung / type chung
  ```
  *Chỉ làm khi G0–G5 đã ổn định* — gộp repo sớm làm chậm mọi việc khác.
- [ ] Stack nâng cấp (giữ nguyên mục "Advanced Stack" SPEC gốc): Caddy + Prometheus + Grafana + Langfuse; SeaweedFS cho storage.

---

## P3. Rủi ro & cách phòng

| Rủi ro | Mức | Cách phòng |
|---|---|---|
| Mất dữ liệu khi gộp DB / `prisma migrate dev` reset | **Cao** | Backup trước mọi lần; viết SQL tay idempotent; đọc `information_schema` trước; không chạy `migrate dev` |
| 2 ORM (Prisma + SQLAlchemy) ghi đè bảng của nhau | Cao | Phân vùng bảng rõ ràng (g1.2); script verify sau mỗi migration |
| Webhook Graph + worker poll xử lý trùng email | Trung | Giữ unique `(id_mailbox, message_id)`; dedupe trước khi tăng `email_count` |
| Agent treo / gọi LLM tốn tiền | Trung | Timeout 120s, retry ≤3, backoff, rate-limit |
| AI tự gửi mail cho khách | **Cao (nghiệp vụ)** | Bất biến HITL: mọi route gửi đều qua `getServerSession` + người bấm |
| Đẩi secret lên git | Cao | `.gitignore` đã chặn `.env`/`*.key`/`*.bot`; rotate Supabase key vì từng commit lịch sử |
| Gộp repo quá sớm | Trung | G6 mới làm monorepo |

## P4. Câu hỏi mở (cần bạn quyết)

| # | Câu hỏi | Mặc định tạm |
|---|---|---|
| Q1 | Dự án Supabase nào là đích gộp? | **ĐÃ CHỐT 2026-10-10 → (A) `nvcanmdfdmyllvopxdst`** (webapp production) — `DATABASE_URL`/`SUPABASE_URL` đã đổi |
| Q2 | Giữ `frontend/` (email-agent demo) hay xoá sau G3? | Giữ lại đánh dấu legacy, xoá ở lần sau |
| Q3 | `agent_runs` do email-agent (Prisma không đọc) hay webapp quản lý? | **Email-agent quản lý**, webapp chỉ đọc qua API |
| Q4 | Có làm monorepo (G6) không? | Chỉ khi G0–G5 xong |
| Q5 | Inbox hiển thị `body_clean` đã cắt quote — có cần giữ `body_full_text` để xem raw không? | Giữ cả 2 cột, UI cho chọn |

---

<!-- BEGIN:SPEC.email-agent.md -->
# SPEC – Kế hoạch làm việc

> Mỗi khi có task mới: thêm một mục ở dưới (mới nhất lên đầu) gồm mục tiêu, các bước, tiêu chí hoàn thành.

## Task 1 – Test kết nối Supabase (`test_db.py`)

**Mục tiêu:** có script kiểm tra nhanh kết nối tới Supabase.

**Các bước**

1. Đọc cấu trúc dự án (repo mới, chỉ có README.md, chưa có `test_db`).
2. Tạo `test_db.py`: đọc `SUPABASE_URL`/`SUPABASE_KEY` từ `.env` hoặc biến môi trường, gọi REST API, có thể đọc thử 1 bảng.
3. Thêm `.env.example`, `.gitignore` (không commit khóa).
4. Chạy test với thông tin thật của người dùng.

**Hoàn thành khi:** `python test_db.py [bảng]` in `[OK]` với credentials thật.

---

## Kế hoạch triển khai tổng thể (4 Giai đoạn)

> **Triết lý thiết kế:** Xây dựng theo hướng "mở" — mọi component đều có thể hoán đổi sau này mà không cần refactor lớn.

---

## Giai đoạn 1 – Thiết lập Hạ tầng "Mở" (Ngày 1–2)

**Mục tiêu:** Dựng khung xương backend với FastAPI và PostgreSQL, tối ưu cho khả năng mở rộng.

### 1.1 Database (PostgreSQL + Alembic)

- Dùng **SQLAlchemy 2.1** + **Alembic 1.20** để quản lý schema từ đầu
- Dùng **Supabase** (PostgreSQL 16) cho bản Demo — tiết kiệm công setup local
- Schema thiết kế sẵn để LangGraph checkpoint ghi thẳng vào các bảng riêng sau này

> **Chuyển đổi sau này:** Schema chuẩn sẵn → LangGraph checkpoint ghi thẳng vào DB này.

### 1.2 Storage Abstraction (Lưu file đính kèm)

- Viết class `StorageProvider` với interface `save_file(bytes) -> str`
- Bản Demo: lưu vào thư mục local (`with open(...)`)

> **Chuyển đổi sau này:** Thay logic bên trong bằng `boto3` để đẩy lên **SeaweedFS** (tương thích S3).

### 1.3 Ingestion (Microsoft Graph)

- Dùng **MSAL 1.39** để lấy OAuth2 token
- Đăng ký **Microsoft Graph Webhook** để nhận event thư mới
- Tạo endpoint `POST /api/webhooks/outlook` trên FastAPI để hứng event

**Hoàn thành khi:**

- [x] Kết nối DB thành công (đã xong ✅)
- [x] Alembic migration chạy được
- [x] `StorageProvider` có thể lưu file local
- [x] Endpoint webhook nhận được ping từ Microsoft Graph

---

## Giai đoạn 2 – Xây dựng AI Agents theo tư duy "State Graph" (Ngày 3–4)

**Mục tiêu:** Viết các Agent đúng định dạng LangGraph để dễ nâng cấp sau.

### Luồng xử lý (Orchestrator tuần tự)

Mỗi Agent nhận `State` (dict chứa thông tin email) → trả về `State` đã cập nhật:

```
Email đến
  → Tách text cơ bản
  → SenderAgent      → State["sender_info"]
  → SecurityAgent    → State["security_flags"]
  → SummarizerAgent  → State["summary"]   (dùng Gemini API)
```

> **Chuyển đổi sau này:** Các hàm này chính là "Nodes" cho LangGraph. Khi nâng cấp, ném vào `StateGraph` — LangGraph tự lo checkpoint và retry.

**Hoàn thành khi:**

- [x] `SenderAgent`, `SecurityAgent`, `SummarizerAgent` chạy tuần tự
- [x] `State` dict được truyền và cập nhật qua từng Agent
- [x] Gemini API trả về summary hợp lệ

---

## Giai đoạn 3 – API & Giao diện HITL (Ngày 5–6)

**Mục tiêu:** Cơ chế Human-in-the-loop để người dùng phân loại và gán nhãn email.

### 3.1 Web API (FastAPI)

| Endpoint | Mô tả |
| --- | --- |
| `GET /api/emails` | Danh sách email đã xử lý |
| `GET /api/emails/{id}` | Chi tiết một email |
| `PATCH /api/emails/{id}/labels` | Gán / cập nhật nhãn |
| `GET /api/stream` | Server-Sent Events — push thông báo email mới |

> **Chuyển đổi sau này:** Khi tích hợp **MCP Python SDK 1.30**, MCP server chỉ cần import và gọi các CRUD function này để cho phép Claude Desktop tương tác.

### 3.2 Giao diện (Next.js 14)

- Dashboard dạng lưới thẻ (Card): hiển thị tóm tắt, cảnh báo lừa đảo
- Nút "Lưu nhãn" → gọi FastAPI → lưu DB → trigger Agent hạ nguồn (n8n hoặc Python script)

**Hoàn thành khi:**

- [x] Tất cả REST API hoạt động và có schema validation
- [x] SSE push được event ra frontend
- [x] Dashboard hiển thị danh sách email + gán nhãn được

---

## Giai đoạn 4 – DevOps & Observability (Ngày 7)

**Mục tiêu:** Áp dụng tiêu chuẩn production ngay từ đầu, tránh nợ kỹ thuật.

### 4.1 Quản lý Code

| Tool | Mục đích |
| --- | --- |
| `uv` | Quản lý venv và thư viện (nhanh hơn pip) |
| `ruff` | Format + lint code |
| `mypy` | Type checking (quan trọng khi làm việc với JSON schema của LLM) |

### 4.2 Đóng gói (Docker Compose)

- `docker-compose.yml` cơ bản: container FastAPI + Uvicorn
- Deploy lên **VPS Ubuntu 24.04**

> **Chuyển đổi sau này:** Thêm các image `Prometheus`, `Grafana`, `Langfuse`, `Caddy`, `SeaweedFS` vào file yaml → `docker-compose up -d` là toàn bộ Advanced Stack khởi động. Caddy tự lo HTTPS.

**Hoàn thành khi:**

- [x] `docker-compose up` chạy được app (backend + frontend healthy: `GET / → 200`, `GET /api/ingestion/status → running:true`, `GET :3000 → 200`)
- [x] `ruff` và `mypy` không báo lỗi (`ruff check .` clean; `mypy app` — Success 21 files)
- [ ] App deploy thành công lên VPS (`deploy.sh` sẵn sàng, chờ bạn chạy với VPS thật)

---

## Giai đoạn 5 - Cải tiến Giao diện

### Hình ảnh Giao diện trang chi tiết từng card email mở rộng tham khảo

- ![alt text](<Screenshot 2026-10-07 081527.png>)
- ![alt text](<Screenshot 2026-10-07 081502.png>)

### 5.1 Cải tiến giao diện

- [x] Giao diện trang mở rộng tại file : E:\AI_LEARNING\email-agent\frontend\app\emails\[id]\page.tsx cần chỉnh lại cấu trúc thông tin hiển thị và thẩm mỹ. Vẫn giữ cấu trúc 70% cho phần nội dung chính, 30% cho phần side bar. Tham khảo 2 ảnh giao diện đính kèm link files ở trên.
- [x] Các thông tin ở phần nội dung chính cần cập nhật theo thứ tự gồm: phần 1 là Định danh email gồm id_email, Tên email, id_mailbox. Phần 2 là Thông tin về người gửi gồm Name,id_sender, email, cc emails, bcc emails, phone, company, is_internal, is_known_customer. Phần 3 là Thông tin nội dung email gồm message_id, thread_id, in_reply_to, body_clean, content_summarized, received_at,has_attachments. Phần 4 là Thông tin về file kèm theo (trường hợp có): id_attachment, file_name, mime_type, size_bytes, storage_key, is_inline, process_status. Lưu ý sắp xếp và trình bày giao diện chuyên nghiệp, giao diện thân thiện, dễ đọc và xem file     E:\AI_LEARNING\email-agent\app\db\db_schema.mmd để hiểu cấu trúc database schema của dự án vì các dữ liệu hiển thị đều lấy từ database.
- [x] Với Mail có file thì ngoài các thông tin trên sẽ có phần hiển thị file đính kèm bên dưới phần thông tin về file để người dùng xem được nội dung file trực tiếp luôn.
- [x] Ngoài những thông tin hiển thị có trong database schema thì sẽ có một phần các data không được hoặc ko cần hiển thị mà tôi đã không liệt kê. Những này vẫn sẽ được tạo, trích xuất và lưu trữ bình thường, dành cho Kỹ sư phía sau quản lý.

### 5.2 Củng cố backend phía sau

- [x] Cần phân tích, đánh giá và xử lý lỗi này: ERROR:app.services.email_processing_pipeline:❌ Transaction Database bị hủy do lỗi: extract() got an unexpected keyword argument 'sender_email'
ERROR:app.api.webhooks:❌ Lỗi luồng process_new_email: extract() got an unexpected keyword argument 'sender_email'
INFO:app.api.webhooks:🔔 Có email mới! Đưa vào hàng đợi xử lý: AQMkAGI4M2IwMAE4LWNiMGQtNDgyYi1iMzI0LTkxNjM1NzhhNmE0ZABGAAADDRKv29S3u02tlwgGMKiXagcAvMoVuwB8nEqLKnaDJNgv5gAAAgEMAAAAvMoVuwB8nEqLKnaDJNgv5gACB8xQEwAAAA==
INFO:     40.126.20.41:0 - "POST /api/webhooks/outlook HTTP/1.1" 202 Accepted
INFO:app.api.webhooks:Đang đưa email ID AQMkAGI4M2IwMAE4LWNiMGQtNDgyYi1iMzI0LTkxNjM1NzhhNmE0ZABGAAADDRKv29S3u02tlwgGMKiXagcAvMoVuwB8nEqLKnaDJNgv5gAAAgEMAAAAvMoVuwB8nEqLKnaDJNgv5gACB8xQEwAAAA== vào Pipeline xử lý...
INFO:app.services.email_processing_pipeline:Đang làm sạch HTML và bóc tách chữ ký...
ERROR:app.services.email_processing_pipeline:❌ Transaction Database bị hủy do lỗi: extract() got an unexpected keyword argument 'sender_email'
ERROR:app.api.webhooks:❌ Lỗi luồng process_new_email: extract() got an unexpected keyword argument 'sender_email'

- [x] Trong làm việc ở công ty, khi nhận email trên outlook thì thường người dùng sẽ trao đổi qua lại liên tục trong 1 email, tạo ra một luồng email rất dài, tương tác, trả lời giữa 2 bên với nhau. Thì cần phân tích, đánh giá và đề xuất giải pháp để giải quyết chính xác trường hợp này.
- [x] Cần kiểm tra kết nối database, luồng hoạt động của hệ thống

### 5.3 Nâng cao

- [x] Test hệ thống với việc lấy và xử lý 30 email trong vòng 7 ngày qua trên outlook , hiển thị trên giao diện đầy đủ,, chính xác để đánh giá xem đạt yêu cầu chưa.

## Stack kỹ thuật tổng hợp

| Layer | Demo Stack | Advanced Stack (sau này) |
| --- | --- | --- |
| **DB** | Supabase (PostgreSQL 16) | Self-hosted PostgreSQL |
| **ORM** | SQLAlchemy 2.1 + Alembic 1.20 | Giữ nguyên |
| **Storage** | Local filesystem | SeaweedFS (S3-compatible) |
| **AI Orchestration** | Python thuần (tuần tự) | LangGraph |
| **LLM** | Gemini API | Gemini |
| **Email Ingestion** | Microsoft Graph + MSAL 1.39 | Giữ nguyên |
| **Frontend** | Next.js 14 | Giữ nguyên |
| **Infra** | Docker Compose + Uvicorn | + Caddy + Prometheus + Grafana + Langfuse |
| **MCP** | — | MCP Python SDK 1.30 |

<!-- END:SPEC.email-agent.md -->

---

# PHẦN III — BẢN LƯU TRỮ: SPEC.md GỐC CỦA WEBAPP (psbv-sale-admin-webapp)

> Nguyên văn `SPEC.md` của repo webapp trước khi hợp nhất. §1–§10: kiến trúc/roadmap; §11: CBU v2; §12: Dashboard Analytics; §13: Email Review Agent.

<!-- BEGIN:SPEC.webapp.md -->
# PSBV Sales Agent Platform — Specification

## 1. Project Overview

**PSBV Sales Agent Platform** là hệ thống CRM nội bộ B2B được xây dựng cho team Sale Admin của PSBV Trading & Service Co., Ltd. Hệ thống tự động hóa toàn bộ vòng đời giao dịch xuất nhập khẩu — từ tiếp nhận Inquiry, hỏi giá hãng (RFO), bóc tách báo giá (AI), tính CBU (Cost Build Up), soạn Quotation, đến quản lý đơn đặt hàng MVPO và chứng từ hải quan.

### 1.1 Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 14 (App Router) + React 18 + TypeScript |
| **Styling** | Tailwind CSS + shadcn/ui components |
| **Database** | PostgreSQL + Prisma ORM 7 |
| **Auth** | NextAuth.js v4 + bcrypt |
| **AI** | Google Gemini API 0.24 |
| **Document** | APITemplate.io |
| **Storage** | Supabase Storage |
| **Email** | Microsoft Graph API (transport duy nhất — xem §5.3) |
| **Deployment** | Vercel |

---

## 2. Business Domain

### 2.1 Core Business Flow

```
┌─────────────────┐
│  INQUIRY        │  Khách hàng gửi yêu cầu báo giá (email/PDF)
│  RECEIVED       │  ─────────────────────────────────────────────
└────────┬────────┘
         │ AI Parse (Gemini)
         ▼
┌─────────────────┐
│  RFO            │  Sale Admin kiểm tra, điều chỉnh items
│  PENDING_ADMIN  │  ─────────────────────────────────────────────
└────────┬────────┘
         │ Gửi RFO cho hãng
         ▼
┌─────────────────┐
│  RFO_SENT_      │  Đang chờ hãng trả lời
│  TO_SUPPLIER    │  ─────────────────────────────────────────────
└────────┬────────┘
         │ Nhận Quote từ hãng
         ▼
┌─────────────────┐
│  SUPPLIER_      │  AI bóc tách PDF Quote từ hãng
│  QUOTED          │  ─────────────────────────────────────────────
└────────┬────────┘
         │ Tính CBU
         ▼
┌─────────────────┐
│  CBU_PENDING_    │  Sale Admin nhập phí logistics, bank...
│  ADMIN          │  ─────────────────────────────────────────────
└────────┬────────┘
         │ Tạo Quotation PDF
         ▼
┌─────────────────┐
│  QUOTATION_     │  Preview & edit quotation
│  DRAFTED        │  ─────────────────────────────────────────────
└────────┬────────┘
         │ Gửi Quotation
         ▼
┌─────────────────┐
│  QUOTED_        │  Gửi báo giá cho khách qua MS Graph
│  TO_CLIENT      │  ─────────────────────────────────────────────
└─────────────────┘
```

### 2.2 Key Business Concepts

| Term | Description |
|------|-------------|
| **RFQ** | Request for Quotation — Đơn yêu cầu báo giá |
| **RFO** | Request for Offer — Phiếu gửi hãng hỏi giá |
| **CBU** | Cost Build Up — Tính giá thành bao gồm tất cả chi phí |
| **DDP** | Delivered Duty Paid — Giá đã bao gồm thuế, vận chuyển |
| **MVPO** | Manufacturer's Vendor Purchase Order — Đơn đặt hàng gửi nhà cung cấp |
| **CI/PL** | Commercial Invoice / Packing List — Chứng từ hải quan |

### 2.3 CBU Calculation Parameters

CBU engine tính toán giá DDP với 30+ parameters (engine v2 ở `src/lib/cbu/` đã sửa các lỗi sai số của bản cũ — đặc tả đầy đủ ở **§11 CBU Module v2**; `bookingExchangeRate` không còn được engine v2 dùng):

| Category | Parameters |
|----------|------------|
| **Tỷ giá** | exchangeRate, bookingExchangeRate, vndRoundingStep, lbToKg |
| **Logistics** | freightCost, freightFixed, freightRatePerKg, chargeableWeightKg, clearanceCost, inlandCost |
| **Bảo hiểm** | insuredValuePercent, insuranceRatePercent, minInsuranceUsd |
| **Ngân hàng** | remittanceRatePercent, bankVatFactor, minRemittanceFeeUsd, receiveRatePercent |
| **Chi phí vốn** | percentValueFinanced, interestRatePercent, financingDays |
| **Thuế & phí** | dutyPercent, commissionPercent, citPercent |

---

## 3. Database Schema

### 3.1 Entity Relationship Diagram

```
┌─────────────┐       1:N        ┌─────────────┐       1:N        ┌─────────────┐
│    User     │◄────────────────│     RFQ     │◄───────────────│   RFQItem   │
├─────────────┤                 ├─────────────┤                 ├─────────────┤
│ id          │                 │ id          │                 │ id          │
│ email       │                 │ rfqCode     │                 │ rfqId (FK)  │
│ password    │                 │ clientId(FK)│                 │ lineNo      │
│ name        │                 │ status       │                 │ rawPartNumber│
│ role        │                 │ ...CBU fields│                 │ supplierUnit│
│ isActive    │                 │ ...logistics │                 │ ...CBU calcs│
└─────────────┘                 └─────────────┘                 └─────────────┘
       │                                 │
       │ 1:N                             │ 1:N
       ▼                                 ▼
┌─────────────┐                  ┌─────────────┐
│    Task     │                  │  Document   │
└─────────────┘                  └─────────────┘

┌─────────────┐       1:N        ┌─────────────┐
│   Client    │──────────────────│     RFQ     │
├─────────────┤                 └─────────────┘
│ id          │
│ name        │
│ companyName │
│ email       │
└─────────────┘

┌─────────────┐
│  Supplier   │
├─────────────┤
│ id          │
│ name        │
│ companyName │
│ email       │
│ ccEmails    │
└─────────────┘
```

### 3.2 Enums

```prisma
enum Role {
  ADMIN       // Master Admin: Toàn quyền + Quản lý User
  SALE_ADMIN  // Sale Admin: Vận hành, CBU, Dashboard
}

enum OrderStatus {
  INQUIRY_RECEIVED          // 1. Khách gửi Yêu cầu
  RFO_PENDING_ADMIN         // 2. Chờ duyệt RFO
  RFO_SENT_TO_SUPPLIER      // 3. Đã gửi Hãng
  SUPPLIER_QUOTED           // 4. Hãng đã báo giá
  CBU_PENDING_ADMIN         // 5. Chờ tính CBU
  QUOTATION_DRAFTED         // 6. Đã sinh Quotation PDF
  QUOTED_TO_CLIENT          // 7. Đã gửi báo giá
}

enum TaskStatus {
  PENDING
  IN_PROGRESS
  DONE
}
```

---

## 4. Application Architecture

### 4.1 Directory Structure

```
psbv-sales-agent-saas/
├── prisma/
│   ├── schema.prisma          # Database schema
│   └── migrations/            # Prisma migrations
│
├── src/
│   ├── app/                   # Next.js App Router
│   │   ├── (auth)/          # Auth routes (login)
│   │   ├── (dashboard)/      # Dashboard routes (auth-gated)
│   │   │   ├── layout.tsx   # Dashboard shell
│   │   │   ├── overview/     # Dashboard overview
│   │   │   ├── rfq/         # RFQ management
│   │   │   │   ├── page.tsx           # RFQ list
│   │   │   │   ├── new/page.tsx       # Create RFQ
│   │   │   │   └── [id]/
│   │   │   │       ├── page.tsx        # RFQ detail
│   │   │   │       ├── rfo-review/    # RFO review & send
│   │   │   │       ├── cbu-calc/      # CBU calculation (được dựng lại theo §11)
│   │   │   │       ├── mvpo/          # MVPO creation
│   │   │   │       └── quote-preview/ # Quotation preview
│   │   │   ├── clients/       # Client management
│   │   │   ├── tasks/        # Task management
│   │   │   ├── database/     # Database browser
│   │   │   ├── system-users/ # User management
│   │   │   └── ai-config/   # AI configuration
│   │   │
│   │   └── api/              # API Routes
│   │       ├── auth/         # NextAuth endpoints
│   │       ├── rfq/          # RFQ CRUD + operations
│   │       ├── clients/      # Client CRUD
│   │       ├── users/        # User CRUD
│   │       ├── tasks/        # Task CRUD
│   │       ├── email/        # Email endpoints
│   │       └── ai-config/    # AI config
│   │
│   ├── components/
│   │   ├── ui/              # shadcn/ui base components
│   │   ├── shared/          # Sidebar, Logout
│   │   ├── providers/        # Auth provider
│   │   ├── rfq/             # RFQ-specific components
│   │   └── cbu/             # (mới, §11.8) Workspace CBU: bảng dòng hàng, tham số, kịch bản
│   │
│   └── lib/                  # Utilities
│       ├── cbu/              # (mới, §11.8) CBU engine v2: math, pools, pricing, profiles, checks
│       ├── utils.ts          # cn() helper
│       ├── auth.ts           # NextAuth config
│       ├── prisma.ts        # Prisma client
│       ├── ms-graph.ts      # MS Graph API client
│       └── email-builder.ts  # Email templates
│
├── .env                      # Environment variables (gitignored)
├── next.config.mjs          # Next.js config
└── package.json
```

### 4.2 API Routes

| Group | Endpoints |
|-------|-----------|
| **RFQ** | `GET/POST /api/rfq`, `GET/PUT/DELETE /api/rfq/[id]` |
| **RFQ Items** | `GET/PUT /api/rfq/[id]/items` |
| **RFQ Status** | `GET/PUT /api/rfq/[id]/status` |
| **CBU** | `POST /api/rfq/[id]/calculate-cbu` *(hiện tại; sẽ thành alias của API v2)* · v2 (§11.8): `GET/PUT /api/rfq/[id]/cbu`, `POST /api/rfq/[id]/cbu/finalize` |
| **Documents** | `POST /api/rfq/[id]/generate-pdf`, `POST /api/rfq/generate-document` |
| **Email** | `POST /api/rfq/[id]/send-quote`, `POST /api/rfq/[id]/send-rfo` |
| **AI Parsing** | `POST /api/rfq/parse-inquiry`, `POST /api/rfq/parse-supplier-quote` |
| **Auth** | `GET/POST /api/auth/[...nextauth]` |
| **Clients** | `GET/POST /api/clients`, `GET/PUT/DELETE /api/clients/[id]` |
| **Users** | `GET/POST /api/users`, `GET/PUT/DELETE /api/users/[id]` |
| **Tasks** | `GET/POST /api/tasks`, `GET/PUT/DELETE /api/tasks/[id]` |

---

## 5. Key Features

### 5.1 RFQ Lifecycle Management

| Feature | Status | Description |
|---------|--------|-------------|
| Tiếp nhận Inquiry | ✅ | Upload PDF, AI bóc tách dữ liệu |
| Tạo RFQ từ Email | ✅ | Xử lý file upload với Gemini |
| Gửi RFO cho Hãng | ✅ | Sinh email RFO, đính kèm file |
| Bóc tách Quote | ✅ | Gemini AI parse supplier quote |
| Tính CBU & DDP | ⚠️ | Chạy được nhưng **sai số** (phân bổ logistics, đơn vị %) và UI khó dùng — đang tái cấu trúc, xem **§11 CBU Module v2** |
| Sinh Quotation PDF | ✅ | APITemplate.io → PDF |
| Preview & Edit Quotation | ✅ | Split-view editor |
| Gửi Quotation | ✅ | MS Graph API → Outlook |
| Tạo MVPO | ✅ | Purchase Order template |
| CI/PL Editing | 🔄 | In progress |
| COC/COO Management | 🔄 | In progress |

### 5.2 AI Integration

| Module | File | Purpose |
|--------|------|---------|
| Inquiry Parsing | `src/lib/gemini-inquiry.ts` | Parse customer inquiry PDF |
| Quote Parsing | `src/lib/gemini-quote.ts` | Parse supplier quote |
| PO Parsing | `src/lib/gemini-po.ts` | Parse customer PO |

### 5.3 Email System

| Provider | File | Usage |
|----------|------|-------|
| MS Graph | `src/lib/ms-graph.ts` | Duy nhất — mọi email (RFO, Quotation, dispatch, mail nhanh) qua Outlook, hỗ trợ PDF attachment optional |

Resend/nodemailer đã gỡ bỏ hoàn toàn ở Sprint 2 (22/09/2026) — trước đó `send-rfo` và `send-rfq` (quick-email-modal) gửi thật qua sandbox domain `onboarding@resend.dev`, không phải domain công ty. Xem PROGRESS.md §4 SPRINT 2.

### 5.4 Document Generation

| Type | Template ID | Status |
|------|------------|--------|
| QUOTATION_CLIENT_PDF | `APITEMPLATE_QUOTATION_TEMPLATE_ID` | ✅ Active |
| MVPO_SUPPLIER_PDF | `APITEMPLATE_MVPO_TEMPLATE_ID` | ✅ Active |
| COMMERCIAL_INVOICE_PDF | TBD | ⏳ Planned |
| CERTIFICATE_COC_COO_PDF | TBD | ⏳ Planned |

---

## 6. Environment Variables

```bash
# Database
DATABASE_URL=postgresql://...

# Auth
NEXTAUTH_URL=https://...
NEXTAUTH_SECRET=...
AUTH_GITHUB_ID=...
AUTH_GITHUB_SECRET=...

# Supabase
NEXT_PUBLIC_SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...

# AI
GOOGLE_GEMINI_API_KEY=...

# Document
APITEMPLATE_API_KEY=...
APITEMPLATE_QUOTATION_TEMPLATE_ID=...
APITEMPLATE_MVPO_TEMPLATE_ID=...

# MS Graph (Email)
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
MS_GRAPH_MAILBOX=drilling@psbvn.com

# Email (Backup)
RESEND_API_KEY=...
```

---

## 7. Development Commands

```bash
# Install dependencies
npm install

# Development
npm run dev

# Build
npm run build

# Database
npx prisma migrate dev      # Create migration
npx prisma migrate deploy   # Apply migrations
npx prisma generate         # Generate client
npx prisma db seed          # Seed data

# Lint
npm run lint

# TypeScript check
npx tsc --noEmit
```

---

## 8. Testing Email

```bash
# Test MS Graph connection
node scripts/test-ms-graph.mjs
```

---

## 9. Deployment

**Target:** Vercel (Next.js 14 App Router)

Vercel tự động deploy khi có push lên GitHub.

**Required Environment Variables on Vercel:**
- `DATABASE_URL`
- `NEXTAUTH_SECRET`
- `NEXTAUTH_URL`
- `NEXT_PUBLIC_SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `GOOGLE_GEMINI_API_KEY`
- `APITEMPLATE_API_KEY`
- `APITEMPLATE_QUOTATION_TEMPLATE_ID`
- `APITEMPLATE_MVPO_TEMPLATE_ID`
- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
- `MS_GRAPH_MAILBOX`

---

## 10. Roadmap

### Phase 1.5 — CBU Module v2 (ưu tiên trước Phase 2)
Sửa đúng công thức theo workbook đã chuẩn hoá, lưu/đọc đầy đủ, dựng lại giao diện, thêm kịch bản Air/Sea và profile Baker Hughes (FCA/DAP). Chi tiết & tiêu chí nghiệm thu: **§11**. Theo dõi tiến độ: `PROGRESS.md` §6.

### Phase 2 — Feature Completion (v0.2)
- [x] CI/PL Editing với template — 3 API route, trang UI, model DB riêng; đã có link vào `/rfq/[id]/cipl` trong action row của danh sách RFQ (22/09)
- [ ] COC/COO document handling — `CERTIFICATE_COC_COO_PDF` vẫn dùng nhầm template Quotation (P3-5), chưa có template APITemplate riêng — cần thiết kế template mới trong dashboard APITemplate.io (ngoài phạm vi code) rồi thêm `APITEMPLATE_COC_COO_TEMPLATE_ID`
- [x] Email Review Agent (human-in-the-loop) v1 — **xong, xem §13 và `PROGRESS.md` §8**: Gemini soạn nháp subject/body email Quotation trên `quote-preview`, Sale Admin luôn duyệt/sửa trước khi gửi qua `send-quote`
- [x] Dashboard analytics (revenue, margin KPIs) v1 — **xong, xem §12 và `PROGRESS.md` §7**: `/overview` có biểu đồ xu hướng doanh thu/margin, phễu trạng thái, top khách hàng

### Phase 3 — Automation (v0.3)
- [ ] Full AI Agent orchestration
- [ ] Automated follow-up emails
- [ ] Webhook integration
- [ ] Real-time notifications

### Phase 4 — Scale (v1.0)
- [ ] Multi-tenant support
- [ ] Mobile responsive enhancements
- [ ] Offline mode (PWA)
- [ ] Advanced reporting & exports

---

## 11. CBU Module v2 — Đặc tả cập nhật (Logic + Giao diện)

> **Trạng thái (22/09/2026):** ✅ **Phase C0–C5 xong.** C3 xong cả kịch bản Air/Sea + so sánh, C4 xong Baker Hughes / `FCA_DAP`, C5 xong: payload Quotation PDF sửa (`unit_price` = `ddpPriceUsd` per unit, `amount` = × qty — bug P2-5), trang legacy (`?legacy=1`), adapter `calculateCBU()`, route `calculate-cbu`, và shim `lib/cbu-engine.ts` **đã bị xoá** — giao diện mới ở `/rfq/[id]/cbu-calc` là **duy nhất**. Engine v2 ở `src/lib/cbu/` khớp Excel từng dòng (cả hai profile); lưu/đọc + API v2 ở `src/lib/cbu/db/`; 314 test pass, `tsc` 0 lỗi, `next build` thành công. **Migration bước 1 VÀ bước 2 ĐÃ áp lên DB Supabase thật** (22/09, có sao lưu trước mỗi bước) — code đã deploy lên `main`/production trước, rồi mới áp bước 2 đúng thứ tự đã định. `npx prisma migrate status` báo "Database schema is up to date!" (xem §11.8).
> **Nguồn sự thật nghiệp vụ:** 4 file markdown trong `documents/CBU_docx/` (đội nghiệp vụ đã phân tích, chỉnh sửa và chuyển từ Excel). `CBU_ANALYSIS_REPORT.md` (27/08) **đã lỗi thời** — xem §11.2.
> **Đã kiểm chứng:** công thức ở §11.4 được chạy thử bằng một prototype và tái tạo **khớp đến từng dòng** các số trong file markdown Hoàng Sơn (AIR: cost 24,576.98 · revenue $32,793.20 · 890,800,000 VND; SEA: 21,477.91 · $28,652.40 · 778,800,000 VND).

### 11.1 Mục tiêu

| # | Mục tiêu | Đo bằng |
|---|----------|---------|
| G1 | **Đúng số**: engine cho kết quả trùng workbook đã chuẩn hoá | Golden test khớp file md, sai số ≤ 5e-5 (USD), VND khớp tuyệt đối |
| G2 | **Lưu/đọc đầy đủ**: mở lại RFQ thấy đúng những gì đã nhập | Round-trip test: lưu → tải lại → kết quả không đổi |
| G3 | **Server là nguồn quyết định giá**: không tin số client gửi lên | API tự tính lại từ input, bỏ qua total/items do client gửi |
| G4 | **Giao diện tối giản, dễ dùng**: nhập hằng ngày ≤ 8 ô trước khi ra giá | Xem §11.9 |
| G5 | **Bao phủ 2 mẫu nghiệp vụ**: DDP nhập khẩu (Hoàng Sơn) và FCA/DAP (Baker Hughes), có kịch bản Air/Sea, Payment/Net 60 | §11.3 |
| G6 | **Tự kiểm**: mọi phiên tính có dòng CHECK như Excel (=0) | §11.4 (Invariants) |

**Ngoài phạm vi (không làm ở v2):** multi-currency EUR, nhiều shipment/forwarder trên cùng 1 kịch bản, phê duyệt margin nhiều cấp, dashboard analytics, xử lý COC/COO.

### 11.2 Hiện trạng đã kiểm chứng (chạy code thật với dữ liệu AC0084)

Kiểm chứng bằng cách nạp 16 dòng AIR của AC0084 vào `lib/cbu-engine.ts` hiện tại và so với Excel.

| # | Phát hiện | Bằng chứng | Mức |
|---|-----------|------------|:---:|
| F1 | **Phân bổ logistics sai ~2 bậc độ lớn.** Engine dùng `netWeightLbs` theo hai nghĩa trái ngược: `extWeight = net × qty` (coi là *đơn vị*) nhưng `weightPerUnit = net ÷ qty` (coi là *tổng dòng*) | Σ(logistics+insurance)×qty = **14.78** trong khi pool = **4,253** (chỉ 0.35%). Excel: bằng pool | 🔴 P0 |
| F2 | **`pct()` tự đoán đơn vị**: giá trị ≤ 1 bị coi là *phân số*. Duty 1% → 100%; Insurance rate `0.01` (=0.01%) → 1%; Remittance `0.2` (=0.2%) → 20% | Duty 1% trên base 100 → **100** (đúng: 1). Insurance **253.23** (Excel 15.00). Bank fee dòng 1 **0.975** (Excel 0.025, gấp 39 lần) | 🔴 P0 |
| F2b | **F1 và F2 lệch ngược chiều nên triệt tiêu ở mức tổng** — tổng cost chỉ lệch +0.8% (24,775.72 vs 24,576.98) nên nhìn tổng tưởng đúng; sai nằm ở từng dòng (giá bán dòng 1: 7.49 vs **7.10**, +5.5%). Đây cũng là lý do test "pass" sau khi sửa fixture `0.2 → 0.002` | | 🔴 |
| F3 | **Duty base**: Excel = `(Material + Logistics đã phân bổ, GỒM insurance) × %Duty`; engine cũ loại insurance ra khỏi base. *(C1 sửa khớp Excel; 22/09 đổi tiếp sang CIF thực theo quyết định Q2 — xem §11.12)* | Lệch nhỏ khi Duty > 0 | 🟠 |
| F4 | **Mặc định chi phí lô hàng không nhất quán**: Excel không có `docFee`; schema mặc định 0 nhưng trang/route fallback **15** (`safeNum(rawData.docFee, 15)`, `docFee ?? 15`) — hiện ít kích hoạt vì Prisma trả 0, nhưng là bẫy. Ngược lại `clearanceCost 150` / `inlandCost 100` (số của một lô mẫu) **đang là mặc định thật** trong schema → mọi RFQ mới tự mang 250 USD chi phí | Đọc `schema.prisma`, `cbu-calc/page.tsx`, `calculate-cbu/route.ts` | 🟡 |
| F5 | **Không lưu được**: `cbuMode`, `targetMarginPercent`, `commissionRate`, `citOnCommission`, `marginOverrideUsd` không có cột DB; route không ghi `supplierUnitPrice` / trọng lượng đã sửa → mở lại là mất | Đọc `prisma/schema.prisma` + `calculate-cbu/route.ts` | 🟠 |
| F6 | **Mở lại RFQ đã lưu → margin 0%**: `RFQItem.marginPercent` có `@default(25)`; route ghi `item.marginPercent ?? 0` (dòng không ghi đè → `null` → **0**); trang tải lại coi `0` là override hợp lệ (`!== null`) → mọi dòng thành margin 0%, giá bán = giá vốn. Trước lần lưu đầu thì mọi dòng mang override ngầm 25%. Cả hai trường hợp làm Target margin toàn đơn mất tác dụng | Suy ra từ đọc code (chưa chạy trên DB) | 🔴 |
| F7 | **Route tin số client**: nhận `items` + tổng đã tính từ trình duyệt và ghi thẳng DB; không Zod | Ai có session đều ghi được giá tuỳ ý | 🟠 |
| F8 | **Tàn dư đã bị loại khỏi workbook**: `bookingExchangeRate` + `effectiveMarginPct` (md §9: "như đã làm với ExchangeRate_Booking"); fallback tỷ giá không thống nhất (engine 25,500 / trang 26,500) | | 🟡 |
| F9 | **Thiếu năng lực workbook đã có**: kịch bản Air/Sea song song + chênh lệch (112,000,000 VND); Baker Hughes (FCA/DAP, Payment-with-Order / Net 60); dòng CHECK; nhóm khách "Nước ngoài" đang bị chặn | | 🟡 |
| F11 | **VAT factor dùng chung**: engine cũ nhân 1.1 cho cả phí *receive*; md ghi remittance = **1.10**, receive = **1.00** (đã sửa ở C1: hai tham số riêng `remitVatFactor`, `receiveVatFactor`) | Đọc md §7 | 🟡 |
| F10 | **UI**: card `max-h-[90vh]` lồng scroll trong page; ~25 ô nhập ở 3 panel hiển thị cùng lúc; 3 bảng tóm tắt căn bằng hack `pt-[45px]` / `pt-[124px]`; cột màu cầu vồng (xanh/tím/lục/xám); nhãn Anh–Việt lẫn lộn; 900 dòng trong 1 file | Đọc `cbu-calc/page.tsx` | 🟡 |

**Trạng thái sửa (21/09/2026):** F1–F4, F11 ✅ engine (C1) · F5, F6, F7 ✅ mã nguồn (C2; cần áp migration để có hiệu lực trên DB thật) · F8 ✅ engine không còn dùng, dọn khỏi UI/DB ở C3 · F9 → C3 (Air/Sea) và C4 (Baker Hughes) · F10 → C3.

**Đính chính `CBU_ANALYSIS_REPORT.md`:** ba "lỗi" nó nêu **không phải lỗi**: (§3.1) *Insurance tính 2 lần* — không, insurance nằm trong pool cùng driver trọng lượng, khớp Excel; (§3.3) *Financing tính 2 lần* — không, `totalFinancingCostUsd` chỉ là số hiển thị, không cộng vào cost; (§3.4) *Commission/CIT ở PRICE_INPUT* — đúng theo md. Bản sửa "logistics allocation" ngày 27/08 (dùng `weight_per_unit ÷ totalWeight`) **cũng chưa đúng** vì `totalWeight` vẫn tính theo nghĩa còn lại (F1).

### 11.3 Hai profile CBU và mô hình kịch bản

Một **CBU sheet** = 1 profile + 1 mode + tham số chung + **N kịch bản** (dùng chung dòng hàng). Kịch bản chỉ ghi đè phần khác nhau giữa các phương án báo giá.

| | `DDP_IMPORT` (mẫu Hoàng Sơn · AC0084) | `FCA_DAP` (mẫu Baker Hughes · AC0481) |
|---|---|---|
| Nhóm khách | Nội địa (VN) | Nước ngoài (MY…) — bỏ chặn "đang phát triển" ở modal CBU |
| Giá đầu ra | DDP USD (+ VND) | Sales Price **FCA** và **DAP** (= FCA + cước) |
| Cấu phần chi phí | Material + Bank/Fin + Logistics + Duty + Commission + CIT | Material + Financial cost (phí NH phân bổ + lãi tín dụng) |
| Kịch bản mặc định | **Air** / **Sea** (khác khối logistics) | **Payment with Order** / **Net 60** (khác ngày tín dụng) |
| Làm tròn giá USD | `ROUNDUP(x, 2)` | `ROUNDUP(x, 0)` |
| Mode | `MARGIN_INPUT` · `PRICE_INPUT` | `MARGIN_INPUT` · `PRICE_INPUT` |
| Ghi đè theo dòng | Margin % và Margin $/unit (ưu tiên $) | Margin % |
| Việc dùng chung | pool bank fee · chi phí vốn · làm tròn · CHECK · server recompute | |

**Đã triển khai (C3).** Kịch bản = một phương án vận chuyển trên **cùng các dòng hàng**. Lưu trong `RFQ.cbuConfig = { schemaVersion, chosenScenarioId, scenarios: [{ id, label, overrides, prices }] }`.

- **Kịch bản đầu tiên là nền**: logistics của nó là các cột phẳng `RFQ.freight*/clearanceCost/inlandCost/docFee` và `overrides` luôn rỗng. Kịch bản sau chỉ lưu phần khác nền (hiện chỉ **logistics**) trong `overrides`. Các tham số còn lại (tỷ giá, margin, hoa hồng, ngân hàng, bảo hiểm, chi phí vốn…) và các dòng hàng (giá gốc, trọng lượng, thuế, ghi đè margin) **dùng chung** mọi kịch bản.
- **`prices`** = giá bán nhập của từng dòng theo kịch bản (chế độ `PRICE_INPUT`; workbook có giá riêng cho Air và Sea). Lưu tường minh sau mỗi lần lưu; config cũ chưa có `prices` thì lấy giá đã lưu trên dòng làm mặc định (tương thích).
- **Kịch bản được chọn** (`chosenScenarioId`) quyết định các cột kết quả mà Quotation đọc: `RFQItem.ddpPriceUsd/unitCostUsd/...` và tổng của `RFQ`. Cột phẳng logistics của RFQ luôn là kịch bản nền, **không** phải kịch bản được chọn.
- **Finalize chỉ chặn theo kịch bản được chọn** (các phương án chỉ để so sánh có thể chưa đủ dữ liệu).
- API: `saveCbuSchema` nhận `scenarios[]` (1–4, id duy nhất, chỉ `overrides.logistics`) và `chosenScenarioId`; bỏ qua `scenarios` = giữ nguyên các kịch bản đã lưu; client cũ gửi giá theo dòng (`items[].ddpPriceUsdInput`) được gán cho kịch bản đầu. `sheet.scenarios[]` trả kết quả từng kịch bản để so sánh.
- Giao diện: thanh tab phương án (thêm = sao chép phương án đang xem, đổi tên, xoá, dấu ✓ = dùng cho Quotation), bảng **So sánh phương án** (pool logistics, giá vốn, doanh thu $ / ₫, lãi, margin, chênh lệch so với phương án được chọn — với AC0084: Air − Sea = 112,000,000 ₫ đúng workbook) và nút "Chọn phương án này". Đã kiểm chứng: Air 890,800,000 ₫, Sea 778,800,000 ₫ (từng dòng khớp md).

### 11.4 Công thức chuẩn — `DDP_IMPORT` (đã kiểm chứng với md)

Quy ước: mọi `…Pct` **nhập theo phần trăm (3 = 3%)**; engine luôn chia 100, **không tự đoán**.

```
# (1) Dòng hàng i — đơn vị TRỌNG LƯỢNG chuẩn: tổng dòng, pound (= cột F Excel = RFQItem.extWeightLbs)
w_i   = extWeightLb_i ÷ qty_i × lbToKg                  # kg / đơn vị
W     = Σ qty_i × w_i          M = Σ qty_i × material_i # tổng của shipment (kịch bản)

# (2) Pool logistics (Sheet Logistic)
freight   = freightAllIn > 0 ? freightAllIn : freightFixed + freightRate × chargeableKg
insurance = MAX( (M + freight) × insuredPct × insuranceRate , minInsurance )   # dùng cột "Insurance", KHÔNG dùng "Min insurance"
pool      = freight + clearance + inland + otherLogistics + insurance          # otherLogistics mặc định 0

# (3) Pool phí ngân hàng (Sheet Bank Fee)
remit     = origin == "Local" ? 0 : MAX( remitRate × remitVat(1.10) × M , minRemit )
receive   = country == "VN"   ? 0 : MAX( receiveRate × receiveVat(1.00) × receiveBase , minReceive )   # receiveBase NHẬP TAY (tránh vòng lặp)
bankTotal = remit + receive + otherBank

# (4) Từng dòng (Sheet Margin Analysis)
financing_i  = material_i × pctFinanced × (interest × days ÷ daysPerYear)
bankFee_i    = financing_i + bankTotal × material_i ÷ M           # cột J "Bank fee & Financial cost"
logistics_i  = pool × w_i ÷ W                                     # cột K (đã gồm insurance) — dùng để cộng vào base_i
freightShare_i  = freight × w_i ÷ W                               # phần cước quốc tế phân bổ cho dòng i
insuranceShare_i = insurance × w_i ÷ W                            # phần bảo hiểm phân bổ cho dòng i
dutyBase_i   = material_i + freightShare_i + insuranceShare_i     # CIF thực — KHÔNG dùng cột L Excel (Material + logistics_i,
               #  vốn gồm cả clearance/inland/other không thuộc trị giá tính thuế). Quyết định Q2, 22/09/2026 — xem §11.12
duty_i       = dutyBase_i × dutyPct_i
base_i       = material_i + bankFee_i + logistics_i + duty_i + custom_i
k            = 1 − commissionPct × (1 + citPct)

MARGIN_INPUT:
  marginUsd_i > 0 ? ddp_i = ROUNDUP( (base_i + marginUsd_i) ÷ k , 2 )
                  : ddp_i = ROUNDUP( base_i ÷ (k − m_i) , 2 )     # m_i = marginPctOverride_i ?? targetMargin
PRICE_INPUT:
  ddp_i = giá nhập tay

commission_i = commissionPct × ddp_i          cit_i = citPct × commission_i
unitCost_i   = base_i + commission_i + cit_i  # = Material + Bank + Logistics + Duty + Commission + CIT
margin_i     = ddp_i − unitCost_i             margin%_i = margin_i ÷ ddp_i   (luôn là KẾT QUẢ)
ddpVnd_i     = ROUNDUP( ddp_i × fx ÷ vndStep ) × vndStep
Tổng: TotalRevenueVnd = Σ qty × ddpVnd · TotalCost = Σ qty × unitCost · NominalMargin% = Σ qty×margin ÷ Σ qty×ddp
Bảo vệ: nếu (k − m_i) ≤ ε → cảnh báo trên dòng, KHÔNG trả giá vô nghĩa.
```

**Invariants tự kiểm (tương ứng dòng CHECK Excel — phải = 0, dung sai 1e-6):**

| ID | Kiểm tra |
|----|----------|
| C1 | `unitCost_i − (material + bankFee + logistics + duty + commission + cit) = 0` |
| C2 | `Σ qty×(bankFee_i − financing_i) − bankTotal = 0` |
| C3 | `Σ qty×logistics_i − pool = 0` (chỉ khi W > 0) |
| C4 | MARGIN_INPUT: `margin%_i ≥ margin mục tiêu_i − 1e-9` (do ROUNDUP chỉ làm tăng) |

Engine trả `checks: { id, label, delta, ok }[]`; UI hiện một chip "✓ Đối soát khớp" hoặc danh sách dòng lệch. **Chốt CBU (finalize) bị chặn nếu có check lỗi.**

### 11.5 Công thức — `FCA_DAP` (Baker Hughes)

```
# Bank pool: remit = MAX(0.2% × 1.1 × M, min 50) ; receive = MAX(rate × base, min) khi Country ≠ VN   (Q4 dưới đây)
financing_i = bankTotal × material_i ÷ M
            + material_i × pctFinanced × (interest × creditDays ÷ daysPerYear)
              # Payment with Order: pctFinanced = 0 → chỉ còn phần phí NH
              # Net 60: pctFinanced = 100%, interest = 15%, creditDays = 45  (file gốc hardcode 15%×45/360)
unitCost_i  = material_i + financing_i
salesFca_i  = MARGIN_INPUT ? ROUNDUP( unitCost_i ÷ (1 − marginPct_i) , 0 ) : giá nhập
salesDap    = Σ qty_i × salesFca_i + freightManual          # cước nhập tay ở cấp đơn (P16), cộng vào TỔNG
freightRef  = pool freight (sheet Logistic) — chỉ tham khảo; cảnh báo nếu |freightRef − freightManual| > 0
```

Thống nhất chi phí vốn giữa hai profile: `financing = material × pctFinanced × interest × days ÷ daysPerYear` (DDP: 50%·15%·15 ngày/360; Baker Net 60: 100%·15%·45 ngày/360).
Số kiểm chứng Baker: FCA unit cost 108.33 → giá **131** (total 3,930, margin 680); Net 60: unit cost 110.31 → giá **133** (total 3,990) + cước 1,100 = DAP **5,090**; Payment with Order: DAP 131 → 3,930 + cước 1,800 = **5,730**.

**Đã triển khai (C4, 22/09/2026)** — `src/lib/cbu/profiles/fca-dap.ts`, golden `__tests__/cbu/fca-dap.golden.test.ts` (số lấy từ md Baker, fixture `ac0481.ts`):
- Mỗi dòng có **hai khối giá trên cùng giá vốn**: FCA (`financial = phí NH phân bổ theo material`, **không** có lãi tín dụng) và DAP (`FCA + material × pctFinanced × lãi × ngày ÷ daysPerYear`). `price = ROUNDUP(unitCost ÷ (1 − margin), 0)` (làm tròn USD nguyên); PRICE_INPUT nhập cả giá FCA lẫn giá DAP theo từng kịch bản.
- **Kịch bản = điều khoản thanh toán** (Payment with Order: 0%/0 ngày · Net 60: 100%/45 ngày, lãi 15%). Trục kịch bản của Baker là `pctFinanced`, `interestPct`, `financingDays` và cước; các tham số còn lại (biểu phí NH, margin mục tiêu, nước đích) dùng chung.
- **Chào giá DAP = Σ qty × giá DAP + một khoản cước trọn gói** (Excel G16 = G15 + P16). Tái dùng hai trường cước của mô hình chung: `logistics.freightAllInUsd` = **cước báo giá** (cộng vào tổng), `logistics.freightFixedUsd` = **cước theo bảng Logistic** (chỉ đối chiếu). Khác nhau ⇒ **cảnh báo** (Net 60: 1,100 vs 1,800 ⇒ chênh $700), không làm hỏng check.
- Không có thuế nhập khẩu, hoa hồng, CIT, bảo hiểm, phân bổ logistics theo trọng lượng ⇒ trọng lượng không bắt buộc, các trường này ẩn khỏi UI; `fx` và bước làm tròn VND vẫn nhập được vì tổng VND của RFQ phụ thuộc chúng.
- **Cơ sở báo giá `quoteBasis` (FCA | DAP)** lưu trong `cbuConfig`; mặc định suy từ Incoterm của RFQ (`DAP`/`DDP` ⇒ DAP, còn lại FCA). Quyết định khối giá nào được lưu vào `RFQItem.ddpPriceUsd` và tổng RFQ (cơ sở DAP: tổng **đã gồm** cước trọn gói). Kịch bản được chọn quyết định như ở DDP.
- Profile lưu ở `RFQ.cbuProfile`; `profileFromRfq` đọc cột này. Chuyển mô hình trong giao diện có bước xác nhận vì nó **đặt lại** tham số/kịch bản về mặc định của mô hình mới (dòng hàng và giá gốc giữ nguyên). Vào từ modal "Nước ngoài" với sheet chưa từng tính ⇒ tự chuyển sang Baker.
- Mặc định Baker (`PROFILE_DEFAULTS.FCA_DAP`): margin mục tiêu 17%, làm tròn USD 0 chữ số, hoa hồng/CIT 0, nước đích MY, phí nhận tiền min $35, lãi 15%; vì phí nhận tiền chưa chốt (Q4) nên `bank.receiveBaseUsd` vẫn **nhập tay**.

### 11.6 Quy ước bắt buộc (áp dụng cho code mới)

1. **Đơn vị %**: UI, DB, API đều dùng số phần trăm (3 = 3%). Chỉ engine chia 100. Cấm auto-detect. *(DB hiện đã lưu theo quy ước này — không cần migrate dữ liệu, chỉ sửa cách engine đọc.)*
2. **Trọng lượng**: chuẩn là **tổng trọng lượng dòng (lb)** = `RFQItem.extWeightLbs`; `netWeightLbs` = `ext ÷ qty` là giá trị dẫn xuất. Nếu `ext` trống thì lấy `netWeightLbs × qty`.
3. **Chi phí theo shipment mặc định = 0** (cước, thông quan, nội địa, phí khác). Các con số 150 / 100 / 15 trong code là *ví dụ của 1 lô hàng*, không phải mặc định. Chỉ **tham số chính sách** (biểu phí NH, điều khoản bảo hiểm, days/year, lb→kg, bước làm tròn VND, tỷ giá) có mặc định — đặt ở **một** file `defaults.ts`.
4. **Không gọi `.toFixed()` trong engine**; mọi số ra khỏi engine phải hữu hạn.
5. **Server tính lại** trước khi lưu; số client chỉ để hiển thị.
6. **Đổi công thức = đổi golden test trước** (TDD). Không sửa fixture cho khớp code.

### 11.7 Phân loại biến → cách hiển thị trong UI

Theo nhãn nhóm mà đội nghiệp vụ đã gắn trong các file md.

| Nhóm | Ví dụ | Trong UI | Nguồn dữ liệu |
|------|-------|----------|---------------|
| 🗄️ DATABASE | Part No, Description, Supplier, Qty, Total Weight, Material Cost; Customer, Country, Goods origin, Incoterm, Payment terms, Inquiry date | **Chỉ đọc** (chữ xám). Trọng lượng & Material cho phép "Sửa" có chủ đích (AI hay bóc thiếu) và gắn nhãn *đã chỉnh*; ghi ngược `RFQItem` | `RFQ`, `RFQItem` |
| 🟦 INPUT | Job No., %Duty, Commission q, CIT c, cước / thông quan / nội địa, Receive base, Margin override, **DDP Price (mode PRICE)** | Ô nhập: viền mảnh + chữ xanh (giữ quy ước Excel "xanh = nhập") | `RFQ.cbuConfig`, `RFQItem` |
| 🟧 DEFAULT | Tỷ giá, Target margin, biểu phí NH, điều khoản bảo hiểm, days/year, bước làm tròn, lb→kg | Panel tham số **thu gọn**, nhãn "Mặc định" + nút "Khôi phục" khi đã sửa | `defaults.ts` → `cbuConfig` |
| 🟧 DEFAULT\* "(Bỏ)" | Target margin, % Value financed, Interest rate, Financing days | **Giữ nguyên trong engine** (vẫn nằm trong công thức). UI đưa vào "Nâng cao" — chờ quyết định **Q1** | như trên |
| ⚙️ COMPUTED / 🟩 LINK | Weight kg, Bank fee, Logistics, Duty, Commission, CIT, Unit cost, Margin, các tổng | Chỉ đọc, chữ đen; tooltip hiện công thức | Engine |

### 11.8 Kiến trúc & mô hình dữ liệu

**Cấu trúc mã**

```
src/lib/cbu/
  types.ts              # CbuInput, CbuScenario, CbuResult, CbuCheck
  math.ts               # n(), g(), roundUp(), roundUpToStep(), pctToFrac()   ← không còn pct() đoán đơn vị
  defaults.ts           # MỘT nơi duy nhất chứa mặc định chính sách (+ theo profile)
  pools.ts              # freight, insurance, bank pool, financing
  pricing.ts            # closed-form, override $, price-input
  profiles/ddp-import.ts · profiles/fca-dap.ts
  checks.ts             # C1–C4
  params.ts             # resolveParams(): partial/garbage → CbuParams đầy đủ, hữu hạn
  legacy.ts             # adapter calculateCBU() cho code cũ (xoá ở C5)
  index.ts              # calculateCbu(lines, params) — API mới
lib/cbu-engine.ts       # re-export mỏng của legacy.ts → xoá khi hợp nhất lib/ (Sprint 2)
# Trạng thái C1: đã có types, math, defaults, params, pools, pricing, checks, profiles/ddp-import, index, legacy.
# (cây thư mục dưới đây là thiết kế ban đầu; profiles/fca-dap, schemas và components/cbu đã có từ C2–C4.)
src/lib/schemas/cbu.schemas.ts   # Zod cho GET/PUT/finalize
src/components/cbu/     # xem §11.9
```
Engine là hàm **thuần**, chỉ import tương đối (không `@/`) để chạy giống nhau ở client, server và Jest.

**Thay đổi Prisma** (tối thiểu, theo phase — xem cảnh báo migration bên dưới)

| Model | Thay đổi | Ghi chú |
|-------|----------|---------|
| `RFQ` | `cbuProfile String? @default("DDP_IMPORT")`, `cbuMode String? @default("MARGIN_INPUT")`, `targetMarginPercent Float? @default(25)`, `commissionRate Float? @default(3)`, `citOnCommission Float? @default(20)` | Sửa F5. `targetMarginPercent` **mặc định 25, không để null**: trang cũ đọc `safeNum(null, 25)` thành 0 (vì `Number(null) = 0`) làm giá về margin 0% |
| `RFQ` | `cbuConfig Json?` (`schemaVersion`, `chosenScenarioId`, `scenarios[]` với `overrides`), `cbuCalculatedAt DateTime?` | Chỉ giữ kịch bản + ghi đè; tham số nền ở cột phẳng (xem §11.3) |
| `RFQ` | đổi mặc định `clearanceCost`, `inlandCost` từ 150/100 → **0**; `exchangeRate` 25500 → 26500 (khớp schema) | Q6 (mặc định tạm). Chỉ ảnh hưởng RFQ tạo mới; giá trị đã lưu giữ nguyên |
| `RFQItem` | `marginOverrideUsd Float?`; **bỏ `@default(25)` của `marginPercent`** (null = dùng Target) | Sửa F6. **Backfill (bước 2 của migration, sau khi deploy code):** `marginPercent IN (0, 25)` → NULL (hai giá trị này chỉ là dấu vết của default cũ và `?? 0`, không mang thông tin); giá trị khác giữ nguyên. Bảng sao lưu `_cbu_v2_margin_backup` được tạo trước khi sửa. *(Điều chỉnh so với bản đầu: không dùng điều kiện theo trạng thái RFQ, vì RFQ đã `QUOTATION_DRAFTED` cũng mang giá trị 0 do lỗi và sẽ mở lại thành margin 0%.)* |
| `RFQItem` | dùng `extWeightLbs` làm trọng lượng chuẩn (không thêm cột) | §11.6-2 |

> ⚠️ **Cảnh báo migration:** DB đang **lệch migration ở cả mức cột** (ví dụ `init` không có `clearanceCost`, `docFee`, `customColumns`…; `exchangeRate` mặc định 25500 còn schema là 26500). **Không chạy `prisma migrate dev`** — Prisma sẽ đề nghị *reset* và xoá dữ liệu.
>
> **Cách đã chọn (đã làm ở C2): migration SQL viết tay, idempotent, tách 2 bước** — chỉ đụng `RFQ` và `RFQItem`, dùng `ADD COLUMN IF NOT EXISTS` / `SET DEFAULT` / `DROP DEFAULT` / `CREATE TABLE IF NOT EXISTS` nên chạy đúng dù DB ở trạng thái lệch nào và chạy lại nhiều lần không hại.
>
> - **Bước 1** `prisma/migrations/20260921120000_cbu_v2` — *chỉ thêm* cột và đổi default. Code production hiện tại (chưa biết các cột này) vẫn chạy bình thường.
> - **Bước 2** `prisma/migrations/20260921120100_cbu_v2_margin_cleanup` — sao lưu, bỏ default và backfill `RFQItem.marginPercent`. **Chỉ áp sau khi code mới đã chạy**: `GET /api/rfq/[id]` bản cũ ép `null → 0` và trang cũ coi 0 là override 0%, nên backfill trước khi deploy sẽ biến các dòng đó thành margin 0% (điều này được phát hiện khi chuẩn bị áp lên DB thật và đã có kiểm tra tự động).
>
> Đối chiếu bằng `prisma migrate diff` (phần đổi schema khớp từng câu lệnh) và **kiểm chứng bằng `node scripts/verify-cbu-migration.mjs`** (Postgres nhúng, không đụng DB thật): áp trên `init`, mỗi bước chạy 2 lần, **sau bước 1 dữ liệu và default `marginPercent` không đổi**, bước 2 backfill và sao lưu đúng.
>
> **Thứ tự triển khai bắt buộc:** (1) backup DB → (2) áp **bước 1** → (3) deploy code → (4) áp **bước 2**. Nếu deploy code mà chưa áp bước 1, mọi truy vấn `RFQ` sẽ lỗi vì Prisma client chọn các cột chưa tồn tại. Nếu phải rollback code, chạy khối ROLLBACK ở cuối file bước 2 *trước*. Cách áp: dán file vào Supabase SQL editor (chạy một lần cả khối) hoặc `npx prisma db execute --file …`; rồi `npx prisma migrate resolve --applied <tên>` (bảng `_prisma_migrations` có tồn tại, hiện chỉ ghi `init`). Cuối mỗi file có khối ROLLBACK thủ công.

**API v2** (mọi route: `getServerSession` + role `ADMIN`/`SALE_ADMIN`, body qua Zod)

| Route | Việc |
|-------|------|
| `GET /api/rfq/[id]/cbu` | Trả meta RFQ, dòng hàng (đã chuẩn hoá trọng lượng), cấu hình đã merge với mặc định, kết quả lưu gần nhất |
| `PUT /api/rfq/[id]/cbu` | Lưu nháp: chỉ nhận **input**; server chạy engine, ghi kết quả + `checks`; status → `CBU_PENDING_ADMIN` |
| `POST /api/rfq/[id]/cbu/finalize` | Như PUT + điều kiện: mọi check OK, mọi dòng có giá > 0 và trọng lượng > 0; status → `QUOTATION_DRAFTED`; đẩy kịch bản `isChosen` xuống cột phẳng |
| `POST /api/rfq/[id]/calculate-cbu` | **Deprecated alias** cho trang cũ: đọc body cũ, **bỏ qua mọi kết quả/tổng client gửi**, chuyển sang input v2 rồi qua cùng service (server tính lại). Lỗi 422 được gộp vào `error` để trang cũ hiển thị được |

**Đã triển khai (C2):** `src/lib/cbu/db/{mapping,service,legacy-body,audit,errors,http}.ts`, `src/lib/schemas/cbu.schemas.ts` (Zod: mọi % là số phần trăm, margin < 100%, khoá lặp bị từ chối, khoá thừa bị loại bỏ), 3 route. Chi tiết hành vi:

- **GET** trả `sheet`: thông tin RFQ, tham số đã hợp nhất mặc định, từng dòng (trọng lượng **tổng dòng**, override), `result` **tính lại mới** từ input đã lưu, và `saved` (số đã lưu trong DB, để so lệch).
- **PUT (nháp) / finalize:** nhận **chỉ input**; đọc dòng hàng từ DB (chống sửa dòng không thuộc RFQ → 400), áp chỉnh sửa, chạy engine, ghi trong một transaction; rồi đọc lại DB để trả đúng thứ mà lần tải sau sẽ thấy.
- **Trạng thái:** nháp → `CBU_PENDING_ADMIN` (kể cả RFQ đang `QUOTATION_DRAFTED`, vì Quotation nháp không còn khớp số); finalize → `QUOTATION_DRAFTED`; **`QUOTED_TO_CLIENT` không bao giờ bị hạ** (giá đã gửi là lịch sử; response kèm ghi chú). *Đây là quyết định của tôi khi làm C2 — bản cũ hạ mọi trạng thái về `CBU_PENDING_ADMIN`.*
- **Cổng finalize (422 + danh sách lý do, không ghi gì):** có ít nhất một dòng; mọi check C1–C4 đạt; mỗi dòng có giá bán hợp lệ, giá gốc > 0 và trọng lượng > 0.
- Trọng lượng lưu: `extWeightLbs` = tổng dòng (chuẩn), `netWeightLbs` = `ext ÷ qty`.
- **Audit:** `scripts/cbu-audit.ts` (chỉ đọc; lõi thuần ở `db/audit.ts` có test) xuất CSV giá đã lưu so với giá v2; dùng `omit` nên chạy được **trước** khi áp migration. Là *ước lượng* (bản cũ không lưu hoa hồng/CIT/margin mục tiêu nên dựng lại từ mặc định) — xem chú thích đầu file.

Kèm script chỉ-đọc `scripts/cbu-audit.ts`: tính lại mọi RFQ đã ở `QUOTATION_DRAFTED`/`QUOTED_TO_CLIENT` bằng engine v2 và xuất CSV chênh lệch giá — phục vụ quyết định thương mại về các báo giá đã gửi (Sprint 0 của `PROGRESS.md`).

### 11.9 Thiết kế giao diện (tối giản · thân thiện · hiện đại)

**Nguyên tắc**

1. **Hiển thị dần (progressive disclosure):** mặc định chỉ thấy thứ Sale Admin gõ mỗi ngày — tỷ giá, margin mục tiêu, hoa hồng, CIT, cước/thông quan/nội địa, và 3 ô mỗi dòng (Trọng lượng · Giá gốc · %Duty). Biểu phí NH, bảo hiểm, chi phí vốn, làm tròn nằm trong mục thu gọn có nhãn "Mặc định".
2. **Mỗi khái niệm một chỗ:** bỏ 3 bảng tóm tắt riêng; số pool (Logistics $4,015, Bank+Fin $110…) hiện ngay trên tiêu đề từng mục tham số.
3. **Một trang, một cuộn:** bỏ card `max-h-[90vh]` lồng scroll; header dính, footer dính, bảng cuộn ngang chỉ ở nhóm cột chi tiết.
4. **Màu có nghĩa:** nền trung tính; **xanh dương = ô nhập**; **xanh lá / đỏ chỉ dùng cho margin** (tốt / âm); cam cho cảnh báo. Bỏ nền cột tím–lục–xanh.
5. **Phản hồi tức thì:** tổng và margin cập nhật khi gõ; dòng margin âm nền đỏ nhạt; dòng thiếu trọng lượng có chấm cam + tooltip "logistics chưa phân bổ được".
6. **Số dễ đọc:** `tabular-nums`, canh phải, USD 2 số lẻ, kg 4 số lẻ, VND theo `vi-VN`; bỏ ký hiệu `$` lặp ở từng ô (đặt trong tiêu đề cột).
7. **Nhãn Việt hoá, giữ thuật ngữ Excel trong tooltip** để người quen bảng tính đối chiếu được (vd. "Giá bán DDP (USD)" — *DDP Price*).

**Bố cục (desktop-first, ≥1024px; dưới đó các panel xếp dọc)**

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ ←  RFQ-2026-0123 · Hoang Son · DDP Vung Tau · 30/70          [Lưu nháp]  [Hoàn tất  →]   │ header dính
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ (● Nhập Margin | ○ Nhập Giá bán)    Kịch bản: [ Air ] [ Sea ] [ + ]         ✓ Đối soát khớp │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ Doanh thu 890.8M ₫   Giá vốn $24,577   Margin 25.05% ●   Air − Sea: +112.0M ₫  [So sánh] │ KPI strip
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ ▾ Cơ bản       Tỷ giá [26,500]  Margin mục tiêu [25]%  Hoa hồng [3]%  CIT [20]%          │
│ ▾ Vận chuyển & bảo hiểm · Air        Cước [3,750]  Thông quan [150]  Nội địa [100]        │
│      Pool logistics $4,015 (gồm bảo hiểm $15)                                              │
│ ▸ Ngân hàng & chi phí vốn  · Pool $110.22  [Mặc định]      ▸ Nâng cao  [Mặc định]          │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│  #  Part No / Mô tả          SL   KL (lb)  Giá gốc  %Thuế │ Chi phí ▸ │ Giá vốn  Giá bán $  Giá bán ₫   Margin │
│  1  A23-170 · 7 5/8" BASIC  320   121.6    4.37    0     │  (thu gọn) │  5.32     7.10     190,000    25.0% │
│  …                                                                                          │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ TỔNG   4,080 · 2,273 lb · $19,271                          Doanh thu 890,800,000 ₫  · 25.05% │ footer dính
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

**Hành vi**

| Vùng | Hành vi |
|------|---------|
| Mode | Segmented control. `PRICE_INPUT`: ẩn cột margin, cột "Giá bán $" thành ô nhập, margin thực là kết quả. `MARGIN_INPUT`: cột "Ghi đè margin" (% và $) ẩn sau nút *Ghi đè margin* vì hiếm dùng |
| Kịch bản | Tab Air/Sea (hoặc Payment/Net 60); `+` nhân bản kịch bản hiện tại. Nút **So sánh** mở bảng cạnh nhau (doanh thu, giá vốn, margin, Δ) và chọn phương án đưa vào Quotation |
| Nhóm cột "Chi phí" | Thu gọn mặc định (chỉ thấy Giá vốn). Mở ra: Bank+Fin · Logistics · Duty · Commission · CIT |
| Dòng | Bấm dòng → ngăn kéo **Cấu trúc giá**: thanh xếp chồng Material / Bank+Fin / Logistics / Duty / Hoa hồng+CIT / Margin, kèm $ và % giá bán (chỉ CSS, không thêm thư viện biểu đồ) |
| Ô nhập | Giữ chuỗi trong state, parse khi blur (chấp nhận `1,5` và `1.5`); `Enter`/`Tab` xuống dòng dưới cùng cột; **dán nhiều dòng từ Excel** vào một cột |
| Mặc định | Ô đã sửa khác mặc định có chấm "Đã sửa" + nút khôi phục |
| Kiểm tra | Chip "Đối soát" (C1–C4). Lỗi liệt kê dòng lệch. Cảnh báo (margin âm, thiếu trọng lượng, `k − m ≤ 0`, receiveBase = 0 khi Country ≠ VN) hiện **tại dòng/ô liên quan**, không gom một khung |
| Lưu | "Lưu nháp" luôn khả dụng; "Hoàn tất" chỉ bật khi hợp lệ, có xác nhận tóm tắt ("Tạo Quotation nháp: 16 dòng · $32,793.20 · margin 25.05%"). Cảnh báo khi rời trang có thay đổi chưa lưu; thông báo bằng `toast` |
| Trạng thái | Skeleton khi tải, trạng thái rỗng khi chưa có dòng hàng (link về bước Quote), lỗi mạng có nút thử lại |

**Truy cập & tương thích:** nhãn `<label>` cho mọi ô; KPI dùng `aria-live="polite"`; tương phản AA; ô nhập cao tối thiểu 32px; điều hướng bàn phím đầy đủ.

**Đã triển khai ở C3 (lát cắt 1, 21/09/2026)** — `src/components/cbu/` + `src/lib/cbu/ui/`: header dính (RFQ, khách, Incoterm, thanh toán, nguồn→đích, trạng thái, "Chưa lưu"), chọn chế độ (segmented), KPI (doanh thu ₫/$, giá vốn, margin có màu, trọng lượng), chip Đối soát, 4 mục tham số thu gọn được (Cơ bản · Vận chuyển mở sẵn; Bảo hiểm/ngân hàng/vốn · Nâng cao thu gọn với nhãn *Mặc định / Đã sửa N* và nút khôi phục), bảng dòng hàng (nhóm cột Nhập liệu / Chi phí / Kết quả; Enter, ↑↓ chuyển dòng; dán nhiều ô từ Excel; cột chi phí và ghi đè margin bật/tắt; hàng mở rộng hiện thanh cấu trúc giá), footer dính (Hoàn tác · Lưu nháp · Hoàn tất), hộp thoại xác nhận có kiểm tra trước bằng cùng quy tắc của server, chặn rời trang khi chưa lưu. Tính toán tức thì ở client bằng đúng engine; server tính lại khi lưu. **Khác với thiết kế ban đầu:** "ngăn kéo Cấu trúc giá" → *hàng mở rộng tại chỗ* (giữ ngữ cảnh, đơn giản, dễ truy cập). **Chưa làm:** tooltip công thức trên tiêu đề cột, dọn `bookingExchangeRate` khỏi DB/UI cũ. *(Kịch bản Air/Sea + so sánh: xong 22/09, xem §11.3.)*

**Thành phần** (`src/components/cbu/`)

```
cbu-workspace.tsx       # container: state (useReducer) + gọi engine (useMemo) + lưu
cbu-header.tsx · mode-switch.tsx · scenario-tabs.tsx · kpi-strip.tsx · checks-badge.tsx
param-section.tsx       # nhóm thu gọn, nhãn Mặc định/Đã sửa, khôi phục
basic-params.tsx · logistics-panel.tsx · bank-finance-panel.tsx · advanced-params.tsx
items-table.tsx · item-row.tsx (React.memo) · num-cell.tsx (parse khi blur, dán nhiều dòng)
price-breakdown-drawer.tsx · scenario-compare.tsx
```
Dùng lại `src/components/ui/` (table, input, select, badge, dialog, popover, toast). Cần bổ sung Tabs, Tooltip, Collapsible, Sheet dựng trên `@base-ui/react` (đã có trong dependencies) — **không thêm thư viện nặng**. Trang cũ giữ truy cập qua `?legacy=1` một bản phát hành để đối chiếu, rồi xoá.

### 11.10 Chiến lược kiểm thử

| Lớp | Nội dung |
|-----|----------|
| **Golden** | `__tests__/cbu/fixtures/ac0084.ts`: 16 dòng × (AIR, SEA) với giá trị kỳ vọng lấy từ md (Bank fee, Logistics, Commission, Unit cost, DDP USD/VND) và tổng (24,576.98 / 32,793.20 / 890,800,000 · 21,477.91 / 28,652.40 / 778,800,000). Dung sai 5e-5; VND khớp tuyệt đối |
| | `PRICE_INPUT`: nạp DDP từ kết quả MARGIN → unit cost y hệt, margin % = 25.05% (round-trip) |
| | `ac0481.ts`: FCA 131 (total 3,930, margin 680); Net 60: 133/đơn vị + cước 1,100 → DAP 5,090 |
| **Hồi quy có tên** | F1 (Σ logistics×qty = pool), F2 (duty 1% → 1%; insurance 15.00; bank fee dòng 1 = 0.025), F3 (duty base gồm insurance), F4 (chi phí lô hàng mặc định = 0), F6 (`marginPercent` null giữ nguyên qua lưu/đọc, không thành 0) |
| **Thuộc tính** | Bảo toàn pool; `unitCost` = tổng cấu phần; `margin% ≥ mục tiêu`; giá đơn điệu theo cost; mọi số hữu hạn với input rác (null/NaN/chuỗi) |
| **API** | Zod từ chối input sai; server bỏ qua total/items client gửi (gửi tổng sai → kết quả lưu vẫn đúng); round-trip lưu → tải |
| **UI** | Sau khi có hạ tầng test ở Sprint 3: `num-cell` (parse `1,5`, dán nhiều dòng), `param-section` (Mặc định/Đã sửa/khôi phục). Trước đó: checklist kiểm tay §11.11-C3 |
| **Tiên quyết** | Sửa `jest.config.js` (`moduleNameMapper` cho `@/`) — hiện 3/4 suite fail |

### 11.11 Kế hoạch triển khai

Thứ tự **C1 trước UI**: giá sai đang đi ra khách hàng, còn giao diện chỉ là tiện dụng. Ước lượng ≈ 14.5 ngày công (1 dev).

| Phase | Nội dung | Ước lượng | Tiêu chí nghiệm thu |
|-------|----------|:---------:|---------------------|
| **C0 · Chuẩn bị** | Sửa `jest.config.js`; commit 4 file md + cập nhật tài liệu; dựng fixtures từ md; đánh dấu `CBU_ANALYSIS_REPORT.md` lỗi thời | 0.5d | `npm test` chạy được; fixtures nạp được |
| **C1 · Engine đúng** *(TDD)* | Viết golden test **trước** (phải fail); dựng `src/lib/cbu/`: `pctToFrac`, trọng lượng chuẩn, pool, duty base gồm insurance, bỏ `docFee` mặc định, bỏ `bookingExchangeRate`/`effectiveMargin`, `checks`; giữ adapter `calculateCBU()` | 2d | Golden AIR/SEA/PRICE_INPUT pass; hồi quy F1–F4 pass; `tsc --noEmit` 0 lỗi. *Tương ứng P0-5, P0-6* |
| **C2 · Lưu/đọc & API** ✅ *code xong 21/09* | Migration SQL tay (5 cột RFQ + `cbuConfig` + `marginOverrideUsd` + bỏ default 25 + backfill); Zod; route v2 + server recompute; alias `calculate-cbu`; `scripts/cbu-audit.ts` | 2d | Round-trip đúng *(đã kiểm chứng bằng DB giả)*; gửi tổng sai vẫn lưu đúng *(đã kiểm chứng)*; audit script chạy trên DB dev *(**chưa** — cần DB)* |
| **C3 · Dựng lại UI** | Workspace + components §11.9; kịch bản Air/Sea + so sánh; `?legacy=1` | 5d | Kiểm tay: nhập một RFQ mới ≤ 8 ô trước khi ra giá; mở lại RFQ đã lưu thấy đúng; không còn cuộn lồng; Lighthouse a11y ≥ 90 |
| **C4 · Profile `FCA_DAP`** ✅ *xong 22/09* | Engine profile Baker Hughes; kịch bản Payment/Net 60; UI FCA/DAP; bỏ chặn nhóm "Nước ngoài" | 3d | Golden `ac0481` pass; DAP = FCA + cước tay; cảnh báo chênh cước — ✅ *xong 22/09* (29 golden + 23 test tích hợp + 10 test render + 15 kiểm tra e2e) |
| **C5 · Hạ nguồn & hoàn thiện** ✅ *xong 22/09* | Sửa payload Quotation PDF (`unit_price` = `ddpPriceUsd` per unit, `amount` = × qty) — `src/app/api/rfq/generate-document/route.ts` *(tương ứng P2-5)*; xoá trang legacy (`legacy-page.tsx`, link "Giao diện cũ"), adapter `calculateCBU()` (`src/lib/cbu/legacy.ts`), shim `lib/cbu-engine.ts`, route alias `calculate-cbu`, `legacyBodyToSaveInput`, `legacyCalculateCbuSchema`, component mồ côi `cbu-form.tsx`, và test tương ứng; cập nhật CLAUDE.md/SPEC.md/PROGRESS.md | 2d | PDF khớp UI ✅; xoá trang legacy ✅; `npm test` 314/314 pass, `tsc --noEmit` 0 lỗi, `npm run lint` không thêm cảnh báo mới, `next build` thành công |

**Rủi ro & giảm thiểu:** (1) *Giá lịch sử đã gửi khách lệch* → chạy `cbu-audit.ts` trước C2, quyết định thương mại do quản lý PSBV; (2) *Migration trên DB lệch* → cảnh báo §11.8; (3) *Người dùng quen bảng cũ* → `?legacy=1` + giữ thuật ngữ Excel trong tooltip; (4) *Hai thư mục `lib/` và `src/lib/`* → engine mới đặt ở `src/lib/cbu/`, shim ở `lib/` đến khi hợp nhất (Sprint 2).

### 11.12 Câu hỏi mở cần quyết định nghiệp vụ

**Đã chốt 22/09/2026** (7/8 — chỉ Q3 chưa rõ, Q8 ngoài phạm vi kỹ thuật). Cột "Trạng thái" ghi có cần sửa code hay quyết định trùng khớp mặc định tạm sẵn có.

| # | Câu hỏi | Quyết định | Trạng thái |
|---|---------|--------------|------------|
| Q1 | 4 tham số gắn "(Bỏ)": *Target margin, % Value financed, Interest rate, Financing days* — thật sự loại khỏi công thức, hay chỉ ẩn khỏi màn hình chính? Lưu ý Target margin là gốc của mode MARGIN_INPUT | **Ẩn đi** (chỉ ẩn khỏi màn hình chính, giữ nguyên trong công thức) | ✅ Không cần sửa — đã đúng từ C3: `targetMarginPct` ở nhóm "basic" (Target margin là input hàng ngày), 3 tham số còn lại đã ở nhóm "policy" (thu gọn) trong `src/lib/cbu/ui/draft.ts` |
| Q2 | Cơ sở tính thuế: Excel dùng `Material + toàn bộ Logistics (gồm thông quan, nội địa, bảo hiểm)`. CIF thực tế chỉ gồm `hàng + cước quốc tế + bảo hiểm`. Giữ theo Excel? | **Theo CIF thực** (đổi khỏi mặc định tạm "Theo Excel") | ✅ Đã sửa 22/09: `dutyBase_i = material_i + freightShare_i + insuranceShare_i` thay vì `material_i + logistics_i` — `src/lib/cbu/profiles/ddp-import.ts`. Chỉ ảnh hưởng dòng có `dutyPct > 0` (AC0084 golden = 0 nên không đổi số vàng; test hồi quy F3 trong `ddp-import.golden.test.ts` đã cập nhật công thức kỳ vọng). Baker (`FCA_DAP`) không có Duty, không ảnh hưởng |
| Q3 | Cột K (phân bổ logistics/dòng) của sheet Margin Analysis trỏ vào cột **R = "Min insurance"** chứ không phải **S = "Insurance"**. Hai giá trị trùng nhau (15) trong file mẫu nên chưa lộ; khi phí bảo hiểm tính ra > mức tối thiểu, Excel sẽ sai. Xác nhận là lỗi công thức trong file gốc? | **Xác nhận LÀ LỖI** — kiểm chứng trực tiếp trên file `.xlsx` gốc 22/09/2026, xem SPEC §11.14 | ✅ Đã xác nhận. Không đổi code — engine đã dùng **S (Insurance tính ra, đúng)** từ trước |
| Q4 | Baker Hughes — phí *International receive*: nhãn 0.05% nhưng công thức 0.005%; Min $35 (Hoàng Sơn: $5); base = DAP revenue (rủi ro vòng lặp). Dùng số nào và có nhập tay base như DDP không? | **Nhập tay** (base) | ✅ Không cần sửa — đã đúng từ C4: `PROFILE_DEFAULTS.FCA_DAP.bank.minReceiveUsd = 35`, `receiveBaseUsd` mặc định 0 và là ô nhập trong `defaults.ts`/`draft.ts` |
| Q5 | Bỏ hẳn `bookingExchangeRate` và "Effective margin" (md ghi đã loại khỏi workbook)? | **Bỏ** khỏi UI/engine, giữ cột DB | ✅ Không cần sửa — đã bỏ khỏi engine/UI từ C3; `CbuParams` không có 2 trường này |
| Q6 | Mặc định Thông quan 150 / Nội địa 100 (schema hiện có, F4) là số của 1 lô mẫu — đặt về 0 và để trống bắt buộc nhập? | **0** | ✅ Không cần sửa — đã đúng từ C2: `CBU_DEFAULTS.logistics.clearanceUsd/inlandUsd = 0` trong `defaults.ts`, migration `20260921120000_cbu_v2` đổi default cột DB |
| Q7 | Baker Hughes — tỷ giá 25,500, hệ số lb→kg 0.46 và trọng lượng 43.2 lb đang hardcode trong công thức; dùng tham số chung (0.4536) và dữ liệu DB? | **Tham số chung** | ✅ Không cần sửa — đã đúng từ C4: Baker dùng `fx`/`lbToKg` chung, không hardcode (weight/duty/insurance vốn đã ẩn hoàn toàn ở Baker) |
| Q8 | Với RFQ đã `QUOTED_TO_CLIENT` có giá lệch do F1/F2: giữ nguyên giá đã báo, hay báo lại? | Ngoài phạm vi kỹ thuật — chờ quản lý PSBV | ⏳ Không có RFQ nào ở `QUOTED_TO_CLIENT` tính đến 21/09 (audit §6.4) nên chưa cấp bách; AC0005 (margin=0% bất thường) vẫn chờ Sale Admin xác nhận |

### 11.13 Định nghĩa "Xong" (Definition of Done)

- Golden test AC0084 (AIR/SEA/PRICE) và AC0481 pass; hồi quy F1–F4, F6 pass; `npm test` xanh toàn bộ; `npx tsc --noEmit` 0 lỗi; `npm run lint` không lỗi mới.
- Lưu → tải lại một RFQ cho **kết quả giống hệt**; API bỏ qua số client gửi.
- Chip "Đối soát" luôn ✓ trên dữ liệu mẫu; finalize bị chặn khi có check lỗi.
- `PROGRESS.md` §6 tích đủ; `CLAUDE.md` mô tả đúng vị trí engine.

### 11.14 Q3 — xác minh trực tiếp trên file Excel gốc (22/09/2026)

Đọc trực tiếp 4 file `.xlsx` trong `documents/CBU_docx/` (thư viện `xlsx`/SheetJS, đọc cả `f` là chuỗi công thức, không chỉ giá trị `v` đã tính sẵn):

- **Không có "named range" thật** theo nghĩa Excel Name Manager — `workbook.xml` của cả 4 file không có phần tử `<definedNames>`. "Named range" trong F-finding trước đây là cách gọi chưa chính xác cho một **mẫu công thức lặp lại**.
- Sheet `Logistic` (cả 2 file Hoàng Sơn — Margin Input và Price Input/CLEAN), dòng 5 (AIR)/dòng 6 (SEA): cột **R** = `"Min insurance (USD)"` (input, giá trị 15 — sàn tối thiểu); cột **S** = `"Insurance (USD)"`, công thức `=MAX((O+M)*P*Q, R)` (phí bảo hiểm tính ra, đã chặn sàn — **đúng**); cột **T** = `"Total Logistic + Insurance"`, công thức `=M+S` (**đúng**, dùng S).
- Sheet `Margin Analysis`, cột K (phân bổ logistics cho từng dòng hàng) — **toàn bộ 32 công thức** (16 dòng AIR tham chiếu `Logistic!$M$5+Logistic!$R$5`, 16 dòng SEA tham chiếu `Logistic!$M$6+Logistic!$R$6`) đều dùng **R**, **không dòng nào** dùng S hay T. Xác nhận bằng cách đếm: `useR: 32, useS: 0` trên cả 2 file Hoàng Sơn.
- Với dữ liệu mẫu AC0084: phí bảo hiểm tính ra thực tế = `(19,271.20+4,000)×1.1×0.0001 ≈ 2.56`, thấp hơn sàn 15 → `MAX(2.56, 15) = 15 = R`. R và S **trùng giá trị do trùng hợp** (nằm dưới sàn), không phải vì công thức đúng — che mất lỗi trong đúng bộ dữ liệu mẫu này, khớp giả thuyết ban đầu của Q3.
- **Kết luận: xác nhận đây là lỗi công thức thật trong file Excel gốc của PSBV** (không phải lỗi của bản `.md` chuyển đổi hay của việc đọc hiểu công thức) — nếu giá trị hàng đủ lớn để phí bảo hiểm tính ra vượt mức sàn, cột K (phân bổ cho từng dòng) trong Excel sẽ tính thiếu, trong khi ô tổng T ở sheet Logistic vẫn hiển thị đúng — hai nơi trong cùng workbook lệch nhau mà không cảnh báo.
- File Baker Hughes (2 file) không có mẫu công thức này (không có khái niệm insurance theo đúng thiết kế của profile `FCA_DAP`).
- **Không cần sửa code**: engine v2 (`src/lib/cbu/pools.ts` → `computeInsurance()`) đã tính đúng theo S (MAX-floored) ngay từ Phase C1, không lặp lại lỗi này. Chỉ cần ghi nhận để giải thích chênh lệch nếu ai đó đối chiếu số của engine với Excel gốc trong trường hợp bảo hiểm vượt sàn.

---

## 12. Dashboard Analytics — kế hoạch triển khai (Phase 2)

**Trạng thái (22/09/2026): v1 xong (A1–A6).** `/overview` giờ có biểu đồ xu hướng doanh thu/margin, phễu trạng thái, top khách hàng — dùng `recharts`, tầng gộp số thuần có test ở `src/lib/analytics/`. Theo dõi tiến độ: `PROGRESS.md` §7.

### 12.1 Hiện trạng đã kiểm chứng

Đọc trực tiếp code (không suy đoán):

- `src/app/(dashboard)/overview/page.tsx` (236 dòng) **không phải trang trống** — đã có: 4 thẻ KPI (Tổng đơn hàng, Tổng giá trị USD, Tổng lợi nhuận, Margin trung bình) tính từ `prisma.rFQ.findMany()` một lần; panel "Trạng thái Đơn hàng" đếm theo `status` với thanh tiến trình CSS tự vẽ (không dùng thư viện); bảng "Đơn hàng mới nhất" (10 RFQ gần nhất).
- **Chưa có thư viện vẽ biểu đồ nào** trong `package.json` (đã kiểm tra recharts/chart.js/victory/nivo/d3/apexcharts — không có gói nào).
- **Chưa có biểu đồ xu hướng theo thời gian** (mọi số hiện tại là snapshot hiện tại, không có "theo tháng").
- Trường dữ liệu đã có sẵn để dùng ngay (không cần đổi schema): `RFQ.status`, `totalRevenueUsd`, `totalMarginUsd`, `actualMarginPct`, `totalRevenueVnd` (BigInt), `createdAt`, `cbuCalculatedAt`, quan hệ `client`.
- **Không có theo dõi "thắng/thua" (won/lost)** ngoài 7 status hiện có — không thể dựng "tỷ lệ chốt đơn" thật (chuyển đổi Inquiry → Quoted) nếu không thêm field mới. **Không làm ở v1** (xem câu hỏi mở §12.6).

### 12.2 Mục tiêu v1

Mở rộng `/overview` hiện có (không tạo trang trùng lặp) với biểu đồ xu hướng, giữ nguyên 3 khối đã có (KPI, status, recent) làm nền — chỉ thay thanh CSS tự vẽ bằng chart thật và thêm 2 biểu đồ mới.

### 12.3 Kiến trúc

- **Thư viện chọn: `recharts`** — SVG-based, chạy tốt trong React Server/Client Component pattern của Next.js App Router đang dùng, nhẹ hơn Chart.js cho nhu cầu bar/line chart cơ bản, không cần canvas.
- **Tầng dữ liệu — hàm thuần, tách khỏi Prisma, có test** (theo đúng phong cách `src/lib/cbu/` — logic thuần tách khỏi I/O để test không cần DB):
  ```
  src/lib/analytics/
    aggregate.ts   # revenueByMonth(rfqs), statusBreakdown(rfqs), topClients(rfqs) — nhận mảng RFQ đã fetch, trả số đã gộp
    types.ts       # kiểu dữ liệu input/output của các hàm trên
  ```
- Trang `/overview` (Server Component) giữ nguyên **một** query `prisma.rFQ.findMany()` hiện có, truyền kết quả qua các hàm `aggregate.ts`, rồi render xuống các Client Component biểu đồ (`"use client"`, nhận props đã tính sẵn — không tự fetch, không tự tính).

### 12.4 Kế hoạch theo giai đoạn

- **A1 — Nền tảng dữ liệu:** cài `recharts`; viết `revenueByMonth()`, `statusBreakdown()`, `topClients()` (hàm thuần) + test đơn vị (không cần DB, đưa mảng RFQ giả vào).
- **A2 — Biểu đồ xu hướng doanh thu/margin:** bar hoặc line chart theo tháng (12 tháng gần nhất), đặt trên `/overview`.
- **A3 — Biểu đồ phễu trạng thái:** bar chart ngang qua `recharts`, giữ đúng 7 status và thứ tự lifecycle. *(Quyết định khi làm 22/09 — khác chút với câu chữ ban đầu "thay thanh CSS": danh sách trạng thái cũ **không bị xoá**, vì nó còn là điều hướng thật (bấm vào lọc `/rfq?status=...`) — xoá sẽ mất chức năng chỉ để đổi giao diện. Biểu đồ được **thêm** phía trên danh sách đó, cùng 1 card.)*
- **A4 — Top khách hàng:** bar chart hoặc bảng xếp hạng 5 khách hàng theo tổng doanh thu.
- **A5 — Test:** test đơn vị cho 3 hàm gộp số; test component (React Testing Library, theo đúng khuôn Sprint 3) cho các wrapper biểu đồ mới — kiểm tra render đúng dữ liệu, không kiểm tra pixel.
- **A6 — Tài liệu:** cập nhật `PROGRESS.md` §7, `CLAUDE.md` khi từng giai đoạn xong.

### 12.5 Định nghĩa "Xong" (v1)

- `/overview` có: KPI cards (giữ nguyên) + biểu đồ xu hướng doanh thu/margin theo tháng + biểu đồ trạng thái + top khách hàng.
- 3 hàm gộp số trong `src/lib/analytics/aggregate.ts` có test đơn vị, không phụ thuộc DB.
- `npx tsc --noEmit` 0 lỗi, `npm run lint` không thêm cảnh báo, `npm test` xanh toàn bộ (bao gồm test mới).
- Không đổi `prisma/schema.prisma` — v1 chỉ đọc, không thêm cột/bảng.

### 12.6 Câu hỏi mở (không chặn v1, để mặc định nêu trong ngoặc)

| # | Câu hỏi | Mặc định tạm |
|---|---------|---------------|
| D1 | Có cần bộ lọc khoảng thời gian (date range picker) không, hay cố định 12 tháng gần nhất? | Cố định 12 tháng, chưa có UI lọc |
| D2 | Có cần theo dõi "thắng/thua" (RFQ bị huỷ/khách từ chối) để tính tỷ lệ chốt đơn thật không — sẽ cần thêm field/status mới? | Chưa làm — ngoài phạm vi v1 |
| D3 | Hiển thị doanh thu bằng USD, VND, hay cả hai? | USD (khớp field đã tổng hợp sẵn `totalRevenueUsd`) |

---

## 13. Email Review Agent — kế hoạch triển khai (Phase 2)

**Trạng thái (22/09/2026): v1 xong (E1–E5).** Trang gửi Quotation (`quote-preview`) giờ tự soạn nháp subject/body bằng Gemini dựa trên dữ liệu RFQ thật (RFQ code, Incoterm, Payment Term, số dòng hàng), có nút soạn lại, con người luôn xem/sửa/duyệt trước khi gửi qua route thật (`send-quote`, không đổi). Theo dõi tiến độ: `PROGRESS.md` §8.

### 13.1 Hiện trạng đã kiểm chứng

Đọc trực tiếp code (không suy đoán):

- `POST /api/agent` (`src/app/api/agent/route.ts`, 64 dòng) — tự ghi chú "This is a placeholder for the actual AI Agent endpoint". Nhận `{prompt}`, **bỏ qua hoàn toàn**, trả cứng một `toolCalls` mẫu (`prepare_email_dispatch` với dữ liệu giả `AC0485`/`client@example.com`/`mock-pdf-url.pdf`) — không gọi AI thật, không có logic thật.
- `src/components/agent/email-review-card.tsx` (239 dòng) — **component đã dựng đầy đủ UI** (form To/CC/BCC/Người gửi/Subject/Body HTML + xem trước PDF trực tiếp + nút "DUYỆT & BẮN MAIL MS GRAPH" gọi thẳng `/api/rfq/send-dispatch` — route thật, đã dùng MS Graph). **Nhưng không có nơi nào trong `src/` import/render component này** — hoàn toàn mồ côi, không ai dùng được. Nội dung To/Subject/Body của nó phải được truyền từ ngoài vào qua props (`initialTo`, `initialSubject`, `initialBody`) — hiện không có gì truyền vào vì không ai render nó.
- **Kết luận: tính năng "Email Review Agent" hiện KHÔNG tồn tại ở bất kỳ hình thức nào người dùng chạm tới được** — không phải "đã xây rồi chỉ cần nối dây", mà là hai mảnh rời rạc (route mock + component mồ côi) chưa từng được ráp lại, cộng thêm chưa có logic AI thật ở đâu cả.
- Luồng gửi email thật đang dùng hôm nay (đã qua Sprint 2, dùng MS Graph): `send-quote` (gửi Quotation), `send-rfo` (gửi RFO hãng), `send-dispatch` (gửi chung) — cả 3 đều nhận nội dung **gõ tay/điền sẵn tĩnh** (xem `quick-email-modal.tsx`'s `EMAIL_ACTIONS` — subject/body mẫu cố định, không có AI soạn).

### 13.2 Phạm vi v1 — quyết định thiết kế

Tên "Email Review Agent (human-in-the-loop)" trong roadmap gốc (SPEC §10) đã tự giới hạn phạm vi: **agent không bao giờ tự gửi email** — chỉ soạn nháp, con người (Sale Admin) xem/sửa/duyệt trước khi bấm gửi. Đây vừa là yêu cầu nghiệp vụ (an toàn, tránh AI gửi nhầm cho khách) vừa khớp đúng tên gọi đã ghi trong roadmap từ trước — không phải quyết định tự đặt ra.

**v1 chỉ làm MỘT việc cụ thể** (không dựng khung "nhiều tool" như mock cũ — hiện chỉ có đúng 1 ca dùng thật, dựng khung tổng quát cho 1 người gọi là thừa trừu tượng): khi RFQ ở trạng thái `QUOTATION_DRAFTED` và Sale Admin chuẩn bị gửi báo giá cho khách, agent dùng Gemini (đã có sẵn `GOOGLE_GEMINI_API_KEY`/`@google/generative-ai`, không thêm nhà cung cấp AI mới) soạn nháp subject + body tiếng Việt/Anh dựa trên dữ liệu RFQ thật (mã đơn, tên khách, số dòng hàng, tổng tiền, điều khoản thanh toán) thay vì template tĩnh hiện tại — hiển thị trong `EmailReviewCard` (component có sẵn, chỉ cần nối dây) để Sale Admin sửa rồi bấm gửi qua route thật đã có (`send-quote`).

**Không làm ở v1** (có thể mở rộng sau, xem §13.6): soạn nháp RFO cho hãng, đa-tool orchestration, tự động gửi không cần duyệt, theo dõi/nhắc follow-up.

### 13.3 Kiến trúc

```
src/lib/agent/
  draft-quotation-email.ts   # draftQuotationEmailWithGemini(context) → { subject, bodyHtml } sau khi validate qua Zod
src/lib/schemas/
  agent.schemas.ts           # draftQuotationEmailOutputSchema — validate JSON Gemini trả về (theo đúng khuôn gemini.schemas.ts của Sprint 2)
src/app/api/rfq/[id]/agent/draft-quotation-email/route.ts   # POST — auth + rate-limit (dùng lại src/lib/rate-limit.ts), CHỈ đọc DB + gọi Gemini, KHÔNG gửi email, KHÔNG ghi DB
```

- Route mới **không** thay thế `send-quote` — nó chỉ trả về `{subject, bodyHtml}` để điền sẵn vào `EmailReviewCard`; việc gửi thật vẫn qua `send-quote` như hiện tại, không đổi.
- Áp dụng lại đúng khuôn bảo mật/validate đã có: `getServerSession` bắt buộc, `validateBody`/Zod cho input, rate-limit như 7 route gọi Gemini khác (Sprint 0), output Gemini luôn qua Zod trước khi trả về client (không tin thẳng JSON AI trả — bài học từ Sprint 2's `gemini.schemas.ts`).
- Xoá `POST /api/agent` (mock) sau khi route thật lên — theo đúng convention dọn code chết của dự án (đã làm với `cbu-form.tsx`, trang CBU legacy…).

### 13.4 Kế hoạch theo giai đoạn

- **E1 — Hàm soạn nháp + schema + test:** `draftQuotationEmailWithGemini()`, `agent.schemas.ts`; test với Gemini client giả lập (mock `@google/generative-ai`, không gọi mạng thật) — theo đúng khuôn `__tests__/schemas/gemini.schemas.test.ts`.
- **E2 — API route:** `POST /api/rfq/[id]/agent/draft-quotation-email`; test tích hợp (mock Gemini + mock Prisma, gọi thẳng route handler) theo đúng khuôn Sprint 3 (`__tests__/api/*.route.test.ts`).
- **E3 — Nối dây UI:** đọc kỹ trang gửi báo giá hiện tại (`quote-preview/page.tsx` hoặc nơi tương đương — cần đọc lại khi bắt tay vào E3, chưa giả định trước) để thay luồng gõ tay hiện tại bằng: gọi route E2 lấy nháp → render `EmailReviewCard` với nháp đó → Sale Admin sửa/duyệt → gửi qua `send-quote` (không đổi route gửi).
- **E4 — Dọn dẹp:** xoá `src/app/api/agent/route.ts` (mock) sau khi E3 chạy ổn.
- **E5 — Test + tài liệu:** cập nhật `PROGRESS.md` §8, `CLAUDE.md`.

### 13.5 Định nghĩa "Xong" (v1)

- Sale Admin mở luồng gửi Quotation, thấy nháp subject/body do Gemini soạn (không phải template tĩnh), sửa được, bấm gửi thật qua MS Graph — không có bước nào AI tự gửi mà không qua con người.
- `POST /api/agent` (mock cũ) đã xoá, không còn code chết.
- Output Gemini luôn qua Zod trước khi hiển thị (không tin thẳng).
- `npx tsc --noEmit` 0 lỗi, test mới xanh, không giảm số test hiện có.

### 13.6 Câu hỏi mở / mở rộng tương lai (không chặn v1)

| # | Câu hỏi | Mặc định tạm |
|---|---------|---------------|
| M1 | Có soạn nháp luôn cho RFO gửi hãng (không chỉ Quotation gửi khách) không? | Chưa làm ở v1 — chỉ Quotation |
| M2 | Ngôn ngữ nháp: tiếng Việt, tiếng Anh, hay theo khách hàng? | Theo đúng ngôn ngữ template tĩnh hiện có cho từng loại (khớp `quick-email-modal.tsx`), Sale Admin tự sửa nếu cần |
| M3 | Có cache/tái dùng nháp đã soạn, hay soạn lại mỗi lần bấm? | Soạn lại mỗi lần — đơn giản, khối lượng RFQ hiện còn nhỏ, chưa cần cache |
| M4 | Phase 3 roadmap ("Full AI Agent orchestration", "Automated follow-up emails") có phụ thuộc vào kiến trúc v1 này không? | Chưa thiết kế — v1 cố tình đơn giản (1 hàm, 1 route), không dựng khung tổng quát trước khi có ca dùng thứ 2 thật sự cần nó |

<!-- END:SPEC.webapp.md -->
