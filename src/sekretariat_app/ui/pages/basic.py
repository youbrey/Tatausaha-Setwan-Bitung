from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class StatCard(QFrame):
    def __init__(self, value: str, caption: str, accent: str = "blue"):
        super().__init__()
        self.setObjectName("StatCard")
        self.setProperty("accent", accent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatValue")
        caption_label = QLabel(caption)
        caption_label.setObjectName("StatLabel")
        layout.addWidget(self.value_label)
        layout.addWidget(caption_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class DashboardPage(QWidget):
    navigate = Signal(str)

    def __init__(self, repository=None):
        super().__init__()
        self.repository = repository
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)
        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Pusat aktivitas administrasi Sekretariat DPRD Kota Bitung")
        subtitle.setObjectName("Subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        stats = QGridLayout()
        stats.setSpacing(12)
        self.stat_cards: dict[str, StatCard] = {}
        for index, (key, value, caption, accent) in enumerate(
            (
                ("travel", "0", "Perjalanan dinas tersimpan", "blue"),
                ("invitations", "0", "Surat undangan tersimpan", "violet"),
                ("drafts", "0", "Draft perlu diselesaikan", "emerald"),
                ("documentation", "—", "Workspace dokumentasi", "amber"),
            )
        ):
            card = StatCard(value, caption, accent)
            self.stat_cards[key] = card
            stats.addWidget(card, 0, index)
        layout.addLayout(stats)

        workspace = QFrame()
        workspace.setObjectName("Card")
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(20, 18, 20, 20)
        header = QLabel("Akses Cepat")
        header.setObjectName("SectionTitle")
        workspace_layout.addWidget(header)
        grid = QGridLayout()
        cards = (
            ("Perjalanan Dinas DPRD", "Buat Surat Tugas dan SPD anggota DPRD", "travel_dprd"),
            ("Perjalanan Dinas Sekretariat", "Buat dokumen perjalanan dinas ASN", "travel_secretariat"),
            ("Surat Undangan", "Buat undangan paripurna atau rapat biasa", "invitation_plenary"),
            ("Rekapitulasi TPP", "Proses PDF finger scan dan ekspor Excel", "tpp"),
            ("Dokumentasi Foto", "Susun kolase, ekspor DOCX/PDF, dan cetak", "documentation"),
        )
        for index, (name, description, route) in enumerate(cards):
            card = QPushButton(f"{name}\n{description}")
            card.setObjectName("QuickCard")
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.clicked.connect(lambda checked=False, value=route: self.navigate.emit(value))
            grid.addWidget(card, index // 2, index % 2)
        workspace_layout.addLayout(grid)
        layout.addWidget(workspace)
        layout.addStretch()
        self.refresh()

    def refresh(self) -> None:
        if not self.repository:
            return
        stats = self.repository.dashboard_stats()
        self.stat_cards["travel"].set_value(str(stats["travel"]))
        self.stat_cards["invitations"].set_value(str(stats["plenary"] + stats["regular"]))
        self.stat_cards["drafts"].set_value(str(stats["drafts"]))
class EmbeddedTPPPage(QWidget):
    def __init__(self):
        super().__init__()
        from tpp_finger_scan.ui.main_window import MainWindow as TPPMainWindow

        class EmbeddedWindow(TPPMainWindow):
            @staticmethod
            def _load_stylesheet() -> None:
                return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.window = EmbeddedWindow()
        self.window.setWindowFlags(Qt.WindowType.Widget)
        layout.addWidget(self.window)
