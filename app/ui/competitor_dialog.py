import os
import webbrowser
from datetime import datetime
from typing import Dict, List, Optional

from PyQt6.QtCore import QDate, QDateTime, Qt, QTime, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (QApplication, QDialog, QFileDialog, QFrame,
                             QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMessageBox, QProgressBar,
                             QPushButton, QRadioButton, QSplitter, QToolTip,
                             QVBoxLayout, QWidget)

from PyQt6.QtCharts import (QChart, QChartView, QDateTimeAxis, QLineSeries,
                            QScatterSeries, QValueAxis)

from app.core.competitor_manager import CompetitorManager
from app.core.image_sync import ImageSyncThread


class CompetitorListItem(QWidget):
    delete_clicked = pyqtSignal(str)

    def __init__(self, wb_code: str, price: str = "", image_path: str = None, store_type: str = "", parent=None):
        super().__init__(parent)
        self.wb_code = wb_code
        self.setFixedHeight(80)
        self.setStyleSheet("""
            CompetitorListItem {
                background: white;
                border-radius: 4px;
            }
            CompetitorListItem:hover {
                background: #f5f8fa;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(12)

        self.img_label = QLabel()
        self.img_label.setFixedSize(80, 80)
        self.img_label.setStyleSheet("""
            QLabel {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background: #f8f8f8;
            }
        """)
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(76, 76, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
                self.img_label.setPixmap(scaled)
            else:
                self.img_label.setText("📷")
                self.img_label.setStyleSheet("""
                    QLabel {
                        border: 1px solid #e0e0e0;
                        border-radius: 6px;
                        background: #f8f8f8;
                        font-size: 32px;
                        color: #ccc;
                    }
                """)
        else:
            self.img_label.setText("📷")
            self.img_label.setStyleSheet("""
                QLabel {
                    border: 1px solid #e0e0e0;
                    border-radius: 6px;
                    background: #f8f8f8;
                    font-size: 32px;
                    color: #ccc;
                }
            """)

        layout.addWidget(self.img_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        wb_label = QLabel(wb_code)
        wb_label.setStyleSheet("font-weight: bold; font-size: 15px; color: #1a1a1a;")
        text_layout.addWidget(wb_label)

        if price:
            price_label = QLabel(f"¥{price}")
            price_label.setStyleSheet("color: #1a73e8; font-size: 14px;")
            text_layout.addWidget(price_label)

        self.store_type_label = QLabel(store_type[0] if store_type else "本")
        self.store_type_label.setFixedSize(28, 28)
        self.store_type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.store_type_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: white;
                border-radius: 14px;
                background: #4caf50;
            }
        """)
        self._update_store_type_style(store_type if store_type else "本土店")
        text_layout.addWidget(self.store_type_label)

        layout.addLayout(text_layout, 1)

        self.del_btn = QPushButton("✕")
        self.del_btn.setFixedSize(32, 32)
        self.del_btn.setToolTip("删除此竞品")
        self.del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #999;
                font-size: 18px;
                font-weight: bold;
                border-radius: 16px;
            }
            QPushButton:hover {
                background: #fee8e8;
                color: #d32f2f;
            }
        """)
        self.del_btn.clicked.connect(self.on_delete_clicked)
        layout.addWidget(self.del_btn)

    def _update_store_type_style(self, store_type: str):
        if store_type == "跨境店":
            self.store_type_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    font-weight: bold;
                    color: white;
                    border-radius: 14px;
                    background: #2196f3;
                }
            """)
        else:
            self.store_type_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    font-weight: bold;
                    color: white;
                    border-radius: 14px;
                    background: #4caf50;
                }
            """)

    def update_store_type(self, store_type: str):
        display_text = store_type[0] if store_type else "本"
        self.store_type_label.setText(display_text)
        self._update_store_type_style(store_type if store_type else "本土店")

    def on_delete_clicked(self):
        self.delete_clicked.emit(self.wb_code)


class PriceChartView(QChartView):
    """价格折线图组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setMinimumHeight(200)
        self.setStyleSheet("background: white; border: none;")
        self.setMouseTracking(True)

        self.chart = QChart()
        self.chart.setTitle("价格趋势")
        self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.chart.setTheme(QChart.ChartTheme.ChartThemeLight)
        self.chart.legend().setVisible(False)

        self.setChart(self.chart)

        self.line_series = QLineSeries()
        self.line_series.setName("价格")
        pen = QPen(QColor(26, 115, 232))
        pen.setWidth(2)
        self.line_series.setPen(pen)
        self.chart.addSeries(self.line_series)

        self.scatter_series = QScatterSeries()
        self.scatter_series.setMarkerSize(8)
        self.scatter_series.setColor(QColor(26, 115, 232))
        self.scatter_series.setBorderColor(QColor(255, 255, 255))
        self.scatter_series.hovered.connect(self.on_point_hovered)
        self.chart.addSeries(self.scatter_series)

        self.axis_x = QDateTimeAxis()
        self.axis_x.setFormat("MM-dd")
        self.axis_x.setTitleText("日期")
        self.axis_x.setLabelsAngle(-30)
        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)
        self.line_series.attachAxis(self.axis_x)
        self.scatter_series.attachAxis(self.axis_x)

        self.axis_y = QValueAxis()
        self.axis_y.setTitleText("价格 (¥)")
        self.axis_y.setLabelFormat("%.0f")
        self.chart.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)
        self.line_series.attachAxis(self.axis_y)
        self.scatter_series.attachAxis(self.axis_y)

        self.current_dates = []
        self.current_prices = []
        self.setEmptyState()

    def on_point_hovered(self, point, state):
        if state:
            try:
                ts = point.x()
                best_idx = -1
                best_diff = float("inf")
                for i, (d, p) in enumerate(zip(self.current_dates, self.current_prices)):
                    dt = QDateTime.fromString(d, "yyyy-MM-dd")
                    diff = abs(dt.toMSecsSinceEpoch() - ts)
                    if diff < best_diff:
                        best_diff = diff
                        best_idx = i
                if best_idx >= 0:
                    price = self.current_prices[best_idx]
                    date = self.current_dates[best_idx]
                    from PyQt6.QtGui import QCursor
                    QToolTip.showText(QCursor.pos(), f"📅 {date}\n💰 ¥{price}", self)
            except Exception:
                pass
        else:
            QToolTip.hideText()

    def leaveEvent(self, event):
        QToolTip.hideText()
        super().leaveEvent(event)

    def setEmptyState(self, message: str = "暂无数据，请选择竞品"):
        self.line_series.clear()
        self.scatter_series.clear()
        self.current_dates = []
        self.current_prices = []
        self.chart.setTitle(message)
        self.axis_x.setRange(QDateTime(QDate(2020, 1, 1), QTime(0, 0)),
                            QDateTime(QDate(2020, 1, 2), QTime(0, 0)))
        self.axis_y.setRange(0, 100)

    def setData(self, dates: List[str], prices: List[float]):
        valid = []
        for d, p in zip(dates, prices):
            try:
                p = float(p)
                if p is not None and p > 0 and p != float("inf") and p != float("-inf"):
                    dt = QDateTime.fromString(d, "yyyy-MM-dd")
                    if dt.isValid():
                        valid.append((d, dt, p))
            except Exception:
                continue

        if not valid:
            self.setEmptyState("无有效价格数据")
            return

        self.current_dates = [v[0] for v in valid]
        self.current_prices = [v[2] for v in valid]
        self.line_series.clear()
        self.scatter_series.clear()

        if len(valid) == 1:
            self.chart.setTitle("价格趋势（仅1条记录）")
            d, dt, p = valid[0]
            ts = dt.toMSecsSinceEpoch()
            self.line_series.append(ts, p)
            self.scatter_series.append(ts, p)
            self.axis_x.setRange(dt.addDays(-1), dt.addDays(1))
            self.axis_y.setRange(max(0, p * 0.5), p * 1.5)
            self.axis_x.setTickCount(3)
            return

        self.chart.setTitle("价格趋势")
        min_price = min(self.current_prices)
        max_price = max(self.current_prices)
        price_range = max_price - min_price
        padding = max(price_range * 0.15, 5) if price_range > 0 else max(min_price * 0.15, 5)

        for d, dt, p in valid:
            ts = dt.toMSecsSinceEpoch()
            self.line_series.append(ts, p)
            self.scatter_series.append(ts, p)

        first_dt = valid[0][1]
        last_dt = valid[-1][1]
        self.axis_x.setRange(first_dt.addDays(-1), last_dt.addDays(1))
        day_span = first_dt.daysTo(last_dt) + 3
        self.axis_x.setTickCount(min(day_span, 15))
        self.axis_y.setRange(max(0, min_price - padding), max_price + padding)
        self.axis_y.setTickCount(5)


class CompetitorDialog(QDialog):

    def __init__(self, store_name: str, product_wb: str, parent=None):
        super().__init__(parent)
        self.store_name = store_name
        self.product_wb = product_wb
        self.manager = CompetitorManager(store_name, product_wb)
        self.current_wb = None
        self.current_days = 7
        self._sync_thread = None
        self._sync_cancelled = False
        self._sync_cancelled_ref = [False]
        self._list_item_widgets = {}

        self.setWindowTitle(f"同行链接 - {product_wb}")
        self.setModal(False)
        self.resize(900, 650)
        self.setup_ui()
        self.refresh_competitor_list()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        add_layout = QHBoxLayout()
        add_layout.addWidget(QLabel("添加竞品 WB编码:"))
        self.wb_input = QLineEdit()
        self.wb_input.setPlaceholderText("输入WB编码")
        self.wb_input.setMinimumWidth(150)
        self.wb_input.returnPressed.connect(self.add_competitor)
        add_layout.addWidget(self.wb_input)

        self.add_btn = QPushButton("➕ 添加")
        self.add_btn.clicked.connect(self.add_competitor)
        add_layout.addWidget(self.add_btn)

        self.sync_img_btn = QPushButton("🖼️ 同步图片")
        self.sync_img_btn.setToolTip("批量下载当前商品所有竞品的主图")
        self.sync_img_btn.clicked.connect(self.sync_images)
        add_layout.addWidget(self.sync_img_btn)

        self.open_mine_btn = QPushButton("🏠 我的链接")
        self.open_mine_btn.setToolTip("在浏览器中打开我的商品链接")
        self.open_mine_btn.clicked.connect(self.open_my_link)
        add_layout.addWidget(self.open_mine_btn)

        self.open_all_btn = QPushButton("🌐 打开全部")
        self.open_all_btn.setToolTip("在浏览器中打开所有竞品链接")
        self.open_all_btn.clicked.connect(self.open_all_links)
        add_layout.addWidget(self.open_all_btn)

        add_layout.addStretch()
        main_layout.addLayout(add_layout)

        self.progress_widget = QWidget()
        self.progress_widget.setVisible(False)
        progress_layout = QHBoxLayout(self.progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        progress_layout.addWidget(self.progress_bar, 1)
        self.progress_label = QLabel("")
        progress_layout.addWidget(self.progress_label)
        self.cancel_sync_btn = QPushButton("取消")
        self.cancel_sync_btn.clicked.connect(self.cancel_sync)
        progress_layout.addWidget(self.cancel_sync_btn)
        main_layout.addWidget(self.progress_widget)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("📋 竞品列表"))

        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(240)
        self.list_widget.setSpacing(2)
        self.list_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background: white;
                outline: none;
            }
            QListWidget::item { padding: 2px 4px; border-radius: 4px; }
            QListWidget::item:selected { background: #e8f0fe; }
            QListWidget::item:hover { background: #f5f8fa; }
        """)
        self.list_widget.model().rowsMoved.connect(self.on_list_reordered)

        left_layout.addWidget(self.list_widget)
        splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        info_frame = QFrame()
        info_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        info_layout = QHBoxLayout(info_frame)

        self.img_label = QLabel("暂无图片")
        self.img_label.setFixedSize(150, 150)
        self.img_label.setStyleSheet("""
            QLabel {
                border: 1px solid #ddd;
                background: #f8f8f8;
                font-size: 14px;
                color: #999;
                border-radius: 4px;
            }
        """)
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self.img_label)

        text_layout = QVBoxLayout()

        self.wb_label = QLabel("WB编码: 未选中")
        self.wb_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.wb_label.linkActivated.connect(self.open_browser)
        self.wb_label.setStyleSheet("font-size: 13px;")
        text_layout.addWidget(self.wb_label)

        self.price_label = QLabel("当前价格: 无")
        self.price_label.setStyleSheet("font-size: 13px; color: #333;")
        text_layout.addWidget(self.price_label)

        store_type_layout = QHBoxLayout()
        store_type_layout.addWidget(QLabel("店铺类型:"))

        self.store_type_radio_btn1 = QRadioButton("本土店")
        self.store_type_radio_btn1.setStyleSheet("""
            QRadioButton {
                font-size: 13px;
                spacing: 5px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
        """)
        self.store_type_radio_btn1.toggled.connect(self.on_store_type_changed)
        store_type_layout.addWidget(self.store_type_radio_btn1)

        self.store_type_radio_btn2 = QRadioButton("跨境店")
        self.store_type_radio_btn2.setStyleSheet("""
            QRadioButton {
                font-size: 13px;
                spacing: 5px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
        """)
        self.store_type_radio_btn2.toggled.connect(self.on_store_type_changed)
        store_type_layout.addWidget(self.store_type_radio_btn2)

        self.store_type_radio_btn1.setChecked(True)

        store_type_layout.addStretch()
        text_layout.addLayout(store_type_layout)

        price_edit_layout = QHBoxLayout()
        price_edit_layout.addWidget(QLabel("修改价格:"))
        self.price_input = QLineEdit()
        self.price_input.setPlaceholderText("输入新价格")
        self.price_input.setFixedWidth(120)
        self.price_input.returnPressed.connect(self.update_price)
        price_edit_layout.addWidget(self.price_input)

        self.update_price_btn = QPushButton("更新")
        self.update_price_btn.clicked.connect(self.update_price)
        price_edit_layout.addWidget(self.update_price_btn)
        price_edit_layout.addStretch()
        text_layout.addLayout(price_edit_layout)

        img_btn_layout = QHBoxLayout()
        self.update_img_btn = QPushButton("🖼️ 修改图片")
        self.update_img_btn.clicked.connect(self.update_image)
        img_btn_layout.addWidget(self.update_img_btn)

        self.paste_img_btn2 = QPushButton("📋 从剪贴板粘贴")
        self.paste_img_btn2.clicked.connect(self.paste_image_for_current)
        img_btn_layout.addWidget(self.paste_img_btn2)
        img_btn_layout.addStretch()
        text_layout.addLayout(img_btn_layout)

        info_layout.addLayout(text_layout)
        info_layout.addStretch()
        right_layout.addWidget(info_frame)

        note_layout = QHBoxLayout()
        note_layout.addWidget(QLabel("备注:"))
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("添加备注...")
        self.note_input.returnPressed.connect(self.save_note)
        note_layout.addWidget(self.note_input)

        self.save_note_btn = QPushButton("保存备注")
        self.save_note_btn.clicked.connect(self.save_note)
        note_layout.addWidget(self.save_note_btn)
        right_layout.addLayout(note_layout)

        chart_frame = QFrame()
        chart_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        chart_frame.setMinimumHeight(220)
        chart_layout = QVBoxLayout(chart_frame)

        chart_title_layout = QHBoxLayout()
        chart_title_layout.addWidget(QLabel("📈 价格趋势"))
        chart_title_layout.addStretch()

        self.chart_7d_btn = QPushButton("7天")
        self.chart_7d_btn.setCheckable(True)
        self.chart_7d_btn.clicked.connect(lambda: self.show_price_chart(7))
        chart_title_layout.addWidget(self.chart_7d_btn)

        self.chart_30d_btn = QPushButton("30天")
        self.chart_30d_btn.setCheckable(True)
        self.chart_30d_btn.clicked.connect(lambda: self.show_price_chart(30))
        chart_title_layout.addWidget(self.chart_30d_btn)

        chart_layout.addLayout(chart_title_layout)

        self.chart_view = PriceChartView()
        chart_layout.addWidget(self.chart_view)

        right_layout.addWidget(chart_frame)

        splitter.addWidget(right_widget)
        splitter.setSizes([280, 620])
        main_layout.addWidget(splitter)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.close_btn)
        main_layout.addLayout(btn_layout)

    def on_store_type_changed(self):
        if not self.current_wb:
            return

        if self.store_type_radio_btn1.isChecked():
            store_type = "本土店"
        else:
            store_type = "跨境店"

        self.manager.update_store_type(self.current_wb, store_type)

        if self.current_wb in self._list_item_widgets:
            widget = self._list_item_widgets[self.current_wb]
            widget.update_store_type(store_type)

    def on_list_reordered(self):
        ordered_wb_codes = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            wb_code = item.data(Qt.ItemDataRole.UserRole)
            if wb_code:
                ordered_wb_codes.append(wb_code)

        if ordered_wb_codes:
            self.manager.reorder_competitors(ordered_wb_codes)

    def sync_images(self):
        """同步当前商品所有竞品的主图（去掉确认弹窗，直接下载）。"""
        data = self.manager.get_all_competitors()
        if not data:
            QMessageBox.information(self, "提示", "暂无竞品数据")
            return

        print(f"📊 当前商品 {self.product_wb} 共有 {len(data)} 个竞品")

        # ✅ 过滤：只下载没有图片的竞品
        wb_codes = []
        for wb_code in data.keys():
            img_path = self.manager.get_image_path(wb_code)
            if img_path and os.path.exists(img_path):
                print(f"   ⏭️ 跳过已有图片: {wb_code}")
                continue
            else:
                print(f"   📥 需要下载: {wb_code}")
                wb_codes.append(wb_code)

        if not wb_codes:
            QMessageBox.information(self, "提示", "所有竞品已有图片，无需同步")
            return

        total = len(wb_codes)
        print(f"📋 最终需要下载的任务数: {total}")

        self._sync_cancelled = False
        self.progress_widget.setVisible(True)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"0/{total}")
        self.sync_img_btn.setEnabled(False)
        self.cancel_sync_btn.setEnabled(True)

        self._sync_cancelled_ref = [False]
        tasks = [(self.manager, wb_code) for wb_code in wb_codes]
        self._sync_thread = ImageSyncThread(tasks, self._sync_cancelled_ref)
        self._sync_thread.progress.connect(self._on_sync_progress)
        self._sync_thread.finished.connect(self._on_sync_finished)
        self._sync_thread.start()

    def _on_sync_progress(self, cur, status):
        self.progress_bar.setValue(cur)
        self.progress_label.setText(f"{cur}/{self.progress_bar.maximum()}")

    def _on_sync_finished(self, success, fail):
        self.progress_widget.setVisible(False)
        self.sync_img_btn.setEnabled(True)
        self.cancel_sync_btn.setEnabled(False)
        self.refresh_competitor_list()
        QMessageBox.information(self, "完成", f"✅ 成功: {success}\n❌ 失败: {fail}")

    def cancel_sync(self):
        self._sync_cancelled_ref[0] = True
        self.cancel_sync_btn.setEnabled(False)
        self.progress_label.setText("正在取消...")

    def open_my_link(self):
        link = f"https://www.wildberries.ru/catalog/{self.product_wb}/detail.aspx?targetUrl=GP"
        webbrowser.open(link)

    def open_all_links(self):
        data = self.manager.get_all_competitors()
        if not data:
            QMessageBox.information(self, "提示", "暂无竞品数据")
            return
        for wb_code in data.keys():
            link = f"https://www.wildberries.ru/catalog/{wb_code}/detail.aspx?targetUrl=GP"
            webbrowser.open(link)

    def add_competitor(self):
        """添加竞品 - 支持输入 WB 编号或完整链接"""
        raw = self.wb_input.text().strip()
        if not raw:
            return

        wb_code = self._extract_wb_code(raw)
        if not wb_code:
            QMessageBox.warning(self, "错误", f"无法从输入中提取 WB 编号：\n{raw}")
            return

        if self.manager.add_competitor(wb_code):
            self.wb_input.clear()
            self.refresh_competitor_list()
            # 选中新添加的竞品
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == wb_code:
                    self.list_widget.setCurrentItem(item)
                    self.on_item_clicked(item)
                    break
            self.list_widget.setFocus()
        else:
            QMessageBox.warning(self, "错误", f"竞品 {wb_code} 已存在或无效")

    def _extract_wb_code(self, text: str) -> str:
        """从用户输入中提取 WB 编号（支持纯数字和链接）"""
        import re

        text = text.strip()

        if text.isdigit():
            return text

        patterns = [
            r"/catalog/(\d+)/",  # /catalog/123456/
            r"/catalog/(\d+)\?",  # /catalog/123456?
            r"catalog/(\d+)",  # catalog/123456
            r"nm=(\d+)",  # nm=123456（部分链接参数）
            r"/(\d{6,12})/",  # 直接匹配6-12位数字（兜底）
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        digit_match = re.search(r"\b(\d{6,12})\b", text)
        if digit_match:
            return digit_match.group(1)

        return None

    def delete_competitor_by_wb(self, wb_code: str):
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除竞品 {wb_code} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.manager.delete_competitor(wb_code)
            if self.current_wb == wb_code:
                self.current_wb = None
                self.clear_detail()
            self.refresh_competitor_list()

    def refresh_competitor_list(self):
        self.list_widget.clear()
        self._list_item_widgets = {}
        data = self.manager.get_all_competitors()
        for wb_code, info in data.items():
            history = info.get("price_history", [])
            price_str = str(history[-1]["price"]) if history else ""
            img_path = self.manager.get_image_path(wb_code)
            store_type = info.get("store_type", "本土店")
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, wb_code)
            widget = CompetitorListItem(wb_code, price_str, img_path, store_type)
            widget.delete_clicked.connect(self.delete_competitor_by_wb)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)
            self._list_item_widgets[wb_code] = widget

    def on_item_clicked(self, item):
        wb_code = item.data(Qt.ItemDataRole.UserRole)
        self.current_wb = wb_code
        competitor = self.manager.get_competitor(wb_code)
        if not competitor:
            return

        link_url = f"https://www.wildberries.ru/catalog/{wb_code}/detail.aspx?targetUrl=GP"
        self.wb_label.setText(f'<a href="{link_url}" style="color:#1a73e8;text-decoration:none;">🔗 WB编码: {wb_code}</a>')

        history = competitor.get("price_history", [])
        if history:
            last_price = history[-1]["price"]
            self.price_label.setText(f"💰 当前价格: ¥{last_price}  (共{len(history)}条记录)")
        else:
            self.price_label.setText("💰 当前价格: 无")

        store_type = competitor.get("store_type", "本土店")
        if store_type == "本土店":
            self.store_type_radio_btn1.setChecked(True)
        else:
            self.store_type_radio_btn2.setChecked(True)

        img_path = self.manager.get_image_path(wb_code)
        if img_path and os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(148, 148, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
                self.img_label.setPixmap(scaled)
                self.img_label.setText("")
            else:
                self.img_label.setText("图片加载失败")
        else:
            self.img_label.setText("暂无图片")

        note = competitor.get("note", "")
        self.note_input.setText(note)
        self.show_price_chart(self.current_days)

    def clear_detail(self):
        self.wb_label.setText("WB编码: 未选中")
        self.price_label.setText("当前价格: 无")
        self.img_label.setText("暂无图片")
        self.note_input.clear()
        self.store_type_radio_btn1.setChecked(True)
        self.store_type_radio_btn2.setChecked(False)
        self.chart_view.setEmptyState()

    def update_price(self):
        if not self.current_wb:
            QMessageBox.warning(self, "提示", "请先选择一个竞品")
            return
        price_text = self.price_input.text().strip()
        if not price_text:
            QMessageBox.warning(self, "错误", "请输入价格")
            return
        try:
            price = float(price_text)
            if price <= 0:
                QMessageBox.warning(self, "错误", "价格必须大于0")
                return
        except ValueError:
            QMessageBox.warning(self, "错误", "请输入有效数字")
            return
        self.manager.update_price(self.current_wb, price)
        self.price_input.clear()
        self.refresh_competitor_list()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == self.current_wb:
                self.on_item_clicked(item)
                break
        self.list_widget.setFocus()
        QMessageBox.information(self, "成功", f"已更新价格: ¥{price}")

    def update_image(self):
        if not self.current_wb:
            QMessageBox.warning(self, "提示", "请先选择一个竞品")
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif)")
        if file_path:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                self.manager.update_image(self.current_wb, pixmap)
                self.refresh_competitor_list()
                for i in range(self.list_widget.count()):
                    item = self.list_widget.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) == self.current_wb:
                        self.on_item_clicked(item)
                        break
                QMessageBox.information(self, "成功", "图片已更新")
            else:
                QMessageBox.warning(self, "错误", "无法加载图片")

    def paste_image_for_current(self):
        if not self.current_wb:
            QMessageBox.warning(self, "提示", "请先选择一个竞品")
            return
        clipboard = QApplication.clipboard()
        if clipboard.mimeData().hasImage():
            pixmap = clipboard.pixmap()
            if not pixmap.isNull():
                self.manager.update_image(self.current_wb, pixmap)
                self.refresh_competitor_list()
                for i in range(self.list_widget.count()):
                    item = self.list_widget.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) == self.current_wb:
                        self.on_item_clicked(item)
                        break
            else:
                QMessageBox.warning(self, "错误", "剪贴板中没有有效图片")
        else:
            QMessageBox.warning(self, "错误", "剪贴板中没有图片")

    def save_note(self):
        if not self.current_wb:
            QMessageBox.warning(self, "提示", "请先选择一个竞品")
            return
        note = self.note_input.text().strip()
        self.manager.update_note(self.current_wb, note)
        QMessageBox.information(self, "成功", "备注已保存")

    def open_browser(self, link):
        webbrowser.open(link)

    def show_price_chart(self, days: int):
        self.current_days = days
        if not self.current_wb:
            self.chart_view.setEmptyState()
            return
        dates, prices = self.manager.get_price_history(self.current_wb, days)
        self.chart_7d_btn.setChecked(days == 7)
        self.chart_30d_btn.setChecked(days == 30)
        if len(dates) == 0:
            self.chart_view.setEmptyState("暂无价格数据")
            return
        self.chart_view.setData(dates, prices)

    def closeEvent(self, event):
        if self._sync_thread and self._sync_thread.isRunning():
            self._sync_cancelled_ref[0] = True
            self._sync_thread.wait(2000)
        super().closeEvent(event)
