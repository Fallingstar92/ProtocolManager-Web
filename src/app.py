import sys

from PySide6.QtWidgets import QApplication

from src.constants import APP_NAME
from src.ui.main_window import MainWindow


def run_app() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())