from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from sekretariat_app.auth import User, UserRepository


class LoginDialog(QDialog):
    def __init__(self, repository: UserRepository, icon_path: str = "", parent=None):
        super().__init__(parent)
        self.repository = repository
        self.user: User | None = None
        self.setWindowTitle("Login - Sekretariat DPRD Kota Bitung")
        self.setFixedSize(930, 570)
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        self._build_ui()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        brand = QFrame()
        brand.setObjectName("LoginBrand")
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(52, 52, 52, 52)
        mark = QLabel("SIPS")
        mark.setObjectName("LoginMark")
        title = QLabel("Sistem Administrasi\nSekretariat DPRD")
        title.setObjectName("LoginBrandTitle")
        subtitle = QLabel("Perjalanan dinas, persuratan, TPP, dan dokumentasi foto dalam satu aplikasi desktop offline.")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("LoginBrandSubtitle")
        brand_layout.addWidget(mark)
        brand_layout.addStretch()
        brand_layout.addWidget(title)
        brand_layout.addWidget(subtitle)
        brand_layout.addStretch()
        office = QLabel("SEKRETARIAT DPRD KOTA BITUNG")
        office.setObjectName("LoginOffice")
        brand_layout.addWidget(office)
        root.addWidget(brand, 5)

        form_host = QWidget()
        form = QVBoxLayout(form_host)
        form.setContentsMargins(54, 64, 54, 54)
        heading = QLabel("Selamat datang")
        heading.setObjectName("LoginTitle")
        help_text = QLabel("Masuk untuk melanjutkan ke dashboard aplikasi.")
        help_text.setObjectName("Subtitle")
        form.addWidget(heading)
        form.addWidget(help_text)
        form.addSpacing(34)
        form.addWidget(self._field_label("Username"))
        self.username = QLineEdit()
        self.username.setPlaceholderText("Masukkan username")
        self.username.setText("admin")
        form.addWidget(self.username)
        form.addSpacing(10)
        form.addWidget(self._field_label("Kata sandi"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Masukkan kata sandi")
        self.password.returnPressed.connect(self._login)
        form.addWidget(self.password)
        self.error = QLabel("")
        self.error.setObjectName("LoginError")
        self.error.setWordWrap(True)
        form.addWidget(self.error)
        login = QPushButton("Masuk ke Aplikasi")
        login.setObjectName("PrimaryButton")
        login.setMinimumHeight(44)
        login.clicked.connect(self._login)
        form.addWidget(login)
        form.addStretch()
        hint = QLabel("Akun awal pengembangan: admin / admin123\nSegera ubah kata sandi melalui menu Kelola User.")
        hint.setObjectName("LoginHint")
        hint.setWordWrap(True)
        form.addWidget(hint)
        root.addWidget(form_host, 4)

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label

    def _login(self) -> None:
        user = self.repository.authenticate(self.username.text(), self.password.text())
        if not user:
            self.error.setText("Username, kata sandi, atau status akun tidak valid.")
            self.password.selectAll()
            self.password.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        self.user = user
        self.accept()
