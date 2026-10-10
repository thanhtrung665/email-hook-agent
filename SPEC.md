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
