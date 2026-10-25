"""Tạo ảnh hóa đơn mẫu (tiếng Việt) để demo và kiểm thử OCR.

Chạy:  python make_sample_invoice.py   ->  hoadon_mau.png (+ hoadon_mau_nghieng.png: bản chụp lệch/mờ)
"""
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]
BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "C:/Windows/Fonts/consolab.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def pick(paths, size):
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


ITEMS = [
    ("Sữa tươi Vinamilk 1L", 2, 32000),
    ("Trứng gà (vỉ 10)", 1, 35000),
    ("Mì gói Hảo Hảo", 5, 4500),
    ("Nước rửa chén Sunlight", 1, 28000),
    ("Dầu gội Clear 340g", 1, 98000),
]


def fmt(n):
    return f"{n:,}".replace(",", ".")


def main():
    f, fb, fs = pick(FONT_CANDIDATES, 26), pick(BOLD_CANDIDATES, 30), pick(FONT_CANDIDATES, 22)
    W, H = 760, 820
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    y = 30
    d.text((W // 2, y), "SIÊU THỊ MINI BÁCH HÓA", font=fb, fill="black", anchor="mt"); y += 44
    d.text((W // 2, y), "12 Phố Huế, Hai Bà Trưng, Hà Nội", font=fs, fill="black", anchor="mt"); y += 32
    d.text((W // 2, y), "ĐT: 0243 123 4567", font=fs, fill="black", anchor="mt"); y += 44
    d.text((40, y), "HÓA ĐƠN BÁN LẺ", font=fb, fill="black"); y += 44
    d.text((40, y), "Ngày: 18/10/2026   Giờ: 18:42", font=f, fill="black"); y += 40
    d.line((40, y, W - 40, y), fill="black", width=2); y += 12
    d.text((40, y), "Tên hàng", font=fs, fill="black")
    d.text((420, y), "SL", font=fs, fill="black")
    d.text((470, y), "Đơn giá", font=fs, fill="black")
    d.text((W - 40, y), "T.Tiền", font=fs, fill="black", anchor="ra"); y += 34
    d.line((40, y, W - 40, y), fill="black", width=1); y += 14
    total = 0
    for name, qty, unit in ITEMS:
        amount = qty * unit
        total += amount
        d.text((40, y), name[:22], font=f, fill="black")
        d.text((425, y), str(qty), font=f, fill="black")
        d.text((470, y), fmt(unit), font=f, fill="black")
        d.text((W - 40, y), fmt(amount), font=f, fill="black", anchor="ra"); y += 40
    d.line((40, y, W - 40, y), fill="black", width=2); y += 16
    d.text((40, y), "TỔNG CỘNG", font=fb, fill="black")
    d.text((W - 40, y), fmt(total), font=fb, fill="black", anchor="ra"); y += 48
    d.text((40, y), "Tiền mặt", font=f, fill="black")
    d.text((W - 40, y), fmt(total + 4000), font=f, fill="black", anchor="ra"); y += 40
    d.text((W // 2, y + 10), "Cảm ơn quý khách!", font=f, fill="black", anchor="mt")
    img.save(os.path.join(HERE, "hoadon_mau.png"))

    # bản "chụp điện thoại": nghiêng, mờ nhẹ, nền xám, nhiễu
    random.seed(1)
    bg = Image.new("RGB", (W + 160, H + 160), (200, 198, 192))
    bg.paste(img.rotate(3, expand=True, fillcolor=(200, 198, 192)), (60, 60))
    bg = bg.filter(ImageFilter.GaussianBlur(0.9))
    px = bg.load()
    for _ in range(25000):
        x, yy = random.randrange(bg.width), random.randrange(bg.height)
        v = random.randint(-25, 25)
        r, g, b = px[x, yy]
        px[x, yy] = (max(0, min(255, r + v)),) * 3
    bg.save(os.path.join(HERE, "hoadon_mau_nghieng.png"))
    print("Tổng đúng:", fmt(total))


if __name__ == "__main__":
    main()
