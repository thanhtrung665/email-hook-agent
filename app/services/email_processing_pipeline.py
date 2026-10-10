import hashlib
import logging
from datetime import datetime

import pytz
from sqlalchemy.orm import Session

from app.db.models import Attachment, Contact, Email, EmailLabel, EmailSummary, Label  # Các ORM Models của bạn
from app.services.email_analyzer_agent import EmailAnalyzerAgent
from app.services.ms_graph import MSGraphService
from app.services.storage import get_storage
from app.utils.email_preprocessing import EmailPreprocessor

logger = logging.getLogger(__name__)

class EmailPipeline:
    def __init__(self, db: Session, mailbox_id: str):
        self.db = db
        self.mailbox_id = mailbox_id # id_mailbox từ bảng mailboxes
        self.graph_service = MSGraphService()
        self.ai_agent = EmailAnalyzerAgent()

    def process_and_save(self, message_id: str):
        """Luồng xử lý End-to-End từ Webhook Payload đến Database"""
        try:
            # ==========================================
            # BƯỚC 1: LẤY DỮ LIỆU TỪ MICROSOFT GRAPH
            # ==========================================
            email_data = self.graph_service.get_email_content(message_id)
            sender_email = email_data.get("from", {}).get("emailAddress", {}).get("address", "unknown")
            sender_name_raw = email_data.get("from", {}).get("emailAddress", {}).get("name", "")
            subject = email_data.get("subject", "")
            has_attachments = email_data.get("hasAttachments", False)
            raw_html = email_data.get("body", {}).get("content", "")

            # Cc/Bcc recipients (nếu MS Graph trả về)
            cc_recipients = [r.get("emailAddress", {}).get("address") for r in email_data.get("ccRecipients", [])]
            bcc_recipients = [r.get("emailAddress", {}).get("address") for r in email_data.get("bccRecipients", [])]

            # Chuyển đổi thời gian
            received_at_str = email_data.get("createdDateTime")
            conversation_id = email_data.get("conversationId")
            internet_message_id = email_data.get("internetMessageId")
            received_at = datetime.fromisoformat(received_at_str.replace('Z', '+00:00')) if received_at_str else datetime.now(pytz.utc)

            # ==========================================
            # BƯỚC 2: TIỀN XỬ LÝ (HYBRID PRE-PROCESSING)
            # ==========================================
            logger.info("Đang làm sạch HTML và bóc tách chữ ký...")
            processed_data = EmailPreprocessor.process(raw_html, sender_email)
            body_clean = processed_data["body_clean"]
            body_full_text = processed_data["body_full_text"]

            # ==========================================
            # BƯỚC 3: KÍCH HOẠT LANGCHAIN AI AGENT
            # ==========================================
            logger.info("Đang phân tích ý định và bảo mật bằng LLM...")
            # Chỉ truyền body_clean (đã bỏ HTML/Reply cũ) để tiết kiệm token và tăng độ chính xác
            ai_result = self.ai_agent.analyze(
                sender=sender_email,
                subject=subject,
                body=body_clean,
                has_attachments=has_attachments
            )

            # Ưu tiên SĐT từ Regex, nếu Regex trượt thì lấy của LLM
            final_phone = processed_data["extracted_phones"][0] if processed_data["extracted_phones"] else ai_result.contact_info.phone

            # ==========================================
            # BƯỚC 4: LƯU DỮ LIỆU VÀO POSTGRESQL (TRANSACTION)
            # ==========================================
            # 4.1. Xử lý Contact (UPSERT)
            contact = self.db.query(Contact).filter(Contact.email_address == sender_email).first()
            if not contact:
                contact = Contact(
                    email_address=sender_email,
                    sender_name=ai_result.contact_info.sender_name or sender_name_raw,
                    company=ai_result.contact_info.company,
                    phone=final_phone,
                    is_internal=False,
                    email_count=1,
                    first_seen_at=datetime.now(pytz.utc),
                    last_seen_at=datetime.now(pytz.utc)
                )
                self.db.add(contact)
            else:
                contact.email_count += 1
                contact.last_seen_at = datetime.now(pytz.utc)
                # Cập nhật thông tin công ty/SĐT nếu trước đó rỗng mà AI mới tìm ra
                if not contact.company and ai_result.contact_info.company:
                    contact.company = ai_result.contact_info.company
                if not contact.phone and final_phone:
                    contact.phone = final_phone

            self.db.flush() # Lấy id_contact để map sang bảng emails

            # 4.2. Lưu Bảng Emails
            # Chuẩn bị conversationId/thread để gom nhóm luồng email dài
            thread_id = conversation_id or internet_message_id
            new_email = Email(
                id_mailbox=self.mailbox_id,
                id_sender=contact.id_contact,
                message_id=message_id,
                thread_id=thread_id,
                in_reply_to=email_data.get("inReplyTo"),
                subject=subject,
                sent_at=received_at, # Thường MS Graph trả về createdDateTime xấp xỉ sent_at
                received_at=datetime.now(pytz.utc),
                body_text=body_full_text,
                body_clean=body_clean,
                language=ai_result.language,
                has_attachments=has_attachments,
                cc_emails=cc_recipients,
                bcc_emails=bcc_recipients,
                status="PROCESSING",
                security_flags=ai_result.security.model_dump() # Dump Pydantic thành JSONB
            )
            self.db.add(new_email)
            self.db.flush()

            # 4.3. Lưu Email Summary
            new_summary = EmailSummary(
                id_email=new_email.id_email,
                content_summarized=ai_result.content_summarized,
                key_points=ai_result.key_points.model_dump(), # JSONB
                model="gemini-2.5-flash"
            )
            self.db.add(new_summary)

            # 4.4. Lưu Email Labels
            # Giả định bạn query id_label dựa trên suggested_label từ AI
            label_record = self.db.query(Label).filter(Label.label_name == ai_result.label_prediction.suggested_label).first()
            if label_record:
                new_email_label = EmailLabel(
                    id_email=new_email.id_email,
                    id_label=label_record.id_label,
                    source="ai",
                    is_primary=True,
                    confidence=ai_result.label_prediction.confidence,
                    reason=ai_result.label_prediction.reason
                )
                self.db.add(new_email_label)

            # 4.5. Tải & Lưu Attachments (Nếu có)
            if has_attachments:
                attachments_data = self.graph_service.get_email_attachments(message_id)

                # Gọi Dependency Injection để lấy instance lưu trữ (Local hoặc Supabase)
                storage_service = get_storage()

                for att in attachments_data:
                    # Bỏ qua toàn bộ ảnh inline (logo/chữ ký/banner) — tiết kiệm storage & compute.
                    # Ảnh inline không phải nội dung nghiệp vụ: nó là hình chèn trong body/chữ ký.
                    if att["is_inline"] and (att["mime_type"] or "").startswith("image/"):
                        logger.info(f"Bo qua anh inline (logo/chu ky): {att['file_name']}")
                        continue

                    file_bytes = att["content_bytes"]

                    # 1. Tính mã băm file SHA-256
                    file_hash = hashlib.sha256(file_bytes).hexdigest()

                    # 2. Định nghĩa tên file lưu trữ (Chống trùng lặp tên giữa các email)
                    storage_path = f"{message_id}/{att['file_name']}"

                    # 3. Gọi hàm save_file qua Interface
                    storage_key = storage_service.save_file(
                        filename=storage_path,
                        data=file_bytes
                    )

                    # 4. Đánh dấu trạng thái xử lý tiếp theo
                    doc_mimes = {
                        "application/pdf",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        "application/msword",
                        "application/vnd.ms-excel",
                    }
                    mime = (att["mime_type"] or "").lower()
                    process_status = "pending_extraction" if mime in doc_mimes else "stored"

                    # 5. Ghi dữ liệu vào PostgreSQL
                    new_att = Attachment(
                        id_email=new_email.id_email,
                        file_name=att["file_name"],
                        mime_type=att["mime_type"],
                        size_bytes=att["size_bytes"],
                        sha256=file_hash,
                        storage_key=storage_key,
                        is_inline=att["is_inline"],
                        process_status=process_status
                    )
                    self.db.add(new_att)

            # Commit toàn bộ Transaction
            self.db.commit()
            logger.info(f"✅ Đã xử lý và lưu hoàn tất Email ID: {new_email.id_email} vào Database!")

            # Đánh dấu luồng xử lý thành công
            new_email.status = "PENDING_ROUTING"
            self.db.commit()

        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ Transaction Database bị hủy do lỗi: {e}")
            raise
