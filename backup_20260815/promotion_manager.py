import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import json
import re


class PromotionManager:
    """促销管理类"""

    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.promotions = []
        self.promo_columns = []
        self.store_name = data_manager.store_name
        self.promo_data_path = f"data/{self.store_name}/促销数据缓存.json"
        self.promo_data_cache = {}  # {wb_code: {promo_name: price}}
        self._load_promotions()
        self._load_promo_data_cache()

    def _load_promotions(self):
        self.promotions = self.data_manager.load_promotions()
        self.promotions.sort(key=lambda x: x.get('start_date', ''))
        self._update_promo_columns()

    def _update_promo_columns(self):
        self.promo_columns = [p['column_name'] for p in self.promotions]

    def _save(self):
        self.data_manager.save_promotions(self.promotions)
        self._update_promo_columns()

    # ===== 促销数据缓存 =====
    def _load_promo_data_cache(self):
        """加载促销数据缓存"""
        if os.path.exists(self.promo_data_path):
            try:
                with open(self.promo_data_path, 'r', encoding='utf-8') as f:
                    self.promo_data_cache = json.load(f)
            except:
                self.promo_data_cache = {}
        else:
            self.promo_data_cache = {}

    def _save_promo_data_cache(self):
        """保存促销数据缓存"""
        os.makedirs(os.path.dirname(self.promo_data_path), exist_ok=True)
        with open(self.promo_data_path, 'w', encoding='utf-8') as f:
            json.dump(self.promo_data_cache, f, ensure_ascii=False, indent=2)

    def cache_promo_price(self, wb_code: str, promo_name: str, price: float):
        """缓存某个商品的促销价格"""
        if wb_code not in self.promo_data_cache:
            self.promo_data_cache[wb_code] = {}
        self.promo_data_cache[wb_code][promo_name] = price
        self._save_promo_data_cache()

    def get_cached_promo(self, wb_code: str) -> Dict[str, float]:
        """获取某商品的所有缓存促销价格"""
        return self.promo_data_cache.get(wb_code, {})

    # ===== 应用到表格 =====
    def apply_promo_to_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """根据缓存数据，给DataFrame填充促销列"""
        if not self.promo_data_cache:
            return df

        # 确保促销列存在
        for col in self.promo_columns:
            if col not in df.columns:
                df[col] = ''

        # 遍历每行，根据WB编号匹配促销数据
        for idx, row in df.iterrows():
            wb = str(row.get('WB编号', '')).strip()
            if not wb or wb == 'nan':
                continue

            if wb in self.promo_data_cache:
                promo_data = self.promo_data_cache[wb]
                for promo_name, price in promo_data.items():
                    # 找到对应的列名
                    for p in self.promotions:
                        if p.get('promotion_name') == promo_name:
                            col = p['column_name']
                            if col in df.columns:
                                df.at[idx, col] = str(price)
                            break

        return df

    def _reorder_and_rename(self, df_current):
        if not self.promotions:
            return df_current

        # 按 start_date 排序，相同则按 upload_time 排序
        self.promotions.sort(key=lambda x: (x.get('start_date', ''), x.get('upload_time', '')))

        promo_data = {}
        for p in self.promotions:
            old_name = p['column_name']
            if old_name and old_name in df_current.columns:
                promo_data[old_name] = df_current[old_name].copy()

        for p in self.promotions:
            old_name = p['column_name']
            if old_name and old_name in df_current.columns:
                df_current = df_current.drop(columns=[old_name])

        for idx, p in enumerate(self.promotions, 1):
            new_name = f"{idx}促"
            p['column_name'] = new_name
            df_current[new_name] = ''

        for p in self.promotions:
            new_name = p['column_name']
            promo_name = p.get('promotion_name', '')
            start_date = p.get('start_date', '')
            matched = False
            for old_name, data in promo_data.items():
                if promo_name and promo_name in old_name:
                    df_current[new_name] = data
                    matched = True
                    break
                if start_date and start_date in old_name:
                    df_current[new_name] = data
                    matched = True
                    break
            if not matched and promo_data:
                old_names = list(promo_data.keys())
                idx_p = self.promotions.index(p)
                if idx_p < len(old_names):
                    df_current[new_name] = promo_data[old_names[idx_p]]

        return df_current

    # ===== 重新排序促销 =====
    def reorder_promotions(self):
        """按开始时间 + 上传时间重新排序促销"""
        if not self.promotions:
            return

        # 按 start_date 升序，相同则按 upload_time 升序
        self.promotions.sort(key=lambda x: (x.get('start_date', ''), x.get('upload_time', '')))

        # 重新命名并更新 DataFrame
        df = self.data_manager.load_products()
        old_names = [p['column_name'] for p in self.promotions]

        # 删除所有促销列
        for col in old_names:
            if col in df.columns:
                df = df.drop(columns=[col])

        # 重新创建促销列
        for idx, p in enumerate(self.promotions, 1):
            new_name = f"{idx}促"
            p['column_name'] = new_name
            df[new_name] = ''

        self.data_manager.save_products(df)
        self._save()
        self._update_promo_columns()

    # ===== 导入促销（修改名称解析） =====
    def import_promotion(self, file_path: str, start_date: str, end_date: str) -> Tuple[int, List[str]]:
        errors = []
        update_count = 0

        try:
            if file_path.endswith('.csv'):
                df_promo = pd.read_csv(file_path, encoding='utf-8-sig', dtype=str, keep_default_na=False)
            else:
                df_promo = pd.read_excel(file_path, sheet_name=0, dtype=str)

            df_promo = df_promo.fillna('')

            # ===== ✅ 修改：解析促销名称，去掉括号内容 =====
            file_basename = os.path.basename(file_path)
            file_name_without_ext = os.path.splitext(file_basename)[0]

            # 1. 去除括号及其内容（俄语括号、中文括号、英文括号）
            file_name_without_ext = re.sub(r'\s*\([^)]*\)', '', file_name_without_ext)  # ( )
            file_name_without_ext = re.sub(r'\s*（[^）]*）', '', file_name_without_ext)  # （ ）
            file_name_without_ext = re.sub(r'\s*\[[^\]]*\]', '', file_name_without_ext)  # [ ]

            # 2. 去除日期时间部分
            file_name_without_ext = re.sub(r'\s*\d{2}\.\d{2}\.\d{4}\s+\d{2}\.\d{2}\.\d{2}', '',
                                           file_name_without_ext)  # 08.07.2026 04.31.44
            file_name_without_ext = re.sub(r'\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', '',
                                           file_name_without_ext)  # 2026-07-08 04:31:44
            file_name_without_ext = re.sub(r'\s*\d{2}\.\d{2}\.\d{4}', '', file_name_without_ext)  # 08.07.2026

            # 3. 去除开头和结尾多余的下划线、空格
            file_name_without_ext = file_name_without_ext.strip(' _-')

            # 4. 取下划线后的部分作为促销名称
            promo_name = file_name_without_ext
            if '_' in file_name_without_ext:
                parts = file_name_without_ext.split('_')
                if len(parts) >= 2:
                    promo_name = '_'.join(parts[1:])

            # 5. 如果最终名称为空，使用原文件名
            if not promo_name.strip():
                promo_name = file_name_without_ext

            print(f"📋 促销名称: {promo_name}")

            wb_col = None
            price_col = None

            for col in df_promo.columns:
                col_clean = str(col).strip()
                if col_clean in ['WB商品编号', 'WB货号']:
                    wb_col = col
                elif col_clean in ['活动计划价格', '活动计划价']:
                    price_col = col

            if not wb_col:
                errors.append("未找到WB编号列")
                return 0, errors

            if not price_col:
                errors.append("未找到活动计划价格列")
                return 0, errors

            df_current = self.data_manager.load_products()

            promo_meta = {
                'column_name': '',
                'promotion_name': promo_name,
                'start_date': start_date,
                'end_date': end_date,
                'upload_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            self.promotions.append(promo_meta)
            df_current = self._reorder_and_rename(df_current)
            self.promotions.sort(key=lambda x: (x.get('start_date', ''), x.get('upload_time', '')))
            latest_promo = self.promotions[-1]['column_name']
            fill_count = 0

            for idx, row in df_promo.iterrows():
                wb = str(row[wb_col]).strip()
                if wb == '' or wb == 'nan':
                    continue

                price_str = str(row[price_col]).strip()
                if price_str == '' or price_str == 'nan':
                    continue

                try:
                    price = float(price_str)
                except ValueError:
                    errors.append(f"价格格式错误: {price_str}")
                    continue

                self.cache_promo_price(wb, promo_name, price)

                mask = df_current['WB编号'].astype(str).str.strip() == wb
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
            col_name = p['column_name']
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
        """清理过期促销"""
        today = datetime.now().strftime('%Y-%m-%d')
        if not self.promotions:
            return

        valid_promotions = []
        removed_promotions = []

        for p in self.promotions:
            end_date = p.get('end_date', '')
            if end_date == '' or end_date >= today:
                valid_promotions.append(p)
            else:
                removed_promotions.append(p)

        if len(valid_promotions) == len(self.promotions):
            return

        df_current = self.data_manager.load_products()

        for p in removed_promotions:
            col_name = p['column_name']
            promo_name = p.get('promotion_name', '')
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
            if p['column_name'] == column_name:
                promo_name = p.get('promotion_name', '')
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
            if p['column_name'] == column_name:
                return p
        return None

    def get_all_meta(self) -> List[Dict]:
        return self.promotions