from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout


class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent

        self.setFixedHeight(42)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 10, 4)
        layout.setSpacing(8)

        self.title = QLabel("Protocol Manager")
        self.title.hide()

        layout.addWidget(self.title)
        layout.addStretch()

        minimize = QPushButton("—")
        maximize = QPushButton("□")
        close = QPushButton("×")

        for button in [minimize, maximize, close]:
            button.setFixedSize(32, 30)

        minimize.setObjectName("WindowButton")
        maximize.setObjectName("WindowButton")
        close.setObjectName("CloseButton")

        minimize.clicked.connect(parent.showMinimized)
        maximize.clicked.connect(self.toggle_maximize)
        close.clicked.connect(parent.close)

        layout.addWidget(minimize)
        layout.addWidget(maximize)
        layout.addWidget(close)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            window_handle = self.parent_window.windowHandle()
            if window_handle:
                window_handle.startSystemMove()
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximize()
            event.accept()

    def toggle_maximize(self):
        if self.parent_window.isMaximized():
            self.parent_window.showNormal()
        else:
            self.parent_window.showMaximized()