"""Excel/CSV 读取公共工具。"""
import pandas as pd


def read_excel_or_csv(file_path: str, sheet_name=0) -> pd.DataFrame:
    """按扩展名选择读取方式，统一返回字符串型 DataFrame。"""
    if str(file_path).lower().endswith(".csv"):
        return pd.read_csv(file_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    return pd.read_excel(file_path, sheet_name=sheet_name, dtype=str)


def read_excel_with_openpyxl(file_path: str) -> pd.DataFrame:
    """用 openpyxl 读取 Excel（保留原更新模板的读取行为，data_only=True）。"""
    import openpyxl

    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active

    all_rows = []
    headers = []
    for row in ws.iter_rows(values_only=True):
        str_row = [str(v) if v is not None else "" for v in row]
        if not headers:
            headers = [h.strip() for h in str_row]
        else:
            all_rows.append(str_row)
    wb.close()

    return pd.DataFrame(all_rows, columns=headers)


def find_column(df: pd.DataFrame, candidates) -> str:
    """返回 df 中第一个匹配候选名的列名；没有则返回空字符串。"""
    for col in df.columns:
        if col in candidates:
            return col
    return ""
