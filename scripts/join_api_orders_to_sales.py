#!/usr/bin/env python3
# fail when labels exist but orders rows < N
labels_dir = DATA_CRM / "labels_grouped" / pd.Timestamp.utcnow().strftime("%Y-%m-%d")
has_labels = labels_dir.exists() and any(p.suffix.lower()==".pdf" for p in labels_dir.rglob("*.pdf"))
min_orders = int(os.getenv("MIN_ORDERS_FOR_TODAY", "10"))
if has_labels and len(orders) < min_orders:
    raise SystemExit(f"Orders rows {len(orders)} < {min_orders} while labels exist; refusing to proceed.")
    
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
from settings.paths import DATA_CRM
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
SCHEMA_DIFF_PATH = REPORTS_DIR / "schema_diff.txt"


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
    # Only build when BOTH sku_key and my_size are present
    if not sku_key or not my_size:
        return ""
    return f"{sku_key}_{my_size}"


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


def load_expected_schema() -> Optional[List[str]]:
    canonical_path = DATA_CRM / "processed_sales_20250813.csv"
    if not canonical_path.exists():
        return None
    try:
        with canonical_path.open("r", encoding="utf-8") as f:
            header = f.readline().strip()
        if not header:
            return None
        return [h.strip() for h in header.split(",")]
    except Exception:
        return None


def enforce_schema(df: pd.DataFrame, expected_columns: List[str]) -> Tuple[pd.DataFrame, str]:
    current_cols = list(df.columns)
    current_set = set(current_cols)
    expected_set = set(expected_columns)

    missing = [c for c in expected_columns if c not in current_set]
    extra = [c for c in current_cols if c not in expected_set]
    order_mismatch = current_cols != expected_columns

    for c in missing:
        df[c] = ""
    df = df[expected_columns]

    diff_lines: List[str] = []
    if missing:
        diff_lines.append("Missing columns added: " + ", ".join(missing))
    if extra:
        diff_lines.append("Extra columns dropped: " + ", ".join(extra))
    if order_mismatch:
        diff_lines.append("Column order adjusted to match canonical processed_sales schema")

    return df, "\n".join(diff_lines)


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
        "product_master_code",
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

    # Normalize join fields
    orders["ksp_sku_id"] = orders["ksp_sku_id"].astype(str).str.strip()
    orders["store_name"] = orders["store_name"].astype(str).str.strip().str.upper()
    orders["product_master_code"] = orders["product_master_code"].astype(str).str.strip()
    orders["product_master_code_norm"] = orders["product_master_code"].str.upper()

    # Map KSP SKU to sku_key using mapping file with tolerant fallbacks
    if KSP_MAP_XLSX.exists():
        kmap = _read_excel(KSP_MAP_XLSX)
        _lower_columns_inplace(kmap)
        # Try to identify columns
        ksp_col = (
            _choose_first_existing(kmap, ["ksp_sku_id", "sku_id_ksp", "code", "ksp", "sku_ksp"])
            or "ksp_sku_id"
        )
        store_col = _choose_first_existing(kmap, ["store_name", "store", "shop_name"]) or None
        # Column containing canonical sku_key result
        result_key_col = (
            _choose_first_existing(
                kmap, ["sku_key", "sku", "master_sku_key", "mastercode", "master_code", "product_master_code"]
            )
            or "sku_key"
        )
        # Column containing product master code in mapping file (for joining by product_master_code)
        pcode_col = _choose_first_existing(kmap, ["product_master_code", "mastercode", "master_code"]) or None

        # Coerce strings in mapping file
        kmap[ksp_col] = kmap[ksp_col].astype(str).str.strip()
        if store_col:
            kmap[store_col] = kmap[store_col].astype(str).str.strip().str.upper()
        kmap[result_key_col] = kmap[result_key_col].astype(str).str.strip()
        if pcode_col:
            kmap[pcode_col] = kmap[pcode_col].astype(str).str.strip().str.upper()

        # Attempt (a): (ksp_sku_id, store_name)
        if store_col:
            right_a = (
                kmap[[ksp_col, store_col, result_key_col]]
                .drop_duplicates()
                .rename(columns={result_key_col: "_mapped_sku_key"})
            )
            joined_a = orders.merge(
                right_a,
                left_on=["ksp_sku_id", "store_name"],
                right_on=[ksp_col, store_col],
                how="left",
            )
            orders["sku_key"] = orders["sku_key"].fillna(joined_a["_mapped_sku_key"])

        # Attempt (b): (product_master_code, store_name)
        if store_col and pcode_col:
            right_b = (
                kmap[[pcode_col, store_col, result_key_col]]
                .drop_duplicates()
                .rename(columns={pcode_col: "_pcode", result_key_col: "_mapped_sku_key"})
            )
            joined_b = orders.merge(
                right_b,
                left_on=["product_master_code_norm", "store_name"],
                right_on=["_pcode", store_col],
                how="left",
            )
            orders["sku_key"] = orders["sku_key"].fillna(joined_b["_mapped_sku_key"])

        # Attempt (c): ksp_sku_id only
        right_c = (
            kmap[[ksp_col, result_key_col]].drop_duplicates().rename(columns={result_key_col: "_mapped_sku_key"})
        )
        joined_c = orders.merge(
            right_c,
            left_on="ksp_sku_id",
            right_on=ksp_col,
            how="left",
        )
        orders["sku_key"] = orders["sku_key"].fillna(joined_c["_mapped_sku_key"])

        # Attempt (d): product_master_code only
        if pcode_col:
            right_d = (
                kmap[[pcode_col, result_key_col]]
                .drop_duplicates()
                .rename(columns={pcode_col: "_pcode", result_key_col: "_mapped_sku_key"})
            )
            joined_d = orders.merge(
                right_d,
                left_on="product_master_code_norm",
                right_on="_pcode",
                how="left",
            )
            orders["sku_key"] = orders["sku_key"].fillna(joined_d["_mapped_sku_key"])

    # Ensure sku_key as string post-mapping
    orders["sku_key"] = orders["sku_key"].astype(str).str.strip()

    # Build sku_id only when both sku_key and my_size are present
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
    out["product_master_code"] = orders.get("product_master_code")
    out["my_size"] = orders.get("my_size")
    out["normalized_phone"] = ""

    # Write missing KSP mapping report
    def _guess_model_group(text: str) -> str:
        t = (text or "").lower()
        import re

        patterns = [
            (r"print", "print"),
            (r"\bbeli\w*\b", "beli"),
            (r"\bwhite\b", "white"),
            (r"\bblack\b|chern", "black"),
        ]
        for pat, label in patterns:
            if re.search(pat, t):
                return label
        return ""

    missing_mask = orders["sku_key"].astype(str).str.len().eq(0)
    missing_rows = orders.loc[missing_mask, ["orderid", "ksp_sku_id", "product_master_code", "store_name", "sku_key"]].copy()
    if not missing_rows.empty:
        guessed = [
            _guess_model_group((sk if isinstance(sk, str) else "") or (pmc if isinstance(pmc, str) else ""))
            for sk, pmc in zip(missing_rows["sku_key"], missing_rows["product_master_code"])
        ]
        missing_rows = missing_rows.assign(guessed_model_group=guessed)[
            ["orderid", "ksp_sku_id", "product_master_code", "store_name", "guessed_model_group"]
        ]
        (REPORTS_DIR / "missing_ksp_mapping.csv").write_text("", encoding="utf-8") if False else None
        missing_rows.to_csv(REPORTS_DIR / "missing_ksp_mapping.csv", index=False)

    # Enforce strict schema to match canonical processed_sales
    expected_columns = load_expected_schema()
    if expected_columns:
        out_strict, diff = enforce_schema(out, expected_columns)
        if diff:
            SCHEMA_DIFF_PATH.write_text(diff + "\n", encoding="utf-8")
        out = out_strict

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
