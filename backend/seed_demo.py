"""Nạp dữ liệu demo (3 tháng gần nhất) cho một tài khoản đã đăng ký.

Chạy (từ thư mục backend/):  python seed_demo.py email@cua-ban.com           # thêm dữ liệu demo
                              python seed_demo.py email@cua-ban.com --reset   # xóa dữ liệu của tài khoản đó rồi nạp lại
Nếu trong .env có DATABASE_URL thì nạp vào database đó (Postgres), ngược lại vào SQLite trên máy.
Cách dễ hơn: đăng nhập vào app rồi bấm "Nạp dữ liệu mẫu" ở màn hình Tổng quan.
"""
import os
import sys

try:  # đọc .env trước khi nạp app.db (để nhận DATABASE_URL)
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

from app import db  # noqa: E402
from app.demo_data import seed  # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit("Thiếu email. Ví dụ: python seed_demo.py email@cua-ban.com [--reset]")
    email = args[0].strip().lower()
    db.init_db()
    with db.session() as conn:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if not row:
        sys.exit(f"Không có tài khoản {email}. Hãy đăng ký trong app trước.")
    n_tx, n_budget = seed(row["id"], reset="--reset" in sys.argv)
    print(f"Đã nạp {n_tx} giao dịch demo và {n_budget} ngân sách cho {email} ({db.backend_name()}).")


if __name__ == "__main__":
    main()
