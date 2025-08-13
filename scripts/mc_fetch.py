#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
import os
import shutil
from pathlib import Path
from zipfile import ZipFile

from dotenv import load_dotenv

from services.kaspi_mc_downloader import download_active_orders, download_waybills


load_dotenv(".env.local", override=False)
load_dotenv(override=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CRM = REPO_ROOT / "data_crm"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch files from Kaspi Merchant Cabinet using browser cookies")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--waybills", action="store_true", help="Download waybills ZIP")
    g.add_argument("--orders", action="store_true", help="Download ActiveOrders XLSX")
    p.add_argument("--url", default=None, help="Override URL (otherwise use env)")
    p.add_argument("--out-date", default=None, help="Output date (YYYY-MM-DD); defaults to today")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.waybills:
        url = args.url or os.getenv("KASPI_WAYBILLS_URL", "").strip()
        if not url:
            raise SystemExit("Missing URL: provide --url or set KASPI_WAYBILLS_URL in .env.local")
        final = download_waybills(url, out_dir=str(DATA_CRM / "inbox" / "waybills"))
        # Extract into raw/ under same date folder
        try:
            raw_dir = final.parent / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            with ZipFile(final, "r") as zf:
                zf.extractall(raw_dir)
            logger.info("Extracted %s to %s", final.name, raw_dir)
        except Exception as e:
            logger.warning("Extraction failed (continuing): %s", e)
        print(str(final))
        return 0

    if args.orders:
        url = args.url or os.getenv("KASPI_ACTIVEORDERS_URL", "").strip()
        if not url:
            raise SystemExit("Missing URL: provide --url or set KASPI_ACTIVEORDERS_URL in .env.local")
        final = download_active_orders(url, out_dir=str(DATA_CRM / "inbox" / "orders"))
        # Copy latest to canonical path for downstream
        latest = DATA_CRM / "active_orders_latest.xlsx"
        try:
            shutil.copy2(final, latest)
            logger.info("Updated %s", latest)
        except Exception as e:
            logger.warning("Could not update %s: %s", latest, e)
        print(str(final))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


