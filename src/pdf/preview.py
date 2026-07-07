from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def open_pdf(path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))