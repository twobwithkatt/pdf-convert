"""
Giao diện chính PySide6 (Qt) cho ứng dụng Quét Số Seri & Đổi Tên PDF.
Hỗ trợ kéo thả, chọn tới 500 file, đa luồng mượt mà, quản lý trạng thái an toàn.
"""

import os
import subprocess
import platform
from typing import List, Set

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar, QComboBox, QCheckBox, QGroupBox,
    QMessageBox, QFrame, QTextEdit, QSplitter
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QDragEnterEvent, QDropEvent

from core.pdf_processor import NamingTemplate, SafePDFProcessor
from core.worker_thread import ScanWorker

class MainWindow(QMainWindow):
    MAX_FILES = 500

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Quét Số Seri & Đổi Tên PDF Tự Động (Sổ Đỏ / Sổ Hồng)")
        self.resize(1080, 750)
        self.setMinimumSize(850, 600)
        self.setAcceptDrops(True)

        self.file_list: List[str] = []
        self.file_set: Set[str] = set()
        self.output_directory: str = ""
        self.worker: ScanWorker = None

        self._setup_ui()
        self._load_stylesheet()

    def _setup_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # ---------------- TOP PANEL: Chọn File & Thư mục đích ----------------
        top_group = QGroupBox("📁 1. Thiết lập nguồn và thư mục lưu")
        top_layout = QVBoxLayout(top_group)
        top_layout.setSpacing(10)

        # Hàng 1: Nút nạp files
        file_row = QHBoxLayout()
        self.lbl_file_count = QLabel("Chưa chọn file nào (Tối đa 500 file)")
        self.lbl_file_count.setStyleSheet("font-weight: bold; color: #2563EB;")

        btn_add_files = QPushButton("➕ Thêm Files PDF...")
        btn_add_files.clicked.connect(self._on_choose_files)

        btn_add_folder = QPushButton("📂 Thêm cả thư mục...")
        btn_add_folder.clicked.connect(self._on_choose_folder)

        btn_clear_files = QPushButton("🗑️ Xóa danh sách")
        btn_clear_files.clicked.connect(self._on_clear_files)

        file_row.addWidget(self.lbl_file_count)
        file_row.addStretch()
        file_row.addWidget(btn_add_files)
        file_row.addWidget(btn_add_folder)
        file_row.addWidget(btn_clear_files)
        top_layout.addLayout(file_row)

        # Hàng 2: Chọn thư mục xuất
        out_row = QHBoxLayout()
        lbl_out = QLabel("Thư mục xuất file:")
        lbl_out.setStyleSheet("font-weight: 600;")
        self.txt_out_dir = QLabel("Chưa chọn thư mục xuất (Mặc định sẽ tạo thư mục 'output_da_doi_ten')")
        self.txt_out_dir.setStyleSheet("background: #F1F5F9; padding: 6px 10px; border-radius: 6px; border: 1px solid #CBD5E1;")

        btn_browse_out = QPushButton("📁 Chọn thư mục lưu...")
        btn_browse_out.clicked.connect(self._on_browse_output_dir)

        btn_open_out = QPushButton("🔍 Mở thư mục")
        btn_open_out.clicked.connect(self._on_open_output_dir)

        out_row.addWidget(lbl_out)
        out_row.addWidget(self.txt_out_dir, 1)
        out_row.addWidget(btn_browse_out)
        out_row.addWidget(btn_open_out)
        top_layout.addLayout(out_row)

        main_layout.addWidget(top_group)

        # ---------------- MIDDLE PANEL: Cấu hình an toàn ----------------
        config_group = QGroupBox("⚙️ 2. Mẫu tên file & Chế độ bảo vệ an toàn")
        config_layout = QHBoxLayout(config_group)
        config_layout.setSpacing(16)

        lbl_naming = QLabel("Mẫu tên file mới:")
        lbl_naming.setStyleSheet("font-weight: 600;")
        self.cbo_naming = QComboBox()
        self.cbo_naming.addItem("Chỉ số seri (ví dụ: [Số_Seri].pdf)", NamingTemplate.ONLY_SERIAL)
        self.cbo_naming.addItem("Số seri - Tên gốc (ví dụ: [Số_Seri] - GiayChungNhan.pdf)", NamingTemplate.SERIAL_ORIGINAL)
        self.cbo_naming.addItem("Tên gốc - Số seri (ví dụ: GiayChungNhan - [Số_Seri].pdf)", NamingTemplate.ORIGINAL_SERIAL)
        self.cbo_naming.setCurrentIndex(0)

        self.chk_unrecognized = QCheckBox("Gom file không đọc được vào thư mục riêng (_CHUA_NHAN_DIEN)")
        self.chk_unrecognized.setChecked(True)

        self.chk_csv_report = QCheckBox("Tự động xuất báo cáo đối soát CSV")
        self.chk_csv_report.setChecked(True)

        config_layout.addWidget(lbl_naming)
        config_layout.addWidget(self.cbo_naming)
        config_layout.addWidget(self.chk_unrecognized)
        config_layout.addWidget(self.chk_csv_report)
        config_layout.addStretch()

        main_layout.addWidget(config_group)

        # ---------------- CENTER PANEL: Bảng danh sách và Splitter Log ----------------
        splitter = QSplitter(Qt.Vertical)

        # Bảng danh sách
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "STT", "Tên file gốc", "Dung lượng", "Số seri phát hiện", "Tên file mới xuất", "Trạng thái"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.Interactive)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.setColumnWidth(1, 260)
        self.table.setColumnWidth(3, 160)
        self.table.setColumnWidth(4, 260)
        self.table.setAlternatingRowColors(True)

        splitter.addWidget(self.table)

        # Khung log chi tiết
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 4, 0, 0)
        lbl_log = QLabel("📜 Nhật ký tiến trình:")
        lbl_log.setStyleSheet("font-weight: bold; color: #475569;")
        self.log_box = QTextEdit()
        self.log_box.setObjectName("log_box")
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(140)
        log_layout.addWidget(lbl_log)
        log_layout.addWidget(self.log_box)

        splitter.addWidget(log_widget)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter, 1)

        # ---------------- BOTTOM PANEL: Tiến độ & Nút điều khiển ----------------
        bottom_group = QFrame()
        bottom_layout = QVBoxLayout(bottom_group)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)

        # Hàng thông tin tiến độ
        status_row = QHBoxLayout()
        self.lbl_status = QLabel("Sẵn sàng quét.")
        self.lbl_status.setStyleSheet("font-weight: 600; color: #1E293B;")
        self.lbl_eta = QLabel("")
        self.lbl_eta.setStyleSheet("color: #64748B; font-weight: 500;")
        status_row.addWidget(self.lbl_status)
        status_row.addStretch()
        status_row.addWidget(self.lbl_eta)
        bottom_layout.addLayout(status_row)

        # Thanh Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        bottom_layout.addWidget(self.progress_bar)

        # Hàng Nút Hành động
        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("🚀 Bắt đầu quét & đổi tên")
        self.btn_start.setObjectName("btn_start")
        self.btn_start.clicked.connect(self._on_start_scan)

        self.btn_pause = QPushButton("⏸️ Tạm dừng")
        self.btn_pause.setObjectName("btn_pause")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._on_pause_scan)

        self.btn_cancel = QPushButton("⏹️ Hủy")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel_scan)

        btn_row.addStretch()
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_pause)
        btn_row.addWidget(self.btn_cancel)
        bottom_layout.addLayout(btn_row)

        main_layout.addWidget(bottom_group)

    def _load_stylesheet(self):
        """Tải file QSS."""
        qss_path = os.path.join(os.path.dirname(__file__), "style.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    # ---------------- DRAG & DROP ----------------
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = []
        for url in event.mimeData().urls():
            local_path = url.toLocalFile()
            if os.path.isfile(local_path) and local_path.lower().endswith(".pdf"):
                paths.append(local_path)
            elif os.path.isdir(local_path):
                for root, _, files in os.walk(local_path):
                    for f in files:
                        if f.lower().endswith(".pdf"):
                            paths.append(os.path.join(root, f))
        self._add_files_to_list(paths)

    # ---------------- FILE & FOLDER HANDLERS ----------------
    def _on_choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn các file PDF cần quét", "", "PDF Files (*.pdf)"
        )
        if files:
            self._add_files_to_list(files)

    def _on_choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa file PDF")
        if folder:
            paths = []
            for root, _, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith(".pdf"):
                        paths.append(os.path.join(root, f))
            self._add_files_to_list(paths)

    def _add_files_to_list(self, new_paths: List[str]):
        added_count = 0
        for path in new_paths:
            abs_path = os.path.abspath(path)
            if abs_path not in self.file_set:
                if len(self.file_list) >= self.MAX_FILES:
                    QMessageBox.warning(
                        self, "Giới hạn số lượng",
                        f"Ứng dụng đang hỗ trợ tối đa {self.MAX_FILES} file trong 1 đợt quét.\n"
                        f"Đã bỏ qua các file vượt quá giới hạn."
                    )
                    break
                self.file_set.add(abs_path)
                self.file_list.append(abs_path)
                added_count += 1

        self._refresh_table()

        # Tự động gợi ý thư mục xuất nếu chưa chọn
        if not self.output_directory and self.file_list:
            default_out = os.path.join(os.path.dirname(self.file_list[0]), "output_da_doi_ten")
            self.output_directory = default_out
            self.txt_out_dir.setText(default_out)

    def _on_clear_files(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Cảnh báo", "Đang trong quá trình quét. Vui lòng Hủy trước khi xóa danh sách!")
            return
        self.file_list.clear()
        self.file_set.clear()
        self._refresh_table()
        self.lbl_status.setText("Đã xóa danh sách.")
        self.progress_bar.setValue(0)
        self.lbl_eta.setText("")

    def _refresh_table(self):
        self.table.setRowCount(len(self.file_list))
        self.lbl_file_count.setText(f"Đã chọn: {len(self.file_list)} / {self.MAX_FILES} file PDF")

        for idx, path in enumerate(self.file_list):
            filename = os.path.basename(path)
            size_mb = os.path.getsize(path) / (1024 * 1024) if os.path.exists(path) else 0

            item_stt = QTableWidgetItem(str(idx + 1))
            item_stt.setTextAlignment(Qt.AlignCenter)
            item_orig = QTableWidgetItem(filename)
            item_size = QTableWidgetItem(f"{size_mb:.2f} MB")
            item_size.setTextAlignment(Qt.AlignCenter)
            item_serial = QTableWidgetItem("—")
            item_serial.setTextAlignment(Qt.AlignCenter)
            item_new = QTableWidgetItem("—")
            item_status = QTableWidgetItem("⏳ Đang chờ")
            item_status.setTextAlignment(Qt.AlignCenter)

            self.table.setItem(idx, 0, item_stt)
            self.table.setItem(idx, 1, item_orig)
            self.table.setItem(idx, 2, item_size)
            self.table.setItem(idx, 3, item_serial)
            self.table.setItem(idx, 4, item_new)
            self.table.setItem(idx, 5, item_status)

    def _on_browse_output_dir(self):
        dir_selected = QFileDialog.getExistingDirectory(self, "Chọn thư mục xuất file mới")
        if dir_selected:
            self.output_directory = os.path.abspath(dir_selected)
            self.txt_out_dir.setText(self.output_directory)

    def _on_open_output_dir(self):
        if not self.output_directory or not os.path.exists(self.output_directory):
            QMessageBox.information(self, "Thông báo", "Thư mục xuất chưa tồn tại hoặc chưa được tạo!")
            return

        # Mở thư mục theo hệ điều hành (macOS / Windows)
        if platform.system() == "Darwin":
            subprocess.run(["open", self.output_directory])
        elif platform.system() == "Windows":
            os.startfile(self.output_directory)
        else:
            subprocess.run(["xdg-open", self.output_directory])

    # ---------------- SCAN CONTROL ----------------
    def _on_start_scan(self):
        if not self.file_list:
            QMessageBox.warning(self, "Chưa có file", "Vui lòng chọn ít nhất 1 file PDF để quét!")
            return

        if not self.output_directory:
            default_out = os.path.join(os.path.dirname(self.file_list[0]), "output_da_doi_ten")
            self.output_directory = default_out
            self.txt_out_dir.setText(default_out)

        os.makedirs(self.output_directory, exist_ok=True)

        # Cấu hình giao diện lúc quét
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_pause.setText("⏸️ Tạm dừng")
        self.btn_cancel.setEnabled(True)
        self.log_box.clear()

        # Tạo luồng Worker ngầm
        self.worker = ScanWorker(
            file_paths=list(self.file_list),
            output_dir=self.output_directory,
            naming_template=self.cbo_naming.currentData(),
            separate_unrecognized=self.chk_unrecognized.isChecked(),
            export_csv=self.chk_csv_report.isChecked(),
            parent=self
        )

        self.worker.progress_updated.connect(self._on_progress_updated)
        self.worker.file_completed.connect(self._on_file_completed)
        self.worker.batch_finished.connect(self._on_batch_finished)
        self.worker.log_emitted.connect(self._on_log_emitted)

        self.worker.start()

    def _on_pause_scan(self):
        if not self.worker:
            return
        if self.worker._is_paused:
            self.worker.resume()
            self.btn_pause.setText("⏸️ Tạm dừng")
        else:
            self.worker.pause()
            self.btn_pause.setText("▶️ Tiếp tục")

    def _on_cancel_scan(self):
        if self.worker:
            reply = QMessageBox.question(
                self, "Xác nhận hủy", "Bạn có chắc chắn muốn hủy quá trình quét hiện tại?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.worker.cancel()
                self.btn_cancel.setEnabled(False)
                self.btn_pause.setEnabled(False)

    # ---------------- WORKER SLOTS ----------------
    def _on_progress_updated(self, current: int, total: int, status_text: str, eta_str: str, percent: int):
        self.progress_bar.setValue(percent)
        self.lbl_status.setText(status_text)
        self.lbl_eta.setText(eta_str)

    def _on_file_completed(self, row_idx: int, serial: str, new_name: str, status: str, note: str):
        if 0 <= row_idx < self.table.rowCount():
            item_serial = self.table.item(row_idx, 3)
            item_new = self.table.item(row_idx, 4)
            item_status = self.table.item(row_idx, 5)

            if item_serial:
                item_serial.setText(serial)
                if serial != "—":
                    item_serial.setForeground(QColor("#2563EB"))
                    font = item_serial.font()
                    font.setBold(True)
                    item_serial.setFont(font)

            if item_new:
                item_new.setText(new_name)

            if item_status:
                item_status.setText(status)
                if status == "Thành công":
                    item_status.setForeground(QColor("#16A34A"))
                elif status == "Chưa nhận diện":
                    item_status.setForeground(QColor("#D97706"))
                else:
                    item_status.setForeground(QColor("#DC2626"))

            # Tự động cuộn đến dòng đang xử lý
            self.table.scrollToItem(item_status)

    def _on_log_emitted(self, message: str, level: str):
        color = "#E2E8F0"
        if level == "success":
            color = "#4ADE80"
        elif level == "warning":
            color = "#FBBF24"
        elif level == "error":
            color = "#F87171"
        elif level == "info":
            color = "#60A5FA"

        html = f'<span style="color: {color};">{message}</span>'
        self.log_box.append(html)

    def _on_batch_finished(self, success_count: int, failed_count: int, report_path: str):
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_cancel.setEnabled(False)

        total = success_count + failed_count
        msg = f"Đã hoàn thành đợt quét!\n\n- Thành công: {success_count} file\n- Không tìm thấy / lỗi: {failed_count} file\n- Tổng số: {total} file"
        if report_path and os.path.exists(report_path):
            msg += f"\n\nBáo cáo CSV: {os.path.basename(report_path)}"

        QMessageBox.information(self, "Hoàn tất", msg)
