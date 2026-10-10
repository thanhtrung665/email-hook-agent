import requests  # Thêm dòng này ở đầu file

from app.core.config import settings
from app.services.ms_graph import MSGraphService


def subscribe():
    graph_service = MSGraphService()
    webhook_url = f"{settings.WEBHOOK_BASE_URL.rstrip('/')}/api/webhooks/outlook"

    print(f"Đang đăng ký Webhook URL: {webhook_url}")
    try:
        res = graph_service.create_webhook_subscription(webhook_url=webhook_url)
        print(f"✅ Đăng ký thành công! ID: {res['id']}")
        print(f"⏰ Hết hạn lúc: {res['expirationDateTime']}")

    # BẮT ĐÚNG LỖI HTTP ĐỂ XEM MICROSOFT NÓI GÌ
    except requests.exceptions.HTTPError as e:
        print(f"❌ Lỗi HTTP: {e.response.status_code}")
        print(f"❌ CHI TIẾT TỪ MICROSOFT: {e.response.text}")

    except Exception as e:
        print(f"❌ Lỗi: {e}")

if __name__ == "__main__":
    subscribe()
