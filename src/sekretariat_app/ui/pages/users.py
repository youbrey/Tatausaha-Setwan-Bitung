from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sekretariat_app.auth import User, UserRepository


class UserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tambah Pengguna")
        form = QFormLayout(self)
        self.username = QLineEdit()
        self.full_name = QLineEdit()
        self.role = QComboBox()
        self.role.addItems(("operator", "admin", "superadmin"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Username", self.username)
        form.addRow("Nama lengkap", self.full_name)
        form.addRow("Peran", self.role)
        form.addRow("Kata sandi", self.password)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class UsersPage(QWidget):
    def __init__(self, repository: UserRepository, current_user: User):
        super().__init__()
        self.repository = repository
        self.current_user = current_user
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        title = QLabel("Kelola User")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Kelola akun dan hak akses aplikasi lokal")
        subtitle.setObjectName("Subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        row = QHBoxLayout()
        row.addStretch()
        add = QPushButton("Tambah Pengguna")
        add.setObjectName("PrimaryButton")
        add.clicked.connect(self.add_user)
        row.addWidget(add)
        layout.addLayout(row)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(("Username", "Nama Lengkap", "Peran", "Status", "ID"))
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout()
        reset = QPushButton("Reset Kata Sandi")
        toggle = QPushButton("Aktifkan/Nonaktifkan")
        reset.clicked.connect(self.reset_password)
        toggle.clicked.connect(self.toggle_active)
        actions.addWidget(reset)
        actions.addWidget(toggle)
        actions.addStretch()
        layout.addLayout(actions)
        if current_user.role not in {"admin", "superadmin"}:
            add.setEnabled(False)
            reset.setEnabled(False)
            toggle.setEnabled(False)
        self.refresh()

    def refresh(self) -> None:
        users = self.repository.list_users()
        self.table.setRowCount(len(users))
        for row, user in enumerate(users):
            values = (user.username, user.full_name, user.role, "Aktif" if user.active else "Nonaktif", str(user.user_id))
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 4:
                    item.setData(Qt.ItemDataRole.UserRole, user.user_id)
                self.table.setItem(row, column, item)

    def add_user(self) -> None:
        dialog = UserDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repository.add_user(dialog.username.text(), dialog.full_name.text(), dialog.role.currentText(), dialog.password.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Data tidak valid", str(exc))
            return
        self.refresh()

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Pilih pengguna", "Pilih satu pengguna terlebih dahulu.")
            return None
        return int(self.table.item(row, 4).text())

    def reset_password(self) -> None:
        user_id = self._selected_id()
        if user_id is None:
            return
        password, accepted = PasswordDialog.get_password(self)
        if not accepted:
            return
        try:
            self.repository.reset_password(user_id, password)
        except ValueError as exc:
            QMessageBox.warning(self, "Kata sandi tidak valid", str(exc))
            return
        QMessageBox.information(self, "Berhasil", "Kata sandi telah diperbarui.")

    def toggle_active(self) -> None:
        user_id = self._selected_id()
        if user_id is None:
            return
        selected = next((user for user in self.repository.list_users() if user.user_id == user_id), None)
        if not selected:
            return
        if selected.user_id == self.current_user.user_id:
            QMessageBox.warning(self, "Tidak diizinkan", "Akun yang sedang digunakan tidak dapat dinonaktifkan.")
            return
        self.repository.set_active(user_id, not selected.active)
        self.refresh()


class PasswordDialog:
    @staticmethod
    def get_password(parent) -> tuple[str, bool]:
        dialog = QDialog(parent)
        dialog.setWindowTitle("Reset Kata Sandi")
        form = QFormLayout(dialog)
        field = QLineEdit()
        field.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Kata sandi baru", field)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        return field.text(), accepted
