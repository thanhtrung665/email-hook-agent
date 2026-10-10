import logging
import re
import sys
import types

import joblib

# Shim cho API sklearn đã bị xóa mà talon (1.4.4, bản PyPI mới) vẫn dùng:
# `from sklearn.externals import joblib` (bỏ từ sklearn 0.23).
# Phải chạy TRƯỚC mọi import sklearn/talon.
_sk_ext = sys.modules.get("sklearn.externals")
if _sk_ext is None:
    try:
        import sklearn.externals as _sk_ext  # noqa: E402
    except ImportError:
        _sk_ext = types.ModuleType("sklearn.externals")
        _sk_ext.__path__ = []  # type: ignore[attr-defined]
        sys.modules["sklearn.externals"] = _sk_ext
_sk_ext.joblib = joblib  # type: ignore[attr-defined]
sys.modules["sklearn.externals.joblib"] = joblib

import sklearn.svm  # noqa: E402

sys.modules.setdefault("sklearn.svm.classes", sklearn.svm)
from bs4 import BeautifulSoup  # noqa: E402
from talon import quotations, signature  # noqa: E402

quotations.register_xpath_extensions()
signature.initialize()

logger = logging.getLogger(__name__)

# Talon classifier không tương thích sklearn mới; bọc try/except để pipeline không chết
def _safe_signature_extract(body: str, sender_email: str):
    try:
        return signature.extract(body, sender_email)
    except Exception as e:
        logger.warning(f"talon signature.extract lỗi (bỏ qua, giữ nguyên body): {e}")
        return body, None

_OUTLOOK_QUOTE_PATTERNS = [
    # Outlook header block: From: X Sent: Y To: ... Subject: ...
    re.compile(
        r'(?:^|\n)From:\s+.+?\n\s*Sent:\s+.+?(?:\n|$)',
        re.IGNORECASE | re.DOTALL,
    ),
    # -----Original Message----- divider
    re.compile(r'^\s*-{2,}\s*Original\s+Message\s*-{2,}\s*$', re.IGNORECASE | re.MULTILINE),
    # On ... wrote: (Gmail-style, ít gặp nhưng có)
    re.compile(r'^\s*On\s+.+wrote:\s*$', re.IGNORECASE | re.MULTILINE),
]


def _strip_outlook_quotes(text: str) -> tuple[str, int]:
    """Cắt quote Outlook/Gmail trong body. Chỉ giữ phần trước quote đầu tiên.
    Trả (clean_text, num_quotes_found).
    """
    earliest = None
    for pat in _OUTLOOK_QUOTE_PATTERNS:
        m = pat.search(text)
        if m and (earliest is None or m.start() < earliest):
            earliest = m.start()
    if earliest is None:
        return text, 0
    num = sum(1 for pat in _OUTLOOK_QUOTE_PATTERNS for _ in pat.finditer(text))
    return text[:earliest].strip(), num


class EmailPreprocessor:
    @staticmethod
    def process(raw_html: str, sender_email: str) -> dict:
        """Làm sạch email và bóc tách dữ liệu cứng mà không cần LLM"""
        # Bóc tách HTML = BeautifulSoup
        soup = BeautifulSoup(raw_html, "html.parser")

        # Trích xuất toàn bộ link
        links = [a.get('href') for a in soup.find_all('a', href=True) if a.get('href')]

        # Lấy văn bản thuần túy
        raw_text = soup.get_text(separator='\n').strip()

        # Xử lý reply cũ và chữ ký với talon
        # Cắt bỏ trích dẫn của các email trước đó trong chuỗi
        text_no_quotes = quotations.extract_from(raw_text, 'text/plain')

        # Cắt thêm quote Outlook (From:/Sent: block, -----Original Message-----)
        # vì talon 'text/plain' không cắt được header kiểu Outlook
        outlook_clean, quote_count = _strip_outlook_quotes(text_no_quotes)
        if quote_count:
            logger.debug(f"cat {quote_count} doan quote Outlook")
            text_no_quotes = outlook_clean

        # Cắt bỏ chữ ký (bọc an toàn: lỗi classifier của talon không làm chết pipeline)
        text_clean, sig = _safe_signature_extract(text_no_quotes, sender_email)

        # Nếu talon không cắt được chữ ký, dừng lại text đã bỏ quote
        final_clean_body = text_clean.strip() if text_clean else text_no_quotes.strip()

        # Dùng Regex trích xuất dữ liệu cứng từ chữ ký hoặc body
        search_area = sig if sig else final_clean_body
        phones = re.findall(r'(?:(?:\+?84|0)[3|5|7|8|9])\d{8}\b', search_area)

        return {
            "body_clean": final_clean_body, # Dùng đưa LLM tóm tắt
            "body_full_text": raw_text, # Lưu trữ đối chiếu
            "signature": sig.strip() if sig else None,
            "extracted_links": list(set(links)),
            "extracted_phones": list(set(phones))
        }
