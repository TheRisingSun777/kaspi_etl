"""
Sync Kaspi orders from API into SQLite (dry-friendly; upserts raw + parsed).

Args:
  --from YYYY-MM-DD --to YYYY-MM-DD --state NEW,ACCEPTED,...

Writes:
  - data_crm/api_cache/orders_{from}_{to}_{state}.json
  - Upsert into tables:
      kaspi_orders_raw(order_id TEXT PK, json TEXT, fetched_at)
      orders(order_id, order_date, status, store_name, sku_name_raw, qty, gross_price_kzt, customer_phone)
      workflows(order_id TEXT PK, state TEXT, updated_at, store_name TEXT)
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.kaspi_api import KaspiAPI


REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data_crm" / "api_cache"
DB_PATH = REPO_ROOT / "db" / "erp.db"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--from", dest="date_from", required=True)
    p.add_argument("--to", dest="date_to", required=True)
    p.add_argument("--state", dest="state", default=None)
    return p.parse_args()


def ensure_tables(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS kaspi_orders_raw (
          order_id TEXT PRIMARY KEY,
          json TEXT,
          fetched_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
          order_id TEXT PRIMARY KEY,
          order_date TEXT,
          status TEXT,
          store_name TEXT,
          sku_name_raw TEXT,
          qty INTEGER,
          gross_price_kzt REAL,
          customer_phone TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS workflows (
          order_id TEXT PRIMARY KEY,
          state TEXT,
          updated_at TEXT,
          store_name TEXT
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_phone ON orders(customer_phone)")
    conn.commit()


def extract_customer_phone(included: List[Dict[str, Any]], rel: Dict[str, Any]) -> Optional[str]:
    # JSON:API include for user may have phone
    try:
        user_ref = (rel.get("user") or {}).get("data") or {}
        user_id = user_ref.get("id")
        for inc in included or []:
            if inc.get("type") == "users" and inc.get("id") == user_id:
                return (inc.get("attributes") or {}).get("phone")
    except Exception:
        return None
    return None


def upsert_order_rows(conn: sqlite3.Connection, payload: Dict[str, Any]) -> int:
    cur = conn.cursor()
    data = payload.get("data") or []
    included = payload.get("included") or []
    n = 0
    for it in data:
        if it.get("type") != "orders":
            continue
        oid = it.get("id")
        attrs = it.get("attributes") or {}
        rels = it.get("relationships") or {}
        items = attrs.get("items") or []
        first_item = items[0] if items else {}
        sku_name_raw = first_item.get("name")
        qty = int(first_item.get("quantity") or 0)
        gross_price_kzt = float(attrs.get("grandTotal") or 0) / 100.0
        store_name = attrs.get("deliveryAddressCity") or attrs.get("pickupPointName") or ""
        order_date = attrs.get("creationDate") or ""
        status = attrs.get("state") or ""
        phone = extract_customer_phone(included, rels) or ""

        # raw upsert
        cur.execute(
            "INSERT INTO kaspi_orders_raw(order_id, json, fetched_at) VALUES(?, ?, ?)\n"
            "ON CONFLICT(order_id) DO UPDATE SET json=excluded.json, fetched_at=excluded.fetched_at",
            (oid, json.dumps(it, ensure_ascii=False), datetime.utcnow().isoformat(timespec="seconds") + "Z"),
        )
        # parsed upsert
        cur.execute(
            "INSERT INTO orders(order_id, order_date, status, store_name, sku_name_raw, qty, gross_price_kzt, customer_phone)\n"
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?)\n"
            "ON CONFLICT(order_id) DO UPDATE SET order_date=excluded.order_date, status=excluded.status, store_name=excluded.store_name,\n"
            "  sku_name_raw=excluded.sku_name_raw, qty=excluded.qty, gross_price_kzt=excluded.gross_price_kzt, customer_phone=excluded.customer_phone",
            (oid, order_date, status, store_name, sku_name_raw, qty, gross_price_kzt, phone),
        )
        # workflows init
        cur.execute(
            "INSERT INTO workflows(order_id, state, updated_at, store_name) VALUES(?, ?, ?, ?)\n"
            "ON CONFLICT(order_id) DO NOTHING",
            (oid, "NEW", datetime.utcnow().isoformat(timespec="seconds") + "Z", store_name),
        )
        n += 1
    conn.commit()
    return n


def main() -> int:
    args = parse_args()
    token = os.environ.get("KASPI_TOKEN")
    if not token:
        raise SystemExit("Missing KASPI_TOKEN in environment")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"orders_{args.date_from}_{args.date_to}_{args.state or 'ALL'}.json"

    api = KaspiAPI(token=token)
    try:
        payload = api.get_orders(args.date_from, args.date_to, state=args.state, page_size=100)
    finally:
        api.close()

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {out_path}")

    with sqlite3.connect(DB_PATH) as conn:
        ensure_tables(conn)
        inserted = upsert_order_rows(conn, payload)
    print(f"Upserted orders: {inserted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


