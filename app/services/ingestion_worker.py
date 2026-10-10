"""
Worker nền: tự động thu thập và phân tích email mới từ Outlook.

Luồng hoạt động:
  1. Kiểm tra khung giờ hoạt động (app/services/schedule.py).
     - Ngoài khung giờ: ngủ (asyncio sleep) cho tới lần kích hoạt kế tiếp.
     - Trong khung giờ: gọi Microsoft Graph delta API lấy email mới.
  2. Bỏ qua email đã xử lý (dedupe theo message_id trong DB).
  3. Đưa email qua EmailPipeline (Graph → preprocess → LLM → PostgreSQL).
  4. Lưu deltaLink vào DB làm cursor cho lần đồng bộ kế tiếp.

Mọi lỗi đều được nuốt + log, worker không bao giờ chết.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.db.base import SessionLocal
from app.db.models import Email, Mailbox
from app.services import schedule
from app.services.email_processing_pipeline import EmailPipeline
from app.services.ms_graph import MSGraphService

logger = logging.getLogger(__name__)


class IngestionWorker:
    """Background worker dùng Graph delta polling, tôn trọng khung giờ hoạt động."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()
        self.graph = MSGraphService()
        self.is_paused = False
        self.next_wake_at: datetime | None = None
        self.last_run_at: datetime | None = None
        self.last_error: str | None = None
        self.stats = {"processed": 0, "skipped": 0, "failed": 0, "cycles": 0}

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run())
        logger.info(
            "🚀 Ingestion worker khởi động — khung giờ hoạt động: %s",
            schedule.describe_schedule(),
        )

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------ main loop
    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if not schedule.is_active():
                    await self._pause_until_active()
                    continue

                self.is_paused = False
                self.next_wake_at = None
                await asyncio.to_thread(self._poll_once)
                self.last_run_at = datetime.now(UTC)
                self.last_error = None
                self.stats["cycles"] += 1

                await self._sleep(settings.INGESTION_POLL_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 — worker phải sống sót
                self.last_error = str(e)
                logger.exception("Lỗi vòng polling: %s", e)
                await self._sleep(settings.INGESTION_ERROR_BACKOFF_SECONDS)

    async def _pause_until_active(self) -> None:
        self.is_paused = True
        now = datetime.now(UTC)
        self.next_wake_at = schedule.next_wake_after_pause(now)
        wait_seconds = max(5.0, (self.next_wake_at - now).total_seconds())
        logger.info(
            "⏸️  Ngoài khung giờ hoạt động — tạm dừng, kích hoạt lại lúc %s (%.1f giây nữa)",
            self.next_wake_at.isoformat(),
            wait_seconds,
        )
        # Ngủ tới khi kích hoạt, nhưng vẫn giữ reference để stop() cắt được.
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=wait_seconds)
        except TimeoutError:
            logger.info("⏵ Đã tới giờ kích hoạt — bắt đầu thu thập email tồn đọng.")
        self.is_paused = False

    async def _sleep(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except TimeoutError:
            pass

    # ------------------------------------------------------------------ sync logic
    def _poll_once(self) -> None:
        db = SessionLocal()
        try:
            mailbox = self._ensure_mailbox(db)
            cursor = mailbox.sync_cursor

            since = None
            if not cursor:
                since = datetime.now(UTC) - timedelta(days=settings.INGESTION_CATCHUP_DAYS)

            messages, new_cursor, has_more = self.graph.get_messages_delta(
                delta_link=cursor,
                since=since,
                top=settings.INGESTION_BATCH_SIZE,
                max_pages=settings.INGESTION_MAX_PAGES,
            )
            logger.info("📥 Delta sync: %d email mới (has_more=%s)", len(messages), has_more)

            for msg in messages:
                self._process_message(db, mailbox, msg.get("id", ""))

            if new_cursor and not has_more:
                mailbox.sync_cursor = new_cursor
                db.commit()
            elif new_cursor:
                # Vẫn còn trang chưa đọc xong — chỉ lưu cursor khi đồng bộ trọn vẹn
                logger.info("⏳ Còn trang delta chưa xử lý — giữ cursor cũ để lần sau đọc tiếp.")
        finally:
            db.close()

    def _ensure_mailbox(self, db) -> Mailbox:
        mailbox = (
            db.query(Mailbox)
            .filter(Mailbox.email_address == settings.MS_TARGET_MAILBOX)
            .first()
        )
        if not mailbox:
            mailbox = Mailbox(email_address=settings.MS_TARGET_MAILBOX, provider="outlook")
            db.add(mailbox)
            db.commit()
            logger.info("📦 Đã tạo mailbox mới: %s", mailbox.id_mailbox)
        return mailbox

    def _process_message(self, db, mailbox: Mailbox, message_id: str) -> None:
        if not message_id:
            return

        already = (
            db.query(Email)
            .filter(Email.id_mailbox == mailbox.id_mailbox, Email.message_id == message_id)
            .first()
        )
        if already:
            self.stats["skipped"] += 1
            logger.info("⏭️  Bỏ qua (đã xử lý): %s", message_id)
            return

        try:
            pipeline = EmailPipeline(db=db, mailbox_id=str(mailbox.id_mailbox))
            pipeline.process_and_save(message_id=message_id)
            self.stats["processed"] += 1
        except Exception as e:  # noqa: BLE001 — 1 email lỗi không được làm hỏng cả vòng
            self.stats["failed"] += 1
            logger.error("❌ Xử lý email %s thất bại: %s", message_id, e)
            db.rollback()

    # ------------------------------------------------------------------ webhook submit
    async def submit(self, message_id: str) -> None:
        """Nhận email từ webhook, xử lý ngay (dedupe trước) để không chờ vòng polling."""
        try:
            await asyncio.to_thread(self._process_message_direct, message_id)
        except Exception as e:  # noqa: BLE001 — webhook không được làm sập request
            logger.error("❌ Xử lý email từ webhook %s thất bại: %s", message_id, e)

    def _process_message_direct(self, message_id: str) -> None:
        db = SessionLocal()
        try:
            mailbox = self._ensure_mailbox(db)
            self._process_message(db, mailbox, message_id)
        finally:
            db.close()

    # ------------------------------------------------------------------ manual trigger
    async def trigger_now(self) -> dict:
        """Ép chạy một vòng đồng bộ ngay (bỏ qua khung giờ) — dùng cho test/debug."""
        async with self._lock:
            before = dict(self.stats)
            try:
                await asyncio.to_thread(self._poll_once)
                self.last_run_at = datetime.now(UTC)
                self.last_error = None
            except Exception as e:  # noqa: BLE001
                self.last_error = str(e)
                logger.exception("Trigger thủ công thất bại: %s", e)
            delta = {k: self.stats[k] - before[k] for k in ("processed", "skipped", "failed")}
            return {"ok": self.last_error is None, "error": self.last_error, "delta": delta}

    def status(self) -> dict:
        return {
            "running": bool(self._task and not self._task.done()),
            "is_paused": self.is_paused,
            "schedule": schedule.describe_schedule(),
            "within_active_window": schedule.is_active(),
            "next_wake_at": self.next_wake_at.isoformat() if self.next_wake_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_error": self.last_error,
            "poll_interval_seconds": settings.INGESTION_POLL_INTERVAL_SECONDS,
            "stats": dict(self.stats),
        }


# Singleton dùng chung cho FastAPI
_worker: IngestionWorker | None = None


def get_worker() -> IngestionWorker:
    global _worker
    if _worker is None:
        _worker = IngestionWorker()
    return _worker
