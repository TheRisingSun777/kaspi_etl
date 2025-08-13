#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import pandas as pd

from scripts.crm_config import REPO_ROOT, get_run_date


RUN_DATE = get_run_date(pd.Timestamp.utcnow().strftime("%Y%m%d"))
DATA_CRM = REPO_ROOT / "data_crm"
PROCESSED_LATEST = DATA_CRM / "processed_sales_latest.csv"
EXPORTS_DIR = DATA_CRM / "exports"


def main() -> int:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    sales = pd.read_csv(PROCESSED_LATEST)
    sales.columns = [c.strip().lower() for c in sales.columns]
    out_cols = [
        "orderid", "date", "store_name", "sku_key", "my_size", "sku_id", "qty", "sell_price",
    ]
    out = sales.reindex(columns=out_cols)
    dated = EXPORTS_DIR / f"sales_for_dashboard_{RUN_DATE}.csv"
    latest = EXPORTS_DIR / "sales_for_dashboard.csv"
    out.to_csv(dated, index=False)
    out.to_csv(latest, index=False)
    print("Dashboard export written:", dated, latest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


