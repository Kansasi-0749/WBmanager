from PyQt6.QtWidgets import (QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel,
                             QVBoxLayout, QWidget)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QFont


class MultiSelectComboBox(QWidget):
    """多选下拉筛选组件 - 美化版"""
    selection_changed = pyqtSignal()

    def __init__(self, items: list = None, parent=None):
        super().__init__(parent)
        self._items = items or []
        self._checked = set(self._items)
        self._popup = None
        self._checkboxes = {}
        self._select_all_cb = None
        self._updating = False

        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 主容器
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 内容区（点击弹出下拉）
        self._content = QFrame()
        self._content.setStyleSheet("""
                QFrame {
                    background: white;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                }
                QFrame:hover {
                    border: 1px solid #4a90d9;
                    background: #f8f9fa;
                }
            """)
        self._content.mousePressEvent = self._on_click
        content_layout = QHBoxLayout(self._content)
        content_layout.setContentsMargins(8, 0, 4, 0)
        content_layout.setSpacing(4)

        # 显示文本
        self._label = QLabel("(全部)")
        self._label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #333;
                border: none;
                background: transparent;
            }
        """)
        content_layout.addWidget(self._label, 1)

        # 下拉箭头
        self._arrow = QLabel("▾")
        self._arrow.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #999;
                border: none;
                background: transparent;
                padding: 0px 2px;
            }
        """)
        content_layout.addWidget(self._arrow)

        main_layout.addWidget(self._content)

    def set_items(self, items: list):
        self._items = items
        self._checked = set(items)
        self._update_display()

    def _on_click(self, event):
        self._show_popup()

    def _show_popup(self):
        if self._popup and self._popup.isVisible():
            self._popup.hide()
            return

        self._popup = QFrame()
        self._popup.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._popup.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e0e4ea;
                border-radius: 8px;
            }
        """)
        # 添加阴影效果（通过设置图形效果）
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 30))
        self._popup.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self._popup)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(1)

        # 全选复选框
        self._select_all_cb = QCheckBox("  全选")
        self._select_all_cb.setStyleSheet("""
            QCheckBox {
                font-size: 11px;
                font-weight: 600;
                color: #555;
                padding: 5px 8px;
                border-radius: 4px;
                spacing: 6px;
            }
            QCheckBox:hover {
                background: #f0f3f7;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
                border-radius: 3px;
                border: 1.5px solid #c0c8d4;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #4a90d9;
                border-color: #4a90d9;
            }
        """)
        self._select_all_cb.clicked.connect(self._on_select_all_clicked)
        layout.addWidget(self._select_all_cb)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border: none; background: #e8ecf0; max-height: 1px;")
        layout.addWidget(sep)

        # 各选项
        self._checkboxes = {}
        for item in self._items:
            cb = QCheckBox(f"  {item}")
            cb.setStyleSheet("""
                QCheckBox {
                    font-size: 11px;
                    color: #333;
                    padding: 5px 8px;
                    border-radius: 4px;
                    spacing: 6px;
                }
                QCheckBox:hover {
                    background: #f5f7fa;
                }
                QCheckBox::indicator {
                    width: 15px;
                    height: 15px;
                    border-radius: 3px;
                    border: 1.5px solid #c0c8d4;
                    background: white;
                }
                QCheckBox::indicator:checked {
                    background: #4a90d9;
                    border-color: #4a90d9;
                }
            """)
            cb.setChecked(item in self._checked)
            cb.clicked.connect(lambda checked, i=item: self._on_item_clicked(i, checked))
            self._checkboxes[item] = cb
            layout.addWidget(cb)

        # 更新全选状态
        self._update_select_all_state()

        # 定位弹出窗口
        global_pos = self.mapToGlobal(QPoint(0, self.height() + 2))
        self._popup.move(global_pos)
        self._popup.setMinimumWidth(self.width())
        self._popup.show()

    def _on_select_all_clicked(self, checked):
        if self._updating:
            return
        self._updating = True

        if checked:
            self._checked = set(self._items)
        else:
            self._checked = set()

        for item, cb in self._checkboxes.items():
            cb.setChecked(item in self._checked)

        self._updating = False
        self._update_display()
        self.selection_changed.emit()

    def _on_item_clicked(self, item, checked):
        if self._updating:
            return
        self._updating = True

        if checked:
            self._checked.add(item)
        else:
            self._checked.discard(item)

        self._update_select_all_state()
        self._update_display()
        self._updating = False
        self.selection_changed.emit()

    def _update_select_all_state(self):
        if not self._select_all_cb:
            return
        if len(self._checked) == len(self._items) and len(self._items) > 0:
            self._select_all_cb.setCheckState(Qt.CheckState.Checked)
        elif len(self._checked) == 0:
            self._select_all_cb.setCheckState(Qt.CheckState.Unchecked)
        else:
            self._select_all_cb.setCheckState(Qt.CheckState.PartiallyChecked)

    def _update_display(self):
        if len(self._checked) == len(self._items) or len(self._checked) == 0:
            self._label.setText("(全部)")
            self._label.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    color: #999;
                    border: none;
                    background: transparent;
                }
            """)
        elif len(self._checked) == 1:
            self._label.setText(list(self._checked)[0])
            self._label.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    color: #333;
                    font-weight: 500;
                    border: none;
                    background: transparent;
                }
            """)
        else:
            count = len(self._checked)
            self._label.setText(f"  已选 {count} 项")
            self._label.setStyleSheet("""
                QLabel {
                    font-size: 10px;
                    color: white;
                    font-weight: 600;
                    border: none;
                    background: #4a90d9;
                    border-radius: 8px;
                    padding: 1px 8px;
                }
            """)

    def get_selected(self) -> list:
        if len(self._checked) == 0 or len(self._checked) == len(self._items):
            return []
        return list(self._checked)

    def reset(self):
        self._checked = set(self._items)
        self._update_display()
