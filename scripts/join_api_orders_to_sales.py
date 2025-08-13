#!/usr/bin/env python3

import logging
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CRM = REPO_ROOT / "data_crm"
ORDERS_CSV = DATA_CRM / "orders_api_latest.csv"
KSP_MAP_XLSX = DATA_CRM / "mappings" / "ksp_sku_map_updated.xlsx"
SKU_MAP_GLOB = list(DATA_CRM.glob("sku_map_crm_*.xlsx"))
RULES_DIR = DATA_CRM / "rules"
STOCK_CSV = DATA_CRM / "stock_on_hand.csv"
PROCESSED_DIR = DATA_CRM / "processed"
STOCK_DIR = DATA_CRM / "stock"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
STOCK_DIR.mkdir(parents=True, exist_ok=True)

RUN_DATE = pd.Timestamp.utcnow().strftime("%Y%m%d")
PROCESSED_SALES_DATED = PROCESSED_DIR / f"processed_sales_{RUN_DATE}.csv"
PROCESSED_SALES_LATEST = DATA_CRM / "processed_sales_latest.csv"
STOCK_UPDATED_DATED = STOCK_DIR / f"stock_on_hand_updated_{RUN_DATE}.csv"
STOCK_UPDATED_LATEST = DATA_CRM / "stock_on_hand_updated.csv"
REPORTS_DIR = DATA_CRM / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
COVERAGE_API = REPORTS_DIR / "mapping_coverage_api.csv"


def _lower_columns_inplace(df: pd.DataFrame) -> None:
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]


def _choose_first_existing(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    for name in candidates:
        if name in df.columns:
            return name
    return None


def _read_excel(path: Path) -> pd.DataFrame:
    try:
        xls = pd.ExcelFile(path, engine="openpyxl")
    except Exception:
        xls = pd.ExcelFile(path)
    return xls.parse(xls.sheet_names[0])


def load_size_rules() -> Dict[str, str]:
    rules_path = RULES_DIR / "size_normalization.csv"
    mapping: Dict[str, str] = {}
    if rules_path.exists():
        df = pd.read_csv(rules_path, comment="#")
        if set([c.lower() for c in df.columns]) >= {"raw", "normalized"}:
            for _, r in df.iterrows():
                raw = str(r.get("raw", "")).strip().lower()
                norm = str(r.get("normalized", "")).strip().upper()
                if raw:
                    mapping[raw] = norm
    # Common fallbacks
    mapping.update(
        {
            "xxl": "2XL",
            "xxxl": "3XL",
            "xxxxl": "4XL",
            "x l": "XL",
            "x-large": "XL",
        }
    )
    return mapping


def normalize_size(value: Any, rules: Dict[str, str]) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    low = text.lower().strip()
    if low in {"nan", "none", "null", "-", "_"}:
        return ""
    # Apply rules exact match
    if low in rules:
        return rules[low]
    # Heuristics
    upper = text.upper().replace(" ", "")
    repl = {"XXXXL": "4XL", "XXXL": "3XL", "XXL": "2XL"}
    for k, v in repl.items():
        upper = upper.replace(k, v)
    # Numeric sizes
    import re

    m = re.search(r"\b(4[4-9]|5[0-9]|6[0-4])\b", upper)
    if m:
        return m.group(1)
    # Letter tokens
    t = re.findall(r"(4XL|3XL|2XL|XL|L|M|S)", upper)
    if t:
        return t[-1]
    return upper


def build_sku_id(sku_key: str, my_size: str) -> str:
    sku_key = (sku_key or "").strip()
    my_size = (my_size or "").strip()
    if not sku_key:
        return ""
    return f"{sku_key}_{my_size}" if my_size else f"{sku_key}_"


def update_stock(stock_df: pd.DataFrame, sales_df: pd.DataFrame, qty_col: str) -> pd.DataFrame:
    """Mirror CRM pipeline stock update behavior.

    - Detect stock quantity column (prefers qty_on_hand)
    - Subtract sold quantities per sku_key
    - Add oversell column
    - Return full dataframe with original columns preserved
    """
    if "sku_key" not in stock_df.columns:
        raise KeyError("Expected column 'sku_key' in stock file")

    stock_df = stock_df.copy()
    stock_df["sku_key"] = stock_df["sku_key"].astype(str).str.strip()

    stock_qty_col = (
        _choose_first_existing(
            stock_df,
            [
                "qty_on_hand",
                "qty",
                "quantity",
                "stock",
                "on_hand",
                "stock_on_hand",
                "available",
                "qty_available",
            ],
        )
        or "qty_on_hand"
    )
    stock_df[stock_qty_col] = pd.to_numeric(stock_df.get(stock_qty_col, 0), errors="coerce").fillna(
        0
    )

    sold_by_key = (
        sales_df.assign(sku_key=lambda d: d["sku_key"].astype(str).str.strip())
        .groupby("sku_key", dropna=False)[qty_col]
        .sum()
        .reset_index()
        .rename(columns={qty_col: "sold_qty"})
    )

    merged = stock_df.merge(sold_by_key, on="sku_key", how="left")
    merged["sold_qty"] = pd.to_numeric(merged["sold_qty"], errors="coerce").fillna(0)
    updated_raw = merged[stock_qty_col] - merged["sold_qty"]
    merged["oversell"] = (-updated_raw).clip(lower=0)
    merged[stock_qty_col] = updated_raw.clip(lower=0)
    return merged


def main() -> int:
    if not ORDERS_CSV.exists():
        logger.info("No orders staging CSV found at %s; nothing to do", ORDERS_CSV)
        return 0

    orders = pd.read_csv(ORDERS_CSV)
    _lower_columns_inplace(orders)

    # Ensure essential columns
    for col in [
        "orderid",
        "date",
        "store_name",
        "ksp_sku_id",
        "sku_key",
        "my_size",
        "qty",
        "sell_price",
    ]:
        if col not in orders.columns:
            orders[col] = pd.NA

    # Normalize size
    rules = load_size_rules()
    orders["my_size"] = orders["my_size"].apply(lambda v: normalize_size(v, rules))

    # Ensure qty numeric (default 1)
    orders["qty"] = pd.to_numeric(orders["qty"], errors="coerce").fillna(1).astype(int)
    orders["sell_price"] = pd.to_numeric(orders["sell_price"], errors="coerce")

    # Map KSP SKU to sku_key using mapping file
    if KSP_MAP_XLSX.exists():
        kmap = _read_excel(KSP_MAP_XLSX)
        _lower_columns_inplace(kmap)
        # Try to identify columns
        ksp_col = (
            _choose_first_existing(kmap, ["ksp_sku_id", "sku_id_ksp", "code", "ksp", "sku_ksp"])
            or "ksp_sku_id"
        )
        store_col = _choose_first_existing(kmap, ["store_name", "store", "shop_name"]) or None
        key_col = (
            _choose_first_existing(
                kmap, ["sku_key", "mastercode", "master_code", "product_master_code"]
            )
            or "sku_key"
        )
        # Coerce strings
        kmap[ksp_col] = kmap[ksp_col].astype(str).str.strip()
        if store_col:
            kmap[store_col] = kmap[store_col].astype(str).str.strip().str.upper()
        kmap[key_col] = kmap[key_col].astype(str).str.strip()
        # Prepare join keys in orders
        orders["ksp_sku_id"] = orders["ksp_sku_id"].astype(str).str.strip()
        orders["store_name"] = orders["store_name"].astype(str).str.strip().str.upper()
        # First try match on (ksp_sku_id, store_name)
        if store_col:
            merged = orders.merge(
                kmap[[ksp_col, store_col, key_col]].drop_duplicates(),
                left_on=["ksp_sku_id", "store_name"],
                right_on=[ksp_col, store_col],
                how="left",
            )
            orders["sku_key"] = orders["sku_key"].fillna(merged[key_col])
        # Fallback: match only on ksp_sku_id
        merged2 = orders.merge(
            kmap[[ksp_col, key_col]].drop_duplicates(),
            left_on="ksp_sku_id",
            right_on=ksp_col,
            how="left",
        )
        orders["sku_key"] = orders["sku_key"].fillna(merged2[key_col])

    # Optional enrichment with SKU map (not required for basic processed log)
    # Build sku_id
    orders["sku_id"] = [
        build_sku_id(k, s)
        for k, s in zip(orders["sku_key"].astype(str), orders["my_size"].astype(str))
    ]

    # Build processed sales log schema
    out = pd.DataFrame()
    out["orderid"] = orders.get("orderid")
    out["date"] = orders.get("date")
    out["sku_id"] = orders.get("sku_id")
    out["store_name"] = orders.get("store_name")
    out["qty"] = orders.get("qty")
    out["sell_price"] = orders.get("sell_price")
    out["customer_height"] = (
        orders.get("customer_height") if "customer_height" in orders.columns else ""
    )
    out["customer_weight"] = (
        orders.get("customer_weight") if "customer_weight" in orders.columns else ""
    )
    out["ksp_sku_id"] = orders.get("ksp_sku_id")
    out["sku_key"] = orders.get("sku_key")
    out["my_size"] = orders.get("my_size")
    out["normalized_phone"] = ""

    # Write processed sales (dated + latest)
    out.to_csv(PROCESSED_SALES_DATED, index=False)
    out.to_csv(PROCESSED_SALES_LATEST, index=False)
    logger.info("Processed sales written: %s and %s", PROCESSED_SALES_LATEST, PROCESSED_SALES_DATED)

    # Update stock
    if STOCK_CSV.exists():
        stock_df = pd.read_csv(STOCK_CSV)
        _lower_columns_inplace(stock_df)
        updated_stock = update_stock(stock_df, out, "qty")
        updated_stock.to_csv(STOCK_UPDATED_DATED, index=False)
        updated_stock.to_csv(STOCK_UPDATED_LATEST, index=False)
        logger.info("Updated stock written: %s and %s", STOCK_UPDATED_LATEST, STOCK_UPDATED_DATED)
    else:
        logger.warning("Stock file missing: %s. Skipping stock update.", STOCK_CSV)

    # Coverage report
    coverage = {
        "total_sales_rows": int(len(out)),
        "rows_with_valid_sku_id": int(out["sku_id"].astype(str).str.len().gt(1).sum()),
        "rows_missing_sku_id": int(out["sku_id"].astype(str).str.len().le(1).sum()),
        "unique_sku_id_in_sales": int(out["sku_id"].nunique(dropna=True)),
        "unique_sku_id_in_map": 0,
        "timestamp": pd.Timestamp.utcnow().isoformat(),
    }
    if KSP_MAP_XLSX.exists():
        try:
            kmap = _read_excel(KSP_MAP_XLSX)
            _lower_columns_inplace(kmap)
            if "sku_key" in kmap.columns and "my_size" in kmap.columns:
                kmap["sku_id"] = (
                    kmap["sku_key"].astype(str).str.strip()
                    + "_"
                    + kmap["my_size"].astype(str).str.strip()
                )
                coverage["unique_sku_id_in_map"] = int(kmap["sku_id"].nunique(dropna=True))
        except Exception:
            pass
    pd.DataFrame([coverage]).to_csv(COVERAGE_API, index=False)
    logger.info("Coverage report written: %s", COVERAGE_API)

    # Summary
    print(f"Processed sales rows: {len(out)}")
    print(f"Output: {PROCESSED_SALES_LATEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
