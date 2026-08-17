from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMainWindow,
                             QPushButton, QTabWidget, QVBoxLayout, QWidget)

from app.core import paths
from app.core.exchange import ExchangeRateFetcher
from app.ui.store_tab import StoreTab


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("商品促销汇总系统")
        self.setMinimumSize(1200, 700)
        icon = paths.icon_path()
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        title_layout = QHBoxLayout()
        title_label = QLabel("🏷️ 商品促销汇总系统")
        title_label.setStyleSheet("font-size: 24px; font-weight: 600; color: #0a1e3c;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #dce4ec;
                border-radius: 8px;
                padding: 4px;
            }
            QTabBar::tab {
                padding: 10px 30px;
                font-size: 14px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: #1a4d8c;
                color: white;
                border-radius: 6px 6px 0 0;
            }
        """)

        from app.core.config import STORES
        from app.ui.package_calculator import PackageCalculator

        self.store_tabs = {}
        for store_name in STORES:
            tab = StoreTab(store_name)
            self.store_tabs[store_name] = tab
            self.tab_widget.addTab(tab, f"🏪 {store_name}")

        self.tab_package = PackageCalculator()
        self.tab_widget.addTab(self.tab_package, "📦 包装计算")

        layout.addWidget(self.tab_widget)

        footer_layout = QHBoxLayout()

        footer = QLabel("💡 提示：悬停促销列表头查看详情 · 售价≤促销价自动绿色高亮 · 右键促销列可删除")
        footer.setStyleSheet("color: #5a7a9a; font-size: 13px; padding: 8px 0;")
        footer_layout.addWidget(footer)

        footer_layout.addStretch()

        self.exchange_label = QLabel("获取汇率中...")
        self.exchange_label.setStyleSheet("""
            QLabel {
                color: #333;
                font-size: 14px;
                font-weight: bold;
                padding: 4px 8px;
                background: #f0f4f8;
                border-radius: 4px;
            }
        """)

        self.copy_rate_btn = QPushButton("📋")
        self.copy_rate_btn.setFixedSize(28, 28)
        self.copy_rate_btn.setToolTip("复制汇率+0.5")
        self.copy_rate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_rate_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 13px;
                padding: 0px;
            }
            QPushButton:hover {
                background: #e8f0fe;
                border-color: #1a73e8;
            }
        """)
        self.copy_rate_btn.clicked.connect(self.copy_exchange_rate)

        footer_layout.addWidget(self.exchange_label)
        footer_layout.addWidget(self.copy_rate_btn)

        layout.addLayout(footer_layout)

        self.fetch_exchange_rate()

    def fetch_exchange_rate(self):
        """通过 API 获取 1 RMB 兑换卢布的汇率"""
        self.rate_thread = ExchangeRateFetcher()
        self.rate_thread.result.connect(self.on_rate_received)
        self.rate_thread.start()

    def on_rate_received(self, rate: float):
        """收到汇率后更新显示"""
        self.current_rate = rate
        self.exchange_label.setText(f"₽ {rate}")
        self.exchange_label.setToolTip(f"1 RMB = {rate} 卢布\n点击复制按钮复制 {rate + 0.5}")

    def copy_exchange_rate(self):
        """复制当前汇率 + 0.5 到剪贴板"""
        if hasattr(self, "current_rate"):
            value = self.current_rate + 0.5
            QApplication.clipboard().setText(str(value))
            QTimer.singleShot(1500, lambda: self.exchange_label.setText(f"₽ {self.current_rate}"))
