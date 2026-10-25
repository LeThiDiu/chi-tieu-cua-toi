"""Đọc hóa đơn từ ảnh: ảnh -> {cửa hàng, ngày, danh sách (tên, số lượng, thành tiền), tổng}.

Hai engine (để so sánh trong báo cáo):
  - gemini    : Gemini Vision, trả JSON theo schema (cần GEMINI_API_KEY, chỉ dùng ở backend)
  - tesseract : OCR truyền thống (pytesseract) + parser theo quy tắc, chạy offline
"""
import io
import json
import os
import re
import unicodedata
from datetime import date, datetime

from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel

MAX_BYTES = 20 * 1024 * 1024  # ảnh điện thoại thường 4-12 MB; sau khi nạp sẽ thu nhỏ về MAX_SIDE
MAX_SIDE = 2000


class InvoiceError(Exception):
    """Lỗi có thể hiển thị cho người dùng."""

    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


# ------------------------------------------------------------------ tiền xử lý ảnh
def load_image(data: bytes) -> Image.Image:
    if not data:
        raise InvoiceError("File ảnh rỗng.")
    if len(data) > MAX_BYTES:
        raise InvoiceError(f"Ảnh quá lớn ({len(data) / 1e6:.1f} MB). Tối đa {MAX_BYTES // 1024 // 1024} MB.", 413)
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise InvoiceError("File không phải ảnh hợp lệ (hỗ trợ JPG, PNG, WEBP).")
    img = ImageOps.exif_transpose(img)  # ảnh chụp điện thoại hay bị xoay theo EXIF
    img = img.convert("RGB")
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    return img


def enhance_for_ocr(img: Image.Image) -> Image.Image:
    g = ImageOps.grayscale(img)
    g = ImageOps.autocontrast(g, cutoff=1)
    if max(g.size) < 1400:  # ảnh nhỏ: phóng to giúp OCR đọc tốt hơn
        k = 1400 / max(g.size)
        g = g.resize((int(g.width * k), int(g.height * k)), Image.LANCZOS)
    return g


# ------------------------------------------------------------------ số / ngày
_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def to_number(tok: str):
    tok = tok.strip()
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", tok):  # 32.000 / 1,250,000
        return int(re.sub(r"[.,]", "", tok))
    m = re.fullmatch(r"(\d+)[.,](\d{1,2})", tok)  # 0,5 / 2.5
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")
    digits = re.sub(r"[^\d]", "", tok)
    return int(digits) if digits else 0


def parse_date(text: str):
    m = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4}|\d{2})\b", text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y += 2000 if y < 100 else 0
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            pass
    m = re.search(r"\b(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})\b", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            pass
    return None


# ------------------------------------------------------------------ parser cho văn bản OCR
def strip_accents(s: str) -> str:
    s = s.lower().replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# Mọi pattern áp dụng trên văn bản đã bỏ dấu + chữ thường (chịu được lỗi OCR về dấu)
SKIP = re.compile(
    r"\b(tong|thanh toan|tien mat|vat|thue|giam gia|chiet khau|khach dua|tien thua|cam on|hotline|mst|"
    r"dia chi|sdt|dt|tel|so hoa don|hoa don|ngay|gio|ban so|quay|thu ngan|stt|don gia|thanh tien|"
    r"so luong|ten hang|mat hang|website|www|wifi|pass|ma so|invoice|receipt|cash|change|subtotal|total|tax)\b"
)
HEADER = re.compile(r"\b(ten hang|mat hang|don gia|thanh tien|so luong|t\.tien|sl)\b")
TOTAL_KEYS = [r"tong thanh toan", r"tong cong", r"tong tien", r"thanh tien thanh toan",
              r"\bthanh toan\b", r"\btotal\b", r"\btong\b"]
_PURE_NUM = re.compile(r"^\d+(?:[.,]\d+)*$")


def _is_num_tok(t: str) -> bool:
    return bool(_PURE_NUM.match(t)) and not (len(t) > 1 and t[0] == "0" and t[1].isdigit())  # bỏ "0243" (sđt)


def parse_receipt_text(text: str) -> dict:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    norm = [strip_accents(ln) for ln in lines]

    store = next((ln for ln, n in zip(lines[:6], norm[:6]) if len(re.findall(r"[^\W\d_]", ln)) >= 3
                  and not parse_date(ln) and not SKIP.search(n)), None)
    inv_date = next((d for d in (parse_date(ln) for ln in lines) if d), None)

    # dòng tổng tiền
    total, total_idx = None, None
    for key in TOTAL_KEYS:
        for i in range(len(lines) - 1, -1, -1):
            if re.search(key, norm[i]):
                nums = [to_number(t) for t in _NUM.findall(lines[i])]
                nums = [n for n in nums if isinstance(n, int) and n >= 1000]
                if nums:
                    total, total_idx = nums[-1], i
                    break
        if total:
            break

    # vùng bảng hàng hóa: sau dòng tiêu đề cột (nếu có) và trước dòng tổng tiền
    start = 0
    for i, n in enumerate(norm[:20]):
        if HEADER.search(n) and len(re.findall(r"[^\W\d_]", n)) >= 3:
            start = i + 1
    end = total_idx if total_idx is not None else len(lines)

    items = []
    for ln, n in zip(lines[start:end], norm[start:end]):
        if SKIP.search(n):
            continue
        toks = ln.split()
        tail = []
        while toks and len(tail) < 3 and _is_num_tok(toks[-1]):
            tail.insert(0, toks.pop())
        if not tail:
            continue
        qty0 = None
        if toks and re.fullmatch(r"\d+[xX*]", toks[-1]):  # "Trà đào 2x 45.000"
            qty0 = int(toks.pop()[:-1])
        if toks and re.fullmatch(r"\d+", toks[0]) and len(toks) > 1 and re.fullmatch(r"[xX*]", toks[1]):
            qty0 = int(toks[0]); toks = toks[2:]  # "2 x Trà đào 45.000"
        name = " ".join(toks)
        name = re.sub(r"^\s*\d+\s*[.)\-]\s*", "", name)  # bỏ số thứ tự "1." "2)"
        name = re.sub(r"[^\w\s().,/+\-%&]", " ", name, flags=re.UNICODE)
        name = re.sub(r"\s+", " ", name).strip(" .-_|:")
        if len(re.findall(r"[^\W\d_]", name)) < 3:
            continue
        nums = [to_number(t) for t in tail]
        money = [x for x in nums if isinstance(x, int) and x >= 1000]
        small = [x for x in nums if not (isinstance(x, int) and x >= 1000)]
        if not money:
            continue
        amount = money[-1]
        unit = money[-2] if len(money) >= 2 else None
        if qty0 is not None:
            qty = qty0
        elif small:
            qty = small[-1]
        elif unit:
            q = amount / unit
            qty = round(q) if abs(q - round(q)) < 0.05 and round(q) >= 1 else 1
        else:
            qty = 1
        items.append({"name": name, "quantity": qty, "unit_price": unit, "amount": amount})
    return {"store_name": store, "date": inv_date, "total": total, "items": items}


# ------------------------------------------------------------------ engine: Tesseract
def extract_tesseract(img: Image.Image) -> dict:
    try:
        import pytesseract
    except ImportError:
        raise InvoiceError("Chưa cài pytesseract (pip install pytesseract).", 503)
    cmd = os.environ.get("TESSERACT_CMD") or next(
        (c for c in (r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe")
         if os.path.exists(c)), None)  # tự tìm ở thư mục cài mặc định trên Windows
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    lang = os.environ.get("TESSERACT_LANG", "vie+eng")
    proc = enhance_for_ocr(img)
    warnings = []
    try:
        try:
            text = pytesseract.image_to_string(proc, lang=lang, config="--psm 6")
        except pytesseract.TesseractError:
            text = pytesseract.image_to_string(proc, lang="eng", config="--psm 6")
            warnings.append("Chưa cài dữ liệu tiếng Việt cho Tesseract (vie.traineddata) nên đọc bằng tiếng Anh, "
                            "dấu tiếng Việt có thể sai.")
    except pytesseract.TesseractNotFoundError:
        raise InvoiceError("Chưa cài Tesseract OCR trên máy chạy backend (xem README, mục Cài đặt).", 503)
    result = parse_receipt_text(text)
    result["raw_text"] = text
    result["warnings"] = warnings
    return result


# ------------------------------------------------------------------ engine: Gemini
class _GItem(BaseModel):
    name: str
    quantity: float | None = None
    unit_price: int | None = None
    amount: int | None = None


class _GInvoice(BaseModel):
    store_name: str | None = None
    date: str | None = None
    total: int | None = None
    items: list[_GItem]


GEMINI_PROMPT = """Bạn là hệ thống trích xuất dữ liệu hóa đơn bán lẻ Việt Nam từ ảnh.
Hãy đọc ảnh và trả về JSON đúng schema. Quy tắc:
- items: mỗi dòng hàng hóa/dịch vụ một phần tử; name giữ nguyên tiếng Việt có dấu như trên hóa đơn.
- quantity: số lượng (mặc định 1 nếu hóa đơn không ghi). unit_price: đơn giá. amount: THÀNH TIỀN của dòng đó.
- Số tiền là số nguyên VND, không có dấu chấm/phẩy ngăn cách (ví dụ 32.000 -> 32000).
- date: định dạng YYYY-MM-DD. total: tổng tiền khách phải thanh toán.
- Không đưa dòng tổng cộng, thuế VAT, giảm giá, tiền khách đưa, tiền thừa vào items.
- Thông tin không đọc được hoặc không có thì để null. TUYỆT ĐỐI không bịa số liệu."""


# Google đổi/ngừng model liên tục (gemini-2.5-flash đã bị giới hạn từ 10/2026) nên không gắn cứng một tên.
# Thứ tự thử: model đã chạy được -> GEMINI_MODEL trong .env (nếu có) -> các model Flash mà key này thấy được
# (mới nhất trước) -> danh sách dự phòng.
GEMINI_FALLBACKS = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite",
                    "gemini-3.5-flash-lite", "gemini-3-flash-preview", "gemini-2.5-flash"]
_ok_model = None  # model đã gọi thành công, nhớ lại để lần quét sau không phải thử lại


def _gemini_models(client) -> list:
    found = []
    try:
        for m in client.models.list():
            n = (m.name or "").removeprefix("models/")
            if "generateContent" in (m.supported_actions or []) and re.fullmatch(r"gemini-\d+(?:\.\d+)?-flash(?:-lite)?", n):
                found.append(n)
    except Exception:
        pass  # không liệt kê được thì dùng danh sách dự phòng
    found.sort(key=lambda n: (float(re.match(r"gemini-(\d+(?:\.\d+)?)", n).group(1)), "lite" not in n), reverse=True)
    wanted = [x.strip() for x in os.environ.get("GEMINI_MODEL", "").split(",") if x.strip()]
    out = []
    for n in ([_ok_model] if _ok_model else []) + wanted + found + GEMINI_FALLBACKS:
        if n and n not in out:
            out.append(n)
    return out[:6]


def _explain_gemini_error(e) -> tuple:
    """Trả về (thông báo cho người dùng, có nên thử model khác không)."""
    code, low, kind = getattr(e, "code", None), str(e).lower(), type(e).__name__.lower()
    if code == 404 or "no longer available" in low or "is not found" in low:
        return "Model Gemini này không còn dùng được với key của bạn.", True
    if code == 429 or "resource_exhausted" in low or "quota" in low:
        return "Đã hết hạn mức gọi Gemini miễn phí (hoặc model này không có gói miễn phí), hãy thử lại sau ít phút.", True
    if "api key" in low or "api_key" in low or code in (401, 403):
        return "API key không hợp lệ hoặc không có quyền dùng Gemini. Hãy tạo key mới ở Google AI Studio và cập nhật backend/.env.", False
    if code in (500, 502, 503, 504) or "unavailable" in low or "overloaded" in low:
        return "Máy chủ Gemini đang quá tải, hãy thử lại sau.", True
    if "timeout" in kind or "timed out" in low:
        return "Gemini phản hồi quá lâu, hãy thử lại.", False
    if "connect" in kind or "getaddrinfo" in low or "network" in kind:
        return "Không kết nối được tới Google, hãy kiểm tra mạng hoặc VPN.", False
    return f"{type(e).__name__}: {str(e)[:200]}", False


def extract_gemini(data: bytes, img: Image.Image) -> dict:
    global _ok_model
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise InvoiceError("Chưa cấu hình GEMINI_API_KEY (xem file .env.example).", 503)
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise InvoiceError("Chưa cài google-genai (pip install google-genai).", 503)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)  # ảnh đã xoay đúng chiều và giảm kích thước
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=45_000))
    part = types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")
    # Không đặt temperature: Google khuyến nghị giữ mặc định cho dòng Gemini 3; schema đã ràng buộc đầu ra.
    cfg = types.GenerateContentConfig(response_mime_type="application/json", response_schema=_GInvoice)

    tried = []
    for model in _gemini_models(client):
        try:
            resp = client.models.generate_content(model=model, contents=[part, GEMINI_PROMPT], config=cfg)
            parsed = json.loads(resp.text or "")
        except json.JSONDecodeError:
            msg, retry = "Gemini trả về dữ liệu không đúng định dạng.", True
        except Exception as e:
            msg, retry = _explain_gemini_error(e)
        else:
            _ok_model = model
            parsed["warnings"], parsed["model"] = [], model
            return parsed
        if model == _ok_model:
            _ok_model = None
        if not retry:
            raise InvoiceError(msg, 502)
        tried.append(f"{model}: {msg}")
    raise InvoiceError("Không model Gemini nào gọi được. " + " | ".join(tried[-3:]), 502)


# ------------------------------------------------------------------ chuẩn hóa + kiểm tra chéo
def normalize(raw: dict) -> dict:
    """Làm sạch kết quả từ engine bất kỳ và kiểm tra tính nhất quán số liệu."""
    warnings = list(raw.get("warnings", []))
    items = []
    for it in raw.get("items") or []:
        name = re.sub(r"\s+", " ", str(it.get("name") or "")).strip()
        if not name:
            continue
        qty = it.get("quantity") or 1
        try:
            qty = float(qty)
        except (TypeError, ValueError):
            qty = 1.0
        if qty <= 0:
            qty = 1.0
        qty = int(qty) if float(qty).is_integer() else round(qty, 2)
        amount, unit = it.get("amount"), it.get("unit_price")
        if amount is None and unit:
            amount = int(round(unit * qty))
        if amount is None or amount <= 0:
            warnings.append(f"Dòng \"{name}\" không đọc được thành tiền, đã bỏ qua.")
            continue
        check = False
        if unit and abs(unit * qty - amount) > max(1000, 0.02 * amount):
            check = True
            warnings.append(f"Dòng \"{name}\": số lượng × đơn giá ({unit * qty:,.0f}) khác thành tiền ({amount:,}). "
                            "Hãy kiểm tra lại.")
        items.append({"name": name, "quantity": qty, "unit_price": unit, "amount": int(amount), "check": check})

    total = raw.get("total")
    s = sum(i["amount"] for i in items)
    if total and items and abs(s - total) > max(1000, 0.01 * total):
        warnings.append(f"Tổng các dòng ({s:,}) khác tổng hóa đơn ({total:,}). Có thể thiếu hoặc sai dòng.")
    if not items:
        warnings.append("Không tìm thấy dòng hàng hóa nào. Hãy chụp rõ hơn hoặc thêm thủ công.")

    d = raw.get("date")
    try:
        d = datetime.strptime(d, "%Y-%m-%d").date().isoformat() if d else None
    except ValueError:
        d = parse_date(str(d)) if d else None
    if not d:
        d = date.today().isoformat()
        warnings.append("Không đọc được ngày trên hóa đơn, đang dùng ngày hôm nay.")
    return {
        "store_name": (raw.get("store_name") or "").strip() or None,
        "date": d,
        "total": total or (s if items else None),
        "items": items,
        "warnings": warnings,
    }


def scan(data: bytes, engine: str = "auto") -> dict:
    img = load_image(data)
    used, extra = engine, []
    if engine == "gemini":
        raw = extract_gemini(data, img)
    elif engine == "tesseract":
        raw = extract_tesseract(img)
    else:  # auto: ưu tiên Gemini, lỗi thì lùi về Tesseract
        if os.environ.get("GEMINI_API_KEY"):
            try:
                raw, used = extract_gemini(data, img), "gemini"
            except InvoiceError as e:
                try:
                    raw, used = extract_tesseract(img), "tesseract"
                except InvoiceError as e2:  # hiện cả hai lỗi để biết đúng nguyên nhân
                    raise InvoiceError(f"Gemini lỗi: {e} | Tesseract cũng lỗi: {e2}", e.status)
                extra.append(f"Gemini lỗi ({e}); đã chuyển sang Tesseract nên kết quả có thể kém chính xác.")
        else:
            raw, used = extract_tesseract(img), "tesseract"
    out = normalize(raw)
    out["warnings"] = extra + out["warnings"]
    out["engine"] = used
    if raw.get("model"):
        out["model"] = raw["model"]
    if raw.get("raw_text") is not None:
        out["raw_text"] = raw["raw_text"]
    return out
