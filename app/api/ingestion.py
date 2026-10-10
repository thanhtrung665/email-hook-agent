"""API kiểm soát worker thu thập email (xem trạng thái / kích hoạt thủ công)."""
import logging

from fastapi import APIRouter

from app.core.config import settings
from app.services.ingestion_worker import get_worker

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/status")
async def ingestion_status():
    """Trạng thái worker: đang chạy/tạm dừng, lịch hoạt động, thống kê."""
    return get_worker().status()


@router.post("/run")
async def trigger_ingestion():
    """
    Ép chạy một vòng đồng bộ NGAY, bỏ qua khung giờ hoạt động.
    Dùng để test hoặc để kéo email tồn đọng ngoài giờ hành chính.
    """
    if not settings.INGESTION_ENABLED:
        return {"ok": False, "error": "INGESTION_ENABLED=false — worker đang tắt."}
    return await get_worker().trigger_now()
