#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import pandas as pd

import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))
from scripts.crm_config import REPO_ROOT, get_run_date


RUN_DATE = get_run_date(pd.Timestamp.utcnow().strftime("%Y%m%d"))
DATA_CRM = REPO_ROOT / "data_crm"
PROCESSED_LATEST = DATA_CRM / "processed_sales_latest.csv"
STOCK_UPDATED = DATA_CRM / "stock_on_hand_updated.csv"
REPORTS_DIR = DATA_CRM / "reports"


def main() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    sales = pd.read_csv(PROCESSED_LATEST)
    sales.columns = [c.strip().lower() for c in sales.columns]
    sales["qty"] = pd.to_numeric(sales.get("qty", 0), errors="coerce").fillna(0)
    sales["date"] = pd.to_datetime(sales.get("date"), errors="coerce")

    # Rolling 14-day demand per sku_key
    def rolling_14d(group: pd.DataFrame) -> float:
        g = group.sort_values("date").set_index("date")
        if g.empty:
            return 0.0
        return float(g["qty"].rolling("14D").sum().iloc[-1])

    demand = (
        sales.dropna(subset=["date"])  # ensure we have dates
        .groupby(["sku_key"], dropna=False)
        .apply(rolling_14d)
        .reset_index(name="rolling_14d_qty")
    )

    stock = pd.read_csv(STOCK_UPDATED)
    stock.columns = [c.strip().lower() for c in stock.columns]
    stock_qty_col = "qty" if "qty" in stock.columns else stock.columns[1]
    stock[stock_qty_col] = pd.to_numeric(stock[stock_qty_col], errors="coerce").fillna(0)

    lead_time_days = 10
    threshold = 5
    df = stock.merge(demand, on="sku_key", how="left")
    df["rolling_14d_qty"] = pd.to_numeric(df["rolling_14d_qty"], errors="coerce").fillna(0)
    df["reorder_point"] = (df["rolling_14d_qty"] / 14.0 * lead_time_days).round()
    df["reorder_point"] = df["reorder_point"].clip(lower=threshold)
    df["should_reorder"] = df[stock_qty_col] < df["reorder_point"]
    out = df[df["should_reorder"]].copy()
    out_path = REPORTS_DIR / f"reorder_suggestions_{RUN_DATE}.csv"
    out.to_csv(out_path, index=False)
    print("Reorder suggestions:", len(out), out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


