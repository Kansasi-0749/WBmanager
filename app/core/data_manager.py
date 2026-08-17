import json
import logging
from typing import Dict, List, Tuple

import pandas as pd

from . import config, paths
from .excel_io import read_excel_with_openpyxl

logger = logging.getLogger(__name__)


class DataManager:
    """数据管理类 - 负责 CSV 和 JSON 的读写。"""

    def __init__(self, store_name: str):
        self.store_name = store_name
        self.data_dir = paths.store_data_dir(store_name)
        self.csv_path = self.data_dir / config.PRODUCT_CSV_NAME
        self.json_path = self.data_dir / config.PROMO_META_JSON_NAME
        self._ensure_dir()

    def _ensure_dir(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_products(self) -> pd.DataFrame:
        if self.csv_path.exists():
            try:
                df = pd.read_csv(self.csv_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
                df = df.replace("", pd.NA)
                for col in config.BASE_COLUMNS:
                    if col not in df.columns:
                        df[col] = ""
                return df
            except Exception as e:
                logger.exception("加载CSV失败: %s", e)
                return self._create_empty_df()
        return self._create_empty_df()

    def _create_empty_df(self) -> pd.DataFrame:
        return pd.DataFrame(columns=config.BASE_COLUMNS)

    def save_products(self, df: pd.DataFrame):
        df_copy = df.copy()
        for col in df_copy.columns:
            df_copy[col] = df_copy[col].apply(
                lambda x: "" if pd.isna(x) or x is None else str(x)
            )
        df_copy.to_csv(self.csv_path, index=False, encoding="utf-8-sig")

    def load_promotions(self) -> List[Dict]:
        if self.json_path.exists():
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("promotions", [])
            except Exception:
                logger.exception("加载促销元数据失败: %s", self.json_path)
                return []
        return []

    def save_promotions(self, promotions: List[Dict]):
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump({"promotions": promotions}, f, ensure_ascii=False, indent=2)

    def import_products(self, file_path: str, mode: str = "append") -> Tuple[int, int, List[str]]:
        errors: List[str] = []
        success_count = 0
        skip_count = 0

        try:
            df_new = _read_import_table(file_path)
            df_new = df_new.fillna("")

            actual_columns = {}
            for target, variants in config.COLUMN_MAPPING.items():
                for col in df_new.columns:
                    if col in variants:
                        actual_columns[target] = col
                        break

            missing = [r for r in ["商品编号", "WB编号"] if r not in actual_columns]
            if missing:
                errors.append(f"缺少必填字段: {missing}")
                return 0, 0, errors

            extracted = pd.DataFrame()
            for target, source in actual_columns.items():
                extracted[target] = df_new[source]

            if "仓库" not in extracted.columns:
                extracted["仓库"] = "FBW"
            if "状态" not in extracted.columns:
                extracted["状态"] = "正常"
            if "类目" not in extracted.columns:
                extracted["类目"] = ""
            if "库存" not in extracted.columns:
                extracted["库存"] = 0
            if "售价" not in extracted.columns:
                extracted["售价"] = 0

            extracted["库存"] = pd.to_numeric(extracted["库存"], errors="coerce").fillna(0).astype(int)
            extracted["售价"] = pd.to_numeric(extracted["售价"], errors="coerce").fillna(0)

            valid_warehouses = config.WAREHOUSES
            extracted["仓库"] = extracted["仓库"].apply(
                lambda x: x if x in valid_warehouses else "FBW"
            )

            valid_status = config.STATUSES
            extracted["状态"] = extracted["状态"].apply(
                lambda x: x if x in valid_status else "正常"
            )

            extracted = extracted[extracted["WB编号"].notna() & (extracted["WB编号"] != "")]

            if mode == "overwrite":
                df_current = self._create_empty_df()
            else:
                df_current = self.load_products()

            existing_wb = set(df_current["WB编号"].astype(str).tolist())

            new_rows = []
            for idx, row in extracted.iterrows():
                wb = str(row["WB编号"]).strip()
                if wb == "" or wb == "nan":
                    continue
                if wb in existing_wb:
                    skip_count += 1
                    errors.append(f"WB编号重复: {wb}")
                    continue
                existing_wb.add(wb)
                new_rows.append({
                    "商品编号": str(row["商品编号"]),
                    "WB编号": wb,
                    "类目": str(row["类目"]),
                    "库存": int(row["库存"]),
                    "仓库": str(row["仓库"]),
                    "状态": str(row["状态"]),
                    "售价": float(row["售价"]),
                })
                success_count += 1

            # 一次性拼接，避免循环内反复 concat
            if new_rows:
                df_current = pd.concat(
                    [df_current, pd.DataFrame(new_rows)], ignore_index=True
                )

            self.save_products(df_current)

        except Exception as e:
            errors.append(f"导入失败: {str(e)}")
            return 0, 0, errors

        return success_count, skip_count, errors

    def update_from_template(self, file_path: str) -> Tuple[int, List[str]]:
        """
        从价格与库存更新模板更新数据
        售价计算：当前价格 × (1 - 当前折扣)
        库存：根据仓库类型选择 WB库存 或 卖家库存
        """
        errors: List[str] = []
        update_count = 0
        matched_count = 0

        try:
            if file_path.lower().endswith((".xlsx", ".xls")):
                df_update = read_excel_with_openpyxl(file_path)
            else:
                df_update = pd.read_csv(file_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)

            df_update = df_update.fillna("")

            print(f"📋 更新表列名: {list(df_update.columns)}")

            wb_col = None
            category_col = None
            seller_code_col = None
            wb_stock_col = None
            seller_stock_col = None
            current_price_col = None
            current_discount_col = None

            for col in df_update.columns:
                col_clean = str(col).strip().replace(" ", "").replace("_", "")
                if col_clean in ["WB货号", "WB商品编号"] or "WB货号" in col_clean:
                    wb_col = col
                elif col_clean in ["卖家货号", "卖家商品编号", "商品编号"] or "卖家货号" in col_clean:
                    seller_code_col = col
                elif col_clean in ["类目", "商品品类"] or "类目" in col_clean:
                    category_col = col
                elif col_clean in ["WB库存", "Wb仓库库存"] or "WB库存" in col_clean:
                    wb_stock_col = col
                elif col_clean in ["卖家库存", "Wb卖家仓库库存"] or "卖家库存" in col_clean:
                    seller_stock_col = col
                elif col_clean in ["当前价格"] or "当前价格" in col_clean:
                    current_price_col = col
                elif col_clean in ["当前折扣"] or "当前折扣" in col_clean:
                    current_discount_col = col

            print(f"🔍 找到列: WB编号={wb_col}, 卖家货号={seller_code_col}, 类目={category_col}")

            if not wb_col:
                errors.append("未找到WB编号列")
                return 0, errors

            if not current_price_col:
                errors.append("未找到'当前价格'列")
                return 0, errors

            df_current = self.load_products()
            print(f"当前数据中共有 {len(df_current)} 个商品")

            df_current["售价"] = pd.to_numeric(df_current["售价"], errors="coerce").fillna(0)
            df_current["库存"] = pd.to_numeric(df_current["库存"], errors="coerce").fillna(0).astype(int)
            df_current["WB编号_str"] = df_current["WB编号"].fillna("").astype(str).str.strip()
            df_current["商品编号_str"] = df_current["商品编号"].fillna("").astype(str).str.strip()

            for idx, row in df_update.iterrows():
                wb = str(row[wb_col]).strip()
                if wb == "" or wb == "nan":
                    continue

                mask = df_current["WB编号_str"] == wb
                matched_by = "WB编号"

                if not mask.any() and seller_code_col:
                    seller_code = str(row[seller_code_col]).strip()
                    if seller_code and seller_code != "nan":
                        mask = df_current["商品编号_str"] == seller_code
                        matched_by = "商品编号"

                if not mask.any():
                    errors.append(f"未找到: {wb}")
                    continue

                matched_count += 1

                current_wb_val = df_current.loc[mask, "WB编号"].values[0]
                if pd.isna(current_wb_val) or str(current_wb_val).strip() in ("", "nan"):
                    df_current.loc[mask, "WB编号"] = wb
                    print(f"📝 回填WB编号: {wb}")

                updated_fields = []

                if category_col:
                    val = str(row[category_col]).strip()
                    if val != "" and val != "nan":
                        df_current.loc[mask, "类目"] = val
                        updated_fields.append("类目")

                price_str = str(row[current_price_col]).strip() if current_price_col else ""
                discount_str = str(row[current_discount_col]).strip() if current_discount_col else "0"

                if price_str in ("", "nan", "None"):
                    price_str = "0"
                if discount_str in ("", "nan", "None"):
                    discount_str = "0"

                try:
                    price_str = price_str.replace(",", "").replace(" ", "")
                    discount_str = discount_str.replace(",", "").replace(" ", "")

                    current_price = float(price_str)
                    discount = float(discount_str)

                    if current_price > 0:
                        new_price = round(current_price * (1 - discount / 100), 2)
                        df_current.loc[mask, "售价"] = new_price
                        updated_fields.append(f"售价={new_price}")
                    else:
                        errors.append(f"当前价格为0: {wb}")
                except ValueError:
                    errors.append(f"售价转换失败: {wb} 价格:{price_str} 折扣:{discount_str}")
                except Exception as e:
                    errors.append(f"售价计算失败: {wb} 错误:{str(e)}")

                warehouse = df_current.loc[mask, "仓库"].values[0] if "仓库" in df_current.columns else "FBW"
                if pd.isna(warehouse):
                    warehouse = "FBW"
                stock_updated = False

                if warehouse == "FBW" and wb_stock_col:
                    stock_val = str(row[wb_stock_col]).strip()
                    if stock_val not in ("", "nan", "None"):
                        try:
                            new_stock = int(float(stock_val))
                            df_current.loc[mask, "库存"] = new_stock
                            stock_updated = True
                            updated_fields.append(f"库存={new_stock}")
                        except Exception:
                            errors.append(f"库存转换失败: {wb} 值:{stock_val}")
                elif warehouse == "FBS" and seller_stock_col:
                    stock_val = str(row[seller_stock_col]).strip()
                    if stock_val not in ("", "nan", "None"):
                        try:
                            new_stock = int(float(stock_val))
                            df_current.loc[mask, "库存"] = new_stock
                            stock_updated = True
                            updated_fields.append(f"库存={new_stock}")
                        except Exception:
                            errors.append(f"库存转换失败: {wb} 值:{stock_val}")
                elif warehouse == "WS":
                    if wb_stock_col:
                        stock_val = str(row[wb_stock_col]).strip()
                        if stock_val not in ("", "nan", "None"):
                            try:
                                new_stock = int(float(stock_val))
                                if new_stock > 0:
                                    df_current.loc[mask, "库存"] = new_stock
                                    stock_updated = True
                                    updated_fields.append(f"库存={new_stock}")
                            except Exception:
                                pass
                    if not stock_updated and seller_stock_col:
                        stock_val = str(row[seller_stock_col]).strip()
                        if stock_val not in ("", "nan", "None"):
                            try:
                                new_stock = int(float(stock_val))
                                df_current.loc[mask, "库存"] = new_stock
                                stock_updated = True
                                updated_fields.append(f"库存={new_stock}")
                            except Exception:
                                pass

                if updated_fields:
                    update_count += 1
                    print(f"✅ 更新({matched_by}): {wb} -> {', '.join(updated_fields)}")
                else:
                    print(f"⚠️ {wb} 无字段更新 (仓库:{warehouse})")

            drop_cols = [c for c in ["WB编号_str", "商品编号_str"] if c in df_current.columns]
            if drop_cols:
                df_current = df_current.drop(columns=drop_cols)

            self.save_products(df_current)
            print(f"\n📊 统计: 匹配 {matched_count} 个, 更新 {update_count} 个")

        except Exception as e:
            errors.append(f"更新失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return 0, errors

        return update_count, errors


def _read_import_table(file_path: str) -> pd.DataFrame:
    """读取导入商品用的 Excel/CSV（保持原有 dtype=str 行为）。"""
    if str(file_path).lower().endswith(".csv"):
        return pd.read_csv(file_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    return pd.read_excel(file_path, dtype=str)
