"""
Entry point khởi chạy ứng dụng Quét Số Seri Sổ Đỏ/Sổ Hồng & Đổi Tên PDF.
Tương thích macOS (Apple Silicon / Intel) và Windows 10/11.
"""

import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from ui.main_window import MainWindow

def main():
    # Cấu hình scale High DPI màn hình Retina / 4K
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("PDF Serial Renamer")
    app.setOrganizationName("Viet Land OCR Tool")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
