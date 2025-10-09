#!/usr/bin/env python3
"""CLI helper to load size-mix shares into the database."""
from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.session import get_session  # noqa: E402
from backend.db.models import SizeMix  # noqa: E402
from backend.ingest.xlsx_loaders import (  # noqa: E402
    _coerce_float,
    _normalize_header,
    _normalize_size_label,
)
from backend.utils.config import load_config  # noqa: E402

logger = logging.getLogger(__name__)


REQUIRED_COLUMNS = {
    "sku_key": ["sku_key", "sku_id_ksp", "sku"],
    "size_label": ["size_kaspi", "size", "my_size"],
    "share": ["share", "share_%", "share percent"],
}


def _find_column(column_lookup: Dict[str, str], aliases: Iterable[str]) -> str | None:
    for alias in aliases:
        key = alias.strip().lower()
        if key in column_lookup:
            return column_lookup[key]
    return None


def _extract_rows(path: Path) -> List[Tuple[str, str, float]]:
    workbook = pd.read_excel(path, engine="openpyxl", sheet_name=None)
    rows: List[Tuple[str, str, float]] = []

    for sheet_name, df in workbook.items():
        column_lookup = {_normalize_header(col): col for col in df.columns}
        sku_col = _find_column(column_lookup, REQUIRED_COLUMNS["sku_key"])
        size_col = _find_column(column_lookup, REQUIRED_COLUMNS["size_label"])
        share_col = _find_column(column_lookup, REQUIRED_COLUMNS["share"])

        if not (sku_col and size_col and share_col):
            continue

        candidate = (
            df[[sku_col, size_col, share_col]]
            .dropna(subset=[sku_col, size_col, share_col])
            .copy()
        )
        if candidate.empty:
            continue

        for _, row in candidate.iterrows():
            sku_key = str(row[sku_col]).strip()
            size_raw = str(row[size_col]).strip()
            share_val = _coerce_float(row[share_col])
            if not sku_key or not size_raw or share_val is None:
                continue
            label = _normalize_size_label(size_raw)
            if not label:
                continue
            rows.append((sku_key, label, share_val))

        if rows:
            logger.info("Loaded size-mix entries from %s!%s", path.name, sheet_name)
            break

    return rows


def load_size_mix_entries(paths: Iterable[Path]) -> Dict[str, Dict[str, float]]:
    aggregated: Dict[str, Dict[str, float]] = defaultdict(dict)

    for path in paths:
        if not path.exists():
            continue
        rows = _extract_rows(path)
        if rows:
            for sku_key, size_label, share in rows:
                aggregated[sku_key][size_label] = share
            break

    return aggregated


def _normalize_shares(shares: Dict[str, float], sku_key: str) -> Dict[str, float]:
    total = sum(v for v in shares.values() if v is not None)
    if total <= 0:
        logger.warning("Size mix shares for %s sum to %.3f; skipping", sku_key, total)
        return {}
    if abs(total - 1.0) > 0.01:
        logger.warning("Size mix shares for %s sum to %.3f; renormalizing.", sku_key, total)
    return {label: value / total for label, value in shares.items()}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load size mix shares from canonical workbooks")
    parser.add_argument(
        "--config",
        type=Path,
        help="Optional CONFIG.yaml override",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config) if args.config else load_config()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    candidate_paths = [
        Path(config.paths.xlsx_sku_map),
        Path(config.paths.xlsx_sales),
    ]

    entries = load_size_mix_entries(candidate_paths)
    if not entries:
        logger.info("No size-mix source files found; nothing to load.")
        return 0

    total_rows = 0
    with get_session() as session:
        for sku_key, shares in entries.items():
            normalized = _normalize_shares(shares, sku_key)
            if not normalized:
                continue
            session.query(SizeMix).filter_by(sku_key=sku_key).delete(synchronize_session=False)
            for size_label, share in normalized.items():
                session.add(SizeMix(sku_key=sku_key, size_label=size_label, share=share))
                total_rows += 1
    logger.info("Inserted %d size-mix rows", total_rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
