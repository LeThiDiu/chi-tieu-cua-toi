"""Chuẩn hóa văn bản dùng chung giữa lúc huấn luyện và lúc dự đoán.

Model được lưu bằng joblib sẽ tham chiếu tới hàm này, nên file này phải nằm
trong PYTHONPATH khi nạp model (backend đã tự thêm thư mục model/ vào sys.path).
"""
import re
import unicodedata


def normalize_text(s: str) -> str:
    """Chữ thường, bỏ dấu tiếng Việt, gộp khoảng trắng.

    Bỏ dấu giúp model chịu được lỗi OCR (mất/sai dấu) và người dùng gõ không dấu.
    """
    s = str(s).lower().replace("đ", "d")
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s).strip()
    return s
