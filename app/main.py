"""프로그램 진입점. `python -m app.main` 으로 실행하거나 PyInstaller로 패키징한다."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.config import ensure_data_dirs
from app.ui.main_window import MainWindow


def main() -> int:
    ensure_data_dirs()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
