"""
Module nhận diện và trích xuất số seri phôi sổ đỏ/sổ hồng (Ví dụ: BH 807694).
Tối ưu đa luồng, hỗ trợ xoay góc 0/90/180/270 độ, lọc nhiễu hoa văn bảo an chìm.
"""

import os
import shutil
import re
import cv2
import numpy as np
import fitz  # PyMuPDF
from typing import Optional, Tuple, List

# Biểu thức chính quy phát hiện số seri phôi: 2 chữ cái hoa + (khoảng trắng tùy chọn) + 6 chữ số
# Ví dụ: BH 807694, BL123456, DA 998877, CM 443322
SERIAL_REGEX = re.compile(r'\b([A-Z]{2})\s*([0-9]{6})\b', re.IGNORECASE)

# Các tiền tố 2 chữ cái thường xuất hiện do nhiễu hoặc trích từ CMND/CCCD/Địa chỉ, cần loại trừ
INVALID_PREFIXES = {
    'ND', 'CD', 'SO', 'NO', 'NG', 'TH', 'XA', 'HU', 'TI', 'VI', 'BO', 'UB', 'TO', 'TB', 'TT', 'DT', 'TR'
}

class SerialOCREngine:
    def __init__(self):
        self.tesseract_available = False
        self.easyocr_reader = None
        self._check_available_engines()

    def _check_available_engines(self):
        """Kiểm tra các engine OCR khả dụng trên hệ thống (Hỗ trợ nhúng tesseract bên trong exe trên Windows)."""
        try:
            import pytesseract
            import sys

            # 1. Kiểm tra nếu đang chạy bên trong PyInstaller bundle (sys._MEIPASS)
            if getattr(sys, 'frozen', False):
                base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
                bundled_tess = os.path.join(base_dir, 'tesseract_engine', 'tesseract.exe')
                bundled_tessdata = os.path.join(base_dir, 'tesseract_engine', 'tessdata')
                if os.path.exists(bundled_tess):
                    pytesseract.pytesseract.tesseract_cmd = bundled_tess
                    os.environ['TESSDATA_PREFIX'] = bundled_tessdata
                    self.tesseract_available = True
                    return

            # 2. Trên Windows: Kiểm tra các thư mục portable và cài đặt phổ biến
            if os.name == 'nt' and not shutil.which('tesseract'):
                exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
                common_win_paths = [
                    os.path.join(exe_dir, 'tesseract_engine', 'tesseract.exe'),
                    os.path.join(exe_dir, 'Tesseract-OCR', 'tesseract.exe'),
                    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                    os.path.expandvars(r'%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe')
                ]
                for p in common_win_paths:
                    if os.path.exists(p):
                        pytesseract.pytesseract.tesseract_cmd = p
                        tessdata_dir = os.path.join(os.path.dirname(p), 'tessdata')
                        if os.path.exists(tessdata_dir):
                            os.environ['TESSDATA_PREFIX'] = tessdata_dir
                        break

            pytesseract.get_tesseract_version()
            self.tesseract_available = True
        except Exception as e:
            self.tesseract_available = False

    def _get_easyocr_reader(self):
        """Khởi tạo EasyOCR nếu được yêu cầu."""
        if self.easyocr_reader is None:
            try:
                import easyocr
                self.easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            except Exception:
                self.easyocr_reader = None
        return self.easyocr_reader

    def extract_serial_from_text(self, text: str) -> Optional[str]:
        """Tìm số seri từ chuỗi văn bản theo format chuẩn [A-Z]{2} [0-9]{6}, loại bỏ CMND."""
        if not text:
            return None
        
        matches = SERIAL_REGEX.findall(text)
        for prefix, digits in matches:
            prefix_upper = prefix.upper()
            if prefix_upper not in INVALID_PREFIXES:
                return f"{prefix_upper} {digits}"
        return None

    def scan_image_fast(self, img_bgr: np.ndarray) -> Optional[str]:
        """
        Quét nhanh số seri từ ảnh:
        - Quét ưu tiên góc trên phải và góc dưới phải (vị trí phôi số seri).
        - Thử các góc xoay 90° (dọc chuẩn phôi sổ), 270°, 0°, 180°.
        - Dùng whitelist chữ và số để Tesseract chạy siêu tốc (< 50ms/vùng).
        """
        import pytesseract

        h, w = img_bgr.shape[:2]
        
        # Danh sách các vùng trọng tâm theo thứ tự xác suất cao nhất của các mẫu phôi sổ
        regions = [
            ("bottom_right", img_bgr[int(h * 0.65):h, int(w * 0.65):w]), # Mẫu phôi ngang (BS 208780, BH 343597)
            ("top_right", img_bgr[0:int(h * 0.4), int(w * 0.65):w]),     # Mẫu phôi dọc xoay (BH 807694)
            ("bottom_right_wide", img_bgr[int(h * 0.5):h, int(w * 0.5):w]),
            ("top_right_wide", img_bgr[0:int(h * 0.5), int(w * 0.5):w]),
            ("top_left", img_bgr[0:int(h * 0.4), 0:int(w * 0.4)]),
            ("bottom_left", img_bgr[int(h * 0.6):h, 0:int(w * 0.4)])
        ]

        tess_config = '--oem 3 --psm 11 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

        for _, region in regions:
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            # Tạo 2 biến thể: grayscale gốc và binarized Otsu để xóa hoa văn hồng chìm
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            for img_variant in [gray, thresh]:
                # Thử góc 0 (chữ ngang) và góc 90 (chữ dọc) trước tiên vì chiếm 99% trường hợp
                for angle in [0, 90, 270, 180]:
                    if angle == 90:
                        rotated = cv2.rotate(img_variant, cv2.ROTATE_90_CLOCKWISE)
                    elif angle == 270:
                        rotated = cv2.rotate(img_variant, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    elif angle == 180:
                        rotated = cv2.rotate(img_variant, cv2.ROTATE_180)
                    else:
                        rotated = img_variant

                    try:
                        txt = pytesseract.image_to_string(rotated, config=tess_config)
                        serial = self.extract_serial_from_text(txt)
                        if serial:
                            return serial
                    except Exception:
                        continue

        # Fallback sang EasyOCR nếu Tesseract chưa bắt được
        easy_reader = self._get_easyocr_reader()
        if easy_reader:
            for _, region in regions:
                for angle in [90, 270, 0]:
                    if angle == 90:
                        r = cv2.rotate(region, cv2.ROTATE_90_CLOCKWISE)
                    elif angle == 270:
                        r = cv2.rotate(region, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    else:
                        r = region
                    try:
                        results = easy_reader.readtext(r, detail=0)
                        txt = " ".join(results)
                        serial = self.extract_serial_from_text(txt)
                        if serial:
                            return serial
                    except Exception:
                        continue

        return None

    def scan_pdf_file(self, pdf_path: str) -> Tuple[Optional[str], str]:
        """
        Quét file PDF để tìm số seri:
        1. Kiểm tra lớp text số (nếu file đã có text layer - 5ms).
        2. Render trang 1 độ phân giải tối ưu (DPI 150-200) -> OCR siêu tốc.
        3. Nếu trang 1 không có, thử trang cuối cùng (trang 4 của phôi sổ).
        """
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return None, "File PDF rỗng (0 trang)"

            # Bước 1: Quét text layer nhanh (Digital text)
            for page_idx in [0, len(doc) - 1]:
                if page_idx < len(doc):
                    page = doc[page_idx]
                    page_text = page.get_text("text")
                    serial = self.extract_serial_from_text(page_text)
                    if serial:
                        doc.close()
                        return serial, "Tìm thấy từ Text Layer"

            # Bước 2: Render trang 1 sang ảnh (DPI 150 ~ cực kỳ rõ nét và tốc độ cao)
            page_1 = doc[0]
            pix_1 = page_1.get_pixmap(dpi=150)
            
            img_data = np.frombuffer(pix_1.samples, dtype=np.uint8).reshape(pix_1.height, pix_1.width, pix_1.n)
            if pix_1.n == 4:
                img_bgr = cv2.cvtColor(img_data, cv2.COLOR_RGBA2BGR)
            else:
                img_bgr = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR)

            pix_1 = None  # Giải phóng bộ nhớ Pixmap

            serial = self.scan_image_fast(img_bgr)
            if serial:
                doc.close()
                return serial, "OCR Trang 1 thành công"

            # Bước 3: Nếu trang 1 chưa thấy và file có nhiều hơn 1 trang, thử trang cuối (Trang 4)
            if len(doc) > 1:
                page_last = doc[len(doc) - 1]
                pix_last = page_last.get_pixmap(dpi=150)
                img_data_last = np.frombuffer(pix_last.samples, dtype=np.uint8).reshape(pix_last.height, pix_last.width, pix_last.n)
                if pix_last.n == 4:
                    img_last_bgr = cv2.cvtColor(img_data_last, cv2.COLOR_RGBA2BGR)
                else:
                    img_last_bgr = cv2.cvtColor(img_data_last, cv2.COLOR_RGB2BGR)
                pix_last = None

                serial = self.scan_image_fast(img_last_bgr)
                if serial:
                    doc.close()
                    return serial, "OCR Trang cuối thành công"

            doc.close()
            return None, "Không tìm thấy số seri"

        except Exception as e:
            return None, f"Lỗi đọc file: {str(e)}"
