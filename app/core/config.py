"""全局配置：店铺、枚举、默认目录、列名规则集中管理。"""
from typing import Dict, List

# 店铺清单（顺序即主窗口 Tab 顺序）
STORES: List[str] = ["6号店", "8号店"]

# 各店铺默认打开目录（与原代码保持一致，可在此集中修改）
STORE_DEFAULT_DIRS: Dict[str, str] = {
    "6号店": r"C:\Users\liuzh\Desktop\Super Browser\李军WB 5-6号",
    "8号店": r"C:\Users\liuzh\Desktop\Super Browser\本土WB 8号",
}

# 数据文件名
PRODUCT_CSV_NAME = "商品数据.csv"
PROMO_META_JSON_NAME = "促销元数据.json"
PROMO_DATA_CACHE_JSON_NAME = "促销数据缓存.json"
COMPETITOR_DIR_NAME = "competitor"
COMPETITOR_IMAGE_SUBDIR = "images"
COMPETITOR_INFO_NAME = "info.json"

# 商品表基础列
BASE_COLUMNS: List[str] = ["商品编号", "WB编号", "类目", "库存", "仓库", "状态", "售价"]
SEQUENCE_COLUMN = "序号"

# 促销列命名规则（第 n 个促销列名）
PROMO_COLUMN_TEMPLATE = "{n}促"

# 仓库 / 状态 / 店铺类型枚举
WAREHOUSES: List[str] = ["FBW", "FBS", "WS"]
STATUSES: List[str] = ["正常", "好卖", "爆款", "淘汰"]
STORE_TYPES: List[str] = ["本土店", "跨境店"]

# 导入模板的列名候选映射（目标列 -> 可能的源列名）
COLUMN_MAPPING: Dict[str, List[str]] = {
    "商品编号": ["商品编号", "卖家商品编号", "卖家的文章", "卖家货号"],
    "WB编号": ["WB商品编号", "WB货号", "WB商品卡"],
    "类目": ["项目", "商品品类", "类目"],
    "库存": ["库存", "WB库存"],
    "仓库": ["仓库"],
    "状态": ["状态"],
    "售价": ["售价", "当前零售价", "价格"],
}
