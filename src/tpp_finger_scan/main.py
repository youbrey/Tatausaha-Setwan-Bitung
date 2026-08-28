from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from tpp_finger_scan.config import APP_NAME
from tpp_finger_scan.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Local Government")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

