import json
import logging
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from . import config, paths
from .excel_io import read_excel_or_csv

logger = logging.getLogger(__name__)


class PromotionManager:
    """促销管理类。"""

    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.promotions: List[Dict] = []
        self.promo_columns: List[str] = []
        self.store_name = data_manager.store_name
        self.promo_data_path = paths.store_data_dir(self.store_name) / config.PROMO_DATA_CACHE_JSON_NAME
        self.promo_data_cache: Dict[str, Dict[str, float]] = {}
        self._load_promotions()
        self._load_promo_data_cache()

    def _load_promotions(self):
        self.promotions = self.data_manager.load_promotions()
        self.promotions.sort(key=lambda x: x.get("start_date", ""))
        self._update_promo_columns()

    def _update_promo_columns(self):
        self.promo_columns = [p["column_name"] for p in self.promotions]

    def _save(self):
        self.data_manager.save_promotions(self.promotions)
        self._update_promo_columns()

    # ===== 促销数据缓存 =====
    def _load_promo_data_cache(self):
        if self.promo_data_path.exists():
            try:
                with open(self.promo_data_path, "r", encoding="utf-8") as f:
                    self.promo_data_cache = json.load(f)
            except Exception:
                logger.exception("加载促销数据缓存失败: %s", self.promo_data_path)
                self.promo_data_cache = {}
        else:
            self.promo_data_cache = {}

    def _save_promo_data_cache(self):
        self.promo_data_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.promo_data_path, "w", encoding="utf-8") as f:
            json.dump(self.promo_data_cache, f, ensure_ascii=False, indent=2)

    def cache_promo_price(self, wb_code: str, promo_name: str, price: float):
        if wb_code not in self.promo_data_cache:
            self.promo_data_cache[wb_code] = {}
        self.promo_data_cache[wb_code][promo_name] = price
        self._save_promo_data_cache()

    def get_cached_promo(self, wb_code: str) -> Dict[str, float]:
        return self.promo_data_cache.get(wb_code, {})

    # ===== 应用到表格 =====
    def apply_promo_to_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """根据缓存数据给 DataFrame 填充促销列（只覆盖缓存命中的行）。"""
        if not self.promo_data_cache:
            return df

        for col in self.promo_columns:
            if col not in df.columns:
                df[col] = ""

        if "WB编号" not in df.columns:
            return df

        wb_series = df["WB编号"].fillna("").astype(str).str.strip()

        for p in self.promotions:
            col = p.get("column_name")
            promo_name = p.get("promotion_name", "")
            if not col or col not in df.columns or not promo_name:
                continue
            values = {}
            for wb, promo_map in self.promo_data_cache.items():
                if promo_name in promo_map:
                    values[wb] = str(promo_map[promo_name])
            if not values:
                continue
            matched = wb_series.isin(values)
            df.loc[matched, col] = wb_series[matched].map(values)

        return df

    def _reorder_and_rename(self, df_current):
        """按开始时间+上传时间排序，重命名促销列为 1促/2促/...。

        旧列数据按促销身份（promotion_name, start_date, upload_time）保留，
        避免按排序位置映射导致数据错配。
        """
        if not self.promotions:
            return df_current

        self.promotions.sort(key=lambda x: (x.get("start_date", ""), x.get("upload_time", "")))

        promo_data = {}
        for p in self.promotions:
            old_name = p.get("column_name")
            if old_name and old_name in df_current.columns:
                key = (p.get("promotion_name", ""), p.get("start_date", ""), p.get("upload_time", ""))
                promo_data[key] = df_current[old_name].copy()

        for p in self.promotions:
            old_name = p.get("column_name")
            if old_name and old_name in df_current.columns:
                df_current = df_current.drop(columns=[old_name])

        for idx, p in enumerate(self.promotions, 1):
            p["column_name"] = config.PROMO_COLUMN_TEMPLATE.format(n=idx)
            df_current[p["column_name"]] = ""

        for p in self.promotions:
            key = (p.get("promotion_name", ""), p.get("start_date", ""), p.get("upload_time", ""))
            if key in promo_data:
                df_current[p["column_name"]] = promo_data[key]

        return df_current

    # ===== 重新排序促销 =====
    def reorder_promotions(self):
        """按开始时间 + 上传时间重新排序促销（清空促销列，数据由缓存重新填充）。"""
        if not self.promotions:
            return

        self.promotions.sort(key=lambda x: (x.get("start_date", ""), x.get("upload_time", "")))

        df = self.data_manager.load_products()
        old_names = [p["column_name"] for p in self.promotions]

        for col in old_names:
            if col in df.columns:
                df = df.drop(columns=[col])

        for idx, p in enumerate(self.promotions, 1):
            p["column_name"] = config.PROMO_COLUMN_TEMPLATE.format(n=idx)
            df[p["column_name"]] = ""

        self.data_manager.save_products(df)
        self._save()
        self._update_promo_columns()

    # ===== 导入促销（名称解析） =====
    def import_promotion(self, file_path: str, start_date: str, end_date: str) -> Tuple[int, List[str]]:
        errors: List[str] = []
        update_count = 0

        try:
            df_promo = read_excel_or_csv(file_path, sheet_name=0)
            df_promo = df_promo.fillna("")

            file_basename = os.path.basename(file_path)
            file_name_without_ext = os.path.splitext(file_basename)[0]

            file_name_without_ext = re.sub(r"\s*\([^)]*\)", "", file_name_without_ext)
            file_name_without_ext = re.sub(r"\s*（[^）]*）", "", file_name_without_ext)
            file_name_without_ext = re.sub(r"\s*\[[^\]]*\]", "", file_name_without_ext)

            file_name_without_ext = re.sub(
                r"\s*\d{2}\.\d{2}\.\d{4}\s+\d{2}\.\d{2}\.\d{2}", "", file_name_without_ext
            )
            file_name_without_ext = re.sub(
                r"\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}", "", file_name_without_ext
            )
            file_name_without_ext = re.sub(r"\s*\d{2}\.\d{2}\.\d{4}", "", file_name_without_ext)

            file_name_without_ext = file_name_without_ext.strip(" _-")

            promo_name = file_name_without_ext
            if "_" in file_name_without_ext:
                parts = file_name_without_ext.split("_")
                if len(parts) >= 2:
                    promo_name = "_".join(parts[1:])

            if not promo_name.strip():
                promo_name = file_name_without_ext

            print(f"📋 促销名称: {promo_name}")

            wb_col = None
            price_col = None

            for col in df_promo.columns:
                col_clean = str(col).strip()
                if col_clean in ["WB商品编号", "WB货号"]:
                    wb_col = col
                elif col_clean in ["活动计划价格", "活动计划价"]:
                    price_col = col

            if not wb_col:
                errors.append("未找到WB编号列")
                return 0, errors

            if not price_col:
                errors.append("未找到活动计划价格列")
                return 0, errors

            df_current = self.data_manager.load_products()

            promo_meta = {
                "column_name": "",
                "promotion_name": promo_name,
                "start_date": start_date,
                "end_date": end_date,
                "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            self.promotions.append(promo_meta)
            df_current = self._reorder_and_rename(df_current)
            # 直接使用本次促销的列名，避免排序后取错列
            latest_promo = promo_meta["column_name"]
            fill_count = 0

            for idx, row in df_promo.iterrows():
                wb = str(row[wb_col]).strip()
                if wb in ("", "nan"):
                    continue

                price_str = str(row[price_col]).strip()
                if price_str in ("", "nan"):
                    continue

                try:
                    price = float(price_str)
                except ValueError:
                    errors.append(f"价格格式错误: {price_str}")
                    continue

                self.cache_promo_price(wb, promo_name, price)

                mask = df_current["WB编号"].astype(str).str.strip() == wb
                if mask.any():
                    df_current.loc[mask, latest_promo] = str(price)
                    fill_count += 1

            update_count = fill_count

            self.data_manager.save_products(df_current)
            self._save()
            self._update_promo_columns()

            print(f"✅ 填充 {fill_count} 个商品, 缓存 {len(self.promo_data_cache)} 个WB的促销数据")

        except Exception as e:
            errors.append(f"导入失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return 0, errors

        return update_count, errors

    def delete_all_promotions(self) -> int:
        if not self.promotions:
            return 0

        df_current = self.data_manager.load_products()
        deleted_count = 0

        for p in self.promotions:
            col_name = p["column_name"]
            if col_name in df_current.columns:
                df_current = df_current.drop(columns=[col_name])
                deleted_count += 1

        self.data_manager.save_products(df_current)
        self.promotions = []
        self.promo_data_cache = {}
        self._save_promo_data_cache()
        self._save()
        self._update_promo_columns()
        return deleted_count

    def clean_expired(self):
        """清理过期促销。"""
        today = datetime.now().strftime("%Y-%m-%d")
        if not self.promotions:
            return

        valid_promotions = []
        removed_promotions = []

        for p in self.promotions:
            end_date = p.get("end_date", "")
            if end_date == "" or end_date >= today:
                valid_promotions.append(p)
            else:
                removed_promotions.append(p)

        if len(valid_promotions) == len(self.promotions):
            return

        df_current = self.data_manager.load_products()

        for p in removed_promotions:
            col_name = p["column_name"]
            promo_name = p.get("promotion_name", "")
            if col_name in df_current.columns:
                df_current = df_current.drop(columns=[col_name])
            for wb in list(self.promo_data_cache.keys()):
                if promo_name in self.promo_data_cache[wb]:
                    del self.promo_data_cache[wb][promo_name]
            self.promo_data_cache = {k: v for k, v in self.promo_data_cache.items() if v}
        self._save_promo_data_cache()

        self.promotions = valid_promotions
        self.reorder_promotions()

        self._save()
        self._update_promo_columns()

    def delete_promotion(self, column_name: str) -> bool:
        if column_name == "__ALL__":
            self.delete_all_promotions()
            return True

        for p in self.promotions:
            if p["column_name"] == column_name:
                promo_name = p.get("promotion_name", "")
                self.promotions.remove(p)
                df_current = self.data_manager.load_products()
                if column_name in df_current.columns:
                    df_current = df_current.drop(columns=[column_name])
                    df_current = self._reorder_and_rename(df_current)
                    self.data_manager.save_products(df_current)
                for wb in list(self.promo_data_cache.keys()):
                    if promo_name in self.promo_data_cache[wb]:
                        del self.promo_data_cache[wb][promo_name]
                self.promo_data_cache = {k: v for k, v in self.promo_data_cache.items() if v}
                self._save_promo_data_cache()
                self._save()
                self._update_promo_columns()
                return True
        return False

    def get_promo_columns(self) -> List[str]:
        return self.promo_columns

    def get_promo_meta(self, column_name: str) -> Optional[Dict]:
        for p in self.promotions:
            if p["column_name"] == column_name:
                return p
        return None

    def get_all_meta(self) -> List[Dict]:
        return self.promotions
