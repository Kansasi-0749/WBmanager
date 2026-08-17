"""人民币→卢布汇率抓取：后台线程 + 双 API 兜底。"""
import json
import logging
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

_APIS = [
    "https://api.exchangerate-api.com/v4/latest/CNY",
    "https://open.er-api.com/v6/latest/CNY",
]


class ExchangeRateFetcher(QThread):
    """获取 1 RMB 兑换卢布的汇率，成功时发射 result(float)。"""

    result = pyqtSignal(float)

    def run(self):
        for url in _APIS:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                rub = data.get("rates", {}).get("RUB", 0)
                if rub > 0:
                    self.result.emit(round(rub, 1))
                    return
            except Exception as e:
                logger.warning("汇率接口失败 %s: %s", url, e)
