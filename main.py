import ctypes
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from app.core import paths
from app.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle("Fusion")

    # 设置应用程序图标（任务栏显示）
    icon = paths.icon_path()
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    # 设置 Windows 任务栏图标
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "com.yourcompany.productpromotion"
        )
    except Exception:
        pass

    window = MainWindow()

    # ✅ 程序启动时窗口最大化
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
