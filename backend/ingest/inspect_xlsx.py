#!/usr/bin/env python3
"""Inspect XLSX sheets and canonical header matches."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Mapping, Sequence

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.ingest.xlsx_loaders import DELIVERY_HEADER_MAP, _normalize_header  # noqa: E402
from backend.ingest.xlsx_offers_loader import canonicalize_account_id, load_store_name_to_id_map  # noqa: E402
from backend.utils.config import load_config  # noqa: E402

logger = logging.getLogger(__name__)


OFFERS_HEADER_MAP: Dict[str, Sequence[str]] = {
    "sku_key": ["SKU_ID_KSP", "SKU_Key", "SKU_key"],
    "store_cell": ["Store_name"],
    "kaspi_product_code": ["Kaspi_art_1"],
    "size_label": ["Size_kaspi"],
    "color": ["Color"],
    "title_core": ["Model", "Kaspi_name_core"],
}


def _detect_columns(columns: Mapping[str, str], mapping: Mapping[str, Sequence[str]]) -> Dict[str, str]:
    matches: Dict[str, str] = {}
    for canonical, aliases in mapping.items():
        for alias in aliases:
            key = alias.strip().lower()
            if key in columns:
                matches.setdefault(canonical, columns[key])
                break
    return matches


def inspect_file(path: Path, sheet: str | None, mode: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    data = pd.read_excel(path, engine="openpyxl", sheet_name=sheet or None)
    if isinstance(data, dict):
        items = data.items()
    else:
        items = [(sheet or "sheet0", data)]

    print(f"Sheets in {path}:")
    for name, df in items:
        column_lookup = {_normalize_header(col): col for col in df.columns}
        mapping = DELIVERY_HEADER_MAP if mode == "delivery" else OFFERS_HEADER_MAP
        matches = _detect_columns(column_lookup, mapping)
        print(f"- {name}")
        print(f"  Raw headers: {list(df.columns)}")
        print(f"  Normalized headers: {list(column_lookup.keys())}")
        print(f"  Canonical matches: {matches}")
        if mode == "offers":
            store_match = matches.get("store_cell")
            print(f"  Store column matched: {store_match if store_match else 'None'}")
            if store_match:
                cfg = load_config()
                store_map = load_store_name_to_id_map(cfg)
                values = (
                    df[store_match]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .unique()
                )
                bad = []
                for value in values:
                    mapped = canonicalize_account_id(
                        value, store_map, log_missing=False
                    )
                    if not mapped:
                        bad.append(value)
                    if len(bad) >= 5:
                        break
                if bad:
                    print(f"  Unmapped store samples: {bad}")
        else:
            resolved_aliases = {}
            for canonical, aliases in mapping.items():
                for alias in aliases:
                    key = alias.strip().lower()
                    if key in column_lookup:
                        resolved_aliases[canonical] = alias
                        break
            print(f"  Alias hits: {resolved_aliases}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect XLSX headers for loader compatibility")
    parser.add_argument("path", type=Path, help="Path to XLSX file")
    parser.add_argument("--sheet", help="Optional sheet name to inspect")
    parser.add_argument(
        "--mode",
        choices=["delivery", "offers"],
        default="delivery",
        help="Inspection mode (delivery or offers)",
    )
    args = parser.parse_args(argv)

    inspect_file(args.path, args.sheet, args.mode)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except FileNotFoundError as exc:
        logger.error(str(exc))
        sys.exit(1)
