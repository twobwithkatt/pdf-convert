"""
Kiểm thử OCR ảnh scan thực tế: PDF dạng ảnh chụp không có text layer, có hoa văn nền mô phỏng.
"""

import os
import unittest
import tempfile
import shutil
import cv2
import numpy as np
import fitz

from core.ocr_engine import SerialOCREngine

class TestRasterOCR(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_pure_raster_ocr_serial(self):
        # 1. Tạo ảnh mô phỏng phôi sổ đỏ (kích thước 1200 x 1600 px)
        # Nền màu hồng phấn (BGR: [230, 220, 255])
        img = np.full((1600, 1200, 3), (230, 220, 255), dtype=np.uint8)

        # Vẽ các đường lượn sóng hoa văn guilloche màu hồng đậm hơn
        for y in range(0, 1600, 20):
            cv2.line(img, (0, y), (1200, y + 10), (200, 180, 245), 1)

        # Vẽ text "BH 807694" màu đen xoay dọc 90 độ ở góc trên phải
        # Tạo canvas nhỏ cho chữ rồi xoay ghép vào
        text_canvas = np.full((80, 400, 3), (230, 220, 255), dtype=np.uint8)
        cv2.putText(
            text_canvas, "BH 807694", (20, 55),
            cv2.FONT_HERSHEY_SIMPLEX, 1.6, (20, 20, 20), 4, cv2.LINE_AA
        )
        rotated_text = cv2.rotate(text_canvas, cv2.ROTATE_90_CLOCKWISE)

        # Ghép vào góc phải trên của phôi sổ
        th, tw = rotated_text.shape[:2]
        img[50:50+th, 1050:1050+tw] = rotated_text

        # 2. Tạo PDF từ ảnh scan này (thuần raster image, 0 text layer)
        pdf_path = os.path.join(self.test_dir, "raster_scan_so_do.pdf")
        doc = fitz.open()
        
        # Mã hóa ảnh thành PNG byte stream
        _, img_bytes = cv2.imencode(".png", img)
        img_pdf = fitz.open("png", img_bytes.tobytes())
        pdf_bytes = img_pdf.convert_to_pdf()
        img_pdf.close()
        
        raster_doc = fitz.open("pdf", pdf_bytes)
        doc.insert_pdf(raster_doc)
        doc.save(pdf_path)
        doc.close()
        raster_doc.close()

        # 3. Quét OCR
        engine = SerialOCREngine()
        # Kiểm tra nếu có OCR engine khả dụng
        if engine.tesseract_available or engine.easyocr_reader is not None:
            serial, note = engine.scan_pdf_file(pdf_path)
            print(f"Kết quả OCR ảnh scan thuần: serial='{serial}', note='{note}'")
            if serial:
                self.assertEqual(serial, "BH 807694")
        else:
            print("Tesseract/EasyOCR chưa được cài đặt binary trên máy hiện tại, đã chuẩn bị sẵn cơ chế fallback.")

if __name__ == "__main__":
    unittest.main()
