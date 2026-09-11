from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from sekretariat_app.auth import User, UserRepository
from sekretariat_app.config import APP_NAME, database_path
from sekretariat_app.sips.repository import SIPSRepository
from sekretariat_app.ui.pages.basic import DashboardPage


class NavButton(QPushButton):
    def __init__(self, text: str, route: str, indent: bool = False):
        super().__init__(text)
        self.route = route
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("nav", True)
        self.setProperty("indent", indent)
        self.setMinimumHeight(40 if not indent else 34)


class ShellWindow(QMainWindow):
    logout_requested = Signal()

    def __init__(self, user: User, repository: UserRepository, icon_path: str = ""):
        super().__init__()
        self.user = user
        self.repository = repository
        self.icon_path = icon_path
        self.setWindowTitle(APP_NAME)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(1600, 940)
        self.setMinimumSize(1180, 720)
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        self.pages: dict[str, QWidget] = {}
        self.nav_buttons: dict[str, NavButton] = {}
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.sips_repository = SIPSRepository(database_path())
        self.sips_service = None
        self._close_approved = False
        self._build_ui()
        self.navigate("dashboard")

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("AppRoot")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())

        content = QFrame()
        content.setObjectName("ContentHost")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)
        layout.addWidget(content, 1)
        self._create_pages()

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("AppSidebar")
        sidebar.setFixedWidth(276)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 20, 14, 16)
        layout.setSpacing(6)

        brand = QHBoxLayout()
        logo = QLabel("S")
        logo.setObjectName("BrandLogo")
        if self.icon_path:
            pixmap = QIcon(self.icon_path).pixmap(46, 46)
            if not pixmap.isNull():
                logo.setPixmap(pixmap)
        brand_text = QVBoxLayout()
        name = QLabel("SIPS TERPADU")
        name.setObjectName("BrandName")
        office = QLabel("SEKRETARIAT DPRD\nKOTA BITUNG")
        office.setObjectName("BrandOffice")
        brand_text.addWidget(name)
        brand_text.addWidget(office)
        brand.addWidget(logo)
        brand.addLayout(brand_text, 1)
        layout.addLayout(brand)
        layout.addSpacing(16)

        scroll = QScrollArea()
        scroll.setObjectName("NavScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_host = QWidget()
        nav_host.setObjectName("NavHost")
        nav_layout = QVBoxLayout(nav_host)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(4)
        nav_layout.addWidget(self._nav("Dashboard", "dashboard"))
        nav_layout.addWidget(self._section_label("SURAT DAN ADMINISTRASI"))
        nav_layout.addWidget(self._group_header("Perjalanan Dinas", "travel_group"))
        self.travel_group = self._submenu(
            (
                ("DPRD", "travel_dprd"),
                ("Sekretariat DPRD", "travel_secretariat"),
            )
        )
        nav_layout.addWidget(self.travel_group)
        travel_recap = self._nav("Rekapitulasi Surat\nPerjalanan Dinas", "travel_recap")
        travel_recap.setMinimumHeight(52)
        nav_layout.addWidget(travel_recap)
        nav_layout.addWidget(self._group_header("Surat Undangan", "invitation_group"))
        self.invitation_group = self._submenu(
            (
                ("Undangan Paripurna", "invitation_plenary"),
                ("Undangan Biasa", "invitation_regular"),
            )
        )
        nav_layout.addWidget(self.invitation_group)
        invitation_recap = self._nav("Rekapitulasi Surat\nUndangan", "invitation_recap")
        invitation_recap.setMinimumHeight(52)
        nav_layout.addWidget(invitation_recap)
        nav_layout.addWidget(self._section_label("KINERJA DAN DOKUMENTASI"))
        nav_layout.addWidget(self._nav("Rekapitulasi TPP", "tpp"))
        nav_layout.addWidget(self._nav("Dokumentasi Foto", "documentation"))
        nav_layout.addWidget(self._nav("Edit PDF", "pdf_editor"))
        nav_layout.addWidget(self._section_label("PENGELOLAAN PERSEDIAAN"))
        nav_layout.addWidget(self._nav("Persediaan Barang", "inventory"))
        nav_layout.addStretch()
        scroll.setWidget(nav_host)
        layout.addWidget(scroll, 1)

        user_card = QFrame()
        user_card.setObjectName("UserCard")
        user_layout = QVBoxLayout(user_card)
        user_layout.setContentsMargins(12, 10, 12, 10)
        user_name = QLabel(self.user.full_name)
        user_name.setObjectName("SidebarUserName")
        role = QLabel(self.user.role.upper())
        role.setObjectName("SidebarRole")
        user_layout.addWidget(user_name)
        user_layout.addWidget(role)
        layout.addWidget(user_card)
        users = self._nav("Kelola User", "users")
        users.setEnabled(self.user.role in {"admin", "superadmin"})
        layout.addWidget(users)
        logout = QPushButton("Logout")
        logout.setObjectName("LogoutButton")
        logout.setCursor(Qt.CursorShape.PointingHandCursor)
        logout.clicked.connect(self._logout)
        layout.addWidget(logout)
        return sidebar

    def _create_pages(self) -> None:
        dashboard = DashboardPage(self.sips_repository)
        dashboard.navigate.connect(self.navigate)
        self._add_page("dashboard", dashboard)

    def _ensure_page(self, route: str):
        if route in self.pages:
            return self.pages[route]
        if route not in self.nav_buttons:
            return None
        if route == "users" and self.user.role not in {"admin", "superadmin"}:
            return None
        if route in {"travel_dprd", "travel_secretariat", "invitation_plenary", "invitation_regular"}:
            from sekretariat_app.sips.service import SIPSService
            from sekretariat_app.ui.pages.sips import InvitationPage, TravelPage
            if self.sips_service is None:
                self.sips_service = SIPSService()
            if route.startswith("travel_"):
                page = TravelPage("dprd" if route == "travel_dprd" else "setwan",
                                  self.sips_service, self.sips_repository, self.user, self.repository)
            else:
                page = InvitationPage("paripurna" if route == "invitation_plenary" else "biasa",
                                      self.sips_service, self.sips_repository, self.user, self.repository)
            page.changed.connect(self._refresh_sips_views)
        elif route in {"travel_recap", "invitation_recap"}:
            from sekretariat_app.ui.pages.sips import SIPSRecapPage
            page = SIPSRecapPage("travel" if route == "travel_recap" else "invitation", self.sips_repository)
            page.edit_requested.connect(self._edit_sips_record)
        elif route == "tpp":
            from sekretariat_app.ui.pages.basic import EmbeddedTPPPage
            page = EmbeddedTPPPage()
        elif route == "documentation":
            from sekretariat_app.ui.pages.documentation import DocumentationPhotoPage
            page = DocumentationPhotoPage()
        elif route == "pdf_editor":
            from sekretariat_app.ui.pages.pdf_editor import PDFEditorPage
            page = PDFEditorPage()
        elif route == "inventory":
            from sekretariat_app.ui.pages.inventory import InventoryPage
            page = InventoryPage(self.user.username)
        elif route == "users":
            from sekretariat_app.ui.pages.users import UsersPage
            page = UsersPage(self.repository, self.user)
        else:
            return None
        self._add_page(route, page)
        return page

    def _add_page(self, route: str, page: QWidget) -> None:
        self.pages[route] = page
        self.stack.addWidget(page)

    def _nav(self, text: str, route: str, indent: bool = False) -> NavButton:
        button = NavButton(text, route, indent)
        button.clicked.connect(lambda checked=False, value=route: self.navigate(value))
        self.nav_group.addButton(button)
        self.nav_buttons[route] = button
        return button

    def _group_header(self, text: str, name: str) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setObjectName("NavGroup")
        button.setCheckable(True)
        button.setChecked(True)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setArrowType(Qt.ArrowType.DownArrow)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda checked, key=name, current=button: self._toggle_group(key, current, checked))
        return button

    def _submenu(self, entries: tuple[tuple[str, str], ...]) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(2)
        for label, route in entries:
            layout.addWidget(self._nav(label, route, True))
        return widget

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("NavSection")
        return label

    def _toggle_group(self, key: str, button: QToolButton, checked: bool) -> None:
        target = self.travel_group if key == "travel_group" else self.invitation_group
        target.setVisible(checked)
        button.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)

    def navigate(self, route: str) -> None:
        page = self._ensure_page(route)
        if not page:
            return
        self.stack.setCurrentWidget(page)
        if hasattr(page, "refresh"):
            page.refresh()
        button = self.nav_buttons.get(route)
        if button:
            button.setChecked(True)

    def _refresh_sips_views(self) -> None:
        for route in ("dashboard", "travel_recap", "invitation_recap"):
            page = self.pages.get(route)
            if page and page is self.stack.currentWidget() and hasattr(page, "refresh"):
                page.refresh()

    def _edit_sips_record(self, route: str, record_id: str) -> None:
        page = self._ensure_page(route)
        if page and hasattr(page, "load_record"):
            page.load_record(record_id)
            self.navigate(route)

    def _logout(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        if QMessageBox.question(self, "Logout", "Keluar dan kembali ke halaman login?") != QMessageBox.StandardButton.Yes:
            return
        if not self._can_close():
            return
        self._close_approved = True
        self.repository.log(self.user.username, "logout", "Logout dari aplikasi")
        self.logout_requested.emit()
        self.close()

    def _can_close(self) -> bool:
        from PySide6.QtWidgets import QMessageBox
        for page in self.pages.values():
            preview = getattr(page, "live_preview", None)
            if preview is not None and not preview.ready_to_close():
                QMessageBox.information(self, "Preview masih diproses", "Preview sedang dihentikan. Tunggu proses aktif selesai, lalu keluar kembali.")
                return False
        pdf = self.pages.get("pdf_editor")
        return pdf is None or pdf.can_close()

    def closeEvent(self, event) -> None:
        if not self._close_approved and not self._can_close():
            event.ignore()
            return
        for page in self.pages.values():
            preview = getattr(page, "live_preview", None)
            if preview is not None:
                preview.shutdown()
            if hasattr(page, "shutdown"):
                page.shutdown()
        super().closeEvent(event)
