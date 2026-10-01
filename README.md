# Ứng Dụng Quét Số Seri & Đổi Tên File PDF Tự Động (Sổ Đỏ / Sổ Hồng)

Ứng dụng Desktop viết bằng **PySide6 (Qt)** giúp tự động quét số seri phôi trên Giấy chứng nhận quyền sử dụng đất (ví dụ: `BH 807694`) và đổi tên file an toàn theo cơ chế batch (hỗ trợ tới 500 file một đợt).

---

## ✨ Tính Năng Nổi Bật

- **Giao diện trực quan**: Hỗ trợ Kéo & Thả (Drag & Drop) cả file hoặc cả thư mục chứa file PDF.
- **Xử lý Batch mượt mà**: Chạy trên luồng Worker riêng (`QThread`), không làm đơ giao diện; tự động giải phóng RAM sau mỗi file.
- **Hỗ trợ nhận diện seri**: Xử lý lọc hoa văn bảo an màu hồng chìm (Guilloche pattern) và nhận diện chữ xoay dọc (0°, 90°, 180°, 270°); kết quả OCR cần được đối chiếu với bản gốc.
- **Hỗ trợ PDF nhiều trang**: Quét các trang để tìm bìa đỏ “Giấy chứng nhận quyền sử dụng đất”, sau đó đọc seri ở góc dưới phải (ví dụ: `BS 208130`).
- **Tách GCN tùy chọn**: Giữ PDF đầy đủ và tạo một PDF riêng cho từng bìa GCN cùng trang ngay sau nó, kể cả khi một file có nhiều GCN.
- **Bảo vệ tệp gốc**:
  - Không sửa đổi hoặc ghi đè file gốc (`shutil.copy2`).
  - Tự động chống trùng tên (`BH 807694 (1).pdf`, `BH 807694 (2).pdf`).
  - Gom file không nhận diện được vào thư mục `_CHUA_NHAN_DIEN/`.
- **Báo cáo đối soát CSV**: Xuất chi tiết danh sách file trước và sau khi đổi tên kèm thời gian xử lý.
- **Đa nền tảng**: Hỗ trợ **macOS** (Apple Silicon / Intel) và **Windows 10 / 11**.
- **Điều khoản và kích hoạt**: Hiển thị điều khoản mỗi lần mở; cần đồng ý và nhập một key chưa dùng. Mỗi key chỉ mở một phiên và được tính là đã dùng khi đóng ứng dụng.

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Trực Tiếp

Các mẫu sổ đỏ/sổ hồng cũ vẫn được quét ở trang đầu hoặc trang cuối. Với PDF nhiều trang có bìa Giấy chứng nhận quyền sử dụng đất, ứng dụng dò trang bìa màu hoặc scan trắng đen rồi dùng seri tìm được theo đúng mẫu đổi tên đã chọn. Bật “Tách từng GCN (bìa + trang kế tiếp) thành PDF riêng” để giữ PDF đầy đủ và tạo một PDF riêng cho mỗi bìa cùng trang ngay sau nó.

### 1. Yêu cầu hệ thống
- Python 3.9 trở lên
- Đã cài Tesseract OCR nếu cần quét PDF dạng ảnh (PDF có lớp text có thể đọc trực tiếp):
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
Khi mở ứng dụng, người dùng cần đọc và đồng ý với điều khoản, sau đó nhập một trong 30 key được cấp. Trạng thái key được lưu cục bộ theo tài khoản người dùng trên máy này; key đã dùng không được dùng lại trên cùng trạng thái cài đặt. Nếu ứng dụng bị buộc thoát, key đang kích hoạt sẽ được tính là đã dùng ở lần mở kế tiếp.

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
