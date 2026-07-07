from pathlib import Path
from version import APP_NAME, APP_VERSION
from PySide6.QtGui import QIcon
from ui.customer_manager_dialog import CustomerManagerDialog
from services.print_manager import print_pdf_with_dialog

from PySide6.QtCore import QDate, QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from pdf.generator import generate_protocol_pdf
from pdf.preview import open_pdf
from services.customers import customer_display_name, load_customers, split_address
from ui.title_bar import TitleBar


TRANSPORT_RECEIVERS = [
    {"type": "transport", "name": "TNT"},
    {"type": "transport", "name": "DHL"},
    {"type": "transport", "name": "PPL"},
    {"type": "transport", "name": "GLS"},
]


class SettingsDialog(QDialog):
    def __init__(self, current_name, parent=None):
        super().__init__(parent)

        self.manage_customers = False

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.resize(420, 260)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        panel = QFrame()
        panel.setObjectName("SettingsPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        label = QLabel("Jméno uživatele")
        label.setObjectName("FieldLabel")
        layout.addWidget(label)

        self.name_input = QLineEdit(current_name)
        layout.addWidget(self.name_input)

        customer_btn = QPushButton("Správa zákazníků")
        customer_btn.clicked.connect(self.open_customer_manager)
        layout.addWidget(customer_btn)

        save_btn = QPushButton("Uložit")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self.accept)
        layout.addWidget(save_btn)

        outer_layout.addWidget(panel)

    def open_customer_manager(self):
        self.manage_customers = True
        self.accept()

    def get_name(self):
        return self.name_input.text().strip()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.drag_position = None

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.customers = load_customers()
        self.selected_customer = self.customers[0] if self.customers else {}
        self.selected_receiver = {"type": "transport", "name": "TNT"}

        self.setWindowTitle(APP_NAME)
        BASE_DIR = Path(__file__).resolve().parents[2]

        self.setWindowIcon(
            QIcon(str(BASE_DIR / "assets" / "icon.png"))
        )
        self.setMinimumSize(1100, 760)
        self.resize(1180, 940)

        self._build_ui()

    def exec_centered_dialog(self, dialog):
        def center():
            dialog_geometry = dialog.frameGeometry()
            dialog_geometry.moveCenter(self.frameGeometry().center())
            dialog.move(dialog_geometry.topLeft())

        QTimer.singleShot(0, center)
        return dialog.exec()

    def center_dialog(self, dialog):
        dialog.move(
           self.frameGeometry().center() - dialog.rect().center()
    )

    def open_customer_manager(self):
        dialog = CustomerManagerDialog(self)

        if self.exec_centered_dialog(dialog):
            self.customers = load_customers()
            self.fill_customer_list()
            self.fill_receiver_list()
            self.statusBar().showMessage("Databáze zákazníků uložena ✔")

    def clear_items_table(self):
        self.items_table.clearContents()
        self.items_table.setRowCount(8)
        self.statusBar().showMessage("Položky protokolu vymazány ✔")

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("AppContainer")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(24, 12, 24, 18)
        root.setSpacing(16)

        root.addWidget(TitleBar(self))

        hero = self._card("GlowCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.setContentsMargins(24, 18, 24, 18)
        hero_layout.setSpacing(6)

        title = QLabel("Protocol Manager")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("HeroTitle")
        hero_layout.addWidget(title)

        subtitle = QLabel("Rychlé vytváření předávacích protokolů")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setObjectName("HeroSubtitle")
        hero_layout.addWidget(subtitle)

        nav = QHBoxLayout()
        nav.setSpacing(10)

        new_btn = QPushButton("Nový protokol")
        new_btn.clicked.connect(self.clear_items_table)

        settings_btn = QPushButton("Nastavení")
        settings_btn.clicked.connect(self.open_settings)

        for btn in [new_btn, settings_btn]:
            nav.addWidget(btn)

        nav.addStretch()
        hero_layout.addLayout(nav)

        root.addWidget(hero)

        recent_layout = QHBoxLayout()
        recent_layout.setContentsMargins(0, 0, 0, 0)
        recent_layout.setSpacing(10)

        self.recent_customer_buttons = []

        for customer in self.customers[:4]:
            btn = QPushButton(customer_display_name(customer))
            btn.setObjectName("RecentCustomerButton")
            btn.setCheckable(True)
            btn.setFixedHeight(36)
            btn.setMinimumWidth(180)

            btn.clicked.connect(lambda checked=False, c=customer: self.select_customer(c))

            self.recent_customer_buttons.append((btn, customer))
            recent_layout.addWidget(btn)

        recent_layout.addStretch()

        root.addLayout(recent_layout)

        form_card = self._card()
        form_layout = QGridLayout(form_card)
        form_layout.setContentsMargins(22, 20, 22, 20)
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(12)

        self.customer_search = QLineEdit()
        self.customer_search.setPlaceholderText("Piš název zákazníka nebo server, např. Gapa nebo r47")
        self.customer_search.textChanged.connect(self.filter_customers)
        self.customer_search.installEventFilter(self)

        self.customer_list = QListWidget()
        self.customer_list.setMaximumHeight(120)
        self.customer_list.itemClicked.connect(self.customer_clicked)
        self.customer_list.hide()

        self._add_field(form_layout, "Zákazník", self.customer_search, 0, 0)
        form_layout.addWidget(self.customer_list, 1, 1)

        self.jira_input = QLineEdit()
        self.jira_input.setPlaceholderText("např. SUP-847")
        self._add_field(form_layout, "Jira", self.jira_input, 2, 0)

        self.protocol_number_input = QLineEdit()
        self.protocol_number_input.setText("0035/2026/PP/IK")
        self.protocol_number_input.setObjectName("ProtocolNumber")
        self._add_field(form_layout, "Číslo protokolu", self.protocol_number_input, 3, 0)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setDate(QDate.currentDate())
        self._add_field(form_layout, "Datum", self.date_edit, 0, 2)

        self.receiver_search = QLineEdit()
        self.receiver_search.setText("TNT")
        self.receiver_search.setPlaceholderText("Piš dopravce nebo zákazníka")
        self.receiver_search.textChanged.connect(self.filter_receivers)
        self.receiver_search.installEventFilter(self)

        self.receiver_list = QListWidget()
        self.receiver_list.setMaximumHeight(120)
        self.receiver_list.itemClicked.connect(self.receiver_clicked)
        self.receiver_list.hide()

        self._add_field(form_layout, "Převzal", self.receiver_search, 1, 2)
        form_layout.addWidget(self.receiver_list, 2, 3)

        self.sender_label = QLabel("Ivan Korec")
        self.sender_label.setObjectName("ValueLabel")
        self._add_field(form_layout, "Předal", self.sender_label, 3, 2)

        root.addWidget(form_card)

        self.fill_customer_list()
        self.fill_receiver_list()

        if self.selected_customer:
            self.select_customer(self.selected_customer)

        items_card = self._card()
        items_layout = QVBoxLayout(items_card)
        items_layout.setContentsMargins(22, 20, 22, 20)
        items_layout.setSpacing(12)

        items_title = QLabel("PŘEDMĚTY")
        items_title.setObjectName("SectionTitle")
        items_layout.addWidget(items_title)

        self.items_table = QTableWidget(8, 3)
        self.items_table.setHorizontalHeaderLabels(["Typ", "SN", "Počet"])
        self.items_table.horizontalHeader().setStretchLastSection(True)
        self.items_table.setItem(0, 0, QTableWidgetItem("Flash"))
        self.items_table.setItem(0, 1, QTableWidgetItem("9221014000460"))
        self.items_table.setItem(0, 2, QTableWidgetItem("1"))

        items_layout.addWidget(self.items_table)
        root.addWidget(items_card, 1)

        actions = QHBoxLayout()
        actions.addStretch()

        preview_btn = QPushButton("Náhled PDF")
        preview_btn.clicked.connect(self.open_preview)

        finish_btn = QPushButton("Dokončit a vytisknout")
        finish_btn.setObjectName("PrimaryButton")
        finish_btn.clicked.connect(self.finish_and_print)

        actions.addWidget(preview_btn)
        actions.addWidget(finish_btn)

        root.addLayout(actions)

        self.statusBar().showMessage("Uloženo ✔")
        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setStyleSheet("color:#7cff00; font-weight:bold; padding-right:8px;")
        self.statusBar().addPermanentWidget(version_label)

    def _card(self, object_name="Card"):
        card = QFrame()
        card.setObjectName(object_name)
        return card

    def _add_field(self, layout, label_text, widget, row, col):
        label = QLabel(label_text)
        label.setObjectName("FieldLabel")
        layout.addWidget(label, row, col)
        layout.addWidget(widget, row, col + 1)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
           self.drag_position = (
               event.globalPosition().toPoint()
               - self.frameGeometry().topLeft()
        )
        event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.isMaximized():
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def eventFilter(self, obj, event):
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(obj, event)

        key = event.key()

        if obj == self.customer_search:
            if key == Qt.Key.Key_Down:
                self.move_list_selection(self.customer_list, 1)
                return True
            if key == Qt.Key.Key_Up:
                self.move_list_selection(self.customer_list, -1)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.confirm_customer_selection()
                return True
            if key == Qt.Key.Key_Escape:
                self.customer_list.hide()
                return True

        if obj == self.receiver_search:
            if key == Qt.Key.Key_Down:
                self.move_list_selection(self.receiver_list, 1)
                return True
            if key == Qt.Key.Key_Up:
                self.move_list_selection(self.receiver_list, -1)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.confirm_receiver_selection()
                return True
            if key == Qt.Key.Key_Escape:
                self.receiver_list.hide()
                return True

        return super().eventFilter(obj, event)

    def move_list_selection(self, list_widget, step):
        if list_widget.count() == 0:
            return

        list_widget.show()
        current_row = list_widget.currentRow()
        new_row = 0 if current_row < 0 else current_row + step
        new_row = max(0, min(new_row, list_widget.count() - 1))
        list_widget.setCurrentRow(new_row)

    def fill_customer_list(self, query=""):
        self.customer_list.clear()
        query = query.lower().strip()

        for customer in self.customers:
            display_name = customer_display_name(customer)
            company = customer.get("company", "").lower()
            server = customer.get("server", "").lower()

            if query and query not in company and query not in server and query not in display_name.lower():
                continue

            item = QListWidgetItem(display_name)
            item.setData(1000, customer)
            self.customer_list.addItem(item)

        if self.customer_list.count() > 0:
            self.customer_list.setCurrentRow(0)

    def filter_customers(self, text):
        self.fill_customer_list(text)
        self.customer_list.setVisible(bool(text.strip()))

    def customer_clicked(self, item):
        self.select_customer(item.data(1000))

    def confirm_customer_selection(self):
        item = self.customer_list.currentItem()

        if item is None and self.customer_list.count() > 0:
            item = self.customer_list.item(0)

        if item:
            self.select_customer(item.data(1000))

    def select_customer(self, customer):
        self.selected_customer = customer
        self.update_recent_customer_buttons()

        self.customer_search.blockSignals(True)
        self.customer_search.setText(customer_display_name(customer))
        self.customer_search.blockSignals(False)

        self.customer_list.hide()

    def update_recent_customer_buttons(self):
        selected_company = self.selected_customer.get("company", "")
        selected_server = self.selected_customer.get("server", "")

        for button, customer in self.recent_customer_buttons:
            is_selected = (
                customer.get("company", "") == selected_company
                and customer.get("server", "") == selected_server
            )

            button.blockSignals(True)
            button.setChecked(is_selected)
            button.blockSignals(False)

    def fill_receiver_list(self, query=""):
        self.receiver_list.clear()
        query = query.lower().strip()

        for receiver in TRANSPORT_RECEIVERS:
            name = receiver["name"]
            if not query or query in name.lower():
                item = QListWidgetItem(name)
                item.setData(1000, receiver)
                self.receiver_list.addItem(item)

        for customer in self.customers:
            display_name = customer_display_name(customer)
            company = customer.get("company", "").lower()
            server = customer.get("server", "").lower()

            if query and query not in company and query not in server and query not in display_name.lower():
                continue

            item = QListWidgetItem(display_name)
            item.setData(1000, {"type": "customer", "customer": customer})
            self.receiver_list.addItem(item)

        if self.receiver_list.count() > 0:
            self.receiver_list.setCurrentRow(0)

    def filter_receivers(self, text):
        self.fill_receiver_list(text)
        self.receiver_list.setVisible(bool(text.strip()))

    def receiver_clicked(self, item):
        self.select_receiver(item.data(1000))

    def confirm_receiver_selection(self):
        item = self.receiver_list.currentItem()

        if item is None and self.receiver_list.count() > 0:
            item = self.receiver_list.item(0)

        if item:
            self.select_receiver(item.data(1000))

    def select_receiver(self, receiver):
        self.selected_receiver = receiver

        self.receiver_search.blockSignals(True)

        if receiver.get("type") == "customer":
            self.receiver_search.setText(customer_display_name(receiver["customer"]))
        else:
            self.receiver_search.setText(receiver.get("name", ""))

        self.receiver_search.blockSignals(False)
        self.receiver_list.hide()

    def get_receiver_text(self):
        receiver = self.selected_receiver or {}

        if receiver.get("type") == "customer":
            customer = receiver.get("customer", {})
            return customer.get("company", self.receiver_search.text()).strip()

        return receiver.get("name", self.receiver_search.text()).strip()

    def open_settings(self):
        dialog = SettingsDialog(self.sender_label.text(), self)
        self.center_dialog(dialog)
        if not self.exec_centered_dialog(dialog):
            return

        if dialog.manage_customers:
            self.open_customer_manager()
            return

        new_name = dialog.get_name()

        if new_name:
            self.sender_label.setText(new_name)

    def open_preview(self):
        pdf_path = generate_protocol_pdf(self.collect_protocol_data())
        open_pdf(pdf_path)

    def finish_and_print(self):
        pdf_path = generate_protocol_pdf(self.collect_protocol_data())

        printed = print_pdf_with_dialog(pdf_path, self)

        if printed:
            self.statusBar().showMessage("Protokol odeslán na tiskárnu ✔")
        else:
            self.statusBar().showMessage("Tisk zrušen")

    def collect_protocol_data(self):
        customer = self.selected_customer or {}
        items = []

        for row in range(self.items_table.rowCount()):
            type_item = self.items_table.item(row, 0)
            value_item = self.items_table.item(row, 1)
            count_item = self.items_table.item(row, 2)

            item_type = type_item.text().strip() if type_item else ""
            value = value_item.text().strip() if value_item else ""
            count = count_item.text().strip() if count_item else ""

            if item_type or value or count:
                items.append({
                    "type": item_type or "Položka",
                    "value": value,
                    "count": count or "1",
                })

        return {
            "protocol_number": self.protocol_number_input.text().strip(),
            "sender_name": self.sender_label.text().strip(),
            "customer_name": customer.get("company", self.customer_search.text()),
            "customer_address": split_address(customer.get("address", "")),
            "jira": self.jira_input.text().strip(),
            "items": items,
            "date": self.date_edit.date().toString("dd.MM.yyyy"),
            "receiver": self.get_receiver_text(),
        }