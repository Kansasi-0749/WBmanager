"""表格筛选逻辑：从 UI 剥离并以 pandas 向量化实现。"""
import pandas as pd


def apply_filters(
    df: pd.DataFrame,
    filters: dict,
    promo_columns: list,
    promo_meta: dict,
    color_filter: str = None,
    category_text: str = "",
) -> pd.DataFrame:
    """按筛选条件过滤数据，返回过滤后的副本。

    筛选顺序与原实现一致：普通筛选 -> 颜色筛选 -> 类目筛选。
    """
    if df is None or df.empty:
        return df.copy() if df is not None else pd.DataFrame()

    df = df.copy()

    # 1. 普通筛选
    for col_name, filter_value in filters.items():
        if not filter_value or filter_value == "(全部)":
            continue
        if col_name not in df.columns:
            continue
        try:
            df[col_name] = df[col_name].fillna("").astype(str).str.strip()
            if filter_value == "__HAS_VALUE__":
                df = df[df[col_name] != ""]
            elif filter_value == "__EMPTY__":
                df = df[df[col_name] == ""]
            elif isinstance(filter_value, list):
                clean_list = [str(v).strip() for v in filter_value]
                if all(v.startswith("__") for v in clean_list):
                    # 条件令牌模式（促销列多条件）：多个条件同时生效（AND）
                    has_value = df[col_name] != ""
                    green = _column_green_mask(df, col_name, promo_meta)
                    mask = pd.Series(True, index=df.index)
                    for token in clean_list:
                        if token == "__HAS_VALUE__":
                            mask &= has_value
                        elif token == "__EMPTY__":
                            mask &= ~has_value
                        elif token == "__GREEN__":
                            mask &= green
                        elif token == "__NOT_GREEN__":
                            mask &= ~green
                    df = df[mask]
                else:
                    df = df[df[col_name].isin(clean_list)]
            else:
                df = df[df[col_name] == str(filter_value).strip()]
        except Exception as e:
            print(f"⚠️ 筛选异常 col={col_name}: {e}")
            continue

    # 2. 颜色筛选
    if color_filter:
        green_mask = _green_highlight_mask(df, promo_columns, promo_meta)
        if color_filter == "green":
            df = df[green_mask]
        elif color_filter == "white":
            df = df[~green_mask]

    # 3. 类目筛选
    if category_text and category_text.strip():
        if "类目" in df.columns:
            df["类目"] = df["类目"].fillna("").astype(str)
            df = df[df["类目"].str.contains(category_text.strip(), case=False, na=False)]

    return df


def _green_highlight_mask(df: pd.DataFrame, promo_columns: list, promo_meta: dict) -> pd.Series:
    """返回行是否为绿色高亮（存在促销价且 0 < 售价 <= 促销价）。"""
    mask = pd.Series(False, index=df.index)
    for col in promo_columns:
        mask = mask | _column_green_mask(df, col, promo_meta)
    return mask


def _column_green_mask(df: pd.DataFrame, col_name: str, promo_meta: dict) -> pd.Series:
    """返回某促销列自身的绿色高亮掩码（该列有促销价且 0 < 售价 <= 促销价）。"""
    mask = pd.Series(False, index=df.index)
    if "售价" not in df.columns or col_name not in df.columns or col_name not in promo_meta:
        return mask
    price = pd.to_numeric(df["售价"], errors="coerce")
    promo_price = pd.to_numeric(df[col_name], errors="coerce")
    return price.notna() & promo_price.notna() & (price > 0) & (price <= promo_price)
