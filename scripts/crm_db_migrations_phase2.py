"""
Phase 2 database migrations (idempotent).

Creates tables if not exist and necessary indexes:
- customers
- wa_outbox
- wa_inbox
- size_recommendations
- workflows
- events_log

Run:
  ./venv/bin/python scripts/crm_db_migrations_phase2.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "db" / "erp.db"


TABLE_SQL = [
    # customers
    (
        "customers",
        """
        CREATE TABLE IF NOT EXISTS customers (
          id TEXT PRIMARY KEY,
          phone TEXT,
          name TEXT,
          created_at TEXT
        )
        """,
    ),
    # wa_outbox
    (
        "wa_outbox",
        """
        CREATE TABLE IF NOT EXISTS wa_outbox (
          id TEXT PRIMARY KEY,
          order_id TEXT,
          to_phone TEXT,
          template TEXT,
          payload_json TEXT,
          status TEXT,
          created_at TEXT
        )
        """,
    ),
    # wa_inbox
    (
        "wa_inbox",
        """
        CREATE TABLE IF NOT EXISTS wa_inbox (
          id TEXT PRIMARY KEY,
          order_id TEXT,
          from_phone TEXT,
          text TEXT,
          parsed_json TEXT,
          created_at TEXT
        )
        """,
    ),
    # size_recommendations
    (
        "size_recommendations",
        """
        CREATE TABLE IF NOT EXISTS size_recommendations (
          order_id TEXT,
          recommended_size TEXT,
          confidence REAL,
          height INT,
          weight INT,
          final_size TEXT,
          created_at TEXT
        )
        """,
    ),
    # workflows
    (
        "workflows",
        """
        CREATE TABLE IF NOT EXISTS workflows (
          order_id TEXT PRIMARY KEY,
          state TEXT,
          updated_at TEXT,
          store_name TEXT
        )
        """,
    ),
    # events_log
    (
        "events_log",
        """
        CREATE TABLE IF NOT EXISTS events_log (
          id TEXT PRIMARY KEY,
          order_id TEXT,
          kind TEXT,
          data_json TEXT,
          created_at TEXT
        )
        """,
    ),
]


INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_wa_outbox_to_phone ON wa_outbox(to_phone)",
    "CREATE INDEX IF NOT EXISTS idx_wa_inbox_from_phone ON wa_inbox(from_phone)",
    "CREATE INDEX IF NOT EXISTS idx_workflows_state ON workflows(state)",
    "CREATE INDEX IF NOT EXISTS idx_events_log_order ON events_log(order_id)",
]


def ensure_db_dir() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def apply_migrations() -> None:
    ensure_db_dir()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        for name, sql in TABLE_SQL:
            cur.execute(sql)
        for sql in INDEX_SQL:
            cur.execute(sql)
        conn.commit()


def main() -> int:
    apply_migrations()
    print(f"Migrations applied to {DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


