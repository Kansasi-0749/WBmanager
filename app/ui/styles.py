"""公共样式表（QSS）集中管理，消除重复定义。"""

BTN_BLUE = """
    QPushButton {
        background-color: #2563eb;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 500;
    }
    QPushButton:hover { background-color: #1d4ed8; }
"""

BTN_ORANGE = """
    QPushButton {
        background-color: #ea580c;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 500;
    }
    QPushButton:hover { background-color: #c2410c; }
"""

BTN_PURPLE = """
    QPushButton {
        background-color: #7c3aed;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 500;
    }
    QPushButton:hover { background-color: #6d28d9; }
"""

BTN_RED = """
    QPushButton {
        background-color: #dc2626;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 500;
    }
    QPushButton:hover { background-color: #b91c1c; }
"""

BTN_GREEN = """
    QPushButton {
        background-color: #0b8c5a;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 500;
    }
    QPushButton:hover { background-color: #0a7048; }
"""

BTN_CYAN = """
    QPushButton {
        background-color: #0891b2;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 500;
    }
    QPushButton:hover { background-color: #0e7490; }
"""

BTN_REFRESH = """
    QPushButton {
        background-color: #2a7de1;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 20px;
        font-weight: 500;
    }
    QPushButton:hover { background-color: #1a5fb0; }
"""

BTN_DELETE_PROMO = """
    QPushButton {
        background-color: #dc2626;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 500;
    }
    QPushButton:hover { background-color: #b91c1c; }
    QPushButton:disabled { background-color: #9ca3af; }
"""

BTN_REFRESH_PROMO = """
    QPushButton {
        background-color: #0b8c5a;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 500;
    }
    QPushButton:hover { background-color: #0a7048; }
    QPushButton:disabled { background-color: #9ca3af; }
"""

BTN_TOGGLE_ADJ = """
    QPushButton {
        background-color: #6b21a5;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 500;
    }
    QPushButton:hover { background-color: #581c87; }
"""

BTN_PROMO_ADJ = """
    QPushButton {
        background-color: #d97706;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 500;
    }
    QPushButton:hover { background-color: #b45309; }
"""

PROMO_COMBO_STYLE = """
    QComboBox {
        border: 1px solid #d0d9e8;
        border-radius: 6px;
        padding: 6px 12px;
        background-color: white;
        font-size: 13px;
    }
    QComboBox:hover { border-color: #2a7de1; }
    QComboBox::drop-down { border: none; }
"""

FILTER_INPUT_STYLE = """
    QLineEdit {
        border: 1px solid #ccc;
        border-radius: 3px;
        padding: 1px 4px;
        font-size: 10px;
        background: white;
    }
    QLineEdit:focus { border: 1px solid #0078d7; }
"""

FILTER_COMBO_STYLE = """
    QComboBox {
        border: 1px solid #ccc;
        border-radius: 3px;
        padding: 1px 2px;
        font-size: 10px;
        background: white;
    }
    QComboBox:focus { border: 1px solid #0078d7; }
"""

COPY_BTN_STYLE = """
    QPushButton {
        background-color: #e8f0fe;
        color: #1a73e8;
        border: 1px solid #1a73e8;
        border-radius: 3px;
        padding: 1px 4px;
        font-size: 10px;
        font-weight: 500;
    }
    QPushButton:hover { background-color: #d2e3fc; }
"""

COPY_STATUS_STYLE = "color: #5a7a9a; font-size: 10px; background: transparent; border: none;"
