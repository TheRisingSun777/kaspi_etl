#!/usr/bin/env python3
"""Alphabetically sort ActiveOrders exports by the Артикул column."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict

import pandas as pd


def normalize_header(value: str) -> str:
    """Return a simplified header name for matching Cyrillic columns."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = text.replace("ё", "е")
    return text


def find_sku_column(df: pd.DataFrame) -> str | None:
    for column in df.columns:
        if normalize_header(column) == "артикул":
            return column
    return None


def sort_workbook(path: Path) -> bool:
    try:
        sheets: Dict[str, pd.DataFrame] = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    except Exception as exc:  # pragma: no cover - defensive logging only
        print(f"WARN: cannot read '{path.name}': {exc}")
        return False

    sorted_any = False

    for name, frame in sheets.items():
        sku_column = find_sku_column(frame)
        if not sku_column:
            continue

        # Derive a stable key for sorting that handles NaNs and mixed types.
        sort_key = frame[sku_column].map(lambda value: "" if pd.isna(value) else str(value).lower())
        frame_sorted = frame.assign(__sort_key=sort_key).sort_values(
            by="__sort_key",
            kind="mergesort",
            ascending=True,
        ).drop(columns="__sort_key")

        sheets[name] = frame_sorted
        sorted_any = True

    if not sorted_any:
        print(f"INFO: skipped '{path.name}' (no Артикул column detected)")
        return False

    try:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            for sheet_name, frame in sheets.items():
                frame.to_excel(writer, sheet_name=sheet_name, index=False)
    except Exception as exc:  # pragma: no cover - defensive logging only
        print(f"WARN: failed to write '{path.name}': {exc}")
        return False

    print(f"Sorted '{path.name}' by column 'Артикул'")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Sort ActiveOrders exports by Артикул")
    parser.add_argument(
        "--orders-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "ActiveOrders",
        help="Directory containing ActiveOrders .xlsx files",
    )
    args = parser.parse_args()

    orders_dir: Path = args.orders_dir
    if not orders_dir.exists():
        print(f"INFO: orders directory '{orders_dir}' does not exist; nothing to sort")
        return 0

    xlsx_files = sorted(p for p in orders_dir.glob("*.xlsx") if not p.name.startswith("~$"))
    if not xlsx_files:
        print(f"INFO: no .xlsx files found in '{orders_dir}'; nothing to sort")
        return 0

    sorted_count = 0
    for path in xlsx_files:
        if sort_workbook(path):
            sorted_count += 1

    print(f"Processed {len(xlsx_files)} file(s); sorted {sorted_count} with Артикул column")
    return 0


if __name__ == "__main__":
    sys.exit(main())
