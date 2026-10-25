"""Nạp dữ liệu demo (3 tháng gần nhất) để dashboard có số liệu khi trình bày.

Chạy (từ thư mục backend/):  python seed_demo.py          # thêm dữ liệu demo
                              python seed_demo.py --reset  # xóa toàn bộ dữ liệu rồi nạp lại
"""
import random
import sys
from datetime import date, timedelta

from app import db

random.seed(7)
POOL = [  # (tên, danh mục, giá thấp, giá cao, số lần/tháng ~)
    ("Cơm tấm sườn bì chả", "Ăn uống", 40000, 55000, 10),
    ("Phở bò tái", "Ăn uống", 45000, 60000, 6),
    ("Bún chả", "Ăn uống", 40000, 50000, 4),
    ("Bánh mì thịt", "Ăn uống", 20000, 30000, 6),
    ("Cà phê sữa đá", "Đồ uống", 25000, 35000, 12),
    ("Trà sữa trân châu", "Đồ uống", 35000, 55000, 6),
    ("Sữa tươi Vinamilk 1L", "Thực phẩm", 30000, 34000, 4),
    ("Trứng gà", "Thực phẩm", 30000, 40000, 3),
    ("Mì gói Hảo Hảo", "Thực phẩm", 18000, 25000, 3),
    ("Nước rửa chén Sunlight", "Gia dụng", 25000, 32000, 1),
    ("Giấy vệ sinh Pulppy", "Gia dụng", 60000, 85000, 1),
    ("Dầu gội Clear", "Chăm sóc cá nhân", 90000, 120000, 1),
    ("Vitamin C 1000mg", "Y tế", 60000, 90000, 1),
    ("Cước Grab bike", "Di chuyển", 25000, 60000, 9),
    ("Xăng RON 95", "Di chuyển", 60000, 90000, 4),
    ("Photo tài liệu", "Học tập", 15000, 60000, 3),
    ("Bút bi Thiên Long", "Học tập", 10000, 25000, 1),
    ("Vé xem phim CGV", "Giải trí", 80000, 110000, 2),
    ("Nạp game Liên Quân", "Giải trí", 50000, 200000, 1),
]
BUDGETS = {"Ăn uống": 1500000, "Đồ uống": 600000, "Thực phẩm": 800000, "Di chuyển": 900000,
           "Giải trí": 500000, "Học tập": 400000}


def main():
    db.init_db()
    with db.session() as conn:
        if "--reset" in sys.argv:
            conn.execute("DELETE FROM transactions")
            conn.execute("DELETE FROM invoices")
            conn.execute("DELETE FROM budgets")
        today = date.today()
        start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        start = (start - timedelta(days=1)).replace(day=1)  # đầu tháng cách đây 2 tháng
        rows, d = [], start
        while d <= today:
            for name, cat, lo, hi, per_month in POOL:
                if random.random() < per_month / 30:
                    amt = round(random.randint(lo, hi), -3)
                    rows.append((d.isoformat(), name, 1, amt, cat, None))
            d += timedelta(days=1)
        # vài khoản bất thường để demo cảnh báo
        rows.append(((today - timedelta(days=3)).isoformat(), "Khám bệnh phòng khám", 1, 1450000, "Y tế", None))
        rows.append(((today - timedelta(days=5)).isoformat(), "Vé concert", 1, 1800000, "Giải trí", None))
        conn.executemany("INSERT INTO transactions(date,name,quantity,amount,category,store) VALUES (?,?,?,?,?,?)", rows)
        for c, v in BUDGETS.items():
            conn.execute("INSERT OR REPLACE INTO budgets(category, monthly_limit) VALUES (?,?)", (c, v))
    print(f"Đã nạp {len(rows)} giao dịch demo và {len(BUDGETS)} ngân sách.")


if __name__ == "__main__":
    main()
