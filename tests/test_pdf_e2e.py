"""
Kiểm thử End-to-End: Tạo PDF mẫu chứa số seri BH 807694 và quét trích xuất.
"""

import os
import unittest
import tempfile
import shutil
import fitz  # PyMuPDF
import cv2
import numpy as np
from unittest.mock import patch

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

    def test_deep_certificate_cover_and_following_page_are_extracted(self):
        sample_pdf_path = os.path.join(self.test_dir, "ho_so_nhieu_trang.pdf")
        doc = fitz.open()

        unrelated_before = doc.new_page()
        unrelated_before.insert_text((80, 100), "GIAY TO DINH KEM")

        cover = doc.new_page()
        cover.insert_text((80, 100), "GIAY CHUNG NHAN QUYEN SU DUNG DAT", fontsize=16)
        cover.insert_text((450, 790), "BS 208130", fontsize=14)

        certificate_page_2 = doc.new_page()
        certificate_page_2.insert_text((80, 100), "THUA DAT VA TAI SAN GAN LIEN VOI DAT", fontsize=14)

        unrelated_after = doc.new_page()
        unrelated_after.insert_text((80, 100), "HOP DONG VAY", fontsize=14)
        doc.save(sample_pdf_path)
        doc.close()

        engine = SerialOCREngine()
        serial, note = engine.scan_pdf_file(sample_pdf_path)
        self.assertEqual(serial, "BS 208130")
        self.assertEqual(engine.last_certificate_page_indices, [1, 2])
        self.assertIn("trang 2", note)

        processor = SafePDFProcessor(self.output_dir)
        success, extracted_path, message = processor.extract_certificate_pages(
            sample_pdf_path, serial, engine.last_certificate_page_indices
        )
        self.assertTrue(success, message)
        self.assertEqual(os.path.basename(extracted_path), "BS 208130 - Giấy chứng nhận.pdf")

        extracted = fitz.open(extracted_path)
        self.assertEqual(len(extracted), 2)
        extracted_text = " ".join(page.get_text("text") for page in extracted)
        extracted.close()
        self.assertIn("GIAY CHUNG NHAN", extracted_text)
        self.assertIn("THUA DAT", extracted_text)
        self.assertNotIn("HOP DONG VAY", extracted_text)

    def test_multiple_certificates_are_scanned_and_split_individually(self):
        sample_pdf_path = os.path.join(self.test_dir, "nhieu_gcn.pdf")
        doc = fitz.open()

        unrelated = doc.new_page()
        unrelated.insert_text((80, 100), "TD 482014")

        for serial, detail in (
            ("BG 439167", "THUA DAT THU NHAT"),
            ("BG 422508", "THUA DAT THU HAI"),
            ("BG 422476", "THUA DAT THU BA"),
        ):
            cover = doc.new_page()
            cover.insert_text((80, 100), "GIAY CHUNG NHAN QUYEN SU DUNG DAT", fontsize=16)
            cover.insert_text((440, 790), serial, fontsize=14)
            data_page = doc.new_page()
            data_page.insert_text((80, 100), detail, fontsize=14)

        doc.save(sample_pdf_path)
        doc.close()

        engine = SerialOCREngine()
        serial, note = engine.scan_pdf_file(sample_pdf_path)
        self.assertEqual(serial, "BG 439167")
        self.assertEqual(
            engine.last_certificate_groups,
            [
                ("BG 439167", [1, 2]),
                ("BG 422508", [3, 4]),
                ("BG 422476", [5, 6]),
            ],
        )
        self.assertIn("3 GCN", note)

        processor = SafePDFProcessor(self.output_dir)
        extracted_page_counts = []
        for certificate_serial, page_indices in engine.last_certificate_groups:
            success, extracted_path, message = processor.extract_certificate_pages(
                sample_pdf_path, certificate_serial, page_indices
            )
            self.assertTrue(success, message)
            extracted = fitz.open(extracted_path)
            extracted_page_counts.append(len(extracted))
            extracted.close()

        self.assertEqual(extracted_page_counts, [2, 2, 2])

    def test_faint_grayscale_certificate_pattern_passes_page_filter(self):
        image = np.full((100, 100, 3), 255, dtype=np.uint8)
        image[::2, :] = (243, 243, 243)
        image[::10, :] = (210, 210, 210)

        self.assertTrue(SerialOCREngine._looks_like_certificate_cover_page(image))

    def test_raster_certificate_cover_is_scanned_beyond_page_one(self):
        sample_pdf_path = os.path.join(self.test_dir, "ho_so_scan.pdf")
        spread_image = np.full((800, 1200, 3), (255, 255, 255), dtype=np.uint8)
        cover_image = np.full((800, 600, 3), (230, 220, 255), dtype=np.uint8)
        cv2.rectangle(cover_image, (2, 2), (597, 797), (0, 0, 255), thickness=5)
        spread_image[:, 600:] = cover_image
        _, image_bytes = cv2.imencode(".png", spread_image)

        doc = fitz.open()
        doc.new_page().insert_text((80, 100), "TRANG KHAC")
        cover_page = doc.new_page(width=842, height=595)
        cover_page.insert_image(cover_page.rect, stream=image_bytes.tobytes())
        doc.save(sample_pdf_path)
        doc.close()

        engine = SerialOCREngine()
        engine.tesseract_available = True
        with patch(
            "pytesseract.image_to_string",
            side_effect=["GIAYCHUNGNHAN QUYENSUDUNGDAT", "BS 208130"],
        ):
            serial, note = engine.scan_pdf_file(sample_pdf_path)

        self.assertEqual(serial, "BS 208130")
        self.assertEqual(engine.last_certificate_page_indices, [1])
        self.assertIn("OCR trang 2", note)

if __name__ == "__main__":
    unittest.main()
