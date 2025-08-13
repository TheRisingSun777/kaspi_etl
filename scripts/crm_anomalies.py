#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from scripts.crm_config import REPO_ROOT, get_run_date

RUN_DATE = get_run_date(pd.Timestamp.utcnow().strftime("%Y%m%d"))
DATA_CRM = REPO_ROOT / "data_crm"
PROCESSED_DIR = DATA_CRM / "processed"
PROCESSED_LATEST = DATA_CRM / "processed_sales_latest.csv"
REPORTS_DIR = DATA_CRM / "reports"


def main() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    anomalies = []

    # Load sales latest and previous day if exists
    latest = pd.read_csv(PROCESSED_LATEST)
    latest.columns = [c.strip().lower() for c in latest.columns]
    latest["qty"] = pd.to_numeric(latest.get("qty", 0), errors="coerce").fillna(0)
    prev_path = PROCESSED_DIR / f"processed_sales_{RUN_DATE}.csv"
    if prev_path.exists():
        prev = pd.read_csv(prev_path)
        prev.columns = [c.strip().lower() for c in prev.columns]
        prev["qty"] = pd.to_numeric(prev.get("qty", 0), errors="coerce").fillna(0)
    else:
        prev = pd.DataFrame(columns=latest.columns)

    # Zero sales for top SKUs
    top = latest.groupby("sku_id", dropna=False)["qty"].sum().sort_values(ascending=False).head(20)
    zero_today = top[top == 0]
    for sku_id in zero_today.index:
        anomalies.append({"type": "zero_sales_top_sku", "sku_id": sku_id, "detail": "today qty=0"})

    # Oversell exists?
    stock_updated = DATA_CRM / "stock_on_hand_updated.csv"
    if stock_updated.exists():
        stock = pd.read_csv(stock_updated)
        stock.columns = [c.strip().lower() for c in stock.columns]
        if "oversell" in stock.columns and (pd.to_numeric(stock["oversell"], errors="coerce").fillna(0) > 0).any():
            total = int(pd.to_numeric(stock["oversell"], errors="coerce").fillna(0).sum())
            anomalies.append({"type": "oversell", "total": total})

    # Write
    out = pd.DataFrame(anomalies)
    out_path = REPORTS_DIR / f"anomalies_{RUN_DATE}.csv"
    out.to_csv(out_path, index=False)
    print("Anomalies:", len(out), out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


