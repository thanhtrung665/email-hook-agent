import logging

from app.models import Label

from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Chuẩn hóa danh sách nhãn thành các Mã (Code) dễ quản lý cho Backend
INITIAL_LABELS = [
    {"name": "INQUIRY", "desc": "Hỏi đáp, tìm hiểu thông tin chung", "priority": 10},
    {"name": "QUOTE", "desc": "Yêu cầu báo giá (Quote)", "priority": 20},
    {"name": "PO", "desc": "Purchase Order - Đơn đặt hàng", "priority": 30},
    {"name": "PROFORMA_INVOICE", "desc": "Hóa đơn thanh toán -> Nhận Bank Slip -> Kế toán xác nhận", "priority": 40},
    {"name": "MISA_MVPO", "desc": "Chứng từ Misa MVPO", "priority": 50},
    {"name": "SOA", "desc": "Sales Order Acknowledgement -> Báo hàng ready kèm thời gian", "priority": 60},
    {"name": "CIPL_CERTIFICATES", "desc": "Commercial Invoice Packing List / Certificates", "priority": 70},
    {"name": "ORDER_PICTURE", "desc": "Hình ảnh đơn hàng", "priority": 80},
    {"name": "AWB_BOL", "desc": "Vận đơn AWB/BOL - Cần giải nghĩa", "priority": 90},
    {"name": "SED", "desc": "Tờ khai xuất khẩu Mỹ", "priority": 100},
    {"name": "SHIPMENT_DOCUMENT", "desc": "Chứng từ từ Hãng tàu/bay -> Báo về shipment cho khách", "priority": 110},
    {"name": "DELIVERY_TICKET", "desc": "Phiếu giao hàng -> Chờ khách gửi lại bản đã ký", "priority": 120},
    {"name": "EXCEPTION", "desc": "Ngoại lệ - Trường hợp hiếm gặp, phức tạp", "priority": 900},
    {"name": "SPAM_ADS", "desc": "Quảng cáo, Spam -> Bỏ qua", "priority": 999},
]

def seed_labels():
    db = SessionLocal()
    try:
        for lbl in INITIAL_LABELS:
            existing = db.query(Label).filter(Label.label_name == lbl["name"]).first()
            if not existing:
                new_label = Label(
                    label_name=lbl["name"],
                    description=lbl["desc"],
                    priority=lbl["priority"],
                    is_active=True
                )
                db.add(new_label)
                logger.info(f"Đã thêm nhãn: {lbl['name']}")
        db.commit()
        logger.info("Hoàn tất nạp danh mục Nhãn!")
    except Exception as e:
        db.rollback()
        logger.error(f"Lỗi: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_labels()
