# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /code

# Cài uv (quản lý dependency) + curl (healthcheck)
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

# 1. Cài dependencies trước để tận dụng cache layer
COPY pyproject.toml ./
RUN uv pip install --system \
        "fastapi>=0.140" "uvicorn[standard]>=0.34" "pydantic>=2.10" \
        "pydantic-settings>=2.7" "python-dotenv>=1.0" \
        "python-multipart>=0.0.18" "sqlalchemy>=2.0.36" "alembic>=1.14" \
        "psycopg[binary]>=3.2" "requests>=2.32" "msal>=1.31" \
        "langchain>=0.3" "langchain-core>=0.3" \
        "langchain-google-genai>=2.0" "beautifulsoup4>=4.12" \
        "lxml>=5.3" "talon>=1.4.4" "scikit-learn>=1.5" "joblib>=1.4" \
        "supabase>=2.7" "pytz>=2024.2" "python-docx>=1.1" "openpyxl>=3.1"

# 2. Copy source
COPY alembic ./alembic
COPY alembic.ini ./
COPY app ./app

EXPOSE 8000

# Chạy migration rồi khởi động API (worker + scheduler chạy trong lifespan).
# Migration không chặn start nếu DB tạm không đạt được (VPS reboot trước DB).
CMD ["sh", "-c", "python -m alembic upgrade head || echo '⚠️  alembic upgrade failed — sẽ retry ở lần restart'; exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/')"
