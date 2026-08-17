import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from PyQt6.QtGui import QPixmap, QImage


class CompetitorManager:
    """竞品数据管理类"""

    def __init__(self, store_name: str, product_wb: str):
        self.store_name = store_name
        self.product_wb = product_wb
        self.base_path = f"data/{store_name}/competitor/{product_wb}"
        self.info_path = os.path.join(self.base_path, "info.json")
        self.img_path = os.path.join(self.base_path, "images")
        os.makedirs(self.img_path, exist_ok=True)
        self._data: Dict[str, dict] = self._load_data()

    def _load_data(self) -> Dict:
        if os.path.exists(self.info_path):
            try:
                with open(self.info_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_data(self):
        with open(self.info_path, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get_all_competitors(self) -> Dict[str, dict]:
        return self._data

    def add_competitor(self, wb_code: str, image_data=None) -> bool:
        if not wb_code or wb_code in self._data:
            return False
        self._data[wb_code] = {
            "wb_code": wb_code,
            "price_history": [],
            "image_path": None,
            "note": "",
            "store_type": "本土店"  # ✅ 默认本土店
        }
        if image_data:
            self._save_image(wb_code, image_data)
        self._save_data()
        return True

    def delete_competitor(self, wb_code: str) -> bool:
        if wb_code in self._data:
            del self._data[wb_code]
            self._save_data()
            return True
        return False

    def get_competitor(self, wb_code: str) -> Optional[dict]:
        return self._data.get(wb_code)

    def update_price(self, wb_code: str, new_price: float):
        if wb_code not in self._data:
            return

        today = datetime.now().strftime("%Y-%m-%d")
        history = self._data[wb_code].get("price_history", [])

        found = False
        for record in history:
            if record["date"] == today:
                record["price"] = new_price
                found = True
                break

        if not found:
            history.append({
                "date": today,
                "price": new_price
            })

        history.sort(key=lambda x: x["date"])
        self._data[wb_code]["price_history"] = history
        self._save_data()

    def update_image(self, wb_code: str, image_data):
        if wb_code in self._data:
            self._save_image(wb_code, image_data)
            self._data[wb_code]["image_path"] = f"images/{wb_code}.png"
            self._save_data()

    def _save_image(self, wb_code: str, image_data):
        file_path = os.path.join(self.img_path, f"{wb_code}.png")
        if isinstance(image_data, QPixmap):
            image_data.save(file_path)
        elif isinstance(image_data, QImage):
            image_data.save(file_path)
        elif isinstance(image_data, bytes):
            try:
                with open(file_path, 'wb') as f:
                    f.write(image_data)
            except:
                pass

    def update_note(self, wb_code: str, note: str):
        if wb_code in self._data:
            self._data[wb_code]["note"] = note
            self._save_data()

    # 更新店铺类型
    def update_store_type(self, wb_code: str, store_type: str):
        if wb_code in self._data:
            self._data[wb_code]["store_type"] = store_type
            self._save_data()

    def get_price_history(self, wb_code: str, days: int = 30):
        if wb_code not in self._data:
            return [], []
        history = self._data[wb_code].get("price_history", [])
        if not history:
            return [], []

        if days > 0:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            recent = [h for h in history if h["date"] >= cutoff]
        else:
            recent = history

        dates = [h["date"] for h in recent]
        prices = [h["price"] for h in recent]
        return dates, prices

    def get_image_path(self, wb_code: str) -> Optional[str]:
        if wb_code not in self._data:
            return None
        rel_path = self._data[wb_code].get("image_path")
        if rel_path:
            full_path = os.path.join(self.base_path, rel_path)
            if os.path.exists(full_path):
                return full_path
        return None

    # 重新排序竞品
    def reorder_competitors(self, ordered_wb_codes: List[str]):
        """按指定顺序重新排列竞品"""
        if not ordered_wb_codes:
            return

        # 创建新的有序字典
        new_data = {}
        for wb_code in ordered_wb_codes:
            if wb_code in self._data:
                new_data[wb_code] = self._data[wb_code]

        # 如果有遗漏的（理论上不会），追加到末尾
        for wb_code, data in self._data.items():
            if wb_code not in new_data:
                new_data[wb_code] = data

        self._data = new_data
        self._save_data()