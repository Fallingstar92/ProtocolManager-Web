from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QPainter
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QMessageBox, QWidget


def print_pdf_with_dialog(pdf_path: Path, parent: QWidget | None = None) -> bool:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setDocName(pdf_path.name)

    dialog = QPrintDialog(printer, parent)

    if dialog.exec() != QPrintDialog.DialogCode.Accepted:
        return False

    document = QPdfDocument(parent)
    document.load(str(pdf_path))

    if document.pageCount() <= 0:
        QMessageBox.critical(parent, "Chyba tisku", "PDF se nepodařilo načíst.")
        return False

    painter = QPainter(printer)

    for page_index in range(document.pageCount()):
        if page_index > 0:
            printer.newPage()

        page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
        image_size = QSize(int(page_rect.width()), int(page_rect.height()))

        image = document.render(page_index, image_size)
        painter.drawImage(page_rect, image)

    painter.end()
    return True