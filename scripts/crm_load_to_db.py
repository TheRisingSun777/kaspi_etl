"""
Load processed CRM sales into SQLite and create helpful views.

Actions:
- Connect to db/erp.db (create directories if needed).
- Load data_crm/processed_sales_20250813.csv into table `sales` (replace).
- Ensure column types as specified; create indexes on orderid, sku_id, store_name.
- Create views: v_sales_by_sku, v_sales_by_model_size, v_sales_by_store_day.

Run:
  ./venv/bin/python scripts/crm_load_to_db.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Tuple

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "db" / "erp.db"
CSV_PATH = REPO_ROOT / "data_crm" / "processed_sales_20250813.csv"


SALES_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sales (
  orderid TEXT,
  date TEXT,
  sku_id TEXT,
  store_name TEXT,
  qty INTEGER,
  sell_price REAL,
  customer_height REAL,
  customer_weight REAL,
  ksp_sku_id TEXT,
  sku_key TEXT,
  my_size TEXT
);
"""

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_sales_orderid ON sales(orderid)",
    "CREATE INDEX IF NOT EXISTS idx_sales_sku_id ON sales(sku_id)",
    "CREATE INDEX IF NOT EXISTS idx_sales_store ON sales(store_name)",
]

VIEWS_SQL = [
    # Drop first to allow changes
    "DROP VIEW IF EXISTS v_sales_by_sku",
    "CREATE VIEW v_sales_by_sku AS\n"
    "  SELECT sku_id, SUM(qty) AS total_qty,\n"
    "         SUM(COALESCE(sell_price, 0) * qty) AS revenue\n"
    "  FROM sales\n"
    "  GROUP BY sku_id",
    "DROP VIEW IF EXISTS v_sales_by_model_size",
    "CREATE VIEW v_sales_by_model_size AS\n"
    "  SELECT sku_key, my_size, SUM(qty) AS total_qty\n"
    "  FROM sales\n"
    "  GROUP BY sku_key, my_size",
    "DROP VIEW IF EXISTS v_sales_by_store_day",
    "CREATE VIEW v_sales_by_store_day AS\n"
    "  SELECT store_name, date, SUM(qty) AS total_qty,\n"
    "         SUM(COALESCE(sell_price, 0) * qty) AS revenue\n"
    "  FROM sales\n"
    "  GROUP BY store_name, date",
]


def ensure_db_dir() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_csv() -> pd.DataFrame:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Missing processed sales CSV: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip().lower() for c in df.columns]

    # Ensure all required columns exist
    required_cols = [
        "orderid",
        "date",
        "sku_id",
        "store_name",
        "qty",
        "sell_price",
        "customer_height",
        "customer_weight",
        "ksp_sku_id",
        "sku_key",
        "my_size",
    ]
    for col in required_cols:
        if col not in df.columns:
            df[col] = pd.NA

    # Cast types
    df["orderid"] = df["orderid"].astype(str)
    df["date"] = df["date"].astype(str)
    df["sku_id"] = df["sku_id"].astype(str)
    df["store_name"] = df["store_name"].astype(str)
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0).astype(int)
    for col in ["sell_price", "customer_height", "customer_weight"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["ksp_sku_id"] = df["ksp_sku_id"].astype(str)
    df["sku_key"] = df["sku_key"].astype(str)
    df["my_size"] = df["my_size"].astype(str)

    # Reorder
    df = df[
        [
            "orderid",
            "date",
            "sku_id",
            "store_name",
            "qty",
            "sell_price",
            "customer_height",
            "customer_weight",
            "ksp_sku_id",
            "sku_key",
            "my_size",
        ]
    ]
    return df


def write_sales_table(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS sales")
    cur.execute(SALES_SCHEMA_SQL)

    rows: List[Tuple] = list(df.itertuples(index=False, name=None))
    cur.executemany(
        "INSERT INTO sales (orderid, date, sku_id, store_name, qty, sell_price, customer_height, customer_weight, ksp_sku_id, sku_key, my_size)\n"
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    for sql in INDEX_SQL:
        cur.execute(sql)
    for sql in VIEWS_SQL:
        cur.execute(sql)
    conn.commit()
    return len(rows)


def main() -> int:
    ensure_db_dir()
    df = load_csv()
    with sqlite3.connect(DB_PATH) as conn:
        inserted = write_sales_table(conn, df)
    print(f"Inserted rows: {inserted} into {DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


