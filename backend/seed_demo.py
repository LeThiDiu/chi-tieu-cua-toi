"""Nạp dữ liệu demo (3 tháng gần nhất) để dashboard có số liệu khi trình bày.

Chạy (từ thư mục backend/):  python seed_demo.py          # thêm dữ liệu demo
                              python seed_demo.py --reset  # xóa toàn bộ dữ liệu rồi nạp lại
Nếu trong .env có DATABASE_URL thì dữ liệu được nạp vào database đó (Postgres), ngược lại vào SQLite trên máy.
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
    n_tx, n_budget = seed(reset="--reset" in sys.argv)
    print(f"Đã nạp {n_tx} giao dịch demo và {n_budget} ngân sách vào {db.backend_name()}.")


if __name__ == "__main__":
    main()
