#!/usr/bin/env python3
"""
CLI to load offers from Business_model workbook into the database.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.session import get_session  # noqa: E402
from backend.ingest.xlsx_offers_loader import load_offers_to_db  # noqa: E402
from backend.utils.config import get_offers_xlsx_path, load_config  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load offers from Business_model XLSX.")
    parser.add_argument(
        "--config",
        type=Path,
        help="Optional path to CONFIG.yaml (defaults to docs/protocol/CONFIG.yaml)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config(args.config) if args.config else load_config()
    offers_path_str = get_offers_xlsx_path(config)
    if not offers_path_str:
        logging.error(
            "Unable to resolve offers catalog path. Set OFFERS_XLSX, update docs/protocol/paths.yaml, or CONFIG.yaml."
        )
        return 1
    offers_path = Path(offers_path_str)
    if not offers_path.exists():
        logging.error("Offers catalog not found at %s", offers_path)
        return 1

    with get_session() as session:
        count = load_offers_to_db(offers_path, session)

    print(f"Loaded offers: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
