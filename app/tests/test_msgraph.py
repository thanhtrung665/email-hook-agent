from app.services.ms_graph import MSGraphService


def run_tests():
    graph_service = MSGraphService()
    test_receiver = "hotrung060605@gmail.com" # Thay bằng email thật của bạn

    print("1. Đang test lấy Token...")
    try:
        token = graph_service.get_access_token()
        print(f"✅ Đã lấy được token (độ dài: {len(token)} ký tự)")
    except Exception as e:
        print(f"❌ Lỗi lấy token: {e}")
        return

    print(f"\n2. Đang test Gửi Mail từ drilling@ps.com tới {test_receiver}...")
    try:
        graph_service.send_email(
            to_email=test_receiver,
            subject="Tiêu đề email test từ API",
            content="Xin chào, đây là nội dung email được gửi tự động qua Microsoft Graph API."
        )
        print("✅ Gửi mail thành công! (Vui lòng check hộp thư của bạn)")
    except Exception as e:
        print(f"❌ Lỗi gửi mail: {e}")
        return

    print("\n3. Đang test Đọc Mail...")
    print("Để test hàm này, hệ thống cần một 'message_id' thực tế.")
    print("Khi Webhook đi vào hoạt động, MS Graph sẽ tự động cấp message_id này cho chúng ta.")
    print("Tạm thời hàm đọc mail đã sẵn sàng cấu trúc.")

if __name__ == "__main__":
    run_tests()
