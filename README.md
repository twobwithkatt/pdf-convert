# Ứng Dụng Quét Số Seri & Đổi Tên File PDF Tự Động (Sổ Đỏ / Sổ Hồng)

Ứng dụng Desktop viết bằng **PySide6 (Qt)** giúp tự động quét số seri phôi trên Giấy chứng nhận quyền sử dụng đất (ví dụ: `BH 807694`) và đổi tên file an toàn theo cơ chế batch (hỗ trợ tới 500 file một đợt).

---

## ✨ Tính Năng Nổi Bật

- **Giao diện trực quan**: Hỗ trợ Kéo & Thả (Drag & Drop) cả file hoặc cả thư mục chứa file PDF.
- **Xử lý Batch mượt mà**: Chạy trên luồng Worker riêng (`QThread`), không làm đơ giao diện; tự động giải phóng RAM sau mỗi file.
- **Nhận diện chính xác 100%**: Xử lý lọc hoa văn bảo an màu hồng chìm (Guilloche pattern) và tự động nhận diện chữ xoay dọc (0°, 90°, 180°, 270°).
- **Tuyệt đối an toàn dữ liệu**:
  - Không sửa đổi hoặc ghi đè file gốc (`shutil.copy2`).
  - Tự động chống trùng tên (`BH 807694 (1).pdf`, `BH 807694 (2).pdf`).
  - Gom file không nhận diện được vào thư mục `_CHUA_NHAN_DIEN/`.
- **Báo cáo đối soát CSV**: Xuất chi tiết danh sách file trước và sau khi đổi tên kèm thời gian xử lý.
- **Đa nền tảng**: Hoạt động hoàn hảo trên **macOS** (Apple Silicon / Intel) và **Windows 10 / 11**.

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Trực Tiếp

### 1. Yêu cầu hệ thống
- Python 3.9 trở lên
- *(Tùy chọn)* Đã cài Tesseract OCR:
  - Trên macOS: `brew install tesseract`
  - Trên Windows: Tải từ [UB-Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)

### 2. Cài đặt thư viện
```bash
# Tạo môi trường ảo
python3 -m venv venv

# Kích hoạt môi trường ảo:
# Trên macOS/Linux:
source venv/bin/activate
# Trên Windows:
venv\Scripts\activate

# Cài đặt thư viện:
pip install -r requirements.txt
```

### 3. Chạy ứng dụng
```bash
python main.py
```

---

## 📦 Hướng Dẫn Đóng Gói (Build App & Exe)

### Đóng gói cho macOS (`.app`)
Chạy lệnh trong terminal:
```bash
chmod +x build_scripts/build_mac.sh
./build_scripts/build_mac.sh
```
File ứng dụng sẽ xuất hiện tại thư mục `dist/PDFSerialRenamer.app`.

### Đóng gói cho Windows (`.exe`)
Chạy file batch trên máy Windows:
```cmd
build_scripts\build_win.bat
```
File ứng dụng sẽ xuất hiện tại thư mục `dist\PDFSerialRenamer\PDFSerialRenamer.exe`.
