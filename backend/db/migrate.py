#!/usr/bin/env python3
"""
Simple migration bootstrapper.

Creates all tables defined in `backend.db.models`, ensures the inventory policy
row exists, and prints a quick table-row summary.
"""
from __future__ import annotations

import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import argparse
from typing import Dict

from sqlalchemy import func, select

from backend.db.models import Base, InventoryPolicy
from backend.db.session import get_database_url, get_engine, get_session
from backend.utils.config import load_config


def _ensure_sqlite_directory() -> None:
    url = get_database_url()
    if url.get_backend_name() != "sqlite":
        return
    database = url.database
    if not database or database in {":memory:", ""}:
        return
    db_path = Path(database)
    db_path.parent.mkdir(parents=True, exist_ok=True)


def _upsert_inventory_policy() -> None:
    cfg = load_config()
    policy = InventoryPolicy(
        id=1,
        L_days=cfg.policy.L_days,
        R_days=cfg.policy.R_days,
        B_days=cfg.policy.B_days,
        z_service=cfg.policy.z_service,
        tv_floor=cfg.policy.tv_floor,
        vat_pct=cfg.policy.vat_pct,
        platform_pct=cfg.policy.platform_pct,
        delivery_blend_city=cfg.policy.delivery_blend_city,
        delivery_blend_country=cfg.policy.delivery_blend_country,
    )
    with get_session() as session:
        session.merge(policy)


def _collect_counts() -> Dict[str, int]:
    counts: Dict[str, int] = {}
    with get_session() as session:
        for table in Base.metadata.sorted_tables:
            result = session.execute(select(func.count()).select_from(table))
            counts[table.name] = result.scalar_one()
    return counts


def _ensure_delivery_bands_columns(engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    column_specs = {
        "fee_city_pct": "NUMERIC",
        "fee_country_pct": "NUMERIC",
        "platform_fee_pct": "NUMERIC",
        "currency_code": "TEXT",
        "fx_rate_kzt": "NUMERIC",
        "vat_rate": "NUMERIC",
        "channel_id": "TEXT",
        "channel_name": "TEXT",
    }

    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info('delivery_bands')").fetchall()
        existing = {row[1] for row in rows}
        for column, ddl_type in column_specs.items():
            if column not in existing:
                conn.exec_driver_sql(
                    f"ALTER TABLE delivery_bands ADD COLUMN {column} {ddl_type}"
                )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Create or upgrade the SQLite schema")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate all tables (SQLite only). WARNING: destructive.",
    )
    args = parser.parse_args(argv)

    _ensure_sqlite_directory()
    engine = get_engine()
    if args.reset:
        if engine.dialect.name != "sqlite":
            print("--reset is only supported for SQLite databases.", file=sys.stderr)
            sys.exit(1)
        Base.metadata.drop_all(engine)
        print("Dropped existing tables (SQLite reset).")

    Base.metadata.create_all(engine)
    _ensure_delivery_bands_columns(engine)
    _upsert_inventory_policy()

    counts = _collect_counts()
    print("Migration complete. Table row counts:")
    for name, count in counts.items():
        print(f"  - {name}: {count}")


if __name__ == "__main__":
    main()
