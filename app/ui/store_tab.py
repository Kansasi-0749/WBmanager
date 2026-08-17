import os
import re

import pandas as pd
from PyQt6.QtCore import QEvent, QObject, Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QComboBox,
                             QDialog, QFileDialog, QFrame, QHBoxLayout,
                             QInputDialog, QLabel, QLineEdit, QMessageBox,
                             QProgressBar, QPushButton, QScrollArea,
                             QSizePolicy, QSpacerItem, QVBoxLayout, QWidget)

from app.core import config, paths
from app.core.competitor_manager import CompetitorManager
from app.core.data_manager import DataManager
from app.core.exporters import export_promo_adjustment, export_summary
from app.core.image_sync import ImageSyncThread
from app.core.promotion_manager import PromotionManager
from app.ui.multi_select_combo import MultiSelectComboBox
from app.ui.styles import (BTN_BLUE, BTN_DELETE_PROMO, BTN_GREEN, BTN_ORANGE,
                           BTN_PROMO_ADJ, BTN_PURPLE, BTN_RED, BTN_REFRESH,
                           BTN_REFRESH_PROMO, BTN_TOGGLE_ADJ, COPY_BTN_STYLE,
                           COPY_STATUS_STYLE, FILTER_COMBO_STYLE,
                           FILTER_INPUT_STYLE, PROMO_COMBO_STYLE)
from app.ui.table_widget import PromoTableWidget
from app.ui.upload_dialog import UploadDialog


# 促销列多选下拉选项 → 筛选条件令牌
_PROMO_OPTION_TO_TOKEN = {
    "✅ 有促销": "__HAS_VALUE__",
    "❌ 无促销": "__EMPTY__",
    "🟢 绿色高亮": "__GREEN__",
    "⬜ 正常颜色": "__NOT_GREEN__",
}


class ShiftWheelFilter(QObject):
    """按住 Shift 滚动鼠标滚轮时横向滚动目标滚动条。
    滚轮向下 → 界面向右滑；滚轮向上 → 界面向左滑。"""

    STEP_PX = 100

    def __init__(self, scrollbar, parent=None):
        super().__init__(parent)
        self.scrollbar = scrollbar

    def eventFilter(self, obj, event):
        if (
            event.type() == QEvent.Type.Wheel
            and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            delta = event.angleDelta().y()
            if delta:
                self.scrollbar.setValue(
                    self.scrollbar.value() - int(delta / 120) * self.STEP_PX
                )
            return True
        return super().eventFilter(obj, event)


class StoreTab(QWidget):
    """单店铺标签页 - 带筛选行"""

    def __init__(self, store_name: str, parent=None):
        super().__init__(parent)
        self.store_name = store_name
        self.data_manager = DataManager(store_name)
        self.promo_manager = PromotionManager(self.data_manager)
        self.filter_widgets = {}
        self.category_input = None
        self.filter_container = None
        self.copy_btn = None
        self.copy_status = None
        self.search_input = None
        self.search_results = []
        self.search_current_index = -1
        self.search_highlighted_row = -1
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._do_search)
        self._pending_search_text = ""
        self._filter_tail_spacer = None
        self._filter_tail_width = 0

        # ===== 设置默认路径 =====
        self.default_dir = config.STORE_DEFAULT_DIRS.get(
            store_name, os.path.expanduser("~")
        )

        self.setup_ui()
        self.load_data()

    def import_and_sort(self, file_path: str):
        """从Excel/CSV读取顺序，然后按照这个顺序重新排列当前数据"""
        try:
            # 1. 读取用户整理好的顺序文件
            if file_path.endswith(".csv"):
                df_order = pd.read_csv(file_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
            else:
                df_order = pd.read_excel(file_path, dtype=str)

            df_order = df_order.fillna("")

            # 2. 获取当前系统中的数据
            df_current = self.data_manager.load_products()

            if df_current.empty:
                QMessageBox.warning(self, "提示", "系统中没有数据可排序")
                return

            # 3. 从排序文件中提取WB编号的顺序
            order_wb_col = None
            for col in df_order.columns:
                if "WB编号" in col or "WB货号" in col:
                    order_wb_col = col
                    break

            if order_wb_col is None:
                QMessageBox.warning(self, "错误", "排序文件中没有找到WB编号列")
                return

            ordered_wb_codes = []
            for idx, row in df_order.iterrows():
                wb = str(row[order_wb_col]).strip()
                if wb and wb != "nan":
                    ordered_wb_codes.append(wb)

            if not ordered_wb_codes:
                QMessageBox.warning(self, "错误", "排序文件中没有有效的WB编号")
                return

            # 4. 按新顺序重新排列数据
            current_data_map = {}
            for idx, row in df_current.iterrows():
                wb = str(row.get("WB编号", "")).strip()
                if wb:
                    current_data_map[wb] = row

            new_rows = []
            matched_wb = []
            for wb in ordered_wb_codes:
                if wb in current_data_map:
                    new_rows.append(current_data_map[wb])
                    matched_wb.append(wb)

            unmatched = set(ordered_wb_codes) - set(matched_wb)
            if unmatched:
                QMessageBox.warning(
                    self, "提示",
                    f"以下 {len(unmatched)} 个WB编号在当前系统中不存在，已跳过:\n{', '.join(list(unmatched)[:10])}",
                )

            if not new_rows:
                QMessageBox.warning(self, "错误", "排序文件中没有找到匹配的商品")
                return

            # 5. 保存新顺序
            df_sorted = pd.DataFrame(new_rows)
            self.data_manager.save_products(df_sorted)
            self.load_data()

            QMessageBox.information(
                self, "排序完成",
                f"✅ 已按新顺序排列 {len(new_rows)} 个商品\n"
                f"⚠️ 跳过系统中不存在的WB编号: {len(unmatched)} 个",
            )
        except Exception as e:
            QMessageBox.critical(self, "错误", f"排序失败: {str(e)}")
            import traceback
            traceback.print_exc()

    # ===== 导出汇总表 =====
    def export_summary(self):
        """导出整个表格到桌面Excel（保留格式 + 条件格式）"""
        try:
            df = self.table.df_full.copy()

            if df.empty:
                QMessageBox.information(self, "提示", "没有数据可导出")
                return

            filename = f"{self.store_name}汇总表.xlsx"
            filepath = paths.desktop_dir() / filename
            export_summary(df, filepath)

            QMessageBox.information(
                self, "导出成功",
                f"已导出到桌面：\n{filename}\n\n",
            )
            self.status_label.setText(f"✅ 已导出: {filename}")

        except ImportError:
            QMessageBox.warning(self, "缺少依赖", "请安装 openpyxl：\npip install openpyxl")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出失败：\n{str(e)}")
            self.status_label.setText("❌ 导出失败")

    def export_promo_adjustment(self):
        """导出促销调整数据（含变化数值和百分比）"""
        try:
            df = self.table.df_full.copy()

            if df.empty:
                QMessageBox.information(self, "提示", "没有数据可导出")
                return

            promo_cols = [col for col in df.columns if "促" in col and col not in ["促销"]]
            if not promo_cols:
                QMessageBox.information(self, "提示", "没有促销数据可导出")
                return

            if "售价" not in df.columns:
                QMessageBox.warning(self, "错误", "数据中没有售价列")
                return

            filename = f"{self.store_name}汇总表.xlsx"
            filepath = paths.desktop_dir() / filename
            export_promo_adjustment(df, filepath)

            QMessageBox.information(
                self, "导出成功",
                f"已导出到桌面：\n{filename}\n\n"
                f"✅ 每个促销列后增加了变化数值和变化百分比列\n"
                f"✅ 促销价绿色 = 售价 ≤ 促销价",
            )
            self.status_label.setText(f"✅ 已导出: {filename}")

        except ImportError:
            QMessageBox.warning(self, "缺少依赖", "请安装 openpyxl：\npip install openpyxl")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出失败：\n{str(e)}")
            self.status_label.setText("❌ 导出失败")
            import traceback
            traceback.print_exc()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(3)

        toolbar = QHBoxLayout()

        self.import_btn = QPushButton("📥 导入商品")
        self.import_btn.setStyleSheet(BTN_BLUE)
        self.import_btn.clicked.connect(self.import_products)
        toolbar.addWidget(self.import_btn)

        self.add_product_btn = QPushButton("➕ 添加商品")
        self.add_product_btn.setStyleSheet(BTN_BLUE)
        self.add_product_btn.clicked.connect(self.add_products_manually)
        toolbar.addWidget(self.add_product_btn)

        self.promo_btn = QPushButton("📊 上传促销")
        self.promo_btn.setStyleSheet(BTN_ORANGE)
        self.promo_btn.clicked.connect(self.upload_promotion)
        toolbar.addWidget(self.promo_btn)

        self.update_btn = QPushButton("🔄 更新库存/价格")
        self.update_btn.setStyleSheet(BTN_BLUE)
        self.update_btn.clicked.connect(self.update_data)
        toolbar.addWidget(self.update_btn)

        self.import_competitor_btn = QPushButton("🔗 导入竞品链接")
        self.import_competitor_btn.setStyleSheet(BTN_PURPLE)
        self.import_competitor_btn.setToolTip("从Excel导入竞品链接\n第1列: WB编号\n第2~10列: 竞品链接(带批注价格)")
        self.import_competitor_btn.clicked.connect(self.import_competitors_from_template)
        toolbar.addWidget(self.import_competitor_btn)

        self.sync_all_img_btn = QPushButton("🖼️ 同步竞品图片")
        self.sync_all_img_btn.setStyleSheet(BTN_PURPLE)
        self.sync_all_img_btn.setToolTip("一键下载所有商品的竞品主图")
        self.sync_all_img_btn.clicked.connect(self.sync_all_competitor_images)
        toolbar.addWidget(self.sync_all_img_btn)

        toolbar.addStretch()

        self.refresh_btn = QPushButton("🔄 刷新数据")
        self.refresh_btn.setStyleSheet(BTN_REFRESH)
        self.refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(self.refresh_btn)

        self.promo_combo = QComboBox()
        self.promo_combo.setPlaceholderText("选择要删除的促销")
        self.promo_combo.setMinimumWidth(180)
        self.promo_combo.setStyleSheet(PROMO_COMBO_STYLE)
        toolbar.addWidget(self.promo_combo)

        self.delete_promo_btn = QPushButton("🗑️ 删除促销")
        self.delete_promo_btn.setStyleSheet(BTN_DELETE_PROMO)
        self.delete_promo_btn.clicked.connect(self.delete_promo_from_toolbar)
        self.delete_promo_btn.setEnabled(False)
        toolbar.addWidget(self.delete_promo_btn)

        self.refresh_promo_btn = QPushButton("🔄 刷新促销")
        self.refresh_promo_btn.setStyleSheet(BTN_REFRESH_PROMO)
        self.refresh_promo_btn.setToolTip("清理过期促销并重新排序")
        self.refresh_promo_btn.clicked.connect(self.refresh_promotions)
        self.refresh_promo_btn.setEnabled(False)
        toolbar.addWidget(self.refresh_promo_btn)

        self.toggle_adj_btn = QPushButton("📊 商品导出")
        self.toggle_adj_btn.setStyleSheet(BTN_TOGGLE_ADJ)
        self.toggle_adj_btn.setToolTip("导出当前表格数据到桌面Excel")
        self.toggle_adj_btn.clicked.connect(self.export_summary)
        toolbar.addWidget(self.toggle_adj_btn)

        self.promo_adj_btn = QPushButton("📊 促销调整")
        self.promo_adj_btn.setStyleSheet(BTN_PROMO_ADJ)
        self.promo_adj_btn.setToolTip("导出促销调整数据（含变化数值和百分比）")
        self.promo_adj_btn.clicked.connect(self.export_promo_adjustment)
        toolbar.addWidget(self.promo_adj_btn)

        self.clear_btn = QPushButton("🗑️ 清空汇总表")
        self.clear_btn.setStyleSheet(BTN_RED)
        self.clear_btn.clicked.connect(self.clear_data)
        toolbar.addWidget(self.clear_btn)

        main_layout.addLayout(toolbar)

        self.filter_container = QWidget()
        self.filter_container.setStyleSheet("""
            QWidget {
                background-color: #f0f2f5;
                border: 1px solid #dce4ec;
                border-bottom: none;
            }
        """)
        self.filter_container.setFixedHeight(32)
        self.filter_layout = QHBoxLayout(self.filter_container)
        self.filter_layout.setContentsMargins(2, 2, 2, 2)
        self.filter_layout.setSpacing(0)

        # 筛选行放进可横向滚动的容器，与表格滚动条同步对齐
        self.filter_scroll = QScrollArea()
        self.filter_scroll.setWidgetResizable(True)
        self.filter_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.filter_scroll.setFixedHeight(32)
        self.filter_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.filter_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.filter_scroll.setWidget(self.filter_container)

        main_layout.addWidget(self.filter_scroll)

        self.table = PromoTableWidget()
        self.table.delete_requested.connect(self.delete_product)
        main_layout.addWidget(self.table)

        # 筛选行与表格横向滚动双向同步
        self.table.horizontalScrollBar().valueChanged.connect(self._sync_filter_scroll)
        self.filter_scroll.horizontalScrollBar().valueChanged.connect(self._sync_table_scroll)

        # Shift + 滚轮：横向滚动表格（筛选行自动跟随）
        self._shift_wheel_filter = ShiftWheelFilter(self.table.horizontalScrollBar())
        self.table.viewport().installEventFilter(self._shift_wheel_filter)
        self.table.horizontalHeader().viewport().installEventFilter(self._shift_wheel_filter)
        self.filter_scroll.viewport().installEventFilter(self._shift_wheel_filter)

        status_layout = QHBoxLayout()
        self.status_label = QLabel("就绪")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        main_layout.addLayout(status_layout)

        self.setLayout(main_layout)

    def _sync_filter_scroll(self, value):
        """表格横向滚动时，筛选行同步滚动，保持控件与表头对齐。"""
        self.filter_scroll.horizontalScrollBar().setValue(value)

    def _sync_table_scroll(self, value):
        """筛选行滚动时，表格横向同步滚动。"""
        self.table.horizontalScrollBar().setValue(value)

    # ===== 刷新促销 =====
    def refresh_promotions(self):
        """刷新促销：清理过期 + 重新排序"""
        try:
            self.status_label.setText("🔄 正在刷新促销...")
            QApplication.processEvents()
            self.promo_manager.clean_expired()
            self.promo_manager.reorder_promotions()
            self.load_data()
            promo_count = len(self.promo_manager.get_promo_columns())
            QMessageBox.information(self, "完成", f"✅ 促销已刷新\n当前共 {promo_count} 个促销")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"刷新促销失败:\n{str(e)}")
            self.status_label.setText("❌ 刷新促销失败")

    # ===== 同步竞品图片 =====
    def sync_all_competitor_images(self):
        """一键同步所有商品的竞品图片"""
        df = self.data_manager.load_products()
        print(f"📊 加载到 {len(df)} 个商品")

        if df.empty:
            QMessageBox.information(self, "提示", "暂无商品数据")
            return

        all_tasks = []
        for _, row in df.iterrows():
            product_wb = str(row.get("WB编号", "")).strip()
            print(f"🔍 处理商品: {product_wb}")
            if not product_wb or product_wb == "nan":
                continue
            manager = CompetitorManager(self.store_name, product_wb)
            data = manager.get_all_competitors()
            print(f"   └─ 竞品数量: {len(data)}")
            for wb_code in data.keys():
                img_path = manager.get_image_path(wb_code)
                if img_path and os.path.exists(img_path):
                    print(f"      ⏭️ 跳过已有图片: {wb_code}")
                    continue
                else:
                    print(f"      📥 需要下载: {wb_code}")
                all_tasks.append((manager, wb_code))

        print(f"📋 最终需要下载的任务数: {len(all_tasks)}")

        if not all_tasks:
            QMessageBox.information(self, "提示", "所有竞品已有图片，无需同步")
            return

        reply = QMessageBox.question(
            self, "同步竞品图片",
            f"共 {len(all_tasks)} 个竞品需要下载主图，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            print("❌ 用户取消同步")
            return

        self._sync_progress_dialog = QDialog(self)
        self._sync_progress_dialog.setWindowTitle("同步竞品图片")
        self._sync_progress_dialog.setFixedSize(420, 120)
        layout = QVBoxLayout(self._sync_progress_dialog)
        self._sync_label = QLabel(f"正在下载 0/{len(all_tasks)}...")
        layout.addWidget(self._sync_label)
        self._sync_bar = QProgressBar()
        self._sync_bar.setMaximum(len(all_tasks))
        layout.addWidget(self._sync_bar)
        self._sync_detail = QLabel("")
        self._sync_detail.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(self._sync_detail)
        self._sync_progress_dialog.show()

        self._sync_cancelled_ref = [False]
        self._sync_thread = ImageSyncThread(all_tasks, self._sync_cancelled_ref)
        self._sync_thread.progress.connect(self._on_sync_progress)
        self._sync_thread.finished.connect(self._on_sync_all_done)
        self._sync_thread.start()

    def _on_sync_progress(self, cur, status):
        self._sync_label.setText(f"{status}  ({cur}/{self._sync_bar.maximum()})")
        self._sync_bar.setValue(cur)

    def _on_sync_all_done(self, success, fail):
        self._sync_progress_dialog.close()
        self.status_label.setText(f"✅ 同步完成: {success}成功/{fail}失败")

    # ===== 导入竞品链接 =====
    def import_competitors_from_template(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择包含竞品链接的Excel文件", self.default_dir,
            "Excel文件 (*.xlsx *.xls)",
        )
        if not file_path:
            return

        excel = None
        try:
            import win32com.client
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            wb = excel.Workbooks.Open(os.path.abspath(file_path))
            ws = wb.ActiveSheet

            total_imported = 0
            total_prices = 0
            skipped = 0
            row = 2

            while True:
                product_wb_val = ws.Cells(row, 1).Value
                if product_wb_val is None:
                    break

                if isinstance(product_wb_val, float) and product_wb_val == int(product_wb_val):
                    product_wb = str(int(product_wb_val))
                else:
                    product_wb = str(product_wb_val).strip()

                if product_wb:
                    manager = CompetitorManager(self.store_name, product_wb)

                    for col in range(2, 11):
                        cell = ws.Cells(row, col)
                        cell_value = str(cell.Value).strip() if cell.Value else ""
                        if not cell_value:
                            continue

                        wb_code = self._extract_wb_from_url(cell_value)
                        if not wb_code:
                            skipped += 1
                            continue

                        if manager.add_competitor(wb_code):
                            total_imported += 1

                        try:
                            comment = cell.Comment
                            if comment:
                                comment_text = comment.Text()
                                if comment_text:
                                    price = self._extract_price_from_comment(comment_text)
                                    if price is not None:
                                        manager.update_price(wb_code, price)
                                        total_prices += 1
                        except Exception:
                            pass

                row += 1
                if row > 10000:
                    break

            wb.Close(False)
            excel.Quit()
            excel = None

            msg = f"✅ 导入竞品: {total_imported} 个\n💰 设置价格: {total_prices} 个\n⏭️ 跳过无效链接: {skipped} 个"
            QMessageBox.information(self, "导入完成", msg)
            self.status_label.setText(f"✅ 竞品导入完成: {total_imported} 个")

        except ImportError:
            QMessageBox.critical(self, "缺少依赖", "请先安装: pip install pywin32")
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"导入竞品链接时出错:\n{str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            if excel:
                try:
                    excel.Quit()
                except Exception:
                    pass

    def _extract_wb_from_url(self, url: str) -> str:
        pattern = r"/catalog/(\d+)/detail\.aspx"
        match = re.search(pattern, url)
        return match.group(1) if match else ""

    def _extract_price_from_comment(self, comment_text: str):
        if not comment_text:
            return None
        lines = comment_text.strip().split("\n")
        for line in reversed(lines):
            numbers = re.findall(r"\d+\.?\d*", line.strip())
            if numbers:
                try:
                    return float(numbers[-1])
                except Exception:
                    continue
        return None

    # ===== 添加商品 =====
    def add_products_manually(self):
        from PyQt6.QtWidgets import QDialogButtonBox, QTextEdit

        dialog = QDialog(self)
        dialog.setWindowTitle("添加商品")
        dialog.setMinimumSize(400, 300)

        layout = QVBoxLayout(dialog)

        label = QLabel("请输入商品编号，每行一个：")
        layout.addWidget(label)

        text_edit = QTextEdit()
        text_edit.setPlaceholderText("G07412429274721\nG07402072401676\n...")
        layout.addWidget(text_edit)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        raw_text = text_edit.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "提示", "未输入任何商品编号")
            return

        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

        df = self.data_manager.load_products()
        existing = set(df["商品编号"].astype(str).str.strip().tolist())

        added = 0
        skipped = 0
        new_rows = []
        for code in lines:
            if code in existing:
                skipped += 1
                continue
            new_rows.append({
                "商品编号": code,
                "WB编号": "",
                "类目": "",
                "库存": 0,
                "仓库": "FBW",
                "状态": "正常",
                "售价": 0,
            })
            existing.add(code)
            added += 1

        if new_rows:
            df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

        self.data_manager.save_products(df)
        self.load_data()

        msg = f"✅ 添加: {added} 个"
        if skipped:
            msg += f"\n⏭️ 跳过重复: {skipped} 个"
        QMessageBox.information(self, "完成", msg)

    # ===== 搜索 =====
    def on_search_text_changed(self, text):
        self._pending_search_text = text.strip()
        self._search_timer.stop()
        self._search_timer.start(300)

    def _do_search(self):
        text = self._pending_search_text
        try:
            self.clear_search_highlight()
            self.search_results = []
            self.search_current_index = -1
            if not text:
                return
            search_text = text.lower()
            for row in range(self.table.rowCount()):
                # 筛选后隐藏的行不参与搜索
                if self.table.isRowHidden(row):
                    continue
                for col in range(self.table.columnCount()):
                    try:
                        item = self.table.item(row, col)
                        item_text = ""
                        if item is not None:
                            item_text = item.text()
                        if not item_text:
                            widget = self.table.cellWidget(row, col)
                            if widget:
                                label = widget.findChild(QLabel)
                                if label:
                                    item_text = label.text()
                        if item_text and search_text in item_text.lower():
                            self.search_results.append((row, col))
                    except Exception:
                        continue
            if self.search_results:
                self.search_current_index = 0
                QTimer.singleShot(10, lambda: self.highlight_search_result(self.search_results[0]))
        except Exception:
            pass

    def highlight_search_result(self, position):
        try:
            row, col = position
            self.clear_search_highlight()
            self.search_highlighted_row = row
            for c in range(self.table.columnCount()):
                item = self.table.item(row, c)
                if item and item.text():
                    item.setBackground(QColor(173, 216, 230))
            first_item = self.table.item(row, 0)
            if first_item:
                self.table.scrollToItem(first_item, QAbstractItemView.ScrollHint.PositionAtCenter)
            self.table.selectRow(row)
            self.table.setFocus()
        except Exception:
            pass

    def clear_search_highlight(self):
        try:
            if self.search_highlighted_row >= 0:
                row = self.search_highlighted_row
                for c in range(self.table.columnCount()):
                    item = self.table.item(row, c)
                    if item and item.text():
                        key = (row, c)
                        if key in self.table.row_bg_cache:
                            item.setBackground(self.table.row_bg_cache[key])
                        else:
                            item.setBackground(QColor(255, 255, 255))
                self.search_highlighted_row = -1
        except Exception:
            self.search_highlighted_row = -1

    def find_next_search(self):
        if not self.search_results or self.search_current_index < 0:
            return
        self.search_current_index = (self.search_current_index + 1) % len(self.search_results)
        self.highlight_search_result(self.search_results[self.search_current_index])

    def find_prev_search(self):
        if not self.search_results or self.search_current_index < 0:
            return
        self.search_current_index = (self.search_current_index - 1) % len(self.search_results)
        self.highlight_search_result(self.search_results[self.search_current_index])

    def copy_selected_cells(self):
        try:
            selected_ranges = self.table.selectedRanges()
            if not selected_ranges:
                if self.copy_status:
                    self.copy_status.setText("⚠️ 未选中")
                    QTimer.singleShot(2000, lambda: self.copy_status.setText(""))
                return
            all_rows = []
            for range_obj in selected_ranges:
                for row in range(range_obj.topRow(), range_obj.bottomRow() + 1):
                    row_data = []
                    for col in range(range_obj.leftColumn(), range_obj.rightColumn() + 1):
                        item = self.table.item(row, col)
                        if item is not None and item.text():
                            row_data.append(item.text())
                        else:
                            widget = self.table.cellWidget(row, col)
                            if widget:
                                label = widget.findChild(QLabel)
                                if label and label.text():
                                    row_data.append(label.text())
                                else:
                                    row_data.append("")
                            else:
                                row_data.append("")
                    if row_data:
                        all_rows.append("\t".join(row_data))
            if all_rows:
                QApplication.clipboard().setText("\n".join(all_rows))
                if self.copy_status:
                    self.copy_status.setText(f"✅ {len(all_rows)}行")
                    QTimer.singleShot(2000, lambda: self.copy_status.setText(""))
        except Exception:
            pass

    def clear_filters(self):
        for col, widget in self.filter_widgets.items():
            if isinstance(widget, MultiSelectComboBox):
                widget.reset()
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
        if self.search_input:
            self.search_input.clear()
        if self.category_input:
            self.category_input.clear()
        self.clear_search_highlight()
        self.table.apply_filter_with_category({}, None, "")
        self.status_label.setText(f"✅ 已清空筛选，共 {len(self.table.df_full)} 个商品")

    def setup_filter_row(self, df):
        while self.filter_layout.count():
            item = self.filter_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.filter_widgets = {}
        self.category_input = None
        self.copy_btn = None
        self.copy_status = None
        self.search_input = None

        all_columns = self.table.get_all_columns()
        normal_filter_columns = ["仓库", "库存", "状态"]

        for col_index, col in enumerate(all_columns):
            width = self.table.columnWidth(col_index)

            if col == "序号":
                label = QLabel("序号")
                label.setStyleSheet("font-weight: bold; color: #888; font-size: 10px;")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setFixedWidth(width)
                label.setFixedHeight(24)
                self.filter_layout.addWidget(label)
                continue

            if col == "类目":
                self.category_input = QLineEdit()
                self.category_input.setPlaceholderText("输入类目筛选...")
                self.category_input.setStyleSheet(FILTER_INPUT_STYLE)
                self.category_input.setFixedWidth(width)
                self.category_input.setFixedHeight(24)
                self.category_input.textChanged.connect(self.on_filter_changed)
                self.filter_layout.addWidget(self.category_input)
                continue

            if col in normal_filter_columns:
                if col in ["仓库", "状态"]:
                    # 多选筛选
                    if col in df.columns:
                        unique_values = df[col].dropna().unique().tolist()
                        unique_values = [str(v) for v in unique_values if str(v).strip()]
                        unique_values.sort()
                        multi = MultiSelectComboBox(unique_values)
                    else:
                        multi = MultiSelectComboBox([])
                    multi.setFixedWidth(width)
                    multi.setFixedHeight(24)
                    multi.selection_changed.connect(lambda: self.on_filter_changed())
                    multi.setProperty("column", col)
                    multi.setProperty("filter_type", "normal")
                    self.filter_widgets[col] = multi
                    self.filter_layout.addWidget(multi)
                else:
                    # 库存等普通下拉
                    combo = QComboBox()
                    combo.addItem("(全部)")
                    combo.setStyleSheet(FILTER_COMBO_STYLE)
                    combo.currentTextChanged.connect(lambda: self.on_filter_changed())
                    combo.setProperty("column", col)
                    combo.setProperty("filter_type", "normal")
                    combo.setFixedWidth(width)
                    combo.setFixedHeight(24)
                    if col in df.columns:
                        unique_values = df[col].dropna().unique().tolist()
                        unique_values = [str(v) for v in unique_values if str(v).strip()]
                        try:
                            unique_values.sort(key=lambda x: int(float(x)))
                        except Exception:
                            unique_values.sort()
                        for val in unique_values:
                            combo.addItem(val)
                    self.filter_widgets[col] = combo
                    self.filter_layout.addWidget(combo)

            elif col in self.table.promo_columns:
                # 促销列：多选筛选，有/无促销 与 绿色高亮/正常颜色 可同时勾选、互不干扰
                multi = MultiSelectComboBox(
                    ["✅ 有促销", "❌ 无促销", "🟢 绿色高亮", "⬜ 正常颜色"]
                )
                multi.setFixedWidth(width)
                multi.setFixedHeight(24)
                multi.selection_changed.connect(lambda: self.on_filter_changed())
                multi.setProperty("column", col)
                multi.setProperty("filter_type", "promo")
                self.filter_widgets[col] = multi
                self.filter_layout.addWidget(multi)

            elif col == "商品编号":
                # 搜索框 + 复制按钮 + 状态标签，总宽度 = width
                search_w = width - 74  # 复制按钮28 + 状态标签46

                self.search_input = QLineEdit()
                self.search_input.setPlaceholderText("🔍 搜索...")
                self.search_input.setStyleSheet(FILTER_INPUT_STYLE)
                self.search_input.setFixedWidth(search_w)
                self.search_input.setFixedHeight(24)
                self.search_input.textChanged.connect(self.on_search_text_changed)
                self.search_input.returnPressed.connect(self.find_next_search)
                self.filter_layout.addWidget(self.search_input)

                self.copy_btn = QPushButton("📋")
                self.copy_btn.setToolTip("选中单元格后点击复制")
                self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                self.copy_btn.setStyleSheet(COPY_BTN_STYLE)
                self.copy_btn.clicked.connect(self.copy_selected_cells)
                self.copy_btn.setFixedWidth(28)
                self.copy_btn.setFixedHeight(24)
                self.filter_layout.addWidget(self.copy_btn)

                self.copy_status = QLabel("")
                self.copy_status.setStyleSheet(COPY_STATUS_STYLE)
                self.copy_status.setFixedWidth(46)
                self.filter_layout.addWidget(self.copy_status)

            else:
                placeholder = QLabel("")
                placeholder.setFixedWidth(width)
                placeholder.setFixedHeight(24)
                self.filter_layout.addWidget(placeholder)

        # 尾部填充：让筛选行内容宽度比表格略宽，抵消表格纵向滚动条占用的视口宽度，
        # 保证两个横向滚动范围一致，最大滚动时筛选控件仍与表头对齐
        self._filter_tail_spacer = QSpacerItem(
            self._filter_tail_width, 0,
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum,
        )
        self.filter_layout.addSpacerItem(self._filter_tail_spacer)
        # 末尾拉伸吸收多余空间，避免 Qt 把剩余宽度平均分到各控件之间造成错位；
        # 内容超出视口时拉伸自动归零，不影响滚动
        self.filter_layout.addStretch()

    def _adjust_filter_tail(self):
        """按表格滚动范围调整筛选行尾部填充宽度，并保证筛选滚动范围 ≥ 表格。"""
        if self._filter_tail_spacer is None:
            return
        if self.filter_scroll.viewport().width() <= 0:
            QTimer.singleShot(50, self._adjust_filter_tail)
            return
        table_total = sum(self.table.columnWidth(i) for i in range(self.table.columnCount()))
        content_no_tail = table_total + 4  # 筛选行左右各 2px 边距
        base_max = max(0, content_no_tail - self.filter_scroll.viewport().width())
        table_max = self.table.horizontalScrollBar().maximum()
        self._filter_tail_width = max(0, table_max - base_max) + 2
        self._filter_tail_spacer.changeSize(
            self._filter_tail_width, 0,
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum,
        )
        self.filter_layout.invalidate()

    def on_filter_changed(self):
        filters = {}
        for col, widget in self.filter_widgets.items():
            if isinstance(widget, MultiSelectComboBox):
                selected = widget.get_selected()
                if not selected:
                    continue
                if widget.property("filter_type") == "promo":
                    filters[col] = [
                        _PROMO_OPTION_TO_TOKEN.get(str(x), str(x)) for x in selected
                    ]
                else:
                    filters[col] = selected
            elif isinstance(widget, QComboBox):
                text = widget.currentText()
                filter_type = widget.property("filter_type")
                if filter_type == "normal" and text and text != "(全部)":
                    filters[col] = text

        category_text = self.category_input.text().strip() if self.category_input else ""

        self.table.apply_filter_with_category(filters, None, category_text)

        visible_count = sum(
            1 for r in range(self.table.rowCount()) if not self.table.isRowHidden(r)
        )
        total_count = len(self.table.df_full)
        desc_parts = []
        for k, v in filters.items():
            if isinstance(v, list) and all(str(x).startswith("__") for x in v):
                token_labels = {
                    "__HAS_VALUE__": "有促销",
                    "__EMPTY__": "无促销",
                    "__GREEN__": "绿色高亮",
                    "__NOT_GREEN__": "正常颜色",
                }
                desc_parts.append(
                    f"{k}=[{','.join(token_labels.get(str(x), str(x)) for x in v)}]"
                )
            elif v == "__HAS_VALUE__":
                desc_parts.append(f"{k}=有促销")
            elif v == "__EMPTY__":
                desc_parts.append(f"{k}=无促销")
            elif isinstance(v, list):
                desc_parts.append(f"{k}=[{','.join(v)}]")
            else:
                desc_parts.append(f"{k}={v}")
        if category_text:
            desc_parts.append(f"类目≈{category_text}")
        if desc_parts:
            self.status_label.setText(f"🔍 {', '.join(desc_parts)} | {visible_count}/{total_count}")
        else:
            self.status_label.setText(f"✅ 共 {total_count} 个商品")

    def load_data(self):
        try:
            df = self.data_manager.load_products()
            promo_columns = self.promo_manager.get_promo_columns()
            self.table.set_store_name(self.store_name)

            df = self.promo_manager.apply_promo_to_df(df)

            self.promo_combo.clear()
            if promo_columns:
                self.promo_combo.addItem("-- 全部促销 --")
                self.promo_combo.addItems(promo_columns)
                self.delete_promo_btn.setEnabled(True)
                self.refresh_promo_btn.setEnabled(True)
            else:
                self.promo_combo.addItem("-- 全部促销 --")
                self.delete_promo_btn.setEnabled(False)
                self.refresh_promo_btn.setEnabled(False)
            meta = {
                col: self.promo_manager.get_promo_meta(col)
                for col in promo_columns
                if self.promo_manager.get_promo_meta(col)
            }
            self.table.set_promo_meta(meta)
            self.table.load_data(df, promo_columns)
            self.setup_filter_row(df)
            QTimer.singleShot(0, self._adjust_filter_tail)
            self.status_label.setText(f"✅ 共 {len(df)} 个商品，促销列: {len(promo_columns)}")
        except Exception as e:
            self.status_label.setText(f"❌ 加载失败: {str(e)}")

    def refresh_data(self):
        try:
            self.status_label.setText("🔄 正在刷新...")
            QApplication.processEvents()
            self.data_manager = DataManager(self.store_name)
            self.promo_manager = PromotionManager(self.data_manager)
            self.load_data()
            self.status_label.setText("✅ 刷新完成")
        except Exception as e:
            self.status_label.setText("❌ 刷新失败")

    def delete_promo_from_toolbar(self):
        promo_name = self.promo_combo.currentText()
        if not promo_name:
            return
        if promo_name == "-- 全部促销 --":
            if QMessageBox.question(
                self, "确认", "删除所有促销？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            ) == QMessageBox.StandardButton.Yes:
                self.promo_manager.delete_all_promotions()
                self.load_data()
            return
        if QMessageBox.question(
            self, "确认", f"删除「{promo_name}」？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self.promo_manager.delete_promotion(promo_name)
            self.load_data()

    def delete_product(self, wb_code: str, product_code: str):
        df = self.data_manager.load_products()
        df["商品编号"] = df["商品编号"].fillna("").astype(str).str.strip()
        df["WB编号"] = df["WB编号"].fillna("").astype(str).str.strip()

        # Bug修复：WB编号为空时禁止按WB匹配删除（会误删整批无WB编号商品），
        # 改为按商品编号匹配，删除前已有二次确认。
        if wb_code:
            mask = df["WB编号"] == wb_code
            key_desc = f"WB: {wb_code}"
        else:
            mask = df["商品编号"] == product_code
            key_desc = f"商品编号: {product_code}"

        if mask.any():
            df = df[~mask]
            self.data_manager.save_products(df)
            self.load_data()
            self.status_label.setText(f"🗑️ 已删除商品: {product_code} ({key_desc})")
        else:
            QMessageBox.warning(self, "错误", f"未找到商品: {product_code}")

    def import_products(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择商品数据文件", "", "Excel/CSV文件 (*.xlsx *.xls *.csv)")
        if not file_path:
            return
        # ✅ 增加 "排序数据" 选项
        mode, ok = QInputDialog.getItem(
            self, "导入模式",
            "请选择导入方式：",
            ["追加数据", "覆盖数据", "排序数据"],
            0, False,
        )
        if not ok or mode == "取消":
            return

        if mode == "排序数据":
            self.import_and_sort(file_path)
        else:
            mode = "append" if mode == "追加数据" else "overwrite"
            success, skipped, errors = self.data_manager.import_products(file_path, mode)
            QMessageBox.information(self, "导入结果", f"成功: {success}, 跳过: {skipped}")
            self.load_data()

    def upload_promotion(self):
        dialog = UploadDialog("上传促销", show_date=True, default_dir=self.default_dir, parent=self)
        if dialog.exec():
            if dialog.file_path:
                start_date, end_date = dialog.get_dates()
                self.promo_manager.import_promotion(dialog.file_path, start_date, end_date)
                self.load_data()

    def update_data(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择更新模板文件", self.default_dir,
            "Excel/CSV文件 (*.xlsx *.xls *.csv)",
        )
        if file_path:
            self.data_manager.update_from_template(file_path)
            self.load_data()

    def clear_data(self):
        if QMessageBox.question(
            self, "确认", "清空所有数据？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self.data_manager.save_products(self.data_manager._create_empty_df())
            self.promo_manager.promotions = []
            self.promo_manager._save()
            self.load_data()
