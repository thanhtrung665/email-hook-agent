import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

# ==========================================
# 1. CẤU TRÚC DỮ LIỆU ĐẦU RA (PYDANTIC MODELS)
# ==========================================

# Map với bảng `contacts`
class ContactExtraction(BaseModel):
    sender_name: str | None = Field(description="Tên người gửi (Ví dụ: Nguyễn Văn A)", default=None)
    company: str | None = Field(description="Tên công ty của người gửi", default=None)
    phone: str | None = Field(description="Số điện thoại của người gửi", default=None)

# Map với cột `emails.security_flags` (JSONB)
class SecurityFlags(BaseModel):
    risk_level: str = Field(description="Mức độ rủi ro: low, medium, high")
    is_phishing: bool = Field(description="Có dấu hiệu lừa đảo, giả mạo, yêu cầu chuyển tiền bất thường không?")
    is_spam: bool = Field(description="Có phải là thư rác, quảng cáo không mong muốn không?")
    flags: list[str] = Field(description="Danh sách cảnh báo ngắn gọn (VD: 'Yêu cầu chuyển tiền gấp', 'Tên miền lạ')", default_factory=list)

# Map với cột `email_summaries.key_points` (JSONB)
class ActionItem(BaseModel):
    task: str = Field(description="Mô tả công việc cần làm")
    due_date: str | None = Field(description="Hạn chót (nếu có, định dạng YYYY-MM-DD hoặc text gốc)", default=None)

class KeyPoints(BaseModel):
    action_items: list[ActionItem] = Field(description="Danh sách công việc cần xử lý", default_factory=list)
    sentiment: str = Field(description="Sắc thái của email: positive, neutral, negative, urgent")

class LabelPrediction(BaseModel):
    suggested_label: str | None = Field(description="Nhãn nghiệp vụ gợi ý (VD: PO, QUOTE, INQUIRY, SPAM_ADS...)", default=None)
    confidence: float = Field(description="Độ tin cậy 0.0 - 1.0", default=1.0)
    reason: str | None = Field(description="Lý do gán nhãn", default=None)

# Model tổng hợp kết quả đầu ra
class EmailAnalysisResult(BaseModel):
    language: str = Field(description="Mã ngôn ngữ của email (VD: vi, en)")
    contact_info: ContactExtraction
    security: SecurityFlags
    content_summarized: str = Field(description="Tóm tắt nội dung chính trong 1-2 câu")
    key_points: KeyPoints
    label_prediction: LabelPrediction = Field(default_factory=LabelPrediction)


# ==========================================
# 2. LANGCHAIN AGENT
# ==========================================
class EmailAnalyzerAgent:
    def __init__(self):
        # Khởi tạo Gemini model
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            api_key=settings.GEMINI_API_KEY,
            temperature=0,  # Giữ ở mức 0 để AI không sáng tạo, đảm bảo trích xuất chính xác 100%
            max_retries=3
        )

        # Ép LLM trả về chuỗi JSON khớp hoàn toàn với cấu trúc EmailAnalysisResult
        self.structured_llm = self.llm.with_structured_output(EmailAnalysisResult)

        # Khởi tạo Prompt Template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """Bạn là một AI Agent phân tích email chuyên sâu.
Nhiệm vụ của bạn là đọc thông tin email (đã được làm sạch HTML) và trích xuất dữ liệu có cấu trúc chính xác tuyệt đối.

HƯỚNG DẪN CHI TIẾT:
1. Contact Info: Cố gắng tìm Tên, Công ty, Số điện thoại trong phần chữ ký (signature) hoặc xưng hô ở đầu/cuối email.
2. Security: Cảnh giác cao với các email giục chuyển tiền, báo lỗi tài khoản, hoặc file đính kèm lạ.
3. Summary & Key Points: Tóm tắt súc tích trong 1-2 câu. Liệt kê rõ các công việc (Action Items) và thời hạn. Phân tích sắc thái (sentiment).

LƯU Ý QUAN TRỌNG:
- Chỉ sử dụng thông tin có trong nội dung email, tuyệt đối không bịa đặt.
- **PHÂN LOẠI NHÃN (BẮT BUỘC):** dựa trên nội dung email, chọn ĐÚNG 1 nhãn dưới đây và đưa vào `label_prediction.suggested_label`
  (không được để None trừ khi hoàn toàn không xác định):
  INQUIRY — Hỏi đáp, tìm hiểu thông tin chung
  QUOTE — Yêu cầu/hồi đáp báo giá
  PO — Đơn đặt hàng
  PROFORMA_INVOICE — Hoá đơn tạm tính
  MISA_MVPO — Chứng từ Misa MVPO
  SOA — Sales Order Acknowledgement (báo hàng ready)
  CIPL_CERTIFICATES — CIPL / chứng từ hải quan / chứng nhận
  ORDER_PICTURE — Hình ảnh đơn hàng
  AWB_BOL — Vận đơn AWB/BOL cần giải nghĩa
  SED — Tờ khai xuất khẩu Mỹ
  SHIPMENT_DOCUMENT — Chứng từ hãng tàu/bay gửi về (báo shipment)
  DELIVERY_TICKET — Phiếu giao hàng chờ bản ký
  EXCEPTION — Ngoại lệ / phức tạp
  SPAM_ADS — Quảng cáo / spam
  Đồng thời ước lượng `confidence` (0.0–1.0) và `reason` ngắn gọn."""),
            ("human", """
THÔNG TIN METADATA:
- Người gửi: {sender}
- Tiêu đề: {subject}
- Có file đính kèm: {has_attachments}

NỘI DUNG EMAIL (ĐÃ LÀM SẠCH):
{body}
""")
        ])

        # Kết nối Prompt và LLM thành một chuỗi (Chain)
        self.chain = self.prompt | self.structured_llm

    def analyze(self, sender: str, subject: str, body: str, has_attachments: bool = False) -> EmailAnalysisResult:
        """Thực thi chuỗi phân tích LangChain"""
        try:
            logger.info("Chạy LangChain Agent: Trích xuất Dữ liệu, Tóm tắt & Quét Bảo mật...")
            result = self.chain.invoke({
                "sender": sender,
                "subject": subject,
                "has_attachments": str(has_attachments),
                "body": body
            })
            return result
        except Exception as e:
            logger.error(f"Lỗi AI Agent: {e}")
            raise
