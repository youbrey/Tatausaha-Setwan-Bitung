from __future__ import annotations

import sys
from importlib.resources import files
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

def _resource(name: str) -> str:
    return str(files("sekretariat_app.resources").joinpath(name))


def _load_theme(app: QApplication) -> None:
    app.setStyleSheet(files("sekretariat_app.resources").joinpath("style.qss").read_text(encoding="utf-8"))


def main() -> int:
    # Dispatch before importing the GUI, repositories, or document modules.
    # A frozen --windowed build has no usable stdin/stdout for worker messages.
    if "--pdf-worker" in sys.argv:
        from sekretariat_app.pdf_tools.worker import main as worker_main
        return worker_main()

    from PySide6.QtGui import QIcon, QPixmapCache
    from PySide6.QtWidgets import QApplication, QDialog
    from sekretariat_app.auth import UserRepository
    from sekretariat_app.config import APP_NAME, ORGANIZATION, database_path
    from sekretariat_app.ui.login import LoginDialog
    from sekretariat_app.ui.shell import ShellWindow

    app = QApplication(sys.argv)
    QPixmapCache.setCacheLimit(32 * 1024)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORGANIZATION)
    app.setStyle("Fusion")
    icon_path = _resource("app_icon.ico")
    app.setWindowIcon(QIcon(icon_path))
    _load_theme(app)
    repository = UserRepository(database_path())

    while True:
        login = LoginDialog(repository, icon_path)
        if login.exec() != QDialog.DialogCode.Accepted or not login.user:
            return 0
        window = ShellWindow(login.user, repository, icon_path)
        logged_out = {"value": False}
        window.logout_requested.connect(lambda: logged_out.update(value=True))
        window.show()
        app.exec()
        if not logged_out["value"]:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
