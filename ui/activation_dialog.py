"""Terms acceptance and one-time launch-key dialog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from core.activation import ActivationError, ActivationManager


TERMS_HTML = """
<h2>Điều khoản sử dụng và giới hạn trách nhiệm</h2>
<p><b>Vui lòng đọc kỹ trước khi tiếp tục.</b></p>
<ol>
  <li><b>Phạm vi ứng dụng.</b> Đây là công cụ hỗ trợ quét PDF, nhận dạng ký tự
  (OCR), tìm số seri, đổi tên và tách trang theo lựa chọn của người dùng.
  Ứng dụng không xác minh tính xác thực, hiệu lực pháp lý, quyền sở hữu hoặc
  nội dung của bất kỳ tài liệu nào.</li>
  <li><b>Trách nhiệm với dữ liệu.</b> Người dùng tự chọn và đưa tài liệu vào
  ứng dụng, đồng thời cam kết mình có quyền hoặc được ủy quyền hợp pháp để xử
  lý tài liệu đó. Người dùng chịu trách nhiệm về nguồn gốc, nội dung, độ chính
  xác, dữ liệu cá nhân/dữ liệu nhạy cảm, quyền và sự đồng ý cần thiết, cũng như
  việc lưu trữ, chia sẻ và sử dụng tài liệu.</li>
  <li><b>Kết quả nhận dạng.</b> OCR và việc xác định trang có thể đọc sai, bỏ
  sót hoặc phân loại nhầm. Kết quả chỉ có tính hỗ trợ; người dùng phải tự đối
  chiếu số seri, trang được tách và các tệp đầu ra với bản gốc trước khi sử
  dụng, nộp hồ sơ hoặc đưa ra quyết định.</li>
  <li><b>Bảo quản bản gốc.</b> Người dùng tự chịu trách nhiệm giữ bản sao dự
  phòng và kiểm tra tệp đầu ra. Không dùng kết quả của ứng dụng như xác nhận
  pháp lý, tư vấn pháp luật hoặc bảo đảm về tính chính xác của tài liệu.</li>
  <li><b>Giới hạn trách nhiệm.</b> Trong phạm vi pháp luật cho phép, nhà phát
  triển không chịu trách nhiệm đối với tài liệu do người dùng đưa vào, quyền
  xử lý tài liệu, quyết định dựa trên kết quả nhận dạng hoặc thiệt hại phát
  sinh từ việc sử dụng kết quả đó. Điều khoản này không loại trừ trách nhiệm
  bắt buộc mà pháp luật không cho phép loại trừ.</li>
</ol>
<p>Bằng cách chọn “Tôi đã đọc và đồng ý” và kích hoạt, người dùng xác nhận đã
đọc, hiểu và đồng ý với các điều khoản trên. Nếu không đồng ý, vui lòng thoát
ứng dụng.</p>
"""


class ActivationDialog(QDialog):
    def __init__(self, activation_manager: ActivationManager, parent=None):
        super().__init__(parent)
        self.activation_manager = activation_manager
        self.setWindowTitle("Điều khoản sử dụng và kích hoạt")
        self.setModal(True)
        self.resize(760, 650)
        self.setMinimumSize(640, 540)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        self.terms = QTextBrowser(self)
        self.terms.setReadOnly(True)
        self.terms.setOpenExternalLinks(False)
        self.terms.setHtml(TERMS_HTML)
        self.terms.setMinimumHeight(300)
        layout.addWidget(self.terms, 1)

        self.accept_terms = QCheckBox("Tôi đã đọc và đồng ý với các điều khoản trên")
        self.accept_terms.setChecked(False)
        layout.addWidget(self.accept_terms)

        self.key_count = QLabel(self)
        self.key_count.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.key_count)

        self.key_input = QLineEdit(self)
        self.key_input.setPlaceholderText("Nhập key kích hoạt, ví dụ: XXXX-XXXX-...")
        self.key_input.setClearButtonEnabled(True)
        layout.addWidget(self.key_input)

        self.notice = QLabel(
            "Mỗi key chỉ dùng một lần và được tính là đã dùng khi đóng ứng dụng. "
            "Nếu ứng dụng bị buộc thoát, key đang dùng sẽ được tính là đã dùng "
            "ở lần mở kế tiếp.",
            self,
        )
        self.notice.setWordWrap(True)
        self.notice.setStyleSheet("color: #475569;")
        layout.addWidget(self.notice)

        self.error = QLabel(self)
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #B91C1C;")
        self.error.hide()
        layout.addWidget(self.error)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.exit_button = QPushButton("Thoát", self)
        self.exit_button.clicked.connect(self.reject)
        buttons.addWidget(self.exit_button)

        self.activate_button = QPushButton("Đồng ý và kích hoạt", self)
        self.activate_button.setDefault(True)
        self.activate_button.clicked.connect(self._activate)
        buttons.addWidget(self.activate_button)
        layout.addLayout(buttons)

        self.accept_terms.toggled.connect(self._update_controls)
        self.key_input.textChanged.connect(self._update_controls)
        self._update_controls()

    def _update_controls(self, *_):
        remaining = self.activation_manager.remaining_count
        self.key_count.setText(
            f"Còn {remaining}/{self.activation_manager.total_count} key chưa sử dụng."
        )
        self.activate_button.setEnabled(
            self.accept_terms.isChecked()
            and bool(self.key_input.text().strip())
            and remaining > 0
        )
        if remaining == 0:
            self.error.setText("Đã dùng hết 30 key. Không thể mở ứng dụng bằng key hiện có.")
            self.error.show()

    def _activate(self):
        try:
            self.activation_manager.reserve_key(self.key_input.text())
        except ActivationError as exc:
            self.error.setText(str(exc))
            self.error.show()
            return

        self.error.hide()
        self.accept()
