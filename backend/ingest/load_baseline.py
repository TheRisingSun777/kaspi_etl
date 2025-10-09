#!/usr/bin/env python3
"""
CLI to load baseline dimensions (products, size mix, delivery bands) into the DB.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.session import get_session
from backend.ingest.xlsx_loaders import (
    load_delivery_bands_to_db,
    load_size_mix_to_db,
    load_sku_map_to_db,
)
from backend.utils.config import get_delivery_xlsx_path, load_config

logger = logging.getLogger(__name__)


def _validate_paths(paths: Dict[str, str]) -> Dict[str, Path]:
    resolved: Dict[str, Path] = {}
    missing = []
    for key, value in paths.items():
        file_path = Path(value).expanduser()
        if not file_path.exists():
            missing.append((key, file_path))
        resolved[key] = file_path
    if missing:
        for key, path in missing:
            logger.error("Missing required file for %s: %s", key, path)
        raise FileNotFoundError("One or more required XLSX files are missing.")
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load baseline dimension data from XLSX files.")
    parser.add_argument(
        "--config",
        type=Path,
        help="Optional path to CONFIG.yaml (defaults to docs/protocol/CONFIG.yaml)",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config) if args.config else load_config()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    delivery_path = get_delivery_xlsx_path(config)
    if not delivery_path:
        logger.error(
            "Unable to resolve delivery bands path. Set DELIVERY_XLSX, update docs/protocol/paths.yaml, or CONFIG.yaml."
        )
        return 1

    try:
        paths = _validate_paths(
            {
                "sku_map": config.paths.xlsx_sku_map,
                "size_mix": config.paths.xlsx_demand,
                "delivery_bands": delivery_path,
            }
        )
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 1

    counts = {"products": 0, "size_mix": 0, "delivery_bands": 0}
    with get_session() as session:
        counts["products"] = load_sku_map_to_db(paths["sku_map"], session)
        counts["size_mix"] = load_size_mix_to_db(paths["size_mix"], session)
        counts["delivery_bands"] = load_delivery_bands_to_db(paths["delivery_bands"], session)

    summary = (
        f"Loaded products: {counts['products']}; "
        f"size_mix rows: {counts['size_mix']}; "
        f"delivery_bands rows: {counts['delivery_bands']}"
    )
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
