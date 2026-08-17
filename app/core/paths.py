"""路径解析：统一处理源码运行与 PyInstaller exe 运行两种模式。"""
import os
import sys
from pathlib import Path

from . import config


def project_root() -> Path:
    """项目根目录：源码运行时为仓库根，exe 运行时为 exe 所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # app/core/paths.py -> parents[2] = 项目根
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return project_root() / "data"


def store_data_dir(store_name: str) -> Path:
    return data_dir() / store_name


def competitor_dir(store_name: str) -> Path:
    return store_data_dir(store_name) / config.COMPETITOR_DIR_NAME


def competitor_base_dir(store_name: str, product_wb: str) -> Path:
    return competitor_dir(store_name) / product_wb


def icon_path() -> Path:
    return project_root() / "icon.ico"


def desktop_dir() -> Path:
    """导出文件的默认桌面目录；桌面不存在时退回用户主目录。"""
    home = Path(os.path.expanduser("~"))
    desktop = home / "Desktop"
    return desktop if desktop.is_dir() else home
