"""
Worker Thread (QThread) xử lý batch file PDF chạy ngầm không làm đơ giao diện.
Hỗ trợ Tạm dừng, Tiếp tục, Hủy, tính thời gian còn lại (ETA) và giải phóng RAM tức thì.
"""

import time
import gc
import os
import datetime
from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition
from typing import List, Dict, Any

from .ocr_engine import SerialOCREngine
from .pdf_processor import SafePDFProcessor, NamingTemplate

class ScanWorker(QThread):
    # Các signals giao tiếp với giao diện chính
    progress_updated = Signal(int, int, str, str, int)  # current, total, status_text, eta_text, percent
    file_completed = Signal(int, str, str, str, str)     # row_idx, serial, new_name, status, note
    batch_finished = Signal(int, int, str)               # success_count, failed_count, report_path
    log_emitted = Signal(str, str)                       # message, level ('info', 'success', 'warning', 'error')

    def __init__(self, file_paths: List[str], output_dir: str, 
                 naming_template: str = NamingTemplate.ONLY_SERIAL,
                 separate_unrecognized: bool = True,
                 export_csv: bool = True,
                 parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.output_dir = output_dir
        self.naming_template = naming_template
        self.separate_unrecognized = separate_unrecognized
        self.export_csv = export_csv

        self._is_cancelled = False
        self._is_paused = False
        self._mutex = QMutex()
        self._pause_condition = QWaitCondition()

    def pause(self):
        """Tạm dừng quá trình quét."""
        self._mutex.lock()
        self._is_paused = True
        self._mutex.unlock()
        self.log_emitted.emit("Đã tạm dừng quá trình quét...", "warning")

    def resume(self):
        """Tiếp tục quá trình quét."""
        self._mutex.lock()
        self._is_paused = False
        self._pause_condition.wakeAll()
        self._mutex.unlock()
        self.log_emitted.emit("Tiếp tục quét batch...", "info")

    def cancel(self):
        """Hủy bỏ toàn bộ quá trình quét."""
        self._mutex.lock()
        self._is_cancelled = True
        if self._is_paused:
            self._is_paused = False
            self._pause_condition.wakeAll()
        self._mutex.unlock()
        self.log_emitted.emit("Yêu cầu hủy quét nhận được...", "warning")

    def run(self):
        """Thực thi luồng quét nền tuần tự theo từng file."""
        total_files = len(self.file_paths)
        if total_files == 0:
            self.batch_finished.emit(0, 0, "")
            return

        self.log_emitted.emit(f"Bắt đầu quét {total_files} file PDF...", "info")
        
        # Khởi tạo engine
        ocr_engine = SerialOCREngine()
        pdf_processor = SafePDFProcessor(
            output_dir=self.output_dir,
            naming_template=self.naming_template,
            separate_unrecognized=self.separate_unrecognized
        )

        records: List[Dict[str, Any]] = []
        success_count = 0
        failed_count = 0
        start_time = time.time()
        file_times = []

        for idx, file_path in enumerate(self.file_paths):
            # Kiểm tra trạng thái hủy
            self._mutex.lock()
            if self._is_cancelled:
                self._mutex.unlock()
                break

            # Kiểm tra trạng thái tạm dừng
            while self._is_paused:
                self._pause_condition.wait(self._mutex)
                if self._is_cancelled:
                    break
            self._mutex.unlock()

            file_start = time.time()
            filename = os.path.basename(file_path)

            # Cập nhật tiến độ ban đầu cho file hiện tại
            percent = int((idx / total_files) * 100)
            status_text = f"Đang quét ({idx + 1}/{total_files}): {filename}"
            
            # Tính ETA (Thời gian còn lại)
            if file_times:
                avg_time = sum(file_times) / len(file_times)
                remaining_files = total_files - idx
                remaining_sec = int(avg_time * remaining_files)
                eta_str = f"Còn lại ~{datetime.timedelta(seconds=remaining_sec)}"
            else:
                eta_str = "Đang tính toán..."

            self.progress_updated.emit(idx + 1, total_files, status_text, eta_str, percent)

            # 1. OCR Tìm số seri
            serial, note = ocr_engine.scan_pdf_file(file_path)
            
            # 2. Xử lý copy an toàn và đổi tên
            is_success, target_path, copy_msg = pdf_processor.process_and_copy_file(file_path, serial)
            target_name = os.path.basename(target_path) if target_path else ""

            # 3. Đánh giá trạng thái
            if serial and is_success:
                status = "Thành công"
                success_count += 1
                self.log_emitted.emit(f"✅ [{idx+1}/{total_files}] {filename} -> {serial} (Lưu: {target_name})", "success")
            elif not serial and is_success:
                status = "Chưa nhận diện"
                failed_count += 1
                self.log_emitted.emit(f"⚠️ [{idx+1}/{total_files}] {filename} -> Không thấy số seri. Đã gom vào {target_name}", "warning")
            else:
                status = "Lỗi"
                failed_count += 1
                self.log_emitted.emit(f"❌ [{idx+1}/{total_files}] {filename} -> {copy_msg}", "error")

            # Ghi nhận kết quả
            records.append({
                "original_name": filename,
                "original_path": file_path,
                "serial": serial or "",
                "output_name": target_name,
                "output_path": target_path,
                "status": status,
                "note": note or copy_msg,
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

            # Bắn tín hiệu cập nhật dòng trên bảng giao diện
            self.file_completed.emit(idx, serial or "—", target_name, status, note or copy_msg)

            # Đo thời gian xử lý và giải phóng bộ nhớ RAM tức thời
            elapsed = time.time() - file_start
            file_times.append(elapsed)
            if len(file_times) > 10:
                file_times.pop(0)  # Giữ trung bình trượt 10 file gần nhất

            # Ép giải phóng bộ nhớ đệm
            gc.collect()

        # Xuất báo cáo CSV nếu được bật
        csv_report_path = ""
        if self.export_csv and records:
            try:
                csv_report_path = SafePDFProcessor.export_csv_report(self.output_dir, records)
                self.log_emitted.emit(f"📊 Đã xuất file báo cáo đối soát: {os.path.basename(csv_report_path)}", "info")
            except Exception as e:
                self.log_emitted.emit(f"Lỗi xuất báo cáo CSV: {str(e)}", "error")

        total_elapsed = time.time() - start_time
        final_eta = f"Hoàn tất trong {datetime.timedelta(seconds=int(total_elapsed))}"
        self.progress_updated.emit(total_files, total_files, "Đã hoàn thành toàn bộ batch!", final_eta, 100)
        self.batch_finished.emit(success_count, failed_count, csv_report_path)
