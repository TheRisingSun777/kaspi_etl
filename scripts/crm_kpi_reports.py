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
REPORTS_DIR = DATA_CRM / "reports"


def _lower(df: pd.DataFrame) -> None:
    df.columns = [str(c).strip().lower() for c in df.columns]


def write_report(df: pd.DataFrame, name: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{name}_{RUN_DATE}.csv"
    df.to_csv(path, index=False)
    return path


def main() -> int:
    sales = pd.read_csv(PROCESSED_LATEST)
    _lower(sales)
    sales["qty"] = pd.to_numeric(sales.get("qty", 0), errors="coerce").fillna(0)
    sales["sell_price"] = pd.to_numeric(sales.get("sell_price", 0), errors="coerce").fillna(0)
    sales["amount"] = sales["qty"] * sales["sell_price"]

    by_sku = sales.groupby("sku_id", dropna=False).agg(qty=("qty", "sum"), revenue=("amount", "sum")).reset_index()
    p1 = write_report(by_sku, "sales_by_sku")
    print("Top SKUs:")
    print(by_sku.sort_values(["qty", "revenue"], ascending=[False, False]).head(10))

    by_store = sales.groupby("store_name", dropna=False).agg(qty=("qty", "sum"), revenue=("amount", "sum")).reset_index()
    p2 = write_report(by_store, "sales_by_store")
    print("Top stores:")
    print(by_store.sort_values(["qty", "revenue"], ascending=[False, False]).head(10))

    by_size = sales.groupby("my_size", dropna=False).agg(qty=("qty", "sum"), revenue=("amount", "sum")).reset_index()
    p3 = write_report(by_size, "sales_by_size")
    print("Top sizes:")
    print(by_size.sort_values(["qty", "revenue"], ascending=[False, False]).head(10))

    sales["date"] = pd.to_datetime(sales.get("date", pd.NaT), errors="coerce")
    daily = sales.dropna(subset=["date"]).groupby(sales["date"].dt.date).agg(qty=("qty", "sum"), revenue=("amount", "sum")).reset_index()
    p4 = write_report(daily, "daily_sales")
    print("Daily totals:")
    print(daily.tail(10))

    print("Reports written:", p1, p2, p3, p4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


