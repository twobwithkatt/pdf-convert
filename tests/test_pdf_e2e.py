"""
Kiểm thử End-to-End: Tạo PDF mẫu chứa số seri BH 807694 và quét trích xuất.
"""

import os
import unittest
import tempfile
import shutil
import fitz  # PyMuPDF

from core.ocr_engine import SerialOCREngine
from core.pdf_processor import SafePDFProcessor, NamingTemplate

class TestPDFEndToEnd(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.test_dir, "output")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_e2e_pdf_serial_extraction(self):
        # 1. Tạo 1 file PDF mẫu có chứa text BH 807694
        sample_pdf_path = os.path.join(self.test_dir, "giay_chung_nhan_goc.pdf")
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)  # A4

        # Thêm text mô phỏng phôi sổ
        page.insert_text((100, 100), "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", fontsize=14)
        page.insert_text((100, 140), "GIẤY CHỨNG NHẬN QUYỀN SỬ DỤNG ĐẤT", fontsize=16)
        page.insert_text((480, 100), "BH 807694", fontsize=14, rotate=90) # Text xoay dọc ở góc phải

        doc.save(sample_pdf_path)
        doc.close()

        # 2. Quét bằng OCR Engine
        engine = SerialOCREngine()
        serial, note = engine.scan_pdf_file(sample_pdf_path)

        print(f"Kết quả quét PDF mẫu: serial='{serial}', note='{note}'")
        self.assertEqual(serial, "BH 807694")

        # 3. Tiến hành copy & đổi tên sang thư mục xuất
        processor = SafePDFProcessor(
            output_dir=self.output_dir,
            naming_template=NamingTemplate.ONLY_SERIAL,
            separate_unrecognized=True
        )
        success, out_path, msg = processor.process_and_copy_file(sample_pdf_path, serial)
        self.assertTrue(success)
        self.assertEqual(os.path.basename(out_path), "BH 807694.pdf")
        self.assertTrue(os.path.exists(out_path))

        # 4. Đảm bảo file gốc vẫn nguyên vẹn
        self.assertTrue(os.path.exists(sample_pdf_path))

if __name__ == "__main__":
    unittest.main()
