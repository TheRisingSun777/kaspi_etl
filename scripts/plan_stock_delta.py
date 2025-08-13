"""
Plan stock decrements for CONFIRMED orders not yet decremented.

Outputs:
- data_crm/reports/stock_delta_plan.csv (sku_id, qty_decrement)
- data_crm/reports/kaspi_stock_update_payload.json ({ data: [ {type:'stocks', id: sku_id, attributes:{available: new_qty}} ] })

Assumptions:
- Uses sales table for sku_id mapping per order
- A simple ledger table stock_deltas(order_id TEXT PK) marks applied decrements; create if missing
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "db" / "erp.db"
REPORTS_DIR = REPO_ROOT / "data_crm" / "reports"
PROCESSED_CSV = REPO_ROOT / "data_crm" / "processed_sales_20250813.csv"


def ensure_tables(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS stock_deltas (
          order_id TEXT PRIMARY KEY,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()


def load_confirmed_order_ids(conn: sqlite3.Connection) -> list[str]:
    cur = conn.cursor()
    cur.execute("SELECT order_id FROM workflows WHERE state='CONFIRMED'")
    return [r[0] for r in cur.fetchall()]


def load_sales() -> pd.DataFrame:
    df = pd.read_csv(PROCESSED_CSV)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def main() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        ensure_tables(conn)
        confirmed = set(load_confirmed_order_ids(conn))

    sales = load_sales()
    if "orderid" not in sales.columns:
        print("processed sales missing orderid column")
        return 0

    # Filter only confirmed orders not yet applied in ledger
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT order_id FROM stock_deltas")
        already = {r[0] for r in cur.fetchall()}

    need = sales[sales["orderid"].isin(list(confirmed - already))].copy()
    need = need.dropna(subset=["sku_id"])  # ensure sku present
    need["qty"] = pd.to_numeric(need["qty"], errors="coerce").fillna(0).astype(int)
    plan = need.groupby("sku_id")["qty"].sum().reset_index().rename(columns={"qty": "qty_decrement"})

    csv_path = REPORTS_DIR / "stock_delta_plan.csv"
    plan.to_csv(csv_path, index=False)

    payload = {
        "data": [
            {"type": "stocks", "id": str(row["sku_id"]), "attributes": {"available": None, "decrement": int(row["qty_decrement"])}}
            for _, row in plan.iterrows()
        ]
    }
    json_path = REPORTS_DIR / "kaspi_stock_update_payload.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Plan CSV: {csv_path}")
    print(f"Kaspi payload JSON: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


