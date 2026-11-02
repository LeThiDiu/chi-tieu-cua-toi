# Chi tiêu của tôi: quản lý chi tiêu cá nhân + nhận dạng hóa đơn

Chụp ảnh hóa đơn, app tự đọc **tên sản phẩm, số lượng, thành tiền**, tự gán **danh mục** bằng model AI, cho bạn **sửa lại nếu sai** rồi mới lưu. Dashboard dự báo chi tiêu cuối tháng, cảnh báo vượt ngân sách và chỉ ra khoản chi bất thường.

Đề tài thuộc **Hướng 4** trong tài liệu hướng dẫn của bộ môn (model có sẵn + model tự huấn luyện, kiến trúc Server/REST API).

## Chạy nhanh (Windows)

1. Cài Python 3.10 trở lên (tick "Add python.exe to PATH"). Không cần cài Node.js, giao diện đã build sẵn.
2. Giải nén, bấm đúp **`run.bat`**. Lần đầu script mở Notepad để bạn dán `GEMINI_API_KEY` (lấy miễn phí ở https://aistudio.google.com/apikey), rồi tự tạo môi trường ảo, cài thư viện (cần mạng, vài phút) và mở trình duyệt tại http://127.0.0.1:8000.
3. Đã có file `.env` từ bản cũ thì chép vào thư mục `backend/` trước khi chạy. **Không đưa `.env` lên GitHub.**

Tesseract chỉ là phương án dự phòng offline (xem mục Cài đặt bên dưới), không bắt buộc nếu Gemini chạy được.

## Kiến trúc

```
React (Vite)  ──HTTP/JSON──►  FastAPI  ──►  SQLite (giao dịch, hóa đơn, ngân sách)
 frontend/                    backend/      │
                                            ├─ Đọc hóa đơn:  Gemini Vision  hoặc  Tesseract OCR + parser
                                            ├─ Model tự huấn luyện: category_model.joblib (phân loại danh mục)
                                            └─ Thống kê: dự báo cuối tháng, cảnh báo ngân sách, chi tiêu bất thường
```

| Thành phần                             | Loại model                                           | Ở đâu                     |
| -------------------------------------- | ---------------------------------------------------- | ------------------------- |
| Đọc hóa đơn (ảnh → dòng hàng)          | Model có sẵn (cách B): Gemini Vision, hoặc Tesseract | `backend/app/invoice.py`  |
| Phân loại danh mục từ tên sản phẩm     | Tự huấn luyện (cách A): TF-IDF + Logistic Regression | `model/train_export.py`   |
| Dự báo, cảnh báo ngân sách, bất thường | Thống kê (trung bình có trọng số, median + MAD)      | `backend/app/insights.py` |

```
expense_ai/
  model/        gen_dataset.py, train_export.py, textnorm.py, data/product_names.csv
  backend/      app/ (main, db, invoice, classifier, insights), seed_demo.py, samples/, requirements.txt, .env.example
  frontend/     React + Vite (đã build sẵn trong frontend/dist)
  tests/        test_api.py
```

## Cài đặt (làm một lần)

**1. Python 3.10+**

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

**2. Tesseract OCR** (engine offline, cũng là phương án dự phòng khi Gemini lỗi)

- Windows: cài từ https://github.com/UB-Mannheim/tesseract/wiki, **tick chọn ngôn ngữ Vietnamese** khi cài. Rồi đặt `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe` trong `backend/.env`.
- Ubuntu: `sudo apt install tesseract-ocr tesseract-ocr-vie`
- macOS: `brew install tesseract tesseract-lang`

**3. Gemini API (khuyến nghị, đọc hóa đơn chính xác hơn)**: lấy key miễn phí tại https://aistudio.google.com/apikey, sao chép `backend/.env.example` thành `backend/.env` và điền `GEMINI_API_KEY`. Không có key vẫn chạy được bằng Tesseract. **Không commit file `.env`.** Để trống `GEMINI_MODEL` thì app tự chọn model Flash mới nhất mà key dùng được (Google ngừng/đổi tên model thường xuyên). Kiểm tra nhanh: `cd backend && python check_gemini.py` (in ra model đang dùng hoặc lý do lỗi cụ thể).

**4. Huấn luyện model phân loại** (bắt buộc chạy trên máy bạn để khớp phiên bản scikit-learn)

```bash
cd model
python gen_dataset.py     # sinh dữ liệu mẫu (có thể bỏ qua nếu đã có data/product_names.csv)
python train_export.py    # huấn luyện, in chỉ số, export category_model.joblib + model_metadata.json
```

## Chạy ứng dụng

```bash
cd backend
python seed_demo.py       # (tùy chọn) nạp 3 tháng dữ liệu demo để dashboard có số liệu
uvicorn app.main:app --port 8000
```

Mở **http://127.0.0.1:8000**: backend tự phục vụ giao diện đã build. Tài liệu API: http://127.0.0.1:8000/docs

**Chế độ phát triển giao diện** (cần Node.js 18+): mở terminal thứ hai

```bash
cd frontend
npm install
npm run dev               # http://localhost:5173, tự chuyển tiếp /api sang cổng 8000
```

Sau khi sửa giao diện, chạy `npm run build` để backend phục vụ bản mới.

## Deploy giao diện app lên Vercel

Giao diện có thể cài lên màn hình chính như app (PWA); API FastAPI vẫn cần chạy trên một dịch vụ riêng. Cấu hình mẫu cho Render nằm ở `render.yaml`.

1. Đẩy project lên GitHub, tạo Web Service trên Render từ repository này và dùng Blueprint (`render.yaml`). Nhập `GEMINI_API_KEY` trong phần Environment của Render để quét hóa đơn online bằng Gemini.
2. Deploy frontend trên Vercel từ cùng repository, đặt **Root Directory** là `frontend`. Vercel tự nhận cấu hình Vite và dùng `frontend/vercel.json` để điều hướng đường dẫn ứng dụng.
3. Trong Vercel, đặt biến môi trường `VITE_API_BASE_URL` thành URL backend Render, ví dụ `https://chi-tieu-api.onrender.com` (không thêm `/` ở cuối), rồi redeploy frontend.
4. Sao chép domain frontend Vercel (ví dụ `https://chi-tieu.vercel.app`) vào `CORS_ORIGINS` trên Render. Có thể nhập nhiều origin, phân tách bằng dấu phẩy. Lưu thay đổi và chờ backend khởi động lại.
5. Mở frontend qua HTTPS. Trên Android/Chrome chọn **Cài ứng dụng** nếu nút xuất hiện hoặc chọn **Thêm vào màn hình chính** trong menu trình duyệt. Trên iPhone dùng **Chia sẻ → Thêm vào màn hình chính** trong Safari.

Render Free có thể ngủ khi không sử dụng và hệ thống tệp của dịch vụ không bền vững; SQLite mặc định có thể mất dữ liệu khi dịch vụ khởi động lại/triển khai. Dùng dịch vụ lưu trữ bền vững cho dữ liệu thật. Gemini API key chỉ đặt ở backend, không đưa vào biến `VITE_*` hoặc mã frontend.

**Thử nhanh không cần ảnh thật:** dùng `backend/samples/hoadon_mau.png` và `hoadon_mau_nghieng.png` (tạo lại bằng `python backend/samples/make_sample_invoice.py`).

## Kiểm thử

```bash
python tests/test_api.py            # 32 ca: hợp lệ + không hợp lệ, in mã HTTP và thời gian
python tests/test_api.py --no-ocr   # bỏ các ca cần Tesseract
```

Test dùng CSDL tạm, không đụng dữ liệu thật và không gọi Gemini thật. Phần Gemini cần tự thử bằng key thật (xem mục dưới).

## API chính

| Method              | Đường dẫn                                 | Mô tả                                                                                           |
| ------------------- | ----------------------------------------- | ----------------------------------------------------------------------------------------------- |
| POST                | `/api/invoices/scan`                      | Ảnh (multipart `file`, `engine`: auto/gemini/tesseract) → dòng hàng + danh mục gợi ý. Chưa lưu. |
| POST                | `/api/invoices`                           | Lưu hóa đơn đã xác nhận (mỗi dòng là một giao dịch)                                             |
| GET/POST/PUT/DELETE | `/api/transactions`                       | Quản lý giao dịch                                                                               |
| POST                | `/api/categorize`                         | Phân loại danh sách tên sản phẩm                                                                |
| GET/PUT             | `/api/budgets`, `/api/budgets/{danh mục}` | Ngân sách theo danh mục                                                                         |
| GET                 | `/api/stats?month=YYYY-MM`                | Thống kê theo danh mục, xu hướng 6 tháng                                                        |
| GET                 | `/api/insights?month=YYYY-MM`             | Dự báo, cảnh báo ngân sách, bất thường, lời khuyên                                              |
| GET                 | `/api/model-info`                         | Metadata model (phiên bản, chỉ số đánh giá)                                                     |

## Vòng phản hồi (cải thiện model theo thời gian)

Khi người dùng **sửa danh mục** AI đã gán (trên màn hình quét hoặc trong danh sách giao dịch), cặp (tên, danh mục đúng) được ghi vào `model/data/feedback.csv`. Lần sau chạy `python train_export.py`, dữ liệu này tự được gộp vào huấn luyện. Đây chính là giai đoạn _Monitor_ trong vòng đời model ở tài liệu của bộ môn.

## Giới hạn đã biết (nên ghi trung thực trong báo cáo)

- **Model phân loại:** bộ dữ liệu đi kèm là **dữ liệu tổng hợp** (~2.100 dòng, 9 danh mục). Đánh giá theo cách chia theo tên sản phẩm gốc (sản phẩm _chưa từng gặp_) cho accuracy khoảng **48%**; với sản phẩm đã có trong dữ liệu thì rất cao. Con số 48% là mức trung thực cho tên hàng hoàn toàn mới và là lý do app luôn cho người dùng sửa danh mục. Muốn tốt hơn: thêm tên sản phẩm thật từ hóa đơn của nhóm vào `data/product_names.csv` (càng nhiều càng tốt) rồi huấn luyện lại. Xem `confusion_matrix` trong `model_metadata.json` để phân tích lỗi.
- **Tesseract** đọc tốt hóa đơn in rõ nét; hóa đơn nhiệt mờ, nhăn, chụp xa sẽ sai nhiều. Parser dựa trên quy tắc nên có thể sót dòng với bố cục lạ. Hệ thống kiểm tra chéo (SL × đơn giá = thành tiền, tổng các dòng = tổng hóa đơn) và cảnh báo khi lệch.
- **Gemini** chưa được kiểm thử với key thật trong bản này (không có key trong môi trường dựng). Code gọi Gemini nằm ở `extract_gemini` trong `backend/app/invoice.py`; hãy thử với vài hóa đơn thật và ghi kết quả vào báo cáo.
- Chưa có đăng nhập: một CSDL SQLite dùng chung cho một người dùng. Mở rộng: thêm bảng `users` và lọc theo `user_id`.
- Dự báo cuối tháng là ước lượng đơn giản (có kèm mức tin cậy), chưa phải mô hình chuỗi thời gian.

## Gợi ý đánh giá cho báo cáo

1. **OCR:** thu 30–50 hóa đơn thật (siêu thị, quán ăn, hiệu thuốc). Với mỗi hóa đơn, ghi số dòng đọc đúng/tổng số dòng, đúng thành tiền, đúng tổng; so sánh Gemini và Tesseract; ghi thời gian. Chụp cả ca xấu (mờ, nghiêng, thiếu sáng) và phân tích vì sao sai.
2. **Phân loại:** báo cáo accuracy, macro-F1, confusion matrix trước và sau khi bổ sung dữ liệu thật.
3. **Kiểm thử:** dán kết quả `tests/test_api.py` (các ca hợp lệ/không hợp lệ, mã HTTP, thời gian phản hồi).
4. **Quyền riêng tư:** nêu rõ khi dùng Gemini thì ảnh hóa đơn được gửi tới Google; Tesseract thì xử lý hoàn toàn trên máy.
   Các lần sau, mở lại thư mục và chạy:

bash
cd backend
source .venv/Scripts/activate
python -m uvicorn app.main:app --port 8000
#   c h i - t i e u - c u a - t o i 
 
 
Giao diện: https://chi-tieu-cua-toi-ohqp.vercel.app
Backend: https://chi-tieu-api-9sxg.onrender.com

Mở https://chi-tieu-api-9sxg.onrender.com/api/health và chờ 30-60 giây cho backend thức dậy, đến khi thấy status: ok.
Mở https://chi-tieu-cua-toi-ohqp.vercel.app rồi nhấn Ctrl + F5.
Dashboard sẽ tự có dữ liệu mẫu, bạn không phải nhập.

Nếu vào thẳng link Vercel mà thấy lỗi đỏ “Không kết nối được máy chủ” thì bạn chỉ cần chờ thêm một chút rồi tải lại.
