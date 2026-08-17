from PyQt6.QtWidgets import (QTableWidget, QTableWidgetItem, QHeaderView,
                             QApplication, QDialog, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QPushButton, QCheckBox, QLabel,
                             QComboBox, QWidget, QMessageBox, QMenu)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QShortcut, QKeySequence, QBrush, QAction
import pandas as pd
import os
import json
from datetime import datetime, date


class SearchDialog(QDialog):
    """搜索对话框 - Ctrl+F 触发"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_table = parent
        self.search_results = []
        self.current_index = -1
        self.previous_item = None
        self.init_ui()

        self.shortcut_find_next = QShortcut(QKeySequence("F3"), self)
        self.shortcut_find_next.activated.connect(self.find_next)
        self.search_input.returnPressed.connect(self.find_next)

    def init_ui(self):
        self.setWindowTitle("🔍 查找")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self.setModal(False)
        self.setFixedWidth(450)
        self.setFixedHeight(200)

        layout = QVBoxLayout()

        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("查找:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入搜索内容...")
        self.search_input.textChanged.connect(self.on_search_text_changed)
        input_layout.addWidget(self.search_input)
        layout.addLayout(input_layout)

        options_layout = QHBoxLayout()
        self.case_sensitive = QCheckBox("大小写敏感")
        self.case_sensitive.setChecked(False)
        options_layout.addWidget(self.case_sensitive)

        self.match_whole = QCheckBox("全词匹配")
        self.match_whole.setChecked(False)
        options_layout.addWidget(self.match_whole)
        options_layout.addStretch()
        layout.addLayout(options_layout)

        btn_layout = QHBoxLayout()
        self.find_next_btn = QPushButton("查找下一个")
        self.find_next_btn.setDefault(True)
        self.find_next_btn.clicked.connect(self.find_next)
        btn_layout.addWidget(self.find_next_btn)

        self.find_prev_btn = QPushButton("查找上一个")
        self.find_prev_btn.clicked.connect(self.find_prev)
        btn_layout.addWidget(self.find_prev_btn)
        btn_layout.addStretch()

        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        self.status_label = QLabel("输入搜索内容开始搜索")
        self.status_label.setStyleSheet("color: #6b7a8a; font-size: 12px;")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def on_search_text_changed(self, text):
        if not text.strip():
            self.clear_highlight()
            self.search_results = []
            self.current_index = -1
            self.status_label.setText("输入搜索内容开始搜索")
            return
        self.perform_search()

    def perform_search(self):
        if not self.parent_table:
            return

        text = self.search_input.text().strip()
        if not text:
            return

        self.clear_highlight()

        self.search_results = []
        row_count = self.parent_table.rowCount()
        col_count = self.parent_table.columnCount()

        case_sensitive = self.case_sensitive.isChecked()
        match_whole = self.match_whole.isChecked()

        search_text = text if case_sensitive else text.lower()

        for row in range(row_count):
            for col in range(col_count):
                item = self.parent_table.item(row, col)
                item_text = ""
                if item is not None:
                    item_text = item.text()
                if not item_text:
                    widget = self.parent_table.cellWidget(row, col)
                    if widget:
                        label = widget.findChild(QLabel)
                        if label:
                            item_text = label.text()
                if not item_text:
                    continue

                compare_text = item_text if case_sensitive else item_text.lower()

                if match_whole:
                    matched = compare_text == search_text
                else:
                    matched = search_text in compare_text

                if matched:
                    self.search_results.append((row, col))

        if self.search_results:
            self.current_index = 0
            self.highlight_item(self.search_results[0])
            self.status_label.setText(f"找到 {len(self.search_results)} 个匹配项，当前在第 1 个")
            self.find_next_btn.setEnabled(True)
            self.find_prev_btn.setEnabled(True)
        else:
            self.current_index = -1
            self.status_label.setText("未找到匹配项")
            self.find_next_btn.setEnabled(False)
            self.find_prev_btn.setEnabled(False)

    def highlight_item(self, position):
        row, col = position
        item = self.parent_table.item(row, col)
        if item is None:
            return

        self.clear_highlight()
        self.previous_item = item
        # ✅ 使用淡蓝色高亮（和商品编号搜索框一致）
        item.setBackground(QColor(173, 216, 230))
        self.parent_table.scrollToItem(item, QTableWidget.ScrollHint.PositionAtCenter)
        self.parent_table.setCurrentCell(row, col)

    def clear_highlight(self):
        if self.previous_item:
            self.previous_item.setBackground(QColor(255, 255, 255))
            self.previous_item = None

        if self.parent_table:
            row_count = self.parent_table.rowCount()
            col_count = self.parent_table.columnCount()
            for row in range(row_count):
                for col in range(col_count):
                    item = self.parent_table.item(row, col)
                    # ✅ 清除淡蓝色高亮
                    if item and item.background().color() == QColor(173, 216, 230):
                        item.setBackground(QColor(255, 255, 255))

    def find_next(self):
        if not self.search_results or self.current_index < 0:
            return
        self.current_index = (self.current_index + 1) % len(self.search_results)
        self.highlight_item(self.search_results[self.current_index])
        self.status_label.setText(f"找到 {len(self.search_results)} 个匹配项，当前在第 {self.current_index + 1} 个")

    def find_prev(self):
        if not self.search_results or self.current_index < 0:
            return
        self.current_index = (self.current_index - 1) % len(self.search_results)
        self.highlight_item(self.search_results[self.current_index])
        self.status_label.setText(f"找到 {len(self.search_results)} 个匹配项，当前在第 {self.current_index + 1} 个")

    def closeEvent(self, event):
        self.clear_highlight()
        super().closeEvent(event)


class PromoTableWidget(QTableWidget):
    """自定义表格组件 - 可筛选 + 同行链接按钮 + 右键删除"""

    filter_changed = pyqtSignal()
    row_highlighted = pyqtSignal(int)
    delete_requested = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.promo_meta = {}
        self.df_full = pd.DataFrame()
        self.df_filtered = pd.DataFrame()
        self.promo_columns = []
        self.search_dialog = None
        self.highlighted_row = -1
        self.row_bg_cache = {}
        self.store_name = ""

        self.setup_ui()

        self.shortcut_find = QShortcut(QKeySequence.StandardKey.Find, self)
        self.shortcut_find.activated.connect(self.show_search_dialog)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_context_menu)

    def setup_ui(self):
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(False)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSortIndicatorShown(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setMinimumHeight(35)
        self.horizontalHeader().setMaximumHeight(50)

        font = self.horizontalHeader().font()
        font.setPointSize(10)
        font.setBold(True)
        self.horizontalHeader().setFont(font)
        self.verticalHeader().setDefaultSectionSize(32)

        self.cellClicked.connect(self.on_cell_clicked)

    def set_store_name(self, name: str):
        self.store_name = name

    def on_context_menu(self, pos):
        row = self.rowAt(pos.y())
        if row < 0:
            return

        self.selectRow(row)

        wb_code = self._get_wb_code_by_row(row)
        product_code = self._get_product_code_by_row(row)

        menu = QMenu(self)

        warehouse_menu = QMenu("🏭 修改仓库", self)
        for wh in ['FBW', 'FBS', 'WS']:
            action = warehouse_menu.addAction(wh)
            action.triggered.connect(lambda checked, r=row, w=wh: self._update_warehouse(r, w))
        menu.addMenu(warehouse_menu)

        status_menu = QMenu("📊 修改状态", self)
        for st in ['正常', '好卖', '爆款', '淘汰']:
            action = status_menu.addAction(st)
            action.triggered.connect(lambda checked, r=row, s=st: self._update_status(r, s))
        menu.addMenu(status_menu)

        menu.addSeparator()

        delete_action = QAction("🗑️ 删除此商品", self)
        delete_action.triggered.connect(lambda: self._confirm_delete(wb_code, product_code))
        menu.addAction(delete_action)

        menu.exec(self.mapToGlobal(pos))

    def _update_warehouse(self, row: int, warehouse: str):
        col_idx = self._get_column_index("仓库")
        if col_idx == -1:
            return
        item = self.item(row, col_idx)
        if item:
            item.setText(warehouse)
        self._save_table_changes()

    def _update_status(self, row: int, status: str):
        col_idx = self._get_column_index("状态")
        if col_idx == -1:
            return
        item = self.item(row, col_idx)
        if item:
            item.setText(status)
            status_colors = {
                '好卖': QColor(217, 240, 217),
                '爆款': QColor(173, 216, 230),
                '淘汰': QColor(252, 200, 200)
            }
            if status in status_colors:
                item.setBackground(status_colors[status])
                self.row_bg_cache[(row, col_idx)] = QBrush(status_colors[status])
            else:
                item.setBackground(QColor(255, 255, 255))
                self.row_bg_cache[(row, col_idx)] = QBrush(QColor(255, 255, 255))
        self._save_table_changes()

    def _save_table_changes(self):
        if self.df_full.empty:
            return

        base_columns = ['商品编号', 'WB编号', '类目', '库存', '仓库', '状态', '售价']
        for row in range(self.rowCount()):
            wb_item = self.item(row, self._get_column_index("WB编号"))
            if not wb_item:
                continue
            wb = wb_item.text().strip()
            mask = self.df_full['WB编号'].astype(str).str.strip() == wb
            if mask.any():
                for col in base_columns:
                    col_idx = self._get_column_index(col)
                    if col_idx >= 0:
                        item = self.item(row, col_idx)
                        if item:
                            val = item.text().strip()
                            if val:
                                self.df_full.loc[mask, col] = val

        parent = self.parent()
        while parent:
            if hasattr(parent, 'data_manager'):
                parent.data_manager.save_products(self.df_full)
                break
            parent = parent.parent()

    def _get_product_code_by_row(self, row: int) -> str:
        col_idx = self._get_column_index("商品编号")
        if col_idx == -1:
            return ""
        widget = self.cellWidget(row, col_idx)
        if widget:
            label = widget.findChild(QLabel)
            if label:
                return label.text().strip()
        item = self.item(row, col_idx)
        return item.text().strip() if item else ""

    def _confirm_delete(self, wb_code: str, product_code: str):
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除此商品吗？\n\n商品编号: {product_code}\nWB编号: {wb_code}\n\n此操作不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit(wb_code, product_code)

    def on_cell_clicked(self, row, col):
        # ✅ 如果点击的是序号列（第0列）
        if col == 0:
            if self.highlighted_row == row:
                self.clear_row_highlight()
            else:
                # 清除搜索高亮（如果有）
                if hasattr(self, 'search_dialog') and self.search_dialog:
                    try:
                        self.search_dialog.clear_highlight()
                    except:
                        pass
                self.highlight_row(row)
        else:
            # 点击非序号列，清除行高亮
            self.clear_row_highlight()

    def highlight_row(self, row):
        if row < 0 or row >= self.rowCount():
            return
        self.clear_row_highlight()
        self.highlighted_row = row
        for col in range(self.columnCount()):
            item = self.item(row, col)
            if item:
                key = (row, col)
                if key not in self.row_bg_cache:
                    current_bg = item.background()
                    if current_bg and current_bg.color().alpha() > 0:
                        self.row_bg_cache[key] = current_bg
                    else:
                        self.row_bg_cache[key] = QBrush(QColor(255, 255, 255))
                item.setBackground(QColor(173, 216, 230))
        self.selectRow(row)
        self.row_highlighted.emit(row)

    def clear_row_highlight(self):
        if self.highlighted_row < 0:
            return
        row = self.highlighted_row
        for col in range(self.columnCount()):
            item = self.item(row, col)
            if item:
                key = (row, col)
                if key in self.row_bg_cache:
                    item.setBackground(self.row_bg_cache[key])
                else:
                    item.setBackground(QColor(255, 255, 255))
        self.clearSelection()
        self.highlighted_row = -1

    def show_search_dialog(self):
        if self.search_dialog is None or not self.search_dialog.isVisible():
            self.search_dialog = SearchDialog(self)
            self.search_dialog.show()
        else:
            self.search_dialog.raise_()
            self.search_dialog.activateWindow()

    def apply_filter(self, filters: dict, color_filter: str = None):
        self.apply_filter_with_category(filters, color_filter, "")

    def apply_filter_with_category(self, filters: dict, color_filter: str = None, category_text: str = ""):
        """应用筛选 - 使用安全字符串匹配"""
        if self.df_full is None or self.df_full.empty:
            self.df_filtered = self.df_full.copy() if self.df_full is not None else pd.DataFrame()
            self.load_filtered_data(self.df_filtered)
            return

        df = self.df_full.copy()

        # ===== 1. 普通筛选（放在最前面，避免其他筛选干扰） =====
        for col_name, filter_value in filters.items():
            if not filter_value or filter_value == "(全部)":
                continue
            if col_name not in df.columns:
                continue
            try:
                # ✅ 转为字符串并去除前后空格
                df[col_name] = df[col_name].fillna('').astype(str).str.strip()
                if filter_value == "__HAS_VALUE__":
                    df = df[df[col_name] != '']
                elif filter_value == "__EMPTY__":
                    df = df[df[col_name] == '']
                elif isinstance(filter_value, list):
                    # ✅ 列表值也 strip，确保匹配
                    clean_list = [str(v).strip() for v in filter_value]
                    df = df[df[col_name].isin(clean_list)]
                else:
                    df = df[df[col_name] == str(filter_value).strip()]
            except Exception as e:
                print(f"⚠️ 筛选异常 col={col_name}: {e}")
                continue

        # ===== 2. 颜色筛选 =====
        if color_filter:
            try:
                color_mask = []
                for idx, row in df.iterrows():
                    row_has_green = False
                    for promo_col in self.promo_columns:
                        if promo_col in row and promo_col in self.promo_meta:
                            try:
                                promo_val = str(row.get(promo_col, '')).strip()
                                if promo_val:
                                    promo_price = float(promo_val)
                                    price_str = row.get('售价', '')
                                    if price_str:
                                        price = float(price_str)
                                        if 0 < price <= promo_price:
                                            row_has_green = True
                                            break
                            except:
                                pass
                    color_mask.append(row_has_green)
                if color_filter == "green":
                    df = df[color_mask]
                elif color_filter == "white":
                    df = df[[not m for m in color_mask]]
            except Exception as e:
                print(f"⚠️ 颜色筛选异常: {e}")

        # ===== 3. 类目筛选（放最后，避免干扰其他列） =====
        if category_text and category_text.strip():
            if '类目' in df.columns:
                try:
                    df['类目'] = df['类目'].fillna('').astype(str)
                    category_lower = category_text.strip().lower()
                    mask = []
                    for val in df['类目'].tolist():
                        try:
                            match = category_lower in val.lower()
                        except:
                            match = False
                        mask.append(match)
                    df = df[mask]
                except Exception as e:
                    print(f"⚠️ 类目筛选异常: {e}")

        self.df_filtered = df
        self.load_filtered_data(df)

    def load_filtered_data(self, df):
        # 关闭排序和重绘
        self.setSortingEnabled(False)
        self.setUpdatesEnabled(False)

        self.clear()
        self.row_bg_cache = {}
        self.highlighted_row = -1

        if df.empty:
            self.setRowCount(0)
            self.setColumnCount(0)
            self.setUpdatesEnabled(True)
            return

        base_columns = ['商品编号', 'WB编号', '类目', '库存', '仓库', '状态', '售价']
        all_columns = ['序号'] + base_columns + self.promo_columns

        for col in base_columns + self.promo_columns:
            if col not in df.columns:
                df[col] = ''

        self.setRowCount(len(df))
        self.setColumnCount(len(all_columns))
        self.setHorizontalHeaderLabels(all_columns)

        col_widths = {
            '序号': 45,
            '商品编号': 200,
            'WB编号': 120,
            '类目': 110,
            '库存': 65,
            '仓库': 70,
            '状态': 70,
            '售价': 85,
        }
        for col in self.promo_columns:
            col_widths[col] = 85

        for i, col in enumerate(all_columns):
            width = col_widths.get(col, 70)
            self.setColumnWidth(i, width)

        # ✅ 获取商品编号和WB编号的列索引（直接用循环查找）
        col_idx_product = -1
        col_idx_wb = -1
        for i, col_name in enumerate(all_columns):
            if col_name == "商品编号":
                col_idx_product = i
            elif col_name == "WB编号":
                col_idx_wb = i

        # ✅ 创建大字体
        big_font = self.font()
        big_font.setPointSize(13)

        for row_idx, (_, row) in enumerate(df.iterrows()):
            seq_item = QTableWidgetItem(str(row_idx + 1))
            seq_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            seq_item.setBackground(QColor(245, 248, 250))
            self.row_bg_cache[(row_idx, 0)] = QBrush(QColor(245, 248, 250))
            self.setItem(row_idx, 0, seq_item)

            for col_idx, col_name in enumerate(all_columns[1:], 1):
                value = row.get(col_name, '')
                if pd.isna(value):
                    value = ''
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                # ✅ 如果是商品编号或WB编号列，使用大字体
                if col_idx == col_idx_product or col_idx == col_idx_wb:
                    item.setFont(big_font)

                bg_color = None

                if col_name in self.promo_columns and col_name in self.promo_meta:
                    try:
                        if str(value).strip():
                            promo_price = float(value)
                            price = float(row.get('售价', 0)) if row.get('售价', '') else 0
                            if 0 < price <= promo_price:
                                bg_color = QColor(212, 237, 201)
                    except:
                        pass

                if col_name == '状态' and value:
                    status_colors = {
                        '好卖': QColor(217, 240, 217),
                        '爆款': QColor(173, 216, 230),
                        '淘汰': QColor(252, 200, 200)
                    }
                    if value in status_colors:
                        bg_color = status_colors[value]

                if bg_color:
                    item.setBackground(bg_color)
                    self.row_bg_cache[(row_idx, col_idx)] = QBrush(bg_color)
                else:
                    self.row_bg_cache[(row_idx, col_idx)] = QBrush(QColor(255, 255, 255))

                self.setItem(row_idx, col_idx, item)

        self._add_competitor_buttons()

        today = datetime.now().strftime("%Y-%m-%d")

        for col_idx, col_name in enumerate(all_columns):
            if col_name in self.promo_meta:
                meta = self.promo_meta[col_name]
                start = meta.get('start_date', '')
                end = meta.get('end_date', '')
                is_active = start <= today <= end if start and end else False

                tooltip = f"📌 促销名称：{meta.get('promotion_name', '')}\n"
                tooltip += f"📅 开始时间：{start}\n"
                tooltip += f"📅 结束时间：{end}"

                if start and end:
                    try:
                        start_date_obj = datetime.strptime(start, "%Y-%m-%d").date()
                        end_date_obj = datetime.strptime(end, "%Y-%m-%d").date()
                        duration = (end_date_obj - start_date_obj).days + 1
                        days_to_start = (start_date_obj - date.today()).days

                        if days_to_start > 0:
                            tooltip += f"\n⏰ 还有 {days_to_start} 天开始，持续 {duration} 天"
                        else:
                            if end:
                                end_date = datetime.strptime(end, "%Y-%m-%d").date()
                                remaining = (end_date - date.today()).days
                                if remaining > 0:
                                    tooltip += f"\n⏳ 剩余 {remaining} 天结束"
                                elif remaining == 0:
                                    tooltip += "\n⚠️ 今天结束"
                                else:
                                    tooltip += f"\n❌ 已过期 {abs(remaining)} 天"
                    except:
                        pass
                elif end:
                    try:
                        end_date = datetime.strptime(end, "%Y-%m-%d").date()
                        remaining = (end_date - date.today()).days
                        if remaining > 0:
                            tooltip += f"\n⏳ 剩余 {remaining} 天结束"
                        elif remaining == 0:
                            tooltip += "\n⚠️ 今天结束"
                        else:
                            tooltip += f"\n❌ 已过期 {abs(remaining)} 天"
                    except:
                        pass

                if is_active:
                    tooltip += "\n\n🟢 当前正在生效"

                header_item = self.horizontalHeaderItem(col_idx)
                if header_item:
                    header_item.setToolTip(tooltip)
                    if is_active:
                        header_item.setText(f"🟢 {col_name}")
                    else:
                        header_item.setText(col_name)

        # 恢复重绘
        self.setUpdatesEnabled(True)
        self.setSortingEnabled(False)

    def _add_competitor_buttons(self):
        col_idx = self._get_column_index("商品编号")
        if col_idx == -1:
            return

        wb_col_idx = self._get_column_index("WB编号")

        for row in range(self.rowCount()):
            old_widget = self.cellWidget(row, col_idx)
            if old_widget:
                self.removeCellWidget(row, col_idx)

        for row in range(self.rowCount()):
            item = self.item(row, col_idx)
            if not item:
                continue
            product_code = item.text().strip()
            if not product_code:
                continue

            item.setText("")

            wb_code = ""
            if wb_col_idx != -1:
                wb_item = self.item(row, wb_col_idx)
                if wb_item:
                    wb_code = wb_item.text().strip()

            container = QWidget()
            container.setProperty("is_competitor_container", True)
            container.setStyleSheet("background: transparent;")
            container.setFixedHeight(28)

            layout = QHBoxLayout(container)
            layout.setContentsMargins(4, 0, 4, 0)
            layout.setSpacing(4)

            label = QLabel(product_code)
            label.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    background: transparent;
                    color: #1a1a1a;
                    padding: 0px;
                }
            """)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            btn = QPushButton("🔗")
            btn.setFixedSize(22, 22)
            btn.setToolTip("查看同行链接")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #e8f0fe;
                    border: 1px solid #1a73e8;
                    border-radius: 4px;
                    font-size: 10px;
                    color: #1a73e8;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #d2e3fc;
                }
            """)
            btn.clicked.connect(
                lambda checked, code=wb_code: self._show_competitor_dialog_by_wb(code)
            )

            layout.addWidget(label, 1)
            layout.addWidget(btn, 0)

            self.setCellWidget(row, col_idx, container)
            self.setRowHeight(row, 28)

    def _get_column_index(self, col_name: str) -> int:
        for i in range(self.columnCount()):
            header = self.horizontalHeaderItem(i)
            if header and header.text() == col_name:
                return i
        return -1

    def _get_store_name(self) -> str:
        if self.store_name:
            return self.store_name
        parent = self.parent()
        while parent:
            if hasattr(parent, 'store_name'):
                return parent.store_name
            parent = parent.parent()
        return "未知店铺"

    def _get_wb_code_by_row(self, row: int) -> str:
        wb_col_idx = self._get_column_index("WB编号")
        if wb_col_idx == -1:
            return ""
        item = self.item(row, wb_col_idx)
        if item:
            return item.text().strip()
        return ""

    def _show_competitor_dialog_by_wb(self, wb_code: str):
        if not wb_code:
            QMessageBox.warning(self, "提示", "未找到该商品的WB编号")
            return
        store_name = self._get_store_name()
        try:
            from competitor_dialog import CompetitorDialog
            dialog = CompetitorDialog(store_name, wb_code, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开竞品对话框失败:\n{str(e)}")

    def _show_competitor_dialog(self, row: int):
        wb_code = self._get_wb_code_by_row(row)
        self._show_competitor_dialog_by_wb(wb_code)

    def set_promo_meta(self, meta: dict):
        self.promo_meta = meta

    def load_data(self, df: pd.DataFrame, promo_columns: list):
        self.df_full = df.copy()
        self.df_filtered = df.copy()
        self.promo_columns = promo_columns
        self.load_filtered_data(df)

    def get_all_columns(self):
        base_columns = ['商品编号', 'WB编号', '类目', '库存', '仓库', '状态', '售价']
        return ['序号'] + base_columns + self.promo_columns