# PROGRESS – Nhật ký công việc

## 2026-10-08 – Task 11: Giai đoạn 4 – DevOps & Observability (ruff/mypy + Docker)

### Đã làm

**4.1 Quản lý code**

- `pyproject.toml` trước đây rỗng (0 byte) → viết đầy đủ: dependencies thật (fastapi, sqlalchemy, psycopg3, talon, supabase…), `[dependency-groups] dev` (ruff/mypy/types-requests), cấu hình `[tool.ruff]` + `[tool.mypy]`.
- Cài `ruff`, `mypy`, `types-requests` (bỏ `types-python-dotenv` — không tồn tại trên registry).
- `ruff check --fix .`: autofix 125 lỗi (import sort, whitespace, `Optional` → `| None`, `timezone.utc` → `UTC`, unused imports).
- Sửa tay 8 lỗi còn lại: `raise ... from e` (B904 ×5), bỏ biến không dùng (F841 ×2), import lên đầu file (E402).
- Khôi phục `import app.db.models` trong `alembic/env.py` bằng `# noqa: F401` — cần cho autogenerate.
- Thêm `explicit_package_bases = true` + `mypy_path = "."` (project không có `__init__.py`).

**4.2 Đóng gói**

- `Dockerfile` (python:3.12-slim + uv, cài deps trước để cache layer), `docker-compose.yml` (backend + frontend, healthcheck, volume `storage/`), `.dockerignore`, `frontend/Dockerfile` (multi-stage, Next standalone), `frontend/.dockerignore`.
- `frontend/next.config.ts`: thêm `output: "standalone"`.
- `deploy.sh` — rsync + docker compose up + healthcheck cho VPS Ubuntu 24.04 (không push `.env` qua git).
- `README.md`, `.gitignore` (chặn `.env`, `.venv`, `node_modules`, `storage/`, `*.bot`).

### Bug tìm được khi chạy thật trong Docker

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| `ImportError: cannot import name 'joblib' from 'sklearn.externals'` trong container, **local thì OK** | Cùng `talon==1.4.4` nhưng PyPI trả 2 wheel khác nội dung: bản trong container dùng `from sklearn.externals import joblib` (API đã xoá từ sklearn 0.23) | Shim `sklearn.externals.joblib` phải set **trước** `from talon import ...` (file cũ đặt sau → không hiệu lực) |
| `alembic upgrade head` fail → container không start | DB tạm không kết nối được | `CMD: "alembic upgrade head \|\| echo warn; exec uvicorn ..."` — không chặn start |

### Kết quả kiểm thử

```
ruff check .    → All checks passed!
mypy app        → Success: no issues found in 21 source files
docker compose config   → valid
docker compose build    → backend 1.34GB + frontend, cả hai Built
docker compose ps:
  email-agent-backend   Up (healthy)      0.0.0.0:8000->8000
  email-agent-frontend  Up                0.0.0.0:3000->3000
GET http://127.0.0.1:8000/                 → 200 {"status":"ok"}
GET http://127.0.0.1:8000/api/ingestion/status → running:true, within_active_window:true
GET http://127.0.0.1:3000/                 → 200
```

### ⚠️ Vướng còn lại (ngoài code)

Supabase **pooler TCP (5432/6543) timeout** từ cả host lẫn container, trong khi `SUPABASE_URL/rest` trả `200`. Tức là REST API sống nhưng connection Postgres bị chặn ở tầng mạng (firewall/tạm thời bảo trì pooler). Đây không phải lỗi Docker/code — worker sẽ tự gom email tồn đọng và xử lý bình thường khi DB kết nối lại (`last_error` trong `/api/ingestion/status` sẽ tự xóa).

### Còn lại để tick `[x]` cuối cùng của Giai đoạn 4

Deploy thật lên VPS: chạy `VPS_HOST=<ip> ./deploy.sh`.

---

## 2026-10-07 – Task 10: Bỏ lưu ảnh inline (logo/chữ ký) & preview đa định dạng (docx/xlsx)

### Vấn đề

1. Ảnh inline (logo công ty, banner chữ ký, ảnh chèn body) bị lưu vào DB + Storage → tốn chi phí lưu trữ, tính toán xử lý mà không phục vụ nghiệp vụ.
2. Preview đính kèm chỉ hỗ trợ PDF/ảnh — email gửi docx/xlsx/pptx (phổ biến ở mảng PO/Quote) không xem được trực tiếp.

### Đã làm

1. **Pipeline bỏ ảnh inline**: `email_processing_pipeline.py` — `is_inline` + mime `image/*` → skip hoàn toàn (không tải, không upload, không lưu DB). `process_status` cho docx, xlsx, pptx, doc, xls giờ là `pending_extraction` (trước chỉ pdf + docx).
2. **Cài thư viện đọc office**: `uv pip install python-docx openpyxl`.
3. **Endpoint preview mới**: `GET /api/emails/attachments/{id}/preview` — trích đoạn đầu (xlsx: 20 dòng, docx: 15 paragraph + bảng) thành JSON bảng cho UI.
4. **Frontend `AttachmentViewer`**: renderer theo loại file — PDF → iframe, ảnh → `<img>`, docx/xlsx/doc/xls/pptx → bảng từ preview API, còn lại nút tải.

### Kết quả kiểm thử

```
xlsx extractor: [['Ten','So luong','Don gia'...], ['Don ho','10','150'...]] ✓
docx extractor: [['Phieu bao gia so 001'], ['San pham: Dong ho ca 5R x 10']] ✓
frontend build → ✓ Compiled successfully
```

⚠️ **Chưa chạy**: xóa các ảnh inline đã lưu trong DB/Storage từ trước — cần bạn xác nhận trước khi tôi thực hiện (xóa dữ liệu thật).

---## 2026-10-07 – Task 9: Kiểm tra kết nối DB & luồng hoạt động hệ thống (Giai đoạn 5.2 – task cuối)

### Kiểm tra đã thực hiện

| # | Thành phần | Kết quả |
|---|---|---|
| 1 | SQLAlchemy → Supabase PostgreSQL | ✅ Kết nối OK (PostgreSQL 17.11) |
| 2 | Supabase REST API (service role) | ✅ OK, đếm đúng 30 email |
| 3 | Tan dữ liệu | ✅ Mailboxes=1, Contacts=13, Emails=30, Attachments=69, Summaries=30 |
| 4 | MS Graph token (client credentials) | ✅ Token 2158 ký tự |
| 5 | `MSGraphService.list_emails(7d)` | ✅ Lấy email Inbox OK |
| 6 | Import `EmailPipeline` | ✅ Sẵn sàng xử lý |
| 7 | Webhook `POST /api/webhooks/outlook` — validation | ✅ Echo `validationToken` 200 |
| 8 | Webhook — payload notification (message_id giả) | ✅ 202 Accepted, vào background task, pipeline gọi Graph và fail đúng kỳ vọng (`ErrorInvalidIdMalformed` với id giả — ID thật hoạt động) |
| 9 | `GET /api/emails` | ✅ 200, total=30 |

### Kết luận

✅ **Toàn bộ luồng hệ thống hoạt động:** Webhook → BackgroundTask → `EmailPipeline` (Graph API → tiền xử lý → Gemini → PostgreSQL) → API đọc → Frontend hiển thị. Database kết nối ổn định cả qua SQLAlchemy lẫn Supabase REST.

---## 2026-10-07 – Task 8: Giải quyết luồng email dài (Giai đoạn 5.2)

### Phân tích vấn đề (từ dữ liệu thật trong DB)

- Outlook gửi reply chứa **toàn bộ lịch sử thread** trong body (một email 56KB có 6 lần lặp `From: ... Sent: ...`); talon `quotations` chỉ cắt quote kiểu plain-text, **không cắt được header block của Outlook** → `body_clean` bị trộn lịch sử, AI tóm tắt kém chính xác.
- DB gom thread tốt qua `thread_id` = `conversationId` (thread dài nhất 7 email), nhưng UI chỉ hiện 1 email lẻ.

### Giải pháp đã triển khai

1. **Cắt quote ở tiền xử lý** — thêm `_strip_outlook_quotes()` vào `app/utils/email_preprocessing.py`: cắt tại delimiter Outlook (`From:`/`Sent:` block), `-----Original Message-----`, `On ... wrote:`. Chỉ giữ nội dung mới nhất.
2. **API lịch sử thread** — thêm `GET /api/emails/{id}/thread` trả list các email cùng `thread_id`, sắp xếp theo `sent_at` tăng dần.
3. **UI** — thêm component `ThreadHistory` vào trang chi tiết: timeline đánh số #1..#n, email hiện tại highlight xanh, click để expand xem tóm tắt + `body_clean`.
4. **Backfill** 30 email cũ trong DB: cắt lại `body_clean` offline (không gọi LLM), cập nhật 20 email.

### Kết quả kiểm thử

```
Hiệu quả cắt quote trên 30 email thật:
  HTML in: 891.370 → body_clean: 25.773 (2.9%)
GET /api/emails/{id}/thread → 200, 7 items đúng thứ tự sent_at
Build frontend              → ✓ Compiled successfully
```
✅ **Email dài: mỗi email giờ chỉ giữ nội dung mới nhất; UI hiển thị đầy đủ lịch sử hội thoại.**

---## 2026-10-07 – Task 7: Test 30 email / 7 ngày từ Outlook (Giai đoạn 5.3)

### Những gì đã làm

- Thêm `list_emails(days, top)` vào `MSGraphService` — lấy email từ Inbox sắp xếp mới nhất trước, filter theo `receivedDateTime` ở Python (tránh lỗi `$filter` Graph)
- Tạo `app/tests/test_bulk_30_emails.py` — chạy: `python -X utf8 -m app.tests.test_bulk_30_emails 30 7`
- Nối Frontend inbox (`frontend/app/page.tsx`) từ `MOCK_EMAILS` sang API thật `GET /api/emails` (server component, `cache: no-store`)

### Lỗi gặp phải & cách fix

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| `GEMINI_API_KEY` invalid | `.env` còn placeholder `your_...` | Người dùng điền key thật vào `.env` |
| `models/gemini-1.5-pro is not found` (404) | API model cũ đã ngừng, key mới mới có nhưng model lỗi thời | Đổi sang `gemini-2.5-flash` trong `email_analyzer_agent.py` + `pipeline` |
| `inReplyTo` trong `$select` → 400 | Thuộc tính này không có trên type Message của Graph | Bỏ khỏi `$select` |
| Talon `AttributeError: NDArrayWrapper.ndim` | Classifier model cũ không tương thích sklearn ≥1.x | Bọc `_safe_signature_extract()` try/except — log warning, giữ nguyên body |

### Kết quả kiểm thử

```
Bulk 30 email / 7 ngay:
  Moi lay       : 30
  Xu ly thanh cong: 29
  Bi loi        : 0
  Bo qua (trung): 1
DB:
  emails=30, summaries=30, attachments=69
  emails_with_files=12, cc=27, thread_id=30
GET /api/emails     → 200 (total: 30)
GET /api/emails/{id}→ 200 (contact, cc, message_id, thread_id ✓)
frontend build      → ✓ Compiled successfully
```
✅ **Giai đoạn 5.3 đạt: 30 email hiển thị đầy đủ, chính xác trên giao diện.**

---## 2026-10-07 – Task 5: Cải tiến Giao diện trang chi tiết email (Giai đoạn 5.1)

### Những gì đã làm

- **Backend – bổ sung dữ liệu cho UI:**
  - `app/db/models.py`: thêm 2 cột `cc_emails`, `bcc_emails` (JSONB) vào bảng `emails`
  - Tạo migration `20261007_0833_6d315b108c0c_add_cc_bcc_to_emails.py` và chạy `alembic upgrade head` thành công
  - `app/services/email_processing_pipeline.py`: trích `ccRecipients`/`bccRecipients` từ MS Graph và lưu vào DB; lưu thêm `thread_id` (dùng `conversationId`), `in_reply_to`; fallback `received_at` khi thiếu `createdDateTime`
  - `app/api/emails_render.py`:
    - Response `GET /api/emails/{id}` trả đủ theo SPEC: `id_mailbox`, `id_sender`, `cc/bcc`, `is_internal`, `is_known_customer`, `message_id`, `thread_id`, `in_reply_to`, `content_summarized`, `is_inline`
    - **Thêm endpoint mới** `GET /api/emails/attachments/{id}` — đọc file từ storage trả `inline` để UI preview trực tiếp (PDF/image)
    - Sửa `LabelAssignRequest.label_id: int` → `str` (theo `label_name` khớp frontend)
- **Frontend – `frontend/app/emails/[id]/page.tsx` viết lại hoàn toàn:**
  - Bỏ mock data → fetch `GET /api/emails/{id}` thật (Next 16: `params` là Promise, unwrap bằng `use()`)
  - Layout đúng 70% nội dung / 30% sidebar (`xl:col-span-8` / `xl:col-span-4`)
  - Nội dung chính hiển thị đúng thứ tự 4 phần theo SPEC:
    1. Định danh email: `id_email`, tiêu đề, `id_mailbox`
    2. Thông tin người gửi: name, `id_sender`, email, cc, bcc, phone, company, `is_internal`, `is_known_customer`
    3. Nội dung email: `message_id`, `thread_id`, `in_reply_to`, `body_clean`, `content_summarized`, `received_at`, `has_attachments`
    4. Thông tin file đính kèm (7 field) — phía dưới là preview file inline (PDF iframe / ảnh / nút tải)
  - Sidebar: HITL gán nhãn nối vào `POST /api/emails/{id}/labels` (nhận `label_name`), AI summary (tldr, action items, cảnh báo bảo mật, sentiment)
  - Các field ẩn trong DB vẫn lưu bình thường, không hiển thị (theo yêu cầu)

### Lỗi gặp phải & cách fix

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| `label_info` / `sender_contact` không tồn tại trên model | Tên relationship trong API cũ khác model (`label`, `sender`) | Đổi lại đúng tên relationship |
| Frontend build lỗi TS2339 `is_inline` không có | Response API cũ thiếu `is_inline` | Thêm vào response attachments |
| Migration rỗng (`pass`) | `alembic revision` không autogenerate | Viết tay `op.add_column` JSONB |

### Kết quả kiểm thử

```
frontend: npm run build → ✓ Compiled successfully, TypeScript OK
backend : python -c "import app.main" → OK (FastAPI 0.145 lazy router)
alembic  : upgrade 9bd05ff0fa81 -> 6d315b108c0c thành công
```
✅ **UI mới build pass, API trả đủ field theo SPEC.**

---

## 2026-10-07 – Task 6: Fix lỗi backend pipeline (Giai đoạn 5.2 – Lỗi `sender_email`)

### Vấn đề gặp phải

```
ERROR: ❌ Transaction Database bị hủy do lỗi: extract() got an unexpected keyword argument 'sender_email'
ERROR: ❌ Lỗi luồng process_new_email: extract() got an unexpected keyword argument 'sender_email'
```
→ Mọi email mới từ webhook đều chết ở bước tiền xử lý, không email nào vào được DB.

### Lỗi gặp phải & cách fix

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| `extract() got an unexpected keyword argument 'sender_email'` | talon `signature.extract(body, sender)` nhận tham số vị trí, code gọi `sender_email=` keyword | `signature.extract(text_no_quotes, sender_email)` (vị trí) |
| Key trả về `"body-full_text"` (gạch ngang) | Lỗi chính tả, pipeline đọc `"body_full_text"` → KeyError ngay sau khi fix talon | Đổi key thành `"body_full_text"` |
| `ai_result.label_prediction` không tồn tại | `EmailAnalysisResult` không có field này → AttributeError | Thêm class `LabelPrediction` + field `label_prediction` (default) vào `EmailAnalysisResult` |

### Thay đổi code đã thực hiện

| File | Thay đổi |
|---|---|
| `app/utils/email_preprocessing.py` | Fix ký gọi `signature.extract`; sửa key `body_full_text` |
| `app/services/email_analyzer_agent.py` | Thêm `LabelPrediction` model, field `label_prediction` |
| `app/services/email_processing_pipeline.py` | Đọc đúng key; thêm `thread_id`/`in_reply_to`/`cc`/`bcc` |

### Kết quả kiểm thử

```
EmailPreprocessor.process(...) → keys: body_clean, body_full_text, extracted_links, extracted_phones, signature ✓
EmailAnalysisResult → có label_prediction mặc định ✓
import app.main → OK ✓
```
✅ **Luồng pipeline không còn crash ở bước tiền xử lý.**

---

## 2026-10-07 – Cập nhật SPEC.md & tạo CLAUDE.md

- Tick checkbox **hoàn thành Giai đoạn 1, 2, 3** trong `SPEC.md` (Giai đoạn 4 giữ nguyên chưa tick; Giai đoạn 5 là việc đang làm)
- Tạo `CLAUDE.md`: tổng quan kiến trúc, cấu trúc thư mục, lệnh chạy, lưu ý quan trọng (lỗi talon, encoding Windows, driver psycopg3, frontend mock), checklist Giai đoạn 5

---

## 2026-10-05 – Task 1: Test kết nối Supabase

- Khảo sát repo: chỉ có `README.md`, chưa có file `test_db` hay credentials.
- Tạo `test_db.py` (stdlib, đọc `.env`, kiểm tra kết nối + đọc thử bảng).
- Tạo `.env.example`, `.gitignore`, `SPEC.md`, `PROGRESS.md`.
- Chạy: chưa kiểm thử được kết nối thật vì chưa có `SUPABASE_URL`/`SUPABASE_KEY`.

---

## 2026-10-06 – Task 2: Fix lỗi kết nối Database & Supabase

### Vấn đề gặp phải

#### Lỗi 1: `SUPABASE_SERVICE_ROLE_KEY` – Field required
- **Nguyên nhân:** `config.py` khai báo `SUPABASE_SERVICE_ROLE_KEY: str` là bắt buộc, nhưng `.env` lúc đó chưa có key này.
- **Giải pháp:** Xác nhận `.env` đã có đủ 3 biến Supabase: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`.

#### Lỗi 2: `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_REDIRECT_URI`, `GEMINI_API_KEY` – Field required
- **Nguyên nhân:** Người dùng đổi các field này từ có giá trị mặc định `""` sang bắt buộc trong `config.py`, nhưng `.env` chỉ có placeholder (`your_azure_client_id`, v.v.).
- **Giải pháp:** Giữ nguyên placeholder trong `.env`; các field này sẽ cần giá trị thật khi tích hợp Microsoft OAuth và Gemini API.

#### Lỗi 3: `ImportError: no pq wrapper available` (psycopg3 thiếu binary)
- **Nguyên nhân:** Venv chỉ cài `psycopg` (v3 thuần Python), thiếu `libpq` hoặc binary wrapper. Lệnh `pip install` trước đó cài nhầm vào Python system thay vì venv.
- **Giải pháp:** Cài `psycopg[binary]` đúng vào venv bằng `uv pip install "psycopg[binary]"`.

#### Lỗi 4: `ModuleNotFoundError: No module named 'psycopg2'`
- **Nguyên nhân:** `DATABASE_URL` dùng scheme `postgresql://` nên SQLAlchemy tự chọn driver `psycopg2` (v2), nhưng venv chỉ có `psycopg` (v3).
- **Giải pháp:** Sửa `app/db/base.py` để tự động đổi scheme sang `postgresql+psycopg://` trước khi truyền vào `create_engine`.

#### Lỗi 5: `UnicodeEncodeError` khi in tiếng Việt ra terminal
- **Nguyên nhân:** Terminal Windows dùng encoding `cp1258`, không hỗ trợ một số ký tự tiếng Việt.
- **Giải pháp:** Chạy Python với flag `-X utf8`: `python -X utf8 -m app.tests.test_db`.

### Thay đổi code đã thực hiện

| File | Thay đổi |
|---|---|
| `app/core/config.py` | Đổi `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_REDIRECT_URI`, `GEMINI_API_KEY` thành bắt buộc (không có default) |
| `app/db/base.py` | Xóa import trùng `settings`; thêm logic tự động đổi scheme `postgresql://` → `postgresql+psycopg://` để dùng psycopg3 |

### Packages đã cài vào venv

```
uv pip install "psycopg[binary]"   # psycopg3 + libpq binary (3.3.6)
```

### Kết quả kiểm thử

```
Tiến hành kiểm tra hệ thống...
✅ [OK] Kết nối SQLAlchemy (PostgreSQL IPv4) thành công!
✅ [OK] Kết nối Supabase API (Service Role) thành công!
```

### Lưu ý vận hành

- Luôn kích hoạt venv trước khi chạy: `.venv\Scripts\Activate.ps1`
- Dùng `python -X utf8` để tránh lỗi encoding tiếng Việt trên terminal Windows
- `DATABASE_URL` phải dùng scheme `postgresql://` hoặc `postgres://` trong `.env` — code sẽ tự đổi sang `postgresql+psycopg://`

---

## 2026-10-06 – Task 3: Tạo Database Schema & Alembic Migration

### Những gì đã làm

- Thiết kế ERD schema đầy đủ cho Phase 1 (file `app/db/database_schema.md` + `email_agent_phase1.mmd`)
- Viết `app/db/models.py` với 8 SQLAlchemy models: `Mailbox`, `Contact`, `Email`, `Label`, `EmailLabel`, `Attachment`, `EmailSummary`, `EmailCard`
- Cập nhật `alembic/env.py` để import models và override `DATABASE_URL` từ `.env`

### Lỗi gặp phải & cách fix

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| `No 'script_location' key found` | `alembic.ini` rỗng hoàn toàn (0 bytes) | Viết lại `alembic.ini` đúng chuẩn |
| `UnicodeDecodeError` khi đọc `alembic.ini` | File có comment UTF-8, terminal dùng `cp1258` | Dùng ASCII thuần trong `alembic.ini` |
| `Mailbox(base)` | Chữ `base` thường thay vì `Base` | Sửa thành `Mailbox(Base)` |
| `__tablename__ = "mailbox":` | Dấu `:` thừa + tên bảng sai | Sửa thành `"mailboxes"` (khớp ForeignKey) |
| `target_metadata` chưa gán trong `run_migrations_online()` | Thiếu dòng assignment | Thêm `target_metadata = Base.metadata` |
| `ModuleNotFoundError: No module named 'app'` | `PYTHONPATH` không bao gồm project root | Set `PYTHONPATH=e:\AI_LEARNING\email-agent` khi chạy alembic |

### Thay đổi code đã thực hiện

| File | Thay đổi |
|---|---|
| `alembic.ini` | Viết lại từ đầu (file bị rỗng), ASCII-only |
| `alembic/env.py` | Thêm `import app.db.models`, gán `target_metadata`, override DB URL từ env |
| `app/db/models.py` | Fix `Mailbox(base)` → `Mailbox(Base)`, fix `"mailbox":` → `"mailboxes"` |

### Kết quả

```
INFO  [alembic.autogenerate] Detected added table 'contacts'
INFO  [alembic.autogenerate] Detected added table 'labels'
INFO  [alembic.autogenerate] Detected added table 'mailboxes'
INFO  [alembic.autogenerate] Detected added table 'emails'
INFO  [alembic.autogenerate] Detected added table 'attachments'
INFO  [alembic.autogenerate] Detected added table 'email_cards'
INFO  [alembic.autogenerate] Detected added table 'email_labels'
INFO  [alembic.autogenerate] Detected added table 'email_summaries'
INFO  [alembic.runtime.migration] Running upgrade -> init_schema
```
✅ **8 bảng đã được tạo thành công trên Supabase.**

### Lệnh chuẩn để chạy Alembic

```powershell
# Tạo migration mới
$env:PYTHONPATH="e:\AI_LEARNING\email-agent"; alembic revision --autogenerate -m "ten_migration"

# Apply lên DB
$env:PYTHONPATH="e:\AI_LEARNING\email-agent"; alembic upgrade head
```

---

## 2026-10-06 – Task 4: Xây dựng MSGraphService & Test gửi mail

### Những gì đã làm

- Tạo `services/ms_graph.py`: class `MSGraphService` dùng MSAL để lấy OAuth2 token (client_credentials) và gọi Microsoft Graph API
- Thêm `MS_TARGET_MAILBOX` vào `config.py` và `.env`
- Tạo `app/tests/test_msgraph.py` để kiểm thử lấy token + gửi mail

### Lỗi gặp phải & cách fix

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| `'Settings' object has no attribute 'MS_TARGET_MAILBOX'` | `config.py` chưa có field (diff chưa được lưu) | Thêm `MS_TARGET_MAILBOX: str` vào class `Settings` |
| `settings.MS_TARGET_MAILBOX` dùng làm default param gây lỗi load | Python evaluate default param tại class definition time, trước khi settings đầy đủ | Đổi sang `None` default + resolve bên trong hàm |
| `OIDC Discovery failed` – authority URL sai | `MS_TENANT_ID` trong `.env` chứa toàn bộ OAuth URL thay vì chỉ GUID | Sửa `.env`: `MS_TENANT_ID=<guid>` (chỉ GUID, không có URL) |
| `authority` bị double-prefix | Code build `authority = f"{tenant_id}"` nhưng tenant_id đã là URL đầy đủ | Fix code: `authority = f"https://login.microsoftonline.com/{tenant_id}"` |
| Import path conflict tạo 2 `settings` instance | Test import `services.ms_graph`, trong khi ms_graph import `app.core.config` → 2 module path khác nhau | Thêm `sys.path.insert(0, project_root)` vào đầu `ms_graph.py` |

### Thay đổi code đã thực hiện

| File | Thay đổi |
|---|---|
| `app/core/config.py` | Thêm `MS_TARGET_MAILBOX: str`, đổi `MS_TENANT_ID` thành bắt buộc (bỏ default `"common"`) |
| `.env` | Sửa `MS_TENANT_ID` thành Tenant GUID thuần; thêm `MS_TARGET_MAILBOX=drilling@psbvn.com` |
| `services/ms_graph.py` | Fix authority URL; đổi default params từ `settings.X` sang `None`; thêm `sys.path` fix |
| `app/tests/test_msgraph.py` | Thêm `from app.core.config import settings` để đồng nhất module context |

### Kết quả kiểm thử

```
1. Dang test lay Token...
✅ Da lay duoc token (do dai: 2158 ky tu)

2. Dang test Gui Mail tu drilling@psbvn.com toi YOUR_PERSONAL_EMAIL@domain.com...
✅ Gui mail thanh cong!

3. Dang test Doc Mail...
Tam thoi ham doc mail da san sang cau truc.
```
✅ **Token lấy thành công, gửi mail qua MS Graph API thành công.**

