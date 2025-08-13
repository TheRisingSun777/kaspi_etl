"""
Process sales from the CRM sales file, match to internal SKU IDs, generate a normalized
sales log, and update stock quantities.

Steps:
- Load CRM sales Excel, the KSP SKU map, optional CRM SKU map, and current stock-on-hand.
- Normalize column names and key fields; compute `sku_id = sku_key + '_' + my_size`.
- Enrich sales with CRM SKU map on `sku_id`. Warn for sales with unknown `sku_id`.
- Update stock levels by subtracting sold quantities per `sku_key` and save updated stock.
- Write a normalized sales log CSV with key fields for downstream processing.

Inputs (relative to repository root):
- data_crm/sales_ksp_crm_20250813_v1.xlsx
- data_crm/mappings/ksp_sku_map_updated.xlsx
- data_crm/sku_map_crm_20250813_v1.xlsx (optional)
- data_crm/stock_on_hand.csv

Outputs:
- data_crm/processed_sales_20250813.csv
- data_crm/stock_on_hand_updated.csv
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import re
from typing import Iterable, List, Optional

import pandas as pd
# Ensure project root on sys.path for imports like `utils.phones`
sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils.phones import parse_kz_phone


REPO_ROOT = Path(__file__).resolve().parents[1]
try:
    from scripts.crm_config import load_crm_config, get_run_date
    CFG = load_crm_config()
    RUN_DATE = get_run_date(pd.Timestamp.utcnow().strftime("%Y%m%d"))
except Exception:
    CFG = {}
    RUN_DATE = os.environ.get("RUN_DATE", pd.Timestamp.utcnow().strftime("%Y%m%d"))
DATA_CRM_DIR = REPO_ROOT / "data_crm"
SALES_XLSX = DATA_CRM_DIR / "sales_ksp_crm_20250813_v1.xlsx"
KSP_MAP_XLSX = DATA_CRM_DIR / "mappings" / "ksp_sku_map_updated.xlsx"
SKU_MAP_XLSX = DATA_CRM_DIR / "sku_map_crm_20250813_v1.xlsx"
STOCK_CSV = DATA_CRM_DIR / "stock_on_hand.csv"
PROCESSED_DIR = DATA_CRM_DIR / "processed"
STOCK_DIR = DATA_CRM_DIR / "stock"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
STOCK_DIR.mkdir(parents=True, exist_ok=True)

PROCESSED_SALES_DATED = PROCESSED_DIR / f"processed_sales_{RUN_DATE}.csv"
STOCK_UPDATED_DATED = STOCK_DIR / f"stock_on_hand_updated_{RUN_DATE}.csv"

PROCESSED_SALES_CSV = DATA_CRM_DIR / "processed_sales_latest.csv"
STOCK_UPDATED_CSV = DATA_CRM_DIR / "stock_on_hand_updated.csv"
MISSING_SKUS_CSV = DATA_CRM_DIR / "missing_skus.csv"
SALES_FIXED_XLSX = DATA_CRM_DIR / "sales_ksp_crm_fixed.xlsx"
ORDERS_CSV = DATA_CRM_DIR / "orders_clean_preview.csv"
ORDERS_XLSX = DATA_CRM_DIR / "orders_kaspi_with_sizes.xlsx"
ORDERS_NORMALIZED_CSV = DATA_CRM_DIR / "orders_with_sizes_normalized.csv"


def _lower_columns_inplace(df: pd.DataFrame) -> None:
    df.columns = [str(c).strip().lower() for c in df.columns]


def _read_excel(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, engine="openpyxl")


def _choose_first_existing(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    for name in candidates:
        if name in df.columns:
            return name
    return None


def _ensure_columns(df: pd.DataFrame, required: Iterable[str]) -> None:
    for col in required:
        if col not in df.columns:
            df[col] = pd.NA


def normalize_size(value: object) -> str:
    """Normalize size tokens to canonical forms.

    - Returns "" for NaN/None/empty or placeholders (nan/none/null/-/_)
    - Collapses spaces and uppercases
    - Maps XXL/XXXL/XXXXL → 2XL/3XL/4XL
    - Accepts explicit 2XL/3XL/4XL and S/M/L/XL
    - If mixed tokens present, picks the last recognized token
    - If a numeric size (44–64) is present, returns that number as string
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    upper = text.upper().strip()
    if upper in {"NAN", "NONE", "NULL", "-", "_"}:
        return ""
    upper = upper.replace(" ", "")

    # Expand common textual variants
    repl = {
        "XXXXL": "4XL",
        "XXXL": "3XL",
        "XXL": "2XL",
        "X-L": "XL",
        "X L": "XL",
        "2 X L": "2XL",
        "3 X L": "3XL",
        "4 X L": "4XL",
    }
    for k, v in repl.items():
        upper = upper.replace(k, v)

    # Recognized tokens
    tokens = re.findall(r"(4[4-9]|5[0-9]|6[0-4]|[2-4]?XL|XL|L|M|S)", upper)
    if tokens:
        return tokens[-1]

    return upper


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame], pd.DataFrame]:
    # Prefer fixed file if present
    sales_path = SALES_FIXED_XLSX if SALES_FIXED_XLSX.exists() else SALES_XLSX
    if not sales_path.exists():
        raise FileNotFoundError(f"Missing sales file: {sales_path}")
    if not KSP_MAP_XLSX.exists():
        raise FileNotFoundError(f"Missing KSP map: {KSP_MAP_XLSX}")
    if not STOCK_CSV.exists():
        raise FileNotFoundError(f"Missing stock file: {STOCK_CSV}")

    sales_df = _read_excel(sales_path)
    _lower_columns_inplace(sales_df)
    sales_df.rename(
        columns={
            "sku_id_ksp": "ksp_sku_id",
            "sku_key": "sku_key",
            "store_name": "store_name",
            "my_size": "my_size",
        },
        inplace=True,
    )

    ksp_map_df = _read_excel(KSP_MAP_XLSX)
    _lower_columns_inplace(ksp_map_df)

    sku_map_df: Optional[pd.DataFrame]
    if SKU_MAP_XLSX.exists():
        sku_map_df = _read_excel(SKU_MAP_XLSX)
        _lower_columns_inplace(sku_map_df)
        # Ensure sku_id exists if typical constituents are present
        if "sku_id" not in sku_map_df.columns:
            if {"sku_key", "my_size"}.issubset(sku_map_df.columns):
                sku_map_df["sku_id"] = (
                    sku_map_df["sku_key"].astype(str).str.strip()
                    + "_"
                    + sku_map_df["my_size"].astype(str).str.strip()
                )
            elif {"sku_key", "size"}.issubset(sku_map_df.columns):
                sku_map_df["sku_id"] = (
                    sku_map_df["sku_key"].astype(str).str.strip()
                    + "_"
                    + sku_map_df["size"].astype(str).str.strip()
                )
            else:
                # Best-effort: cannot create sku_id; proceed without enrichment
                print(
                    "Note: `sku_map_crm_20250813_v1.xlsx` lacks 'sku_id' and 'sku_key'/'my_size' columns."
                )
    else:
        sku_map_df = None

    stock_df = pd.read_csv(STOCK_CSV)
    _lower_columns_inplace(stock_df)

    return sales_df, ksp_map_df, sku_map_df, stock_df


def compute_sku_id_inplace(sales_df: pd.DataFrame) -> None:
    if "sku_key" not in sales_df.columns:
        raise KeyError("Expected column 'sku_key' in sales file after normalization")
    # Ensure columns exist and clean NaN/None → ""
    if "my_size" not in sales_df.columns:
        sales_df["my_size"] = ""
    sales_df["_sku_id_issue"] = ""

    def clean_string(val: object) -> str:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return ""
        s = str(val).strip()
        if not s or s.lower() in {"nan", "none", "null", "-", "_"}:
            return ""
        return s

    sales_df["sku_key"] = sales_df["sku_key"].apply(clean_string)
    sales_df["my_size"] = sales_df["my_size"].apply(normalize_size)

    # Build sku_id only when sku_key is present; else mark issue
    def build_sku_id(row: pd.Series) -> str:
        key = row.get("sku_key", "")
        size = row.get("my_size", "")
        if not key:
            row["_sku_id_issue"] = "missing_sku_key"
            return ""
        return f"{key}_{size}" if size else f"{key}_"

    sales_df["sku_id"] = sales_df.apply(build_sku_id, axis=1)


def enrich_with_sku_map(sales_df: pd.DataFrame, sku_map_df: Optional[pd.DataFrame]) -> pd.DataFrame:
    if sku_map_df is None or "sku_id" not in sku_map_df.columns:
        print("Proceeding without SKU map enrichment (file missing or lacks 'sku_id').")
        return sales_df.copy()

    sku_map_ids = set(sku_map_df["sku_id"].astype(str))
    not_found_mask = ~sales_df["sku_id"].astype(str).isin(sku_map_ids)
    missing_ids = sorted(sales_df.loc[not_found_mask, "sku_id"].dropna().unique().tolist())
    if missing_ids:
        preview = ", ".join(missing_ids[:20])
        more = "" if len(missing_ids) <= 20 else f" ... (+{len(missing_ids) - 20} more)"
        print(f"Warning: {len(missing_ids)} sales SKU IDs not in SKU map: {preview}{more}")

    # Left-join to enrich; suffix mapped columns clearly
    enriched = sales_df.merge(sku_map_df, on="sku_id", how="left", suffixes=("", "_map"))
    return enriched


def write_missing_skus_report(
    sales_df: pd.DataFrame,
    sku_map_df: Optional[pd.DataFrame],
    qty_col: str,
    output_path: Path,
) -> pd.DataFrame:
    """
    Create a simple report of sales rows whose sku_id is not present in the CRM SKU map.
    The report includes sku_id with occurrence count and total quantity sold.
    """
    df = sales_df.copy()
    df["sku_id"] = df.get("sku_id", "").astype(str)
    df["sku_key"] = df.get("sku_key", "").astype(str)
    df["my_size"] = df.get("my_size", "").astype(str)
    df["ksp_sku_id"] = df.get("ksp_sku_id", "").astype(str)
    qty_series = pd.to_numeric(df.get(qty_col, 1), errors="coerce").fillna(1)
    df["_qty_num"] = qty_series

    # Determine membership in map
    in_map = pd.Series([False] * len(df))
    if sku_map_df is not None and "sku_id" in sku_map_df.columns:
        sku_ids_in_map = set(sku_map_df["sku_id"].astype(str))
        in_map = df["sku_id"].isin(sku_ids_in_map)

    # Reasons
    reasons = []
    for _, r in df.iterrows():
        sku_id = r["sku_id"].strip()
        if not sku_id:
            if str(r.get("_sku_id_issue", "")) == "missing_sku_key":
                reasons.append("missing_sku_key")
            else:
                reasons.append("blank_sku_id")
        elif not sku_id in sku_ids_in_map if (sku_map_df is not None and "sku_id" in sku_map_df.columns) else True:
            reasons.append("not_in_map")
        else:
            reasons.append("")
    df["reason"] = reasons

    missing_df = df[(df["reason"] != "")].copy()

    if missing_df.empty:
        report_df = pd.DataFrame(columns=[
            "sku_id", "ksp_sku_id", "occurrences", "total_qty",
            "example_sku_key", "example_my_size", "example_store_name",
            "has_ksp_id", "reason",
        ])
    else:
        report_df = (
            missing_df
            .groupby(["sku_id", "reason", "ksp_sku_id"], dropna=False)
            .agg(
                occurrences=("sku_id", "size"),
                total_qty=("_qty_num", "sum"),
                example_sku_key=("sku_key", "first"),
                example_my_size=("my_size", "first"),
                example_store_name=("store_name", "first"),
            )
            .reset_index()
            .assign(has_ksp_id=lambda d: d["ksp_sku_id"].astype(str).str.strip().ne(""))
            .sort_values(["total_qty", "occurrences"], ascending=[False, False])
        )

    # Save dated and latest
    today = pd.Timestamp.utcnow().strftime("%Y%m%d")
    dated_path = output_path.parent / f"missing_skus_{today}.csv"
    latest_path = output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_df.to_csv(dated_path, index=False)
    report_df.to_csv(latest_path, index=False)
    return report_df


def _first_number(text: str) -> float | None:
    if pd.isna(text):
        return None
    m = re.search(r"([0-9]+(?:[.,][0-9]+)?)", str(text))
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def _normalize_height_cm(val) -> float | None:
    n = _first_number(val)
    if n is None:
        return None
    # Treat 1.5–2.2 as meters; else assume centimeters
    if 1.5 <= n <= 2.2:
        return round(n * 100)
    return round(n)


def _normalize_weight_kg(val) -> float | None:
    n = _first_number(val)
    return float(n) if n is not None else None


def _choose_col(df: pd.DataFrame, candidates: list[str] | tuple[str, ...]):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def load_orders_with_sizes() -> pd.DataFrame | None:
    if ORDERS_CSV.exists():
        odf = pd.read_csv(ORDERS_CSV, encoding="utf-8-sig")
    elif ORDERS_XLSX.exists():
        odf = pd.read_excel(ORDERS_XLSX, engine="openpyxl")
    else:
        return None
    odf.columns = [str(c).strip().lower() for c in odf.columns]

    order_col = _choose_col(odf, ["orderid", "order_id", "id_order", "заказ", "номер заказа"])
    h_col = _choose_col(odf, ["рост", "рост, см", "рост (см)", "height", "customer_height"])
    w_col = _choose_col(odf, ["вес", "вес, кг", "вес (кг)", "weight", "customer_weight"])

    if not order_col:
        print("Warning: orders-with-sizes file lacks an order id column; skipping enrichment.")
        return None

    out = pd.DataFrame()
    out["orderid"] = odf[order_col].astype(str).str.strip()
    out["customer_height"] = odf[h_col].map(_normalize_height_cm) if h_col else pd.NA
    out["customer_weight"] = odf[w_col].map(_normalize_weight_kg) if w_col else pd.NA

    # Drop exact dupes by orderid keeping first
    out = out.drop_duplicates(subset=["orderid"])
    out.to_csv(ORDERS_NORMALIZED_CSV, index=False)
    print(f"Orders-with-sizes normalized: {ORDERS_NORMALIZED_CSV} ({len(out)} rows)")
    return out


def choose_qty_column(df: pd.DataFrame) -> str:
    candidates = [
        "qty",
        "quantity",
        "qty_sold",
        "count",
        "amount",
        "pieces",
    ]
    chosen = _choose_first_existing(df, candidates)
    if chosen is None:
        print("Note: No quantity column found in sales. Assuming qty = 1 per row.")
        df["qty"] = 1
        return "qty"
    return chosen


def choose_stock_qty_column(df: pd.DataFrame) -> str:
    candidates = [
        "qty",
        "quantity",
        "stock",
        "on_hand",
        "stock_on_hand",
        "available",
        "qty_available",
    ]
    chosen = _choose_first_existing(df, candidates)
    if chosen is None:
        # Create when absent
        df["qty"] = 0
        return "qty"
    return chosen


def update_stock(stock_df: pd.DataFrame, sales_df: pd.DataFrame, qty_col: str) -> pd.DataFrame:
    if "sku_key" not in stock_df.columns:
        raise KeyError("Expected column 'sku_key' in stock file")

    stock_qty_col = choose_stock_qty_column(stock_df)

    # Sum sold qty per sku_key
    sales_df = sales_df.copy()
    sales_df["sku_key"] = sales_df["sku_key"].astype(str).str.strip()
    sold_by_key = sales_df.groupby("sku_key", dropna=False)[qty_col].sum().reset_index()
    sold_by_key.rename(columns={qty_col: "sold_qty"}, inplace=True)

    merged = stock_df.merge(sold_by_key, on="sku_key", how="left")
    merged["sold_qty"] = merged["sold_qty"].fillna(0)
    merged[stock_qty_col] = pd.to_numeric(merged[stock_qty_col], errors="coerce").fillna(0)
    updated_raw = merged[stock_qty_col] - merged["sold_qty"]
    merged["oversell"] = (-updated_raw).clip(lower=0)
    merged["updated_qty"] = updated_raw.clip(lower=0)

    # Prefer to keep schema stable: write updated_qty and also overwrite the original qty column
    merged[stock_qty_col] = merged["updated_qty"]
    merged.drop(columns=["updated_qty"], inplace=True)

    # Oversell report
    total_oversell = int(merged["oversell"].sum())
    if total_oversell > 0:
        reports_dir = DATA_CRM_DIR / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        oversell_path = reports_dir / f"oversell_{RUN_DATE}.csv"
        oversell_df = merged.loc[merged["oversell"] > 0, ["sku_key", stock_qty_col, "sold_qty", "oversell"]].copy()
        oversell_df.rename(columns={stock_qty_col: "before_qty"}, inplace=True)
        oversell_df.to_csv(oversell_path, index=False)
        print(f"Oversell detected: total {total_oversell}. Details: {oversell_path}")

    return merged


def make_normalized_sales_log(df: pd.DataFrame, qty_col: str) -> pd.DataFrame:
    # Candidate source columns
    orderid_col = _choose_first_existing(df, ["orderid", "order_id", "id_order", "order no", "order_no", "order number"])
    date_col = _choose_first_existing(df, ["date", "order_date", "created_at", "order_datetime", "order_date_time"]) 
    price_col = _choose_first_existing(df, ["sell_price", "price", "unit_price", "price_total", "amount"])
    phone_col = _choose_first_existing(df, ["phone", "customer_phone", "phone_number"]) 
    height_col = _choose_first_existing(df, ["customer_height", "height"]) 
    weight_col = _choose_first_existing(df, ["customer_weight", "weight"]) 

    out = pd.DataFrame()
    out["orderid"] = df[orderid_col] if orderid_col else pd.NA
    out["date"] = df[date_col] if date_col else pd.NA
    out["sku_id"] = df.get("sku_id", pd.NA)
    out["store_name"] = df.get("store_name", pd.NA)
    out["qty"] = pd.to_numeric(df[qty_col], errors="coerce").fillna(0).astype(int)
    out["sell_price"] = pd.to_numeric(df[price_col], errors="coerce") if price_col else pd.NA
    # Prefer merged customer_height/customer_weight if present
    out["customer_height"] = df.get("customer_height", pd.NA)
    out["customer_weight"] = df.get("customer_weight", pd.NA)

    # Add a few helpful context fields
    out["ksp_sku_id"] = df.get("ksp_sku_id", pd.NA)
    out["sku_key"] = df.get("sku_key", pd.NA)
    out["my_size"] = df.get("my_size", pd.NA)

    # Normalized phone
    if phone_col:
        out["normalized_phone"] = df[phone_col].apply(parse_kz_phone)
        # Warn on invalid phones
        invalid_count = int((out["normalized_phone"] == "").sum())
        if invalid_count > 0:
            print(f"Warning: {invalid_count} rows have invalid/unparseable phone numbers")
    else:
        out["normalized_phone"] = ""

    return out


def main() -> int:
    # Ensure output directory exists
    DATA_CRM_DIR.mkdir(parents=True, exist_ok=True)

    sales_df, ksp_map_df, maybe_sku_map_df, stock_df = load_inputs()
    orders_sizes_df = load_orders_with_sizes()

    # ensure 'orderid' exists in sales_df for merge
    if "orderid" not in sales_df.columns:
        oc = _choose_first_existing(sales_df, ["orderid", "order_id", "id_order", "order no", "order_no"])
        if oc and oc != "orderid":
            sales_df["orderid"] = sales_df[oc].astype(str).str.strip()

    # merge height/weight
    if orders_sizes_df is not None and "orderid" in sales_df.columns:
        sales_df = sales_df.merge(orders_sizes_df, on="orderid", how="left")

    compute_sku_id_inplace(sales_df)

    qty_col = choose_qty_column(sales_df)

    # Dedupe before enrichment
    reports_dir = DATA_CRM_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    duplicates_path = reports_dir / f"duplicates_{RUN_DATE}.csv"
    before_count = len(sales_df)
    # Natural key: (orderid, sku_id) if available; else fallback composite
    if "orderid" in sales_df.columns and "sku_id" in sales_df.columns:
        key_cols = ["orderid", "sku_id"]
    else:
        key_cols = [c for c in ["ksp_sku_id", "store_name", "sku_id", "date"] if c in sales_df.columns]
    if key_cols:
        # Identify perfect duplicates
        sales_df["_dup_key"] = sales_df[key_cols].astype(str).agg("|".join, axis=1)
        dup_counts = sales_df.groupby("_dup_key").size().reset_index(name="count")
        dup_keys = set(dup_counts.loc[dup_counts["count"] > 1, "_dup_key"].astype(str))
        removed_rows = sales_df[sales_df["_dup_key"].isin(dup_keys)].copy()
        if not removed_rows.empty:
            removed_rows.to_csv(duplicates_path, index=False)
        # Keep first occurrence and sum qty for exact dupes
        if "qty" in sales_df.columns:
            aggregated = sales_df.groupby(list(set(key_cols + ["sku_key", "my_size", "store_name"])) , dropna=False, as_index=False).agg({
                "qty": "sum"
            })
            # Merge back non-qty columns from first occurrence
            firsts = sales_df.sort_index().drop_duplicates(subset=key_cols, keep="first")
            sales_df = firsts.drop(columns=["qty"], errors="ignore").merge(aggregated, on=list(set(key_cols + ["sku_key", "my_size", "store_name"])), how="left")
        else:
            sales_df = sales_df.drop_duplicates(subset=key_cols, keep="first")
        sales_df.drop(columns=["_dup_key"], inplace=True, errors="ignore")
    after_count = len(sales_df)
    if after_count < before_count:
        print(f"Deduped sales: removed {before_count - after_count} rows → {duplicates_path}")

    enriched_df = enrich_with_sku_map(sales_df, maybe_sku_map_df)

    # Update stock and write (dated + latest)
    updated_stock_df = update_stock(stock_df, sales_df, qty_col)
    STOCK_DIR.mkdir(parents=True, exist_ok=True)
    updated_stock_df.to_csv(STOCK_UPDATED_DATED, index=False)
    updated_stock_df.to_csv(STOCK_UPDATED_CSV, index=False)
    print(f"Updated stock written: {STOCK_UPDATED_CSV} and {STOCK_UPDATED_DATED}")

    # Build normalized sales log and write (dated + latest)
    normalized_sales = make_normalized_sales_log(enriched_df, qty_col)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    normalized_sales.to_csv(PROCESSED_SALES_DATED, index=False)
    normalized_sales.to_csv(PROCESSED_SALES_CSV, index=False)
    print(f"Processed sales log written: {PROCESSED_SALES_CSV} and {PROCESSED_SALES_DATED}")

    # Missing SKU report
    missing_report_df = write_missing_skus_report(sales_df, maybe_sku_map_df, qty_col, MISSING_SKUS_CSV)
    print(
        f"Missing SKU report written: {MISSING_SKUS_CSV} (unique missing sku_id: {len(missing_report_df)})"
    )

    # Coverage report
    coverage = {
        "total_sales_rows": int(len(sales_df)),
        "rows_with_valid_sku_id": int(sales_df["sku_id"].astype(str).str.len().gt(1).sum()),
        "rows_missing_sku_id": int(sales_df["sku_id"].astype(str).str.len().le(1).sum()),
        "unique_sku_id_in_sales": int(sales_df["sku_id"].nunique(dropna=True)),
        "unique_sku_id_in_map": int((maybe_sku_map_df["sku_id"].nunique(dropna=True)) if (maybe_sku_map_df is not None and "sku_id" in maybe_sku_map_df.columns) else 0),
        "timestamp": pd.Timestamp.utcnow().isoformat(),
    }
    reports_dir = DATA_CRM_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    coverage_path = reports_dir / "mapping_coverage.csv"
    pd.DataFrame([coverage]).to_csv(coverage_path, index=False)
    print(f"Coverage report written: {coverage_path}")

    # Print summary
    total_rows = len(sales_df)
    sold_per_sku = (
        normalized_sales.groupby("sku_id", dropna=False)["qty"].sum().reset_index().sort_values("qty", ascending=False)
    )
    print(f"Sales processed: {total_rows}")
    print("Total quantity sold per sku_id:")
    # Print top 25 to keep output readable
    for _, row in sold_per_sku.head(25).iterrows():
        print(f"  {row['sku_id']}: {int(row['qty'])}")
    if len(sold_per_sku) > 25:
        print(f"  ... and {len(sold_per_sku) - 25} more")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # surface clear message
        print(f"Error: {exc}")
        raise SystemExit(1)


