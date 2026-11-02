"""Kịch bản kiểm thử API: đầu vào hợp lệ và không hợp lệ, so mã HTTP mong đợi, đo thời gian phản hồi.

Chạy (từ thư mục gốc project):   python tests/test_api.py
Không cần bật server: dùng TestClient + CSDL tạm, không đụng vào dữ liệu thật.
Thêm tham số  --no-ocr  để bỏ qua các ca cần Tesseract.
"""
import os
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.environ["EXPENSE_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.pop("GEMINI_API_KEY", None)  # test không gọi Gemini thật

from fastapi.testclient import TestClient  # noqa: E402

from app import db, main  # noqa: E402

main.FEEDBACK_CSV = os.path.join(tempfile.mkdtemp(), "feedback.csv")
SAMPLE = os.path.join(ROOT, "backend", "samples", "hoadon_mau.png")
SAMPLE_TILT = os.path.join(ROOT, "backend", "samples", "hoadon_mau_nghieng.png")
SKIP_OCR = "--no-ocr" in sys.argv

results = []


def check(name, expected, call, verify=None):
    t0 = time.perf_counter()
    r = call()
    ms = (time.perf_counter() - t0) * 1000
    ok = r.status_code == expected
    extra = ""
    if ok and verify:
        try:
            msg = verify(r)
            ok = msg is None or msg is True
            extra = "" if ok else f"  <- {msg}"
        except Exception as e:  # noqa: BLE001
            ok, extra = False, f"  <- verify lỗi: {e}"
    results.append(ok)
    print(f"[{'OK ' if ok else 'FAIL'}] {name:46s} HTTP {r.status_code} (mong đợi {expected}) - {ms:6.0f} ms{extra}")
    return r


def main_tests():
    with TestClient(main.app) as c:
        check("Health", 200, lambda: c.get("/api/health"), lambda r: r.json()["model_ready"] or "model chưa nạp")
        check("Model info có metrics", 200, lambda: c.get("/api/model-info"),
              lambda r: "accuracy" in r.json()["metrics_test"])

        # --- tài khoản: chưa đăng nhập thì bị chặn, đăng ký / đăng nhập / token
        check("Chưa đăng nhập: danh sách giao dịch bị chặn", 401, lambda: c.get("/api/transactions"))
        check("Chưa đăng nhập: thống kê bị chặn", 401, lambda: c.get("/api/stats"))
        check("Chưa đăng nhập: phân loại bị chặn", 401, lambda: c.post("/api/categorize", json={"names": ["a"]}))
        check("Token giả bị từ chối", 401, lambda: c.get("/api/auth/me", headers={"Authorization": "Bearer abc.def.ghi"}))
        # dữ liệu có từ trước khi có đăng nhập (user_id rỗng) -> tài khoản ĐẦU TIÊN nhận lại
        db.init_db()
        with db.session() as conn:
            conn.execute("INSERT INTO transactions(date,name,quantity,amount,category) VALUES ('2026-09-05','Dữ liệu cũ',1,12000,'Khác')")
            conn.execute("INSERT INTO budgets(category, monthly_limit) VALUES ('Khác', 500000)")
        reg = {"email": "Diu@Example.com", "password": "matkhau123", "name": "Diu"}
        r = check("Đăng ký tài khoản A", 201, lambda: c.post("/api/auth/register", json=reg),
                  lambda r: bool(r.json()["token"]) and r.json()["user"]["email"] == "diu@example.com" or r.json())
        token_a = r.json()["token"]
        check("Đăng ký: email trùng (không phân biệt hoa/thường)", 409,
              lambda: c.post("/api/auth/register", json={**reg, "email": "DIU@example.com"}))
        check("Đăng ký: mật khẩu quá ngắn", 422, lambda: c.post("/api/auth/register", json={**reg, "email": "x@y.vn", "password": "123"}))
        check("Đăng ký: email sai định dạng", 422, lambda: c.post("/api/auth/register", json={**reg, "email": "khong-phai-email"}))
        check("Đăng ký: tên rỗng", 422, lambda: c.post("/api/auth/register", json={**reg, "email": "x@y.vn", "name": "  "}))
        check("Đăng nhập đúng", 200, lambda: c.post("/api/auth/login", json={"email": "diu@example.com", "password": "matkhau123"}),
              lambda r: bool(r.json()["token"]))
        check("Đăng nhập: sai mật khẩu", 401, lambda: c.post("/api/auth/login", json={"email": "diu@example.com", "password": "saimatkhau"}))
        check("Đăng nhập: email không tồn tại", 401, lambda: c.post("/api/auth/login", json={"email": "ai@do.vn", "password": "matkhau123"}))
        c.headers["Authorization"] = f"Bearer {token_a}"
        check("Lấy thông tin tài khoản (/me)", 200, lambda: c.get("/api/auth/me"),
              lambda r: r.json()["user"]["name"] == "Diu" or r.json())
        check("Tài khoản đầu tiên nhận lại dữ liệu cũ", 200, lambda: c.get("/api/transactions?month=2026-09"),
              lambda r: [i["name"] for i in r.json()["items"]] == ["Dữ liệu cũ"] or r.json())
        check("Dữ liệu cũ kèm cả ngân sách cũ", 200, lambda: c.get("/api/budgets"),
              lambda r: any(b["category"] == "Khác" and b["monthly_limit"] == 500000 for b in r.json()["budgets"]) or r.json())

        # --- phân loại
        check("Phân loại: cà phê -> Đồ uống", 200, lambda: c.post("/api/categorize", json={"names": ["Cà phê sữa đá"]}),
              lambda r: r.json()["results"][0]["category"] == "Đồ uống" or r.json())
        check("Phân loại: không dấu (Grab)", 200, lambda: c.post("/api/categorize", json={"names": ["Cuoc Grab bike"]}),
              lambda r: r.json()["results"][0]["category"] == "Di chuyển" or r.json())
        check("Phân loại: danh sách rỗng", 422, lambda: c.post("/api/categorize", json={"names": []}))
        check("Phân loại: thiếu trường", 422, lambda: c.post("/api/categorize", json={}))

        # --- giao dịch
        good = {"date": "2026-10-20", "name": "Trà sữa trân châu", "amount": 45000, "quantity": 1}
        r = check("Tạo giao dịch hợp lệ (tự gán danh mục)", 201, lambda: c.post("/api/transactions", json=good),
                  lambda r: r.json()["category"] == "Đồ uống" or r.json())
        tx_id = r.json()["id"]
        check("Tạo giao dịch: ngày sai định dạng", 422, lambda: c.post("/api/transactions", json={**good, "date": "20/10/2026"}))
        check("Tạo giao dịch: số tiền âm", 422, lambda: c.post("/api/transactions", json={**good, "amount": -5}))
        check("Tạo giao dịch: số tiền là chữ", 422, lambda: c.post("/api/transactions", json={**good, "amount": "abc"}))
        check("Tạo giao dịch: tên rỗng", 422, lambda: c.post("/api/transactions", json={**good, "name": "  "}))
        check("Tạo giao dịch: danh mục không tồn tại", 422, lambda: c.post("/api/transactions", json={**good, "category": "Xyz"}))
        check("Sửa giao dịch (đổi danh mục)", 200,
              lambda: c.put(f"/api/transactions/{tx_id}", json={**good, "category": "Giải trí"}),
              lambda r: r.json()["category"] == "Giải trí")
        check("Sửa giao dịch không tồn tại", 404, lambda: c.put("/api/transactions/99999", json=good))
        check("Danh sách theo tháng", 200, lambda: c.get("/api/transactions?month=2026-10"),
              lambda r: len(r.json()["items"]) == 1)
        check("Danh sách: tháng sai định dạng", 422, lambda: c.get("/api/transactions?month=2026-13"))
        check("Xóa giao dịch", 204, lambda: c.delete(f"/api/transactions/{tx_id}"))
        check("Xóa giao dịch đã xóa", 404, lambda: c.delete(f"/api/transactions/{tx_id}"))

        # --- hóa đơn
        check("Scan: file không phải ảnh", 422,
              lambda: c.post("/api/invoices/scan", files={"file": ("a.txt", b"hello", "text/plain")}))
        check("Scan: file rỗng", 422, lambda: c.post("/api/invoices/scan", files={"file": ("a.png", b"", "image/png")}))
        check("Scan: engine không hợp lệ", 422,
              lambda: c.post("/api/invoices/scan", data={"engine": "abc"}, files={"file": ("a.png", b"x", "image/png")}))
        check("Scan: Gemini khi chưa có API key", 503,
              lambda: c.post("/api/invoices/scan", data={"engine": "gemini"},
                             files={"file": ("a.png", open(SAMPLE, "rb").read(), "image/png")}))
        scan_result = {}
        if not SKIP_OCR:
            for label, path in [("hóa đơn rõ", SAMPLE), ("hóa đơn chụp nghiêng/mờ", SAMPLE_TILT)]:
                def verify(r):
                    d = r.json()
                    names = " | ".join(i["name"] for i in d["items"])
                    scan_result[label] = d
                    if len(d["items"]) != 5:
                        return f"đọc được {len(d['items'])}/5 dòng: {names}"
                    if d["total"] != 247500 or sum(i["amount"] for i in d["items"]) != 247500:
                        return f"tổng sai: {d['total']}"
                    return True
                check(f"Scan Tesseract: {label} (5 dòng, tổng 247.500)", 200,
                      lambda p=path: c.post("/api/invoices/scan", data={"engine": "tesseract"},
                                            files={"file": ("hd.png", open(p, "rb").read(), "image/png")}), verify)

        # --- lưu hóa đơn đã xác nhận + phản hồi danh mục
        payload = {"store_name": "Bách Hóa", "date": "2026-10-18", "engine": "tesseract", "items": [
            {"name": "Sữa tươi Vinamilk 1L", "quantity": 2, "amount": 64000, "category": "Thực phẩm",
             "predicted_category": "Thực phẩm"},
            {"name": "Nước rửa chén Sunlight", "quantity": 1, "amount": 28000, "category": "Chăm sóc cá nhân",
             "predicted_category": "Gia dụng"},
        ]}
        check("Lưu hóa đơn (2 dòng, 1 dòng sửa danh mục)", 201, lambda: c.post("/api/invoices", json=payload),
              lambda r: (r.json()["saved"] == 2 and r.json()["total"] == 92000 and r.json()["feedback_logged"] == 1) or r.json())
        check("Lưu hóa đơn: không có dòng nào", 422, lambda: c.post("/api/invoices", json={**payload, "items": []}))
        check("Lưu hóa đơn: dòng có số tiền 0", 422,
              lambda: c.post("/api/invoices", json={**payload, "items": [{"name": "A", "amount": 0}]}))

        # --- ngân sách, thống kê, hỗ trợ quyết định
        check("Đặt ngân sách", 200, lambda: c.put("/api/budgets/Thực phẩm", json={"monthly_limit": 100000}))
        check("Đặt ngân sách: danh mục lạ", 422, lambda: c.put("/api/budgets/Xyz", json={"monthly_limit": 100000}))
        check("Đặt ngân sách: số âm", 422, lambda: c.put("/api/budgets/Thực phẩm", json={"monthly_limit": -1}))
        check("Thống kê tháng", 200, lambda: c.get("/api/stats?month=2026-10"),
              lambda r: r.json()["total"] == 92000 or r.json()["total"])
        check("Insights: cảnh báo ngân sách Thực phẩm (64k/100k)", 200, lambda: c.get("/api/insights?month=2026-10"),
              lambda r: any(a["category"] == "Thực phẩm" and a["status"] in ("ok", "at_risk", "warning")
                            for a in r.json()["budget_alerts"]) or r.json()["budget_alerts"])

        # --- tách dữ liệu giữa các tài khoản
        check("Đăng ký tài khoản B", 201,
              lambda: c.post("/api/auth/register", json={"email": "b@example.com", "password": "matkhau456", "name": "B"}))
        token_b = c.post("/api/auth/login", json={"email": "b@example.com", "password": "matkhau456"}).json()["token"]
        hb = {"Authorization": f"Bearer {token_b}"}
        check("B không thấy giao dịch của A", 200, lambda: c.get("/api/transactions?limit=2000", headers=hb),
              lambda r: r.json()["items"] == [] or f"B thấy {len(r.json()['items'])} giao dịch")
        check("B không nhận dữ liệu cũ (chỉ tài khoản đầu tiên)", 200, lambda: c.get("/api/transactions?month=2026-09", headers=hb),
              lambda r: r.json()["items"] == [])
        check("B: thống kê trống", 200, lambda: c.get("/api/stats?month=2026-10", headers=hb), lambda r: r.json()["total"] == 0)
        check("B: ngân sách của B không có giá trị của A", 200, lambda: c.get("/api/budgets", headers=hb),
              lambda r: all(b["monthly_limit"] == 0 for b in r.json()["budgets"]) or r.json())
        a_id = c.get("/api/transactions?month=2026-10").json()["items"][0]["id"]
        check("B sửa giao dịch của A -> 404", 404, lambda: c.put(f"/api/transactions/{a_id}", json=good, headers=hb))
        check("B xóa giao dịch của A -> 404", 404, lambda: c.delete(f"/api/transactions/{a_id}", headers=hb))
        check("A vẫn còn giao dịch của mình", 200, lambda: c.get("/api/transactions?month=2026-10"),
              lambda r: any(i["id"] == a_id for i in r.json()["items"]))
        check("B nạp dữ liệu mẫu cho riêng B", 200, lambda: c.post("/api/demo/seed", headers=hb),
              lambda r: r.json()["seeded"] is True)
        check("B nạp lần hai: không nạp trùng", 200, lambda: c.post("/api/demo/seed", headers=hb),
              lambda r: r.json()["seeded"] is False)
        check("Dữ liệu mẫu của B không lọt sang A", 200, lambda: c.get("/api/transactions?month=2026-10"),
              lambda r: len(r.json()["items"]) == 2 or f"A có {len(r.json()['items'])} giao dịch tháng 10")
    passed = sum(results)
    print(f"\nKết quả: {passed}/{len(results)} ca đạt")
    return passed == len(results)


if __name__ == "__main__":
    sys.exit(0 if main_tests() else 1)
