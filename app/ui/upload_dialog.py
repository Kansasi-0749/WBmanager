from PyQt6.QtWidgets import (QDateEdit, QDialog, QFileDialog, QGroupBox, QHBoxLayout,
                             QLabel, QMessageBox, QProgressBar, QPushButton,
                             QVBoxLayout)
from PyQt6.QtCore import QDate, Qt, pyqtSignal
import os


class UploadDialog(QDialog):
    """通用上传对话框"""

    file_selected = pyqtSignal(str)

    def __init__(self, title: str, show_date: bool = True, default_dir: str = None, parent=None):
        super().__init__(parent)
        self.title = title
        self.show_date = show_date
        self.default_dir = default_dir or os.path.expanduser("~")
        self.file_path = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle(self.title)
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout()

        # 日期选择
        if self.show_date:
            date_group = QGroupBox("促销日期")
            date_layout = QHBoxLayout()

            date_layout.addWidget(QLabel("开始日期:"))
            self.start_date = QDateEdit()
            self.start_date.setDate(QDate.currentDate())
            self.start_date.setCalendarPopup(True)
            date_layout.addWidget(self.start_date)

            date_layout.addWidget(QLabel("结束日期:"))
            self.end_date = QDateEdit()
            self.end_date.setDate(QDate.currentDate().addDays(14))
            self.end_date.setCalendarPopup(True)
            date_layout.addWidget(self.end_date)

            date_group.setLayout(date_layout)
            layout.addWidget(date_group)

        # 文件选择
        file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout()

        self.drop_label = QLabel("📁 拖拽文件到此处，或点击下方按钮选择")
        self.drop_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #c8d6e8;
                border-radius: 10px;
                padding: 30px;
                background-color: #f8faff;
                font-size: 14px;
                color: #5a7a9a;
            }
        """)
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setAcceptDrops(True)
        file_layout.addWidget(self.drop_label)

        btn_layout = QHBoxLayout()
        self.select_btn = QPushButton("选择文件")
        self.select_btn.clicked.connect(self.select_file)
        btn_layout.addWidget(self.select_btn)

        self.clear_btn = QPushButton("清除")
        self.clear_btn.clicked.connect(self.clear_file)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()

        file_layout.addLayout(btn_layout)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # 按钮
        btn_layout2 = QHBoxLayout()
        self.ok_btn = QPushButton("确认上传")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setEnabled(False)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout2.addStretch()
        btn_layout2.addWidget(self.ok_btn)
        btn_layout2.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout2)

        self.setLayout(layout)

    def select_file(self):
        """选择文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", self.default_dir,
            "Excel/CSV文件 (*.xlsx *.xls *.csv)"
        )
        if file_path:
            self.set_file(file_path)

    def set_file(self, file_path: str):
        """设置文件路径"""
        self.file_path = file_path
        self.drop_label.setText(f"📄 {os.path.basename(file_path)}")
        self.drop_label.setStyleSheet("""
            QLabel {
                border: 2px solid #4a8c3f;
                border-radius: 10px;
                padding: 30px;
                background-color: #f0f8ee;
                font-size: 14px;
                color: #2a6a2a;
            }
        """)
        self.ok_btn.setEnabled(True)
        self.file_selected.emit(file_path)

    def clear_file(self):
        """清除文件"""
        self.file_path = None
        self.drop_label.setText("📁 拖拽文件到此处，或点击下方按钮选择")
        self.drop_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #c8d6e8;
                border-radius: 10px;
                padding: 30px;
                background-color: #f8faff;
                font-size: 14px;
                color: #5a7a9a;
            }
        """)
        self.ok_btn.setEnabled(False)

    def get_dates(self):
        """获取日期"""
        if self.show_date:
            return (self.start_date.date().toString("yyyy-MM-dd"),
                    self.end_date.date().toString("yyyy-MM-dd"))
        return (None, None)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            file_path = files[0]
            ext = os.path.splitext(file_path)[1].lower()
            if ext in [".xlsx", ".xls", ".csv"]:
                self.set_file(file_path)
            else:
                QMessageBox.warning(self, "不支持", "请上传Excel或CSV文件")
