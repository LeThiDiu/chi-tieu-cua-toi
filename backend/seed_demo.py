"""Nạp dữ liệu demo (3 tháng gần nhất) để dashboard có số liệu khi trình bày.

Chạy (từ thư mục backend/):  python seed_demo.py          # thêm dữ liệu demo
                              python seed_demo.py --reset  # xóa toàn bộ dữ liệu rồi nạp lại
"""
import sys

from app.demo_data import seed


def main():
    n_tx, n_budget = seed(reset="--reset" in sys.argv)
    print(f"Đã nạp {n_tx} giao dịch demo và {n_budget} ngân sách.")


if __name__ == "__main__":
    main()
