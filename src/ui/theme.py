def app_stylesheet() -> str:
    return """
    * {
        font-family: "Segoe UI", Arial;
        font-size: 14px;
    }

    QMainWindow {
        background-color: transparent;
    }

    #AppContainer {
        background-color: #050805;
        border: 1px solid #63ff00;
        border-radius: 22px;
    }

    #HeroTitle {
        color: #f4fff4;
        font-size: 34px;
        font-weight: 800;
        background: transparent;
    }

    #HeroSubtitle {
        color: #7cff00;
        font-size: 17px;
        background: transparent;
    }

    #SectionTitle {
        color: #7cff00;
        font-size: 15px;
        font-weight: 800;
        background: transparent;
    }

    #Card {
        background-color: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #101710,
            stop:1 #070b07
        );
        border: 1px solid #2f6f18;
        border-radius: 18px;
    }

    #SettingsContainer {
        background-color: #050805;
        border: 1px solid #63ff00;
        border-radius: 16px;
    }

    #SettingsPanel {
        background-color: #050805;
        border: 1px solid #63ff00;
        border-radius: 18px;
    }

    #SettingsDialog {
        background-color: #050805;
        border: 1px solid #63ff00;
        border-radius: 18px;
    }

    #GlowCard {
        background-color: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #111a11,
            stop:1 #070b07
        );
        border: 1px solid #6dff00;
        border-radius: 20px;
    }

    QLabel {
        color: #f2fff2;
        background: transparent;
        border: none;
    }

    #FieldLabel {
        color: #7cff00;
        font-size: 13px;
        font-weight: 800;
        background: transparent;
        border: none;
    }

    QLineEdit, QDateEdit {
        background-color: #0b100b;
        color: #f4fff4;
        border: 1px solid #2c4c22;
        border-radius: 11px;
        padding: 10px 13px;
        min-height: 24px;
        selection-background-color: #7cff00;
        selection-color: #071007;
    }

    QLineEdit:focus, QDateEdit:focus {
        border: 1px solid #7cff00;
        background-color: #0f160f;
    }

    QPushButton {
        background-color: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 #151d15,
            stop:1 #070b07
        );
        color: #f4fff4;
        border: 1px solid #345f22;
        border-radius: 13px;
        padding: 11px 22px;
        font-weight: 700;
        min-height: 24px;
    }

    QPushButton#RecentCustomerButton:checked {
        background-color: #7cff00;
        color: #071007;
        border: 1px solid #a6ff3d;
    }

    QPushButton:hover {
        border: 1px solid #7cff00;
        background-color: #172617;
    }

    QPushButton:pressed {
        background-color: #7cff00;
        color: #071007;
    }

    #PrimaryButton {
        background-color: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #8cff00,
            stop:1 #54c900
        );
        color: #071007;
        border: 1px solid #9dff28;
        border-radius: 14px;
        font-size: 15px;
        font-weight: 900;
        padding: 12px 28px;
    }

    #PrimaryButton:hover {
        background-color: #9dff28;
    }

    #WindowButton {
        background-color: #070b07;
        color: #dfffd8;
        border: 1px solid #263d1f;
        border-radius: 8px;
        min-width: 34px;
        min-height: 26px;
        padding: 0;
    }

    #WindowButton:hover {
        border: 1px solid #7cff00;
    }

    #WindowButton, #CloseButton {
        min-width: 32px;
        max-width: 32px;
        min-height: 30px;
        max-height: 30px;
        border-radius: 9px;
        padding: 0px;
    }

    #CloseButton:hover {
        background-color: #7cff00;
        color: #071007;
    }

    QListWidget {
        background-color: #080d08;
        color: #f4fff4;
        border: 1px solid #5bd600;
        border-radius: 12px;
        padding: 5px;
    }

    QListWidget::item {
        padding: 8px;
        border-radius: 8px;
    }

    QListWidget::item:selected {
        background-color: #7cff00;
        color: #071007;
    }

    QTableWidget {
        background-color: #060906;
        color: #f4fff4;
        gridline-color: #1f3d16;
        border: 1px solid #3f8f1e;
        border-radius: 14px;
        selection-background-color: white;
        selection-color: black;
    }

    QTableWidget::item {
        padding: 7px;
    }

    QHeaderView::section {
        background-color: #141914;
        color: white;
        border: none;
        border-bottom: 1px solid #335522;
        padding: 10px;
        font-size: 13px;
        font-weight: 700;
    }

    QStatusBar {
        background: transparent;
        color: #7cff00;
        font-weight: 700;
    }
    """