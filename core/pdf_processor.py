"""
Module xử lý an toàn file PDF:
- Copy sang thư mục xuất (KHÔNG đè hoặc sửa file gốc).
- Giải quyết trùng tên tự động (BH 807694 (1).pdf, BH 807694 (2).pdf).
- Gom file không nhận diện được vào thư mục con _CHUA_NHAN_DIEN.
- Tạo báo cáo tổng hợp CSV đối soát.
"""

import os
import shutil
import csv
import datetime
from typing import Dict, Any, List, Optional, Tuple

class NamingTemplate:
    ONLY_SERIAL = "ONLY_SERIAL"         # BH 807694.pdf
    SERIAL_ORIGINAL = "SERIAL_ORIGINAL" # BH 807694 - TenGoc.pdf
    ORIGINAL_SERIAL = "ORIGINAL_SERIAL" # TenGoc - BH 807694.pdf

class SafePDFProcessor:
    def __init__(self, output_dir: str, 
                 naming_template: str = NamingTemplate.ONLY_SERIAL,
                 separate_unrecognized: bool = True):
        self.output_dir = output_dir
        self.naming_template = naming_template
        self.separate_unrecognized = separate_unrecognized
        self.used_filenames = set()
        
        # Đảm bảo thư mục xuất tồn tại
        os.makedirs(self.output_dir, exist_ok=True)
        if self.separate_unrecognized:
            self.unrecognized_dir = os.path.join(self.output_dir, "_CHUA_NHAN_DIEN")
            os.makedirs(self.unrecognized_dir, exist_ok=True)
        else:
            self.unrecognized_dir = self.output_dir

        # Quét các file đã có sẵn trong thư mục xuất để chống ghi đè
        for f in os.listdir(self.output_dir):
            self.used_filenames.add(f.lower())

    def sanitize_filename(self, filename: str) -> str:
        """Loại bỏ ký tự cấm trong tên file trên Windows và macOS."""
        invalid_chars = '<>:"/\\|?*\0'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename.strip()

    def generate_safe_filename(self, original_path: str, serial: Optional[str]) -> str:
        """Tạo tên file mới an toàn không bị trùng lặp."""
        orig_base = os.path.basename(original_path)
        orig_stem, _ = os.path.splitext(orig_base)

        if not serial:
            # File không nhận diện được
            base_name = f"_CHUA_NHAN_DIEN_{orig_stem}.pdf" if not self.separate_unrecognized else orig_base
        else:
            # Làm sạch số seri
            clean_serial = serial.strip().upper()
            if self.naming_template == NamingTemplate.ONLY_SERIAL:
                base_name = f"{clean_serial}.pdf"
            elif self.naming_template == NamingTemplate.SERIAL_ORIGINAL:
                base_name = f"{clean_serial} - {orig_stem}.pdf"
            elif self.naming_template == NamingTemplate.ORIGINAL_SERIAL:
                base_name = f"{orig_stem} - {clean_serial}.pdf"
            else:
                base_name = f"{clean_serial}.pdf"

        base_name = self.sanitize_filename(base_name)
        target_stem, ext = os.path.splitext(base_name)

        # Chống trùng lặp (Duplicate resolution)
        final_name = base_name
        counter = 1
        while final_name.lower() in self.used_filenames:
            final_name = f"{target_stem} ({counter}){ext}"
            counter += 1

        self.used_filenames.add(final_name.lower())
        return final_name

    def process_and_copy_file(self, original_path: str, serial: Optional[str]) -> Tuple[bool, str, str]:
        """
        Copy an toàn file gốc sang thư mục xuất với tên mới:
        - Giữ nguyên vẹn 100% file gốc.
        - Trả về: (success: bool, target_path: str, message: str)
        """
        if not os.path.exists(original_path):
            return False, "", "File gốc không tồn tại"

        safe_filename = self.generate_safe_filename(original_path, serial)

        if serial:
            dest_dir = self.output_dir
        else:
            dest_dir = self.unrecognized_dir

        dest_path = os.path.join(dest_dir, safe_filename)

        try:
            # Copy giữ nguyên timestamp và metadata
            shutil.copy2(original_path, dest_path)
            return True, dest_path, "Copy thành công"
        except Exception as e:
            return False, "", f"Lỗi khi copy: {str(e)}"

    @staticmethod
    def export_csv_report(output_dir: str, records: List[Dict[str, Any]]) -> str:
        """Xuất file báo cáo đối soát dạng CSV."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(output_dir, f"bao_cao_scan_seri_{timestamp}.csv")

        fieldnames = [
            "STT",
            "Tên file gốc",
            "Đường dẫn gốc",
            "Số seri phát hiện",
            "Tên file mới",
            "Đường dẫn xuất",
            "Trạng thái",
            "Ghi chú",
            "Thời gian xử lý"
        ]

        with open(report_path, mode='w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for idx, r in enumerate(records, 1):
                writer.writerow({
                    "STT": idx,
                    "Tên file gốc": r.get("original_name", ""),
                    "Đường dẫn gốc": r.get("original_path", ""),
                    "Số seri phát hiện": r.get("serial", "") or "Không có",
                    "Tên file mới": r.get("output_name", ""),
                    "Đường dẫn xuất": r.get("output_path", ""),
                    "Trạng thái": r.get("status", ""),
                    "Ghi chú": r.get("note", ""),
                    "Thời gian xử lý": r.get("time", "")
                })

        return report_path
