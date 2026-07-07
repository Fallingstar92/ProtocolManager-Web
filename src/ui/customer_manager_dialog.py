from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout
)

from services.customers import load_customers, save_customers


class CustomerManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Správa zákazníků")
        self.resize(900, 600)

        self.customers = load_customers()

        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Server", "Firma", "Adresa"])
        self.table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(self.table)

        buttons = QHBoxLayout()

        add_btn = QPushButton("+ Přidat")
        delete_btn = QPushButton("Smazat vybraného")
        save_btn = QPushButton("Uložit")

        add_btn.clicked.connect(self.add_row)
        delete_btn.clicked.connect(self.delete_selected_row)
        save_btn.clicked.connect(self.save_and_close)

        buttons.addWidget(add_btn)
        buttons.addWidget(delete_btn)
        buttons.addStretch()
        buttons.addWidget(save_btn)

        layout.addLayout(buttons)

        self.load_table()

    def load_table(self):
        self.table.setRowCount(0)

        for customer in self.customers:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(customer.get("server", "")))
            self.table.setItem(row, 1, QTableWidgetItem(customer.get("company", "")))
            self.table.setItem(row, 2, QTableWidgetItem(customer.get("address", "")))

    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, 0, QTableWidgetItem(""))
        self.table.setItem(row, 1, QTableWidgetItem(""))
        self.table.setItem(row, 2, QTableWidgetItem(""))

    def delete_selected_row(self):
        row = self.table.currentRow()

        if row >= 0:
            self.table.removeRow(row)

    def save_and_close(self):
        customers = []

        for row in range(self.table.rowCount()):
            server_item = self.table.item(row, 0)
            company_item = self.table.item(row, 1)
            address_item = self.table.item(row, 2)

            server = server_item.text().strip() if server_item else ""
            company = company_item.text().strip() if company_item else ""
            address = address_item.text().strip() if address_item else ""

            if not company:
                continue

            customers.append({
                "server": server,
                "company": company,
                "address": address,
            })

        customers = sorted(customers, key=lambda c: c["company"].lower())
        save_customers(customers)

        self.accept()