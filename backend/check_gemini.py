"""Kiểm tra nhanh Gemini có gọi được không. Chạy trong thư mục backend:
    python check_gemini.py                  (dùng ảnh mẫu)
    python check_gemini.py duong_dan_anh.jpg"""
import os
import sys
import time

from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))
from app import invoice  # noqa: E402

if not os.environ.get("GEMINI_API_KEY"):
    sys.exit("[LỖI] Chưa có GEMINI_API_KEY trong backend/.env")
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "samples", "hoadon_mau.png")
data = open(path, "rb").read()
t = time.time()
try:
    r = invoice.normalize(invoice.extract_gemini(data, invoice.load_image(data)))
except invoice.InvoiceError as e:
    sys.exit(f"[LỖI] {e}")
print(f"[OK] {time.time() - t:.1f}s, model {invoice._ok_model}: {r['store_name']} | {r['date']} | tổng {r['total']}")
for i in r["items"]:
    print("  ", i["name"], i["quantity"], i["unit_price"], i["amount"])
for w in r["warnings"]:
    print("  !", w)
