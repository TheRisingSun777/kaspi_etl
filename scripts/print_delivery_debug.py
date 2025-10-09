#!/usr/bin/env python3
"""
Print a quick snapshot of delivery fee inputs after canonical alias resolution.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.ingest.xlsx_loaders import _coerce_float, _coerce_pct, resolve_delivery_sheet  # noqa: E402
from backend.utils.config import get_delivery_xlsx_path  # noqa: E402

COLUMNS_TO_SHOW: Sequence[str] = (
    "price_min",
    "price_max",
    "weight_min_kg",
    "weight_max_kg",
    "fee_city_pct",
    "fee_country_pct",
    "fee_city_kzt",
    "fee_country_kzt",
    "platform_fee_pct",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print first 10 delivery rows after alias coercion.")
    parser.add_argument("--limit", type=int, default=10, help="Number of rows to show (default: 10)")
    args = parser.parse_args(argv)

    delivery_path = get_delivery_xlsx_path()
    if not delivery_path:
        print(
            "Unable to resolve delivery XLSX path. Set DELIVERY_XLSX, update docs/protocol/paths.yaml, or CONFIG.yaml.",
            file=sys.stderr,
        )
        return 1

    file_path = Path(delivery_path)
    if not file_path.exists():
        print(f"Delivery XLSX not found at {file_path}", file=sys.stderr)
        return 1

    sheets = pd.read_excel(file_path, engine="openpyxl", sheet_name=None)
    df, resolved_columns = resolve_delivery_sheet(sheets)

    rows = []
    limit = max(1, args.limit)
    for _, row in df.iterrows():
        record = {}
        for field in COLUMNS_TO_SHOW:
            column_name = resolved_columns.get(field)
            raw_value = row[column_name] if column_name else None
            if field in {"fee_city_pct", "fee_country_pct", "platform_fee_pct"}:
                record[field] = _coerce_pct(raw_value)
            else:
                record[field] = _coerce_float(raw_value)
        rows.append(record)
        if len(rows) >= limit:
            break

    if not rows:
        print("No rows available to display.")
        return 0

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 120)
    print(f"Resolved delivery file: {file_path}")
    print(pd.DataFrame(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
