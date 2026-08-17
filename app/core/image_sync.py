"""竞品主图下载：URL 生成与后台线程的单一实现。"""
import logging
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

# 与原实现一致：两个域名各 60 个 basket 编号
_BASKET_DOMAINS = ["wildberries.ru", "wbbasket.ru"]
BASKET_COUNT = 60


def build_image_urls(wb_code: str):
    """按 Wildberries 规则生成候选主图 URL 列表。"""
    vol = wb_code[:4]
    part = wb_code[:6]
    urls = []
    for domain in _BASKET_DOMAINS:
        for b in range(1, BASKET_COUNT + 1):
            urls.append(
                f"https://basket-{b:02d}.{domain}/vol{vol}/part{part}/{wb_code}/images/big/1.webp"
            )
    return urls


def download_image(url: str, timeout: float = 5.0):
    """下载图片，失败返回 None。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            img_data = resp.read()
        if img_data and len(img_data) > 1000:
            return img_data
    except Exception:
        return None
    return None


class ImageSyncThread(QThread):
    """后台下载线程。

    tasks 为 [(CompetitorManager, wb_code), ...]；progress 发射 (序号, 状态文本)，
    finished 发射 (成功数, 失败数)。支持通过 cancelled_ref[0] 取消。
    """

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(int, int)

    def __init__(self, tasks, cancelled_ref, parent=None):
        super().__init__(parent)
        self.tasks = tasks
        self.cancelled_ref = cancelled_ref

    def run(self):
        success = 0
        fail = 0
        for i, (manager, wb_code) in enumerate(self.tasks):
            if self.cancelled_ref[0]:
                self.progress.emit(i + 1, "已取消")
                break

            downloaded = False
            for url in build_image_urls(wb_code):
                if self.cancelled_ref[0]:
                    break
                img_data = download_image(url)
                if img_data is not None:
                    manager.update_image(wb_code, img_data)
                    success += 1
                    downloaded = True
                    break

            if not downloaded:
                fail += 1

            self.progress.emit(i + 1, f"{'✅' if downloaded else '❌'} {wb_code}")

        self.finished.emit(success, fail)
