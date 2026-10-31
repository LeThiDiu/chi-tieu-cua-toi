"""REST API cho ứng dụng quản lý chi tiêu + nhận dạng hóa đơn.

Chạy (từ thư mục backend/):  uvicorn app.main:app --reload --port 8000
Tài liệu API tương tác:       http://127.0.0.1:8000/docs
"""
import csv
import os
import re
import time
from contextlib import asynccontextmanager
from datetime import date, datetime

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import demo_data

try:  # nạp biến môi trường từ backend/.env nếu có
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
except ImportError:
    pass

from . import classifier, db, insights, invoice

DEFAULT_CATEGORIES = ["Ăn uống", "Đồ uống", "Thực phẩm", "Gia dụng", "Chăm sóc cá nhân",
                      "Y tế", "Di chuyển", "Học tập", "Giải trí", "Khác"]
FEEDBACK_CSV = os.path.join(classifier.MODEL_DIR, "data", "feedback.csv")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    # Render Free xóa ổ đĩa mỗi lần service ngủ/khởi động lại -> tự nạp dữ liệu demo khi database trống.
    # Mặc định chỉ bật trên Render (biến RENDER do Render tự đặt); bật/tắt thủ công bằng AUTO_SEED_DEMO=1/0.
    if os.environ.get("AUTO_SEED_DEMO", "1" if os.environ.get("RENDER") else "0") == "1":
        try:
            if demo_data.seed_if_empty():
                print("[INFO] Database trống -> đã nạp dữ liệu demo.")
        except Exception as e:  # không để lỗi seed làm sập API
            print(f"[CẢNH BÁO] Không nạp được dữ liệu demo: {e}")
    try:
        classifier.load_model()  # nạp model một lần khi khởi động
    except classifier.ModelNotReady as e:
        print(f"[CẢNH BÁO] {e}")
    yield


app = FastAPI(title="Expense AI API", version="1.0.0", lifespan=lifespan)
cors_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
cors_origins.extend(origin.strip() for origin in os.environ.get("CORS_ORIGINS", "").split(",") if origin.strip())
app.add_middleware(CORSMiddleware, allow_origins=cors_origins,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(invoice.InvoiceError)
async def invoice_error_handler(request, exc: invoice.InvoiceError):
    return JSONResponse(status_code=exc.status, content={"detail": str(exc)})


@app.exception_handler(classifier.ModelNotReady)
async def model_error_handler(request, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(RequestValidationError)
async def validation_handler(request, exc: RequestValidationError):
    # Thông báo lỗi dễ đọc: chỉ rõ trường nào sai
    msgs = [f"{'.'.join(str(p) for p in e['loc'] if p not in ('body', 'query'))}: {e['msg']}" for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "; ".join(msgs)})


# ------------------------------------------------------------------ schemas
def categories_list() -> list[str]:
    return classifier.categories() if classifier.is_ready() else DEFAULT_CATEGORIES


def _check_date(v: str) -> str:
    try:
        return datetime.strptime(v, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ValueError("ngày phải có dạng YYYY-MM-DD và hợp lệ")


class TxIn(BaseModel):
    date: str
    name: str = Field(..., min_length=1, max_length=200)
    quantity: float = Field(1, gt=0, le=100000)
    amount: int = Field(..., gt=0, le=10_000_000_000)
    category: str | None = None
    store: str | None = Field(None, max_length=200)
    note: str | None = Field(None, max_length=500)

    _d = field_validator("date")(_check_date)

    @field_validator("name")
    @classmethod
    def _strip(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("tên không được để trống")
        return v


class InvItemIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    quantity: float = Field(1, gt=0, le=100000)
    amount: int = Field(..., gt=0, le=10_000_000_000)
    category: str | None = None
    predicted_category: str | None = None  # để ghi nhận phản hồi khi người dùng sửa danh mục


class InvoiceSaveIn(BaseModel):
    store_name: str | None = Field(None, max_length=200)
    date: str
    items: list[InvItemIn] = Field(..., min_length=1, max_length=200)
    engine: str | None = None

    _d = field_validator("date")(_check_date)


class BudgetIn(BaseModel):
    monthly_limit: int = Field(..., ge=0, le=10_000_000_000)


class CategorizeIn(BaseModel):
    names: list[str] = Field(..., min_length=1, max_length=200)


def valid_month(month: str | None) -> str:
    if not month:
        return date.today().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise HTTPException(422, "month phải có dạng YYYY-MM")
    return month


def _resolve_category(name: str, category: str | None) -> str:
    cats = categories_list()
    if category:
        if category not in cats:
            raise HTTPException(422, f"Danh mục không hợp lệ: {category}. Hợp lệ: {', '.join(cats)}")
        return category
    if classifier.is_ready():
        return classifier.categorize([name])[0]["category"]
    return "Khác"


def _log_feedback(pairs: list[tuple[str, str]]):
    if not pairs:
        return
    new = not os.path.exists(FEEDBACK_CSV)
    os.makedirs(os.path.dirname(FEEDBACK_CSV), exist_ok=True)
    with open(FEEDBACK_CSV, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["name", "category"])
        w.writerows(pairs)


def _tx(row) -> dict:
    return dict(row)


# ------------------------------------------------------------------ hệ thống / model
@app.get("/api/health")
def health():
    return {"status": "ok", "model_ready": classifier.is_ready(),
            "gemini_configured": bool(os.environ.get("GEMINI_API_KEY"))}


@app.get("/api/model-info")
def model_info():
    """Metadata của model phân loại (giống /model-info trong ví dụ của tài liệu)."""
    if not classifier.is_ready():
        raise classifier.ModelNotReady("Chưa có model. Chạy: cd model && python train_export.py")
    m = {k: v for k, v in classifier.META.items() if k != "confusion_matrix"}
    m["gemini_configured"] = bool(os.environ.get("GEMINI_API_KEY"))
    return m


@app.get("/api/categories")
def get_categories():
    return {"categories": categories_list()}


@app.post("/api/categorize")
def categorize(body: CategorizeIn):
    names = [n.strip() for n in body.names if n.strip()]
    if not names:
        raise HTTPException(422, "names không có tên hợp lệ")
    return {"results": [{"name": n, **r} for n, r in zip(names, classifier.categorize(names))]}


# ------------------------------------------------------------------ hóa đơn
@app.post("/api/invoices/scan")
async def scan_invoice(file: UploadFile = File(...), engine: str = Form("auto")):
    """Nhận ảnh hóa đơn -> tên sản phẩm, số lượng, thành tiền + danh mục gợi ý. CHƯA lưu vào DB."""
    if engine not in ("auto", "gemini", "tesseract"):
        raise HTTPException(422, "engine phải là auto, gemini hoặc tesseract")
    data = await file.read()
    t0 = time.perf_counter()
    result = invoice.scan(data, engine)
    if result["items"] and classifier.is_ready():
        preds = classifier.categorize([i["name"] for i in result["items"]])
        for it, p in zip(result["items"], preds):
            it["category"], it["confidence"] = p["category"], p["confidence"]
    else:
        for it in result["items"]:
            it["category"], it["confidence"] = "Khác", 0.0
    result["elapsed_ms"] = round((time.perf_counter() - t0) * 1000)
    return result


@app.post("/api/invoices", status_code=201)
def save_invoice(body: InvoiceSaveIn):
    """Lưu hóa đơn đã được người dùng xác nhận: tạo 1 invoice + mỗi dòng hàng là một giao dịch."""
    resolved, feedback = [], []
    for it in body.items:
        cat = _resolve_category(it.name, it.category)
        resolved.append((it, cat))
        if it.category and it.predicted_category and it.category != it.predicted_category:
            feedback.append((it.name, it.category))
    total = sum(it.amount for it, _ in resolved)
    with db.session() as conn:
        cur = conn.execute("INSERT INTO invoices(store_name, date, total, engine) VALUES (?,?,?,?)",
                           (body.store_name, body.date, total, body.engine))
        inv_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO transactions(date,name,quantity,amount,category,store,invoice_id) VALUES (?,?,?,?,?,?,?)",
            [(body.date, it.name, it.quantity, it.amount, cat, body.store_name, inv_id) for it, cat in resolved],
        )
    _log_feedback(feedback)
    return {"invoice_id": inv_id, "saved": len(resolved), "total": total, "feedback_logged": len(feedback)}


# ------------------------------------------------------------------ giao dịch
@app.get("/api/transactions")
def list_transactions(month: str | None = None, category: str | None = None, q: str | None = None,
                      limit: int = Query(500, ge=1, le=2000)):
    sql, args = "SELECT * FROM transactions WHERE 1=1", []
    if month:
        first, last = insights.month_bounds(valid_month(month))
        sql += " AND date BETWEEN ? AND ?"
        args += [first.isoformat(), last.isoformat()]
    if category:
        sql += " AND category = ?"
        args.append(category)
    if q:
        sql += " AND name LIKE ?"
        args.append(f"%{q}%")
    sql += " ORDER BY date DESC, id DESC LIMIT ?"
    args.append(limit)
    with db.session() as conn:
        return {"items": [_tx(r) for r in conn.execute(sql, args)]}


@app.post("/api/transactions", status_code=201)
def create_transaction(tx: TxIn):
    cat = _resolve_category(tx.name, tx.category)
    with db.session() as conn:
        cur = conn.execute(
            "INSERT INTO transactions(date,name,quantity,amount,category,store,note) VALUES (?,?,?,?,?,?,?)",
            (tx.date, tx.name, tx.quantity, tx.amount, cat, tx.store, tx.note))
        return _tx(conn.execute("SELECT * FROM transactions WHERE id=?", (cur.lastrowid,)).fetchone())


@app.put("/api/transactions/{tx_id}")
def update_transaction(tx_id: int, tx: TxIn):
    cat = _resolve_category(tx.name, tx.category)
    with db.session() as conn:
        old = conn.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone()
        if not old:
            raise HTTPException(404, "Không tìm thấy giao dịch")
        conn.execute("UPDATE transactions SET date=?,name=?,quantity=?,amount=?,category=?,store=?,note=? WHERE id=?",
                     (tx.date, tx.name, tx.quantity, tx.amount, cat, tx.store, tx.note, tx_id))
        if tx.category and tx.category != old["category"]:
            _log_feedback([(tx.name, tx.category)])
        return _tx(conn.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone())


@app.delete("/api/transactions/{tx_id}", status_code=204)
def delete_transaction(tx_id: int):
    with db.session() as conn:
        if not conn.execute("DELETE FROM transactions WHERE id=?", (tx_id,)).rowcount:
            raise HTTPException(404, "Không tìm thấy giao dịch")


# ------------------------------------------------------------------ ngân sách / thống kê
@app.get("/api/budgets")
def get_budgets():
    with db.session() as conn:
        rows = {r["category"]: r["monthly_limit"] for r in conn.execute("SELECT * FROM budgets")}
    return {"budgets": [{"category": c, "monthly_limit": rows.get(c, 0)} for c in categories_list()]}


@app.put("/api/budgets/{category}")
def set_budget(category: str, body: BudgetIn):
    if category not in categories_list():
        raise HTTPException(422, f"Danh mục không hợp lệ: {category}")
    with db.session() as conn:
        if body.monthly_limit == 0:
            conn.execute("DELETE FROM budgets WHERE category=?", (category,))
        else:
            conn.execute("INSERT INTO budgets(category, monthly_limit) VALUES (?,?) "
                         "ON CONFLICT(category) DO UPDATE SET monthly_limit=excluded.monthly_limit",
                         (category, body.monthly_limit))
    return {"category": category, "monthly_limit": body.monthly_limit}


@app.get("/api/stats")
def stats(month: str | None = None):
    with db.session() as conn:
        return insights.monthly_stats(conn, valid_month(month))


@app.get("/api/insights")
def get_insights(month: str | None = None):
    """Hỗ trợ ra quyết định: dự báo cuối tháng, cảnh báo ngân sách, chi tiêu bất thường, lời khuyên."""
    with db.session() as conn:
        return insights.build_insights(conn, valid_month(month))


# ------------------------------------------------------------------ phục vụ giao diện đã build (tùy chọn)
_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "frontend", "dist")
if os.path.isdir(_DIST):
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="web")
