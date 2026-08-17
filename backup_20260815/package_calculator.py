from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QLineEdit, QGroupBox, QGridLayout,
                             QFrame, QHeaderView, QTableWidget, QTableWidgetItem)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont


class PackageCalculator(QWidget):
    """包装尺寸计算工具 - 三个输入框对比"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.results = {}
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)

        # ===== 标题 =====
        title = QLabel("📦 包装尺寸计算工具")
        title.setStyleSheet("font-size: 20px; font-weight: 600; color: #0a1e3c;")
        main_layout.addWidget(title)

        # ===== 三个输入框 =====
        input_layout = QHBoxLayout()
        input_layout.setSpacing(20)

        self.inputs = []
        for i in range(3):
            group = QGroupBox(f"输入框 {i+1}")
            group.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #dce4ec;
                    border-radius: 6px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 6px;
                }
            """)
            group_layout = QVBoxLayout()

            input_field = QLineEdit()
            input_field.setPlaceholderText("例: 13x12x3 或 13 12 3")
            input_field.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #c8d6e8;
                    border-radius: 4px;
                    padding: 10px 12px;
                    font-size: 16px;
                    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
                }
                QLineEdit:focus {
                    border: 1px solid #1a73e8;
                }
            """)
            input_field.textChanged.connect(lambda text, idx=i: self.on_input_changed(idx, text))
            group_layout.addWidget(input_field)
            self.inputs.append(input_field)

            group.setLayout(group_layout)
            input_layout.addWidget(group)

        main_layout.addLayout(input_layout)

        # ===== 操作按钮 =====
        btn_layout = QHBoxLayout()
        self.clear_btn = QPushButton("🗑️ 清空全部")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #e8e8e8;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #d0d0d0; }
        """)
        self.clear_btn.clicked.connect(self.clear_all)
        btn_layout.addStretch()
        btn_layout.addWidget(self.clear_btn)
        main_layout.addLayout(btn_layout)

        # ===== 分隔线 =====
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)

        # ===== 结果表格 =====
        result_label = QLabel("📊 计算结果")
        result_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #0a1e3c;")
        main_layout.addWidget(result_label)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["输入框 1", "输入框 2", "输入框 3"])
        self.table.setRowCount(4)  # ✅ 4行
        self.table.setVerticalHeaderLabels(["📐 体积 (cm³)", "💧 容量 (L)", "📉 差值", "📊 百分比"])
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #dce4ec;
                border-radius: 6px;
                gridline-color: #e8ecf0;
            }
            QTableWidget::item {
                padding: 12px 8px;
                font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
                font-size: 16px;
            }
            QHeaderView::section {
                background-color: #f0f2f5;
                font-weight: bold;
                font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
                font-size: 14px;
                padding: 8px 10px;
                border: none;
                border-right: 1px solid #dce4ec;
                border-bottom: 1px solid #dce4ec;
            }
        """)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.verticalHeader().setDefaultSectionSize(55)
        self.table.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._set_placeholder()

        main_layout.addWidget(self.table)
        main_layout.addStretch()
        self.setLayout(main_layout)

    def _set_placeholder(self):
        font = QFont("Segoe UI", 16)
        for row in range(4):
            for col in range(3):
                item = QTableWidgetItem("—")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFont(font)
                self.table.setItem(row, col, item)

    def on_input_changed(self, idx: int, text: str):
        self.calculate_all()

    def parse_dimensions(self, text: str):
        text = text.strip()
        if not text:
            return None

        import re
        parts = re.split(r'[xX\s]+', text)
        parts = [p for p in parts if p]

        if len(parts) == 3:
            try:
                l = float(parts[0])
                w = float(parts[1])
                h = float(parts[2])
                if l > 0 and w > 0 and h > 0:
                    return (l, w, h)
            except ValueError:
                return None
        return None

    def calculate_all(self):
        self.results = {}
        for i, input_field in enumerate(self.inputs):
            text = input_field.text().strip()
            dims = self.parse_dimensions(text)
            if dims:
                l, w, h = dims
                volume = l * w * h
                liter = volume / 1000
                self.results[i] = {
                    "volume": volume,
                    "liter": liter,
                    "dimensions": dims,
                    "valid": True
                }
            else:
                self.results[i] = {"valid": False}

        base_idx = None
        base_data = None
        for i in range(3):
            if self.results.get(i, {}).get("valid", False):
                base_idx = i
                base_data = self.results[i]
                break

        font = QFont("Segoe UI", 16)
        font_bold = QFont("Segoe UI", 16, QFont.Weight.Bold)

        for row in range(4):
            for col in range(3):
                idx = col
                item = QTableWidgetItem()
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                if row == 0:
                    if self.results.get(idx, {}).get("valid", False):
                        vol = self.results[idx]["volume"]
                        item.setText(f"{vol:,.0f}")
                        item.setFont(font_bold)
                    else:
                        item.setText("—")
                        item.setFont(font)

                elif row == 1:
                    if self.results.get(idx, {}).get("valid", False):
                        lit = self.results[idx]["liter"]
                        item.setText(f"{lit:.2f}")
                        item.setFont(font_bold)
                    else:
                        item.setText("—")
                        item.setFont(font)

                elif row == 2:
                    if base_data and base_idx is not None and idx != base_idx:
                        if self.results.get(idx, {}).get("valid", False):
                            vol_diff = self.results[idx]["volume"] - base_data["volume"]
                            lit_diff = self.results[idx]["liter"] - base_data["liter"]
                            if vol_diff > 0:
                                item.setText(f"+{vol_diff:,.0f}  (+{lit_diff:+.2f}L)")
                            else:
                                item.setText(f"{vol_diff:,.0f}  ({lit_diff:+.2f}L)")
                            if vol_diff > 0:
                                item.setForeground(QColor(220, 38, 38))
                            elif vol_diff < 0:
                                item.setForeground(QColor(22, 163, 74))
                            else:
                                item.setForeground(QColor(107, 114, 128))
                            item.setFont(font_bold)
                        else:
                            item.setText("—")
                            item.setFont(font)
                    elif base_idx is not None and idx == base_idx:
                        item.setText("基准")
                        item.setForeground(QColor(26, 115, 232))
                        item.setFont(font_bold)
                    else:
                        item.setText("—")
                        item.setFont(font)

                elif row == 3:
                    if base_data and base_idx is not None and idx != base_idx:
                        if self.results.get(idx, {}).get("valid", False):
                            percent = (self.results[idx]["volume"] / base_data["volume"] - 1) * 100
                            if percent > 0:
                                item.setText(f"+{percent:.1f}%")
                            else:
                                item.setText(f"{percent:.1f}%")
                            if percent > 0:
                                item.setForeground(QColor(220, 38, 38))
                            elif percent < 0:
                                item.setForeground(QColor(22, 163, 74))
                            else:
                                item.setForeground(QColor(107, 114, 128))
                            item.setFont(font_bold)
                        else:
                            item.setText("—")
                            item.setFont(font)
                    elif base_idx is not None and idx == base_idx:
                        item.setText("基准")
                        item.setForeground(QColor(26, 115, 232))
                        item.setFont(font_bold)
                    else:
                        item.setText("—")
                        item.setFont(font)

                self.table.setItem(row, col, item)

    def clear_all(self):
        for input_field in self.inputs:
            input_field.clear()
        self.calculate_all()