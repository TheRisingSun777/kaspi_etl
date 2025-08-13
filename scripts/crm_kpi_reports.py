#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from scripts.crm_config import REPO_ROOT, get_run_date, load_crm_config

CFG = load_crm_config()
RUN_DATE = get_run_date(pd.Timestamp.utcnow().strftime("%Y%m%d"))

DATA_CRM = REPO_ROOT / "data_crm"
PROCESSED_LATEST = DATA_CRM / "processed_sales_latest.csv"
REPORTS_DIR = DATA_CRM / "reports"


def _lower(df: pd.DataFrame) -> None:
    df.columns = [str(c).strip().lower() for c in df.columns]


def _load_adjustments(run_date: str) -> pd.DataFrame:
    paths = [
        (DATA_CRM / f"returns_{run_date}.csv", "return"),
        (DATA_CRM / f"cancellations_{run_date}.csv", "cancellation"),
    ]
    frames = []
    for p, kind in paths:
        if p.exists():
            df = pd.read_csv(p)
            _lower(df)
            df["type"] = kind
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["orderid", "sku_id", "qty", "amount", "type"])  # type: ignore


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

    # Apply returns/cancellations adjustments if present
    adj = _load_adjustments(RUN_DATE)
    if not adj.empty:
        adj_group = adj.groupby(["orderid", "sku_id", "type"], dropna=False).agg(
            adj_qty=("qty", lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()),
            adj_amount=("amount", lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()),
        ).reset_index()

        # Prepare reconciliation rows
        recon = []
        for _, r in adj_group.iterrows():
            recon.append({
                "orderid": r["orderid"],
                "sku_id": r["sku_id"],
                "type": r["type"],
                "qty_subtracted": r["adj_qty"],
                "amount_subtracted": r["adj_amount"],
            })
        recon_df = pd.DataFrame(recon, columns=["orderid", "sku_id", "type", "qty_subtracted", "amount_subtracted"])  # type: ignore
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        recon_path = REPORTS_DIR / f"reconciliation_{RUN_DATE}.csv"
        recon_df.to_csv(recon_path, index=False)

        # Merge totals by orderid+sku_id regardless of type
        adj_tot = adj_group.groupby(["orderid", "sku_id"], dropna=False).agg(
            adj_qty=("adj_qty", "sum"),
            adj_amount=("adj_amount", "sum"),
        ).reset_index()
        sales = sales.merge(adj_tot, on=["orderid", "sku_id"], how="left")
        sales["adj_qty"] = pd.to_numeric(sales.get("adj_qty", 0), errors="coerce").fillna(0)
        sales["adj_amount"] = pd.to_numeric(sales.get("adj_amount", 0), errors="coerce").fillna(0)
        # Subtract; if adj_amount is zero, fallback to qty * sell_price
        sales["qty"] = sales["qty"] - sales["adj_qty"]
        fallback_amt = (sales["adj_qty"] * sales["sell_price"]).fillna(0)
        sales["amount"] = sales["amount"] - sales["adj_amount"].where(sales["adj_amount"] != 0, fallback_amt)

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


