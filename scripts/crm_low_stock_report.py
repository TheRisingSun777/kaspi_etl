"""
Low-stock velocity report (Phase 1).

Inputs:
- db/erp.db (table `sales` with columns incl. date, sku_id, sku_key, qty, sell_price)
- data_crm/stock_on_hand_updated.csv (must include sku_key and a stock quantity column)

Logic:
- Compute last 14-day sales velocity.
- Prefer per-sku_id rows; if no sku_id has velocity for a given sku_key, emit a sku_key-level row.
- safety_factor = 1.5
- reorder_qty = max(0, velocity_14d * safety_factor - current_stock)
- days_cover = current_stock / (velocity_14d / 14) if velocity_14d > 0 else ''

Output:
- data_crm/reports/low_stock_{YYYYMMDD}.csv with columns:
  sku_id_or_key, stock_now, velocity_14d, days_cover, reorder_qty

Run:
  ./venv/bin/python scripts/crm_low_stock_report.py
"""

from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "db" / "erp.db"
SALES_SQL = "SELECT date, sku_id, sku_key, qty FROM sales"
STOCK_CSV = REPO_ROOT / "data_crm" / "stock_on_hand_updated.csv"
REPORTS_DIR = REPO_ROOT / "data_crm" / "reports"
SAFETY_FACTOR = 1.5


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
    for name in candidates:
        if name in df.columns:
            return name
    df["qty"] = 0
    return "qty"


def load_sales() -> pd.DataFrame:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Missing DB: {DB_PATH}")
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(SALES_SQL, conn)
    df.columns = [c.strip().lower() for c in df.columns]
    df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce")
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0).astype(int)
    return df


def load_stock() -> pd.DataFrame:
    if not STOCK_CSV.exists():
        raise FileNotFoundError(f"Missing stock file: {STOCK_CSV}")
    df = pd.read_csv(STOCK_CSV)
    df.columns = [c.strip().lower() for c in df.columns]
    if "sku_key" not in df.columns:
        raise KeyError("Expected 'sku_key' in stock CSV")
    qty_col = choose_stock_qty_column(df)
    df[qty_col] = pd.to_numeric(df[qty_col], errors="coerce").fillna(0)
    return df[["sku_key", qty_col]].rename(columns={qty_col: "stock_now"})


def compute_window(df_sales: pd.DataFrame, days: int = 14) -> pd.DataFrame:
    valid = df_sales.dropna(subset=["date_parsed"]).copy()
    if valid.empty:
        return df_sales.iloc[0:0].copy()
    end = valid["date_parsed"].max()
    start = end - timedelta(days=days - 1)
    window = valid[(valid["date_parsed"] >= start) & (valid["date_parsed"] <= end)].copy()
    return window


def main() -> int:
    sales = load_sales()
    stock = load_stock()

    window = compute_window(sales, days=14)

    # Map sku_id -> sku_key using all-time sales (more robust)
    id_to_key = (
        sales.dropna(subset=["sku_id", "sku_key"]) 
        .drop_duplicates(subset=["sku_id"]) 
        .set_index("sku_id")["sku_key"].to_dict()
    )

    # Velocities
    vel_by_id = window.groupby("sku_id", dropna=False)["qty"].sum().reset_index()
    vel_by_key = window.groupby("sku_key", dropna=False)["qty"].sum().reset_index()

    # Prepare output rows
    rows: list[dict] = []

    # First: per-sku_id entries with velocity > 0
    for _, r in vel_by_id.iterrows():
        sku_id = str(r["sku_id"]) if pd.notna(r["sku_id"]) else ""
        velocity_14d = int(r["qty"]) if pd.notna(r["qty"]) else 0
        if velocity_14d <= 0:
            continue
        sku_key = id_to_key.get(sku_id, None)
        stock_now = 0
        if sku_key is not None:
            srow = stock[stock["sku_key"].astype(str) == str(sku_key)]
            if not srow.empty:
                stock_now = float(srow.iloc[0]["stock_now"])  # may not be int in CSV
        avg_daily = velocity_14d / 14.0
        days_cover = (stock_now / avg_daily) if avg_daily > 0 else ""
        reorder = max(0.0, velocity_14d * SAFETY_FACTOR - stock_now)
        rows.append(
            {
                "sku_id/sku_key": sku_id,
                "stock_now": int(round(stock_now)),
                "velocity_14d": int(velocity_14d),
                "days_cover": round(days_cover, 1) if isinstance(days_cover, float) else "",
                "reorder_qty": int(math.ceil(reorder)),
            }
        )

    # Second: sku_key-level for keys that have velocity but no sku_id row above
    produced_ids = {row["sku_id/sku_key"] for row in rows}
    for _, r in vel_by_key.iterrows():
        sku_key = str(r["sku_key"]) if pd.notna(r["sku_key"]) else ""
        # skip if any sku_id already reported for this key
        if any((id_to_key.get(sid) == sku_key) for sid in produced_ids if sid in id_to_key):
            continue
        velocity_14d = int(r["qty"]) if pd.notna(r["qty"]) else 0
        if velocity_14d <= 0:
            continue
        srow = stock[stock["sku_key"].astype(str) == sku_key]
        stock_now = float(srow.iloc[0]["stock_now"]) if not srow.empty else 0.0
        avg_daily = velocity_14d / 14.0
        days_cover = (stock_now / avg_daily) if avg_daily > 0 else ""
        reorder = max(0.0, velocity_14d * SAFETY_FACTOR - stock_now)
        rows.append(
            {
                "sku_id/sku_key": sku_key,
                "stock_now": int(round(stock_now)),
                "velocity_14d": int(velocity_14d),
                "days_cover": round(days_cover, 1) if isinstance(days_cover, float) else "",
                "reorder_qty": int(math.ceil(reorder)),
            }
        )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"low_stock_{datetime.now().strftime('%Y%m%d')}.csv"

    columns = ["sku_id/sku_key", "stock_now", "velocity_14d", "days_cover", "reorder_qty"]
    if not rows:
        pd.DataFrame(columns=columns).to_csv(out_path, index=False)
    else:
        df_out = pd.DataFrame(rows)[columns]
        df_out.sort_values(["reorder_qty", "velocity_14d"], ascending=[False, False]).to_csv(out_path, index=False)
    print(f"Low-stock report written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


