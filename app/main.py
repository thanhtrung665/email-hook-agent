import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.emails_render import router as email_router
from app.api.ingestion import router as ingestion_router
from app.api.webhooks import router as webhook_router
from app.core.config import settings
from app.services.ingestion_worker import get_worker

# 1. Cấu hình log cơ bản
logging.basicConfig(level=logging.INFO)

# 2. Lifespan: khởi động / dừng background ingestion worker cùng app
@asynccontextmanager
async def lifespan(_: FastAPI):
    worker = get_worker()
    if settings.INGESTION_ENABLED:
        worker.start()
    else:
        logging.getLogger(__name__).warning("INGESTION_ENABLED=false — worker thu thập email TẮT.")
    try:
        yield
    finally:
        await worker.stop()

# 3. BẮT BUỘC KHỞI TẠO APP TRƯỚC
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Email Multi-Agent System",
    version="1.0.0",
    lifespan=lifespan,
)

# 4. SAU ĐÓ MỚI ĐĂNG KÝ ROUTER VÀO APP
app.include_router(webhook_router, prefix="/api/webhooks")

app.include_router(email_router, prefix="/api/emails", tags=["Emails"])

app.include_router(ingestion_router, prefix="/api/ingestion", tags=["Ingestion"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Cho phép Next.js gọi vào
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 5. API kiểm tra sức khỏe hệ thống
@app.get("/")
def health_check():
    return {"status": "ok", "message": "Email Hook Agent is running."}
