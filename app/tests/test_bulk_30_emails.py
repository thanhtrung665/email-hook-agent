"""Giai đoạn 5.3: Lấy và xử lý 30 email trong 7 ngày qua từ Outlook.

Cách chạy:
    .venv\\Scripts\\python.exe -X utf8 -m app.tests.test_bulk_30_emails [top] [days]
    (mặc định: 30 email / 7 ngày)
"""
import logging
import sys
import traceback

from app.core.config import settings
from app.db.base import SessionLocal
from app.db.models import Email, Mailbox
from app.services.email_processing_pipeline import EmailPipeline
from app.services.ms_graph import MSGraphService

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def ensure_mailbox(db) -> Mailbox:
    """Đảm bảo có 1 record mailbox trong DB (FK cho emails.id_mailbox)."""
    m = db.query(Mailbox).filter(Mailbox.email_address == settings.MS_TARGET_MAILBOX).first()
    if not m:
        m = Mailbox(email_address=settings.MS_TARGET_MAILBOX, provider="outlook")
        db.add(m)
        db.commit()
        logger.info(f"Da tao mailbox moi: {m.id_mailbox}")
    return m


def main(top: int = 30, days: int = 7):
    graph = MSGraphService()
    db = SessionLocal()
    try:
        mailbox = ensure_mailbox(db)
        logger.info(f"Lay toi da {top} email trong {days} ngay qua (mailbox={settings.MS_TARGET_MAILBOX})")

        messages = graph.list_emails(days=days, top=top)
        if not messages:
            print("Khong co email nao trong khoang thoi gian nay.")
            return

        ok, failed, skipped = 0, 0, 0
        for i, msg in enumerate(messages, 1):
            message_id = msg["id"]
            subject = msg.get("subject", "(khong co tieu de)")
            # Bo qua email da xu ly truoc do (dedup theo unique constraint mailbox+message_id)
            exists = db.query(Email).filter(Email.message_id == message_id).first()
            if exists:
                logger.info(f"[{i}/{len(messages)}] SKIP (da co): {subject[:60]}")
                skipped += 1
                continue

            logger.info(f"[{i}/{len(messages)}] Dang xu ly: {subject[:60]}")
            try:
                pipeline = EmailPipeline(db=db, mailbox_id=str(mailbox.id_mailbox))
                pipeline.process_and_save(message_id=message_id)
                ok += 1
            except Exception as e:
                failed += 1
                logger.error(f"Loi xu ly email {message_id}: {e}")
                traceback.print_exc()
                db.rollback()  # pipeline co rollback, nhung dam bao session sach

        total_in_db = db.query(Email).count()
        print("\n=== KET QUA ===")
        print(f"Moi lay       : {len(messages)}")
        print(f"Xu ly thanh cong: {ok}")
        print(f"Bi loi        : {failed}")
        print(f"Bo qua (trung): {skipped}")
        print(f"Tong emails trong DB: {total_in_db}")
    finally:
        db.close()


if __name__ == "__main__":
    top = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    main(top, days)
