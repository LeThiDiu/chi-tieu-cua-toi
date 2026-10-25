"""Sinh bộ dữ liệu tên sản phẩm -> danh mục (tiếng Việt) để huấn luyện model phân loại.

Mỗi danh mục có danh sách "tên gốc"; script nhân bản bằng kích cỡ/thương hiệu và
thêm nhiễu giống lỗi OCR (bỏ dấu, viết hoa, rơi ký tự).
Cột `group` = tên gốc, dùng để chia train/test không bị rò rỉ dữ liệu.

Chạy:  python gen_dataset.py   ->  data/product_names.csv

LƯU Ý CHO BÁO CÁO: đây là dữ liệu tổng hợp để khởi động nhanh. Nhóm nên bổ sung
tên sản phẩm lấy từ hóa đơn thật (sửa trực tiếp file CSV) rồi huấn luyện lại.
"""
import csv
import os
import random
import unicodedata

random.seed(42)

BASE = {
    "Ăn uống": [
        "Phở bò tái", "Phở gà", "Bún chả", "Bún bò Huế", "Bún riêu cua", "Cơm tấm sườn bì chả",
        "Cơm gà xối mỡ", "Cơm rang dưa bò", "Bánh mì thịt", "Bánh mì trứng ốp la", "Xôi xéo",
        "Mì xào hải sản", "Hủ tiếu nam vang", "Bánh cuốn nóng", "Lẩu thái hải sản", "Gà rán",
        "Pizza hải sản", "Hamburger bò", "Khoai tây chiên", "Cơm văn phòng", "Mì cay cấp độ 3",
        "Bánh xèo", "Chả giò chiên", "Gỏi cuốn tôm thịt", "Cháo sườn", "Cơm niêu cá kho",
        "Bún đậu mắm tôm", "Nem nướng Nha Trang", "Cơm chiên dương châu", "Mì quảng",
    ],
    "Đồ uống": [
        "Trà sữa trân châu", "Cà phê sữa đá", "Cà phê đen", "Bạc xỉu", "Trà đào cam sả",
        "Trà vải", "Sinh tố bơ", "Nước cam ép", "Nước mía", "Matcha latte", "Americano",
        "Cappuccino", "Trà chanh giã tay", "Sữa chua trân châu", "Nước dừa", "Coca Cola lon",
        "Pepsi chai", "Nước suối Aquafina", "Trà xanh không độ", "Red Bull", "Sting dâu",
        "Bia Tiger lon", "Bia Hà Nội chai", "Nước ép dưa hấu", "Smoothie xoài", "Trà tắc",
        "Nước khoáng Lavie", "Cacao đá xay",
    ],
    "Thực phẩm": [
        "Sữa tươi Vinamilk", "Sữa chua có đường", "Trứng gà", "Gạo ST25", "Dầu ăn Simply",
        "Nước mắm Nam Ngư", "Đường trắng", "Muối i-ốt", "Mì gói Hảo Hảo", "Mì Omachi",
        "Thịt ba chỉ", "Thịt bò xay", "Ức gà phi lê", "Cá hồi phi lê", "Tôm sú", "Rau muống",
        "Cải thảo", "Cà chua", "Khoai tây", "Hành tây", "Chuối", "Táo Fuji", "Cam sành",
        "Xúc xích Vissan", "Bánh quy Oreo", "Snack Oishi", "Đậu hũ", "Cà rốt",
        "Bánh mì sandwich", "Phô mai Con Bò Cười", "Sữa đặc Ông Thọ", "Tương ớt Chinsu",
        "Nấm rơm", "Bắp cải", "Dưa leo", "Sữa đậu nành Fami", "Bơ lạt", "Cá thu đông lạnh",
    ],
    "Gia dụng": [
        "Nước rửa chén Sunlight", "Nước lau sàn Sunlight", "Bột giặt OMO", "Nước xả vải Comfort",
        "Giấy vệ sinh Pulppy", "Khăn giấy rút", "Túi rác đen", "Bóng đèn LED 9W", "Pin AA Panasonic",
        "Ổ cắm điện 3 lỗ", "Chổi quét nhà", "Cây lau nhà", "Bình nước giữ nhiệt", "Hộp đựng thực phẩm",
        "Nước tẩy Javel", "Nước rửa tay Lifebuoy", "Bàn chải chà sàn", "Màng bọc thực phẩm",
        "Dây điện nối dài", "Kéo cắt", "Băng keo trong", "Móc treo quần áo", "Xịt phòng Glade",
        "Thùng rác nhỏ", "Găng tay cao su", "Nước giặt Ariel", "Khăn lau đa năng",
    ],
    "Chăm sóc cá nhân": [
        "Dầu gội Clear", "Dầu gội Sunsilk", "Sữa tắm Dove", "Sữa rửa mặt Cetaphil", "Kem đánh răng PS",
        "Bàn chải đánh răng", "Kem chống nắng Anessa", "Son dưỡng môi", "Lăn khử mùi Nivea",
        "Dao cạo râu Gillette", "Băng vệ sinh Diana", "Khẩu trang y tế", "Nước hoa hồng Thayers",
        "Sữa dưỡng thể Vaseline", "Xà phòng Lifebuoy", "Dầu xả Pantene", "Nước súc miệng Listerine",
        "Tẩy trang Garnier", "Kem dưỡng da tay", "Mặt nạ giấy", "Cắt tóc nam", "Gội đầu massage",
        "Làm móng tay", "Tăm bông", "Bông tẩy trang",
    ],
    "Y tế": [
        "Paracetamol 500mg", "Vitamin C 1000mg", "Thuốc cảm Decolgen", "Thuốc ho Prospan",
        "Oresol", "Men tiêu hóa Biolactyl", "Băng cá nhân Urgo", "Cồn y tế 70 độ", "Nước muối sinh lý",
        "Thuốc đau bụng Buscopan", "Dầu gió xanh", "Cao dán Salonpas", "Khám bệnh phòng khám",
        "Xét nghiệm máu", "Kem bôi da Gentrisone", "Thuốc nhỏ mắt V.Rohto", "Khẩu trang N95",
        "Nhiệt kế điện tử", "Viên uống Omega 3", "Thuốc dạ dày Phosphalugel", "Kẽm Zinc",
        "Thuốc hạ sốt trẻ em", "Gạc y tế vô trùng", "Khám răng", "Canxi D3",
    ],
    "Di chuyển": [
        "Cước Grab bike", "Cước GrabCar", "Cước Be bike", "Taxi Mai Linh", "Vé xe buýt",
        "Vé tàu điện Cát Linh", "Xăng RON 95", "Xăng E5 RON 92", "Đổ xăng xe máy", "Gửi xe máy",
        "Phí gửi xe ô tô", "Vé xe khách Hà Nội Hải Phòng", "Vé tàu hỏa Hà Nội Vinh",
        "Vé máy bay Vietjet", "Phí cầu đường", "Rửa xe máy", "Thay nhớt xe máy", "Vá lốp xe",
        "Bảo dưỡng xe", "Vé xe limousine", "Gojek bike", "Xanh SM taxi điện", "Phí BOT",
        "Bơm hơi lốp",
    ],
    "Học tập": [
        "Vở ô ly 200 trang", "Bút bi Thiên Long", "Bút chì 2B", "Bút highlight", "Sách giáo trình",
        "Photo tài liệu", "In tài liệu A4", "Giấy A4 Double A", "Cặp sách", "Máy tính Casio fx-580",
        "Thước kẻ 30cm", "Sổ tay bìa cứng", "Khóa học online", "Học phí tiếng Anh", "Sách tham khảo",
        "USB 32GB", "Chuột máy tính", "Bàn phím cơ", "Gia hạn Microsoft 365", "Bìa còng", "Tập vẽ A3",
        "Kẹp giấy", "Mực in Canon", "Đóng quyển báo cáo", "Thẻ thư viện",
    ],
    "Giải trí": [
        "Vé xem phim CGV", "Vé xem phim Lotte", "Bắp rang bơ", "Nạp game Liên Quân", "Nạp thẻ Steam",
        "Netflix gói tháng", "Spotify Premium", "YouTube Premium", "Karaoke 2 giờ", "Vé công viên nước",
        "Vé concert", "Sách truyện tranh", "Bowling 2 ván", "Billiards 1 giờ", "Net quán 3 giờ",
        "Vé tham quan bảo tàng", "Board game cafe", "Đồ chơi lego", "Nạp thẻ Garena",
        "Vé sự kiện âm nhạc", "Thuê sân cầu lông", "Thuê sân bóng mini", "Gói tập gym tháng",
        "Vé trò chơi khu vui chơi",
    ],
}

SIZES = ["", "", "", " 1L", " 500ml", " 330ml", " 250g", " 1kg", " x2", " (size M)", " (size L)",
         " loại lớn", " loại nhỏ", " combo", " 2 phần", " 100g", " hộp", " chai", " gói", " túi"]
PREFIX = ["", "", "", "", "SP ", "Hàng ", ""]


def strip_accents(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def ocr_noise(s: str) -> str:
    r = random.random()
    if r < 0.25:
        s = strip_accents(s)
    elif r < 0.35:
        s = s.upper()
    elif r < 0.45:
        s = strip_accents(s).upper()
    if len(s) > 6 and random.random() < 0.15:  # đánh rơi một ký tự
        i = random.randrange(1, len(s) - 1)
        s = s[:i] + s[i + 1:]
    if random.random() < 0.08 and "o" in s:  # nhầm o -> 0
        s = s.replace("o", "0", 1)
    return s


def main():
    rows = []
    for cat, names in BASE.items():
        for base in names:
            seen = set()
            for _ in range(8):
                text = ocr_noise(random.choice(PREFIX) + base + random.choice(SIZES))
                if text not in seen:
                    seen.add(text)
                    rows.append((text, cat, base))
            rows.append((base, cat, base))
    random.shuffle(rows)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "product_names.csv")
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "category", "group"])
        w.writerows(rows)
    print(f"Đã ghi {len(rows)} dòng, {len(BASE)} danh mục -> {out}")


if __name__ == "__main__":
    main()
