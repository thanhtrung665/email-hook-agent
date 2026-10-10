import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import base64
import logging
from datetime import UTC, datetime, timedelta

import msal
import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

class MSGraphService:
    def __init__(self):
        self.client_id = settings.MS_CLIENT_ID
        self.client_secret = settings.MS_CLIENT_SECRET
        self.tenant_id = settings.MS_TENANT_ID

        # Endpoint login MS (format chuan)
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"

        # Thiết lập MSAL thay cho cURL login (grant_type=client_credentials)
        self.app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret,
        )
        self.base_url = "https://graph.microsoft.com/v1.0"

    def get_access_token(self) -> str:
        """Lấy token cấp ứng dụng (Application Permission)"""
        scopes = ["https://graph.microsoft.com/.default"]

        result = self.app.acquire_token_silent(scopes, account=None)
        if not result:
            result = self.app.acquire_token_for_client(scopes=scopes)

        if "access_token" in result:
            return result["access_token"]

        logger.error(f"Lỗi lấy token: {result}")
        raise Exception(f"Không thể lấy MS Graph Token: {result.get('error_description', result)}")

    def send_email(self, to_email: str, subject: str, content: str, sender_mailbox: str | None = None) -> bool:
        """
        Thực thi lệnh cURL gửi mail.
        Mặc định sử dụng hòm thư drilling@psbvn.com theo cấu hình.
        """
        if sender_mailbox is None:
            sender_mailbox = settings.MS_TARGET_MAILBOX
        token = self.get_access_token()
        url = f"{self.base_url}/users/{sender_mailbox}/sendMail"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "AnchorMailbox": sender_mailbox
        }

        payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": content
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": to_email
                        }
                    }
                ]
            },
            "saveToSentItems": "true"
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            logger.info(f"Đã gửi email thành công tới {to_email} từ hòm thư {sender_mailbox}")
            return True
        except requests.exceptions.HTTPError as e:
            error_msg = e.response.text
            logger.error(f"Lỗi HTTP khi gửi mail: {e.response.status_code} - {error_msg}")
            raise Exception(f"Gửi mail thất bại: {error_msg}") from e

    def get_email_content(self, message_id: str, mailbox: str | None = None) -> dict:
        """
        Thực thi lệnh cURL đọc mail để lấy chi tiết email (Tiêu đề, Nội dung, Sender).
        """
        token = self.get_access_token()
        # Endpoint chuẩn của MS Graph để lấy 1 message cụ thể
        if mailbox is None:
            mailbox = settings.MS_TARGET_MAILBOX
        url = f"{self.base_url}/users/{mailbox}/messages/{message_id}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "AnchorMailbox": mailbox
        }

        try:
            # Lệnh cURL đọc mail sử dụng method GET
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_msg = e.response.text
            logger.error(f"Lỗi HTTP khi đọc mail: {e.response.status_code} - {error_msg}")
            raise Exception(f"Đọc mail thất bại: {error_msg}") from e


    def get_email_attachments(self, message_id: str, mailbox: str = settings.MS_TARGET_MAILBOX) -> list:
        """
        Tải toàn bộ file đính kèm của một email thông qua MS Graph API.
        Trả về danh sách các dictionary chứa metadata và dữ liệu nhị phân của file.
        """
        token = self.get_access_token()
        url = f"{self.base_url}/users/{mailbox}/messages/{message_id}/attachments"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "AnchorMailbox": mailbox
        }

        try:
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            data = response.json()

            attachments = []
            if "value" in data:
                for att in data["value"]:
                    # Chỉ lấy file thực tế (bỏ qua các dạng đính kèm dạng link - itemAttachment)
                    if att.get("@odata.type") == "#microsoft.graph.fileAttachment":
                        # Giải mã dữ liệu base64 thành bytes nhị phân
                        content_b64 = att.get("contentBytes", "")
                        content_bytes = base64.b64decode(content_b64) if content_b64 else b""

                        attachments.append({
                            "id_attachment_ms": att.get("id"),
                            "file_name": att.get("name"),
                            "mime_type": att.get("contentType"),
                            "size_bytes": att.get("size"),
                            "is_inline": att.get("isInline", False), # True nếu là ảnh chèn thẳng vào chữ ký/body
                            "content_bytes": content_bytes
                        })

            logger.info(f"Đã tải thành công {len(attachments)} file đính kèm cho email {message_id}")
            return attachments

        except requests.exceptions.HTTPError as e:
            error_msg = e.response.text
            logger.error(f"Lỗi HTTP khi tải file đính kèm: {e.response.status_code} - {error_msg}")
            raise Exception(f"Tải file đính kèm thất bại: {error_msg}") from e

    # Hàm tạo webhook subscription
    def create_webhook_subscription(self, webhook_url: str, mailbox: str = settings.MS_TARGET_MAILBOX) -> dict:
        """ Đăng ký microsoft nhận thông báo khi có email mới"""
        token = self.get_access_token()
        url = f"{self.base_url}/subscriptions"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Webhook hết hạn sau 2 ngày, giới hạn tối đa 4230 phút
        expiration = datetime.now(UTC) + timedelta(days=2)

        payload = {
            "changeType" : "created", # Lắng nghe sự kiện tạo mới email
            "notificationUrl" : webhook_url,
            "resource" : f"/users/{mailbox}/mailFolders/inbox/messages",
            "expirationDateTime" : expiration.isoformat(),
            "clientState" : settings.WEBHOOK_SECRET
        }

        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        return response.json()

    # Hàm lấy danh sách email trong khoảng thời gian (Giai đoạn 5.3: bulk test 30 email / 7 ngày)
    def list_emails(
        self,        mailbox: str | None = None,
        days: int = 7,
        top: int = 30,
    ) -> list[dict]:
        """Lấy tối đa `top` email nhận trong `days` ngày qua (từ Inbox, sắp xếp mới nhất trước)."""
        if mailbox is None:
            mailbox = settings.MS_TARGET_MAILBOX
        token = self.get_access_token()
        url = f"{self.base_url}/users/{mailbox}/mailFolders/inbox/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "AnchorMailbox": mailbox,
        }
        params = {
            "$orderby": "receivedDateTime desc",
            "$top": str(top * 3),  # lấy dư, cắt theo filter ngày ở dưới
            "$select": "id,subject,from,receivedDateTime,createdDateTime,hasAttachments,conversationId,internetMessageId,body,toRecipients,ccRecipients,bccRecipients",
        }
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=20)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error(f"list_emails HTTP error: {e.response.status_code} - {e.response.text}")
            raise

        items = resp.json().get("value", [])
        since = datetime.now(UTC).timestamp() - days * 86400
        filtered = []
        for it in items:
            rdt = it.get("receivedDateTime")
            if not rdt:
                continue
            ts = datetime.fromisoformat(rdt.replace("Z", "+00:00")).timestamp()
            if ts >= since:
                filtered.append(it)
            if len(filtered) >= top:
                break
        logger.info(f"list_emails: lay duoc {len(filtered)} email tu {mailbox} trong {days} ngay qua")
        return filtered

    def get_messages_delta(
        self,
        delta_link: str | None = None,
        since: datetime | None = None,
        mailbox: str | None = None,
        top: int = 25,
        max_pages: int = 10,
    ) -> tuple[list[dict], str | None, bool]:
        """
        Lấy email MỚI qua Microsoft Graph delta API (inkremental sync).

        - Lần đầu (delta_link=None): gọi `/messages/delta` kèm $filter receivedDateTime ge `since`
          để không kéo cả mailbox.
          - Các lần sau: gọi thẳng deltaLink đã lưu (Graph tự trả deltaLink mới).
          - Trả về (messages, next_delta_link, has_more).

        Graph yêu cầu $filter chỉ được dùng ở lần đầu, nên khi có delta_link
        thì không truyền params lọc.
        """
        if mailbox is None:
            mailbox = settings.MS_TARGET_MAILBOX
        token = self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "AnchorMailbox": mailbox,
        }

        if delta_link:
            next_url: str | None = delta_link
            params = {"$top": str(top)}
        else:
            next_url = f"{self.base_url}/users/{mailbox}/mailFolders/inbox/messages/delta"
            params = {"$top": str(top)}
            if since is not None:
                # Graph chấp nhận ISO-8601 UTC trong $filter
                since_iso = since.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                params["$filter"] = f"receivedDateTime ge {since_iso}"

        collected: list[dict] = []
        next_delta: str | None = None
        pages = 0

        while next_url and pages < max_pages:
            pages += 1
            try:
                resp = requests.get(next_url, headers=headers, params=params, timeout=30)
            except requests.exceptions.RequestException as e:
                logger.error(f"get_messages_delta network error: {e}")
                raise

            if resp.status_code == 410:
                # DeltaLink quá hạn (~24h) — reset về lần đồng bộ mới
                logger.warning("DeltaLink hết hạn (410) — sẽ đồng bộ lại từ đầu.")
                return [], None, False
            if resp.status_code == 400 and "ReceivedDateTimeFilterNotSupported" in resp.text:
                # Khi delta_link được Graph trả về, $filter bị từ chối — retry không filter
                next_url = resp.json().get("@odata.nextLink", next_url) or next_url
                params.pop("$filter", None)
                pages -= 1
                continue

            resp.raise_for_status()
            data = resp.json()
            collected.extend(data.get("value", []))

            if "@odata.nextLink" in data:
                next_url = data["@odata.nextLink"]
                params = {}  # nextLink đã chứa query string đầy đủ
            elif "@odata.deltaLink" in data:
                next_delta = data["@odata.deltaLink"]
                next_url = None
            else:
                next_url = None

        return collected, next_delta, next_url is not None

