"""
Kiểm thử logic trích xuất số seri, chống trùng lặp tên file và xử lý an toàn.
"""

import os
import unittest
import tempfile
import shutil

from core.ocr_engine import SerialOCREngine, SERIAL_REGEX
from core.pdf_processor import SafePDFProcessor, NamingTemplate

class TestPDFProcessing(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.test_dir, "output")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_regex_serial_extraction(self):
        engine = SerialOCREngine()

        # Kiểm tra các format số seri thực tế
        test_cases = [
            ("CỘNG HÒA XÃ HỘI... BH 807694 ...", "BH 807694"),
            ("Số vào sổ cấp GCN: BH807694", "BH 807694"),
            ("DA 123456", "DA 123456"),
            ("bl 987654", "BL 987654"),
            ("Không có số seri ở đây 12345678", None),
        ]

        for raw_text, expected in test_cases:
            res = engine.extract_serial_from_text(raw_text)
            self.assertEqual(res, expected, f"Thất bại với raw_text: {raw_text}")

    def test_safe_naming_and_duplicate_resolution(self):
        processor = SafePDFProcessor(
            output_dir=self.output_dir,
            naming_template=NamingTemplate.ONLY_SERIAL,
            separate_unrecognized=True
        )

        # Tạo file giả lập
        dummy_orig_1 = os.path.join(self.test_dir, "doc1.pdf")
        dummy_orig_2 = os.path.join(self.test_dir, "doc2.pdf")
        dummy_orig_3 = os.path.join(self.test_dir, "doc3_bad.pdf")
        with open(dummy_orig_1, "w") as f: f.write("dummy pdf 1")
        with open(dummy_orig_2, "w") as f: f.write("dummy pdf 2")
        with open(dummy_orig_3, "w") as f: f.write("dummy pdf 3")

        # 1. File thứ nhất với seri BH 807694
        success1, path1, _ = processor.process_and_copy_file(dummy_orig_1, "BH 807694")
        self.assertTrue(success1)
        self.assertEqual(os.path.basename(path1), "BH 807694.pdf")

        # 2. File thứ hai bị TRÙNG seri BH 807694 -> Tự động thêm (1)
        success2, path2, _ = processor.process_and_copy_file(dummy_orig_2, "BH 807694")
        self.assertTrue(success2)
        self.assertEqual(os.path.basename(path2), "BH 807694 (1).pdf")

        # 3. File thứ ba không nhận diện được số seri -> Tự động vào _CHUA_NHAN_DIEN
        success3, path3, _ = processor.process_and_copy_file(dummy_orig_3, None)
        self.assertTrue(success3)
        self.assertTrue("_CHUA_NHAN_DIEN" in path3)

        # 4. Kiểm tra file gốc không bị xóa/thay đổi
        self.assertTrue(os.path.exists(dummy_orig_1))
        self.assertTrue(os.path.exists(dummy_orig_2))
        self.assertTrue(os.path.exists(dummy_orig_3))

if __name__ == "__main__":
    unittest.main()
