"""
Module nhận diện và trích xuất số seri phôi sổ đỏ/sổ hồng (Ví dụ: BH 807694)
và bìa đỏ GCN trong PDF nhiều trang (Ví dụ: BS 208130).
Hỗ trợ xoay góc 0/90/180/270 độ, lọc nhiễu hoa văn bảo an chìm.
"""

import os
import shutil
import re
import unicodedata
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
        self.last_certificate_page_indices: List[int] = []
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

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Chuẩn hóa chữ tiếng Việt để so khớp tiêu đề dù OCR bỏ dấu."""
        normalized = unicodedata.normalize("NFD", text or "")
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        normalized = normalized.replace("Đ", "D").replace("đ", "d").upper()
        return re.sub(r"[^A-Z0-9]+", " ", normalized).strip()

    def _is_land_certificate_cover_text(self, text: str) -> bool:
        """Nhận diện trang bìa Giấy chứng nhận quyền sử dụng đất qua tiêu đề."""
        normalized = self._normalize_text(text)
        return "GIAY CHUNG NHAN" in normalized and "QUYEN SU DUNG DAT" in normalized

    @staticmethod
    def _render_page_bgr(page, dpi: int) -> np.ndarray:
        """Render trang PDF về ảnh BGR ba kênh để xử lý bằng OpenCV."""
        pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
        rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    @staticmethod
    def _looks_like_red_certificate_page(img_bgr: np.ndarray) -> bool:
        """Lọc nhanh các trang có nền/hoa văn đỏ trước khi chạy OCR tiêu đề."""
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        hue = hsv[:, :, 0]
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]
        red_pixels = (
            ((hue <= 12) | (hue >= 168))
            & (saturation >= 25)
            & (value >= 80)
        )
        return float(np.count_nonzero(red_pixels)) / red_pixels.size >= 0.015

    def _scan_certificate_cover_image(self, img_bgr: np.ndarray) -> Optional[str]:
        """Chỉ lấy seri sau khi OCR xác nhận trang bìa đỏ đúng tiêu đề chứng nhận."""
        import pytesseract

        title_config = "--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        serial_config = "--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

        for angle in (0, 90, 180, 270):
            if angle == 90:
                oriented = cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE)
            elif angle == 180:
                oriented = cv2.rotate(img_bgr, cv2.ROTATE_180)
            elif angle == 270:
                oriented = cv2.rotate(img_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
            else:
                oriented = img_bgr

            height, width = oriented.shape[:2]
            title_crop = oriented[int(height * 0.27):int(height * 0.53), int(width * 0.06):int(width * 0.94)]
            if title_crop.size == 0:
                continue

            title_gray = cv2.cvtColor(title_crop, cv2.COLOR_BGR2GRAY)
            title_gray = cv2.resize(title_gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            _, title_binary = cv2.threshold(title_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            title_found = False
            for title_image in (title_gray, title_binary):
                try:
                    title_text = pytesseract.image_to_string(title_image, config=title_config)
                except Exception:
                    continue
                if self._is_land_certificate_cover_text(title_text):
                    title_found = True
                    break

            if not title_found:
                continue

            # Seri của mẫu bìa này nằm ở góc dưới bên phải.
            serial_crop = oriented[int(height * 0.79):int(height * 0.99), int(width * 0.62):width]
            if serial_crop.size:
                serial_gray = cv2.cvtColor(serial_crop, cv2.COLOR_BGR2GRAY)
                serial_gray = cv2.resize(serial_gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
                _, serial_binary = cv2.threshold(serial_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                for serial_image in (serial_gray, serial_binary):
                    try:
                        serial_text = pytesseract.image_to_string(serial_image, config=serial_config)
                    except Exception:
                        continue
                    serial = self.extract_serial_from_text(serial_text)
                    if serial:
                        return serial

            # Dự phòng cho bản scan bị lệch: quét lại các góc như luồng seri cũ.
            try:
                serial = self.scan_image_fast(oriented)
                if serial:
                    return serial
            except Exception:
                continue

        return None

    @staticmethod
    def _collect_certificate_page_indices(doc, cover_page_idx: int) -> List[int]:
        """Lấy trang bìa GCN và đúng một trang liền sau nó."""
        last_page_idx = min(cover_page_idx + 1, len(doc) - 1)
        return list(range(cover_page_idx, last_page_idx + 1))

    def scan_image_fast(self, img_bgr: np.ndarray) -> Optional[str]:
        """
        Quét đa tầng siêu tốc (< 0.5s/file) hỗ trợ mọi trường hợp:
        1. Phôi ngang chuẩn (Góc dưới phải - 0 độ) -> ví dụ: BS 208780, BH 343597
        2. Phôi dọc chuẩn (Góc trên phải - 90 độ) -> ví dụ: BH 807694
        3. Phôi ngang bị scan lộn ngược (Góc trên trái - 180 độ) -> ví dụ: BS 303400
        4. Phôi dọc bị scan lộn ngược (Góc dưới trái - 270 độ)
        """
        import pytesseract

        h, w = img_bgr.shape[:2]
        
        # 4 góc tiềm năng của trang scan
        corners = {
            'br': img_bgr[int(h * 0.60):h, int(w * 0.60):w], # Góc dưới phải
            'tr': img_bgr[0:int(h * 0.40), int(w * 0.60):w], # Góc trên phải
            'tl': img_bgr[0:int(h * 0.40), 0:int(w * 0.40)], # Góc trên trái (khi file lộn ngược 180 độ)
            'bl': img_bgr[int(h * 0.60):h, 0:int(w * 0.40)]  # Góc dưới trái (khi file lộn ngược 270 độ)
        }

        tess_config = '--oem 3 --psm 11 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

        # 4 cặp Góc - Hướng tương ứng với 99.9% vị trí phôi thực tế
        primary_pairs = [
            ('br', 0),    # Phôi ngang chuẩn (chữ góc dưới phải, đọc ngang)
            ('tr', 90),   # Phôi dọc chuẩn (chữ góc trên phải, đọc dọc)
            ('tl', 180),  # Phôi ngang lộn ngược (chữ nằm ở góc trên trái, đọc ngược 180 độ)
            ('bl', 270)   # Phôi dọc lộn ngược (chữ nằm ở góc dưới trái, đọc ngược 270 độ)
        ]

        # Đợt 1: Quét siêu tốc Grayscale trên 4 cặp chuẩn (mất ~0.2s)
        for cname, angle in primary_pairs:
            gray = cv2.cvtColor(corners[cname], cv2.COLOR_BGR2GRAY)
            if angle == 90:
                r = cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE)
            elif angle == 180:
                r = cv2.rotate(gray, cv2.ROTATE_180)
            elif angle == 270:
                r = cv2.rotate(gray, cv2.ROTATE_90_COUNTERCLOCKWISE)
            else:
                r = gray

            try:
                txt = pytesseract.image_to_string(r, config=tess_config)
                serial = self.extract_serial_from_text(txt)
                if serial:
                    return serial
            except Exception:
                continue

        # Đợt 2: Quét phân ngưỡng Otsu loại bỏ hoa văn hồng chìm trên 4 cặp chuẩn
        for cname, angle in primary_pairs:
            gray = cv2.cvtColor(corners[cname], cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            if angle == 90:
                r = cv2.rotate(thresh, cv2.ROTATE_90_CLOCKWISE)
            elif angle == 180:
                r = cv2.rotate(thresh, cv2.ROTATE_180)
            elif angle == 270:
                r = cv2.rotate(thresh, cv2.ROTATE_90_COUNTERCLOCKWISE)
            else:
                r = thresh

            try:
                txt = pytesseract.image_to_string(r, config=tess_config)
                serial = self.extract_serial_from_text(txt)
                if serial:
                    return serial
            except Exception:
                continue

        # Đợt 3: Quét dự phòng tất cả các góc còn lại (fallback cho các file chụp xiên/xoay lạ)
        fallback_angles = [0, 90, 180, 270]
        for cname in ['br', 'tr', 'tl', 'bl']:
            gray = cv2.cvtColor(corners[cname], cv2.COLOR_BGR2GRAY)
            for angle in fallback_angles:
                if (cname, angle) in primary_pairs:
                    continue
                if angle == 90:
                    r = cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE)
                elif angle == 180:
                    r = cv2.rotate(gray, cv2.ROTATE_180)
                elif angle == 270:
                    r = cv2.rotate(gray, cv2.ROTATE_90_COUNTERCLOCKWISE)
                else:
                    r = gray

                try:
                    txt = pytesseract.image_to_string(r, config=tess_config)
                    serial = self.extract_serial_from_text(txt)
                    if serial:
                        return serial
                except Exception:
                    continue

        return None

    def scan_pdf_file(self, pdf_path: str) -> Tuple[Optional[str], str]:
        """
        Quét PDF để tìm seri của phôi cũ ở trang đầu/cuối hoặc bìa đỏ GCN ở bất kỳ trang nào.
        """
        doc = None
        self.last_certificate_page_indices = []
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return None, "File PDF rỗng (0 trang)"

            first_text_serial = None
            last_text_serial = None

            # Ưu tiên bìa GCN ở bất kỳ vị trí nào. Kiểm tra text layer trước vì rất nhanh.
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                page_text = page.get_text("text")
                is_cover_text = self._is_land_certificate_cover_text(page_text)

                if page_idx == 0:
                    first_text_serial = self.extract_serial_from_text(page_text)
                if page_idx == len(doc) - 1:
                    last_text_serial = self.extract_serial_from_text(page_text)

                if is_cover_text:
                    serial = self.extract_serial_from_text(page_text)
                    if serial:
                        self.last_certificate_page_indices = self._collect_certificate_page_indices(
                            doc, page_idx
                        )
                        return serial, f"Tìm thấy từ Text Layer trang {page_idx + 1} (Giấy chứng nhận)"
                    if self.tesseract_available:
                        cover_img = self._render_page_bgr(page, 150)
                        serial = self._scan_certificate_cover_image(cover_img)
                        if serial:
                            self.last_certificate_page_indices = self._collect_certificate_page_indices(
                                doc, page_idx
                            )
                            return serial, f"OCR trang {page_idx + 1} (Giấy chứng nhận quyền sử dụng đất)"

                # Bản scan thường không có text layer. Thumbnail màu giúp chỉ OCR kỹ trang đỏ.
                if self.tesseract_available and not is_cover_text:
                    thumbnail = self._render_page_bgr(page, 50)
                    if self._looks_like_red_certificate_page(thumbnail):
                        cover_img = self._render_page_bgr(page, 150)
                        serial = self._scan_certificate_cover_image(cover_img)
                        if serial:
                            self.last_certificate_page_indices = self._collect_certificate_page_indices(
                                doc, page_idx
                            )
                            return serial, f"OCR trang {page_idx + 1} (Giấy chứng nhận quyền sử dụng đất)"

            # Giữ tương thích với các phôi cũ vốn chỉ quét trang đầu và trang cuối.
            for page_idx, text_serial in ((0, first_text_serial), (len(doc) - 1, last_text_serial)):
                if text_serial:
                    return text_serial, "Tìm thấy từ Text Layer"

            if self.tesseract_available:
                legacy_pages = [(0, "OCR Trang 1 thành công")]
                if len(doc) > 1:
                    legacy_pages.append((len(doc) - 1, "OCR Trang cuối thành công"))

                for page_idx, success_note in legacy_pages:
                    img_bgr = self._render_page_bgr(doc[page_idx], 150)
                    serial = self.scan_image_fast(img_bgr)
                    if serial:
                        return serial, success_note

            return None, "Không tìm thấy số seri"

        except Exception as e:
            return None, f"Lỗi đọc file: {str(e)}"
        finally:
            if doc is not None:
                doc.close()
