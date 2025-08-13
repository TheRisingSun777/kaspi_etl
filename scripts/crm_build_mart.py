#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import pandas as pd

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from scripts.crm_config import load_crm_config, get_run_date, REPO_ROOT


CFG = load_crm_config()
RUN_DATE = get_run_date(pd.Timestamp.utcnow().strftime("%Y%m%d"))

DATA_CRM = REPO_ROOT / "data_crm"
PROCESSED_LATEST = DATA_CRM / "processed_sales_latest.csv"
CRM_MAP_XLSX = DATA_CRM / "sku_map_crm_20250813_v1.xlsx"
MART_DIR = DATA_CRM / "mart"


def _lower(df: pd.DataFrame) -> None:
    df.columns = [str(c).strip().lower() for c in df.columns]


def build_dims_and_fact() -> None:
    MART_DIR.mkdir(parents=True, exist_ok=True)

    sales = pd.read_csv(PROCESSED_LATEST)
    _lower(sales)

    # dim_store
    dim_store = pd.DataFrame({"store_name": sorted(sales.get("store_name", pd.Series(dtype=str)).dropna().unique())})
    dim_store.to_csv(MART_DIR / "dim_store.csv", index=False)

    # dim_date (based on sales dates)
    dates = pd.to_datetime(sales.get("date", pd.Series(dtype=str)), errors="coerce").dropna().dt.date.unique()
    if len(dates) == 0:
        date_df = pd.DataFrame({"date": []})
    else:
        date_range = pd.date_range(min(dates), max(dates), freq="D").date
        date_df = pd.DataFrame({"date": date_range})
        date_df["year"] = pd.to_datetime(date_df["date"]).dt.year
        date_df["month"] = pd.to_datetime(date_df["date"]).dt.month
        date_df["day"] = pd.to_datetime(date_df["date"]).dt.day
        date_df["ymd"] = pd.to_datetime(date_df["date"]).dt.strftime("%Y-%m-%d")
    date_df.to_csv(MART_DIR / "dim_date.csv", index=False)

    # dim_product from CRM map if present, else from sales
    if CRM_MAP_XLSX.exists():
        prod = pd.read_excel(CRM_MAP_XLSX, engine="openpyxl")
        _lower(prod)
        if "sku_id" not in prod.columns and {"sku_key", "my_size"}.issubset(prod.columns):
            prod["sku_id"] = prod["sku_key"].astype(str) + "_" + prod["my_size"].astype(str)
        dim_product = prod.drop_duplicates(subset=["sku_id"]).copy()
    else:
        dim_product = sales[["sku_id", "sku_key", "my_size"]].drop_duplicates()
    dim_product.to_csv(MART_DIR / "dim_product.csv", index=False)

    # fact_sales
    fact = sales.copy()
    for c in ["qty", "sell_price"]:
        if c in fact.columns:
            fact[c] = pd.to_numeric(fact[c], errors="coerce").fillna(0)
    fact["amount"] = fact.get("qty", 0) * fact.get("sell_price", 0)
    fact.to_csv(MART_DIR / f"fact_sales_{RUN_DATE}.csv", index=False)

    # PK checks (basic non-null checks)
    assert dim_store["store_name"].isna().sum() == 0
    if "sku_id" in dim_product.columns:
        assert dim_product["sku_id"].isna().sum() == 0


def main() -> int:
    build_dims_and_fact()
    print("Data mart written to:", DATA_CRM / "mart")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


