"""
Entry point khởi chạy ứng dụng Quét Số Seri Sổ Đỏ/Sổ Hồng & Đổi Tên PDF.
Tương thích macOS (Apple Silicon / Intel) và Windows 10/11.
"""

import sys

from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
from PySide6.QtCore import Qt, QLockFile

from core.activation import ActivationManager, ActivationStateError, default_state_path
from ui.activation_dialog import ActivationDialog
from ui.main_window import MainWindow

def main():
    # Cấu hình scale High DPI màn hình Retina / 4K
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("PDF Serial Renamer")
    app.setOrganizationName("Viet Land OCR Tool")

    state_path = default_state_path()
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        app_lock = QLockFile(str(state_path.with_suffix(".lock")))
        app_lock.setStaleLockTime(0)
        if not app_lock.tryLock(0):
            QMessageBox.information(
                None,
                "Không thể mở phiên ứng dụng",
                "PDF Serial Renamer có thể đang chạy ở một cửa sổ khác hoặc "
                "không thể tạo tệp trạng thái kích hoạt. Hãy kiểm tra rồi thử lại.",
            )
            return 1
        activation_manager = ActivationManager(state_path=state_path)
    except (ActivationStateError, OSError) as exc:
        QMessageBox.critical(
            None,
            "Không thể đọc trạng thái kích hoạt",
            f"{exc}\n\nỨng dụng sẽ đóng để tránh làm mất lượt key.",
        )
        return 1

    activation_dialog = ActivationDialog(activation_manager)
    if activation_dialog.exec() != QDialog.DialogCode.Accepted:
        return 0

    app.aboutToQuit.connect(activation_manager.consume_active_key)

    window = MainWindow()
    window.show()

    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
