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
