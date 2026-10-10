import asyncio
import logging

from fastapi import APIRouter, Request, Response

from app.services import schedule
from app.services.ingestion_worker import get_worker

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/outlook")
async def outlook_webhook(request: Request):
    """Endpoint hứng Webhook từ Microsoft Graph"""

    # 1. Validation (Microsoft gửi mã xác thực)
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        logger.info("✅ Nhận yêu cầu xác thực Webhook từ Microsoft.")
        return Response(content=validation_token, media_type="text/plain", status_code=200)

    # 2. Notification (Microsoft báo có email mới)
    try:
        payload = await request.json()
        for event in payload.get("value", []):
            message_id = (event.get("resourceData") or {}).get("id")
            if not message_id:
                continue

            # Ngoài khung giờ hoạt động: bỏ qua, để worker delta sync gom lúc kích hoạt.
            # Xử lý ngay ở đây sẽ chạy ngoài lịch và có thể trùng với worker.
            if not schedule.is_active():
                logger.info(
                    "⏸️  Ngoài khung giờ hoạt động — bỏ qua email %s, worker sẽ lấy lại khi tới giờ.",
                    message_id,
                )
                continue

            logger.info(f"🔔 Có email mới! Đưa vào hàng đợi xử lý: {message_id}")
            # Fire-and-forget: không await để trả 202 ngay cho Microsoft
            asyncio.create_task(get_worker().submit(message_id))

        return Response(status_code=202)
    except Exception as e:
        logger.error(f"Lỗi xử lý webhook payload: {str(e)}")
        return Response(status_code=500)
