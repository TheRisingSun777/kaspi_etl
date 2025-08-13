#!/usr/bin/env python3

"""
Kaspi Waybills Downloader (local-use)

Reads env:
- KASPI_MERCHANT_ID
- KASPI_MERCHANT_COOKIE  (copy full Cookie string from browser DevTools)
- KASPI_MERCHANT_API_BASE (default: https://mc.shop.kaspi.kz)
- KASPI_WAYBILLS_URL (optional; full URL captured from DevTools → "Print all waybills")

Usage:
  ./venv/bin/python scripts/kaspi_waybills_download.py --date YYYY-MM-DD [--url FULL_URL]

Notes:
- Prefer passing the exact URL seen in DevTools (Network) for the "Print all waybills" action.
- If --url not provided, the script uses env KASPI_WAYBILLS_URL. If still absent, exits with a helpful error.
- Saves ZIP to data_crm/inputs/waybill_YYYYMMDD.zip and logs filename + size.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv


# Load environment (.env.local preferred, then .env)
load_dotenv(".env.local", override=False)
load_dotenv(override=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CRM = REPO_ROOT / "data_crm"
INPUTS_DIR = DATA_CRM / "inputs"
INPUTS_DIR.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download Kaspi waybills ZIP (cookie-based)")
    p.add_argument("--date", default=None, help="Date tag YYYY-MM-DD (defaults to today)")
    p.add_argument("--url", default=None, help="Full waybills URL captured from DevTools (Network)")
    return p.parse_args()


def date_to_stamp(date_str: Optional[str]) -> tuple[str, str]:
    if date_str:
        try:
            d = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise SystemExit("--date must be YYYY-MM-DD")
    else:
        d = dt.date.today()
    return d.isoformat(), d.strftime("%Y%m%d")


def pick_url(cli_url: Optional[str]) -> str:
    base = os.getenv("KASPI_MERCHANT_API_BASE", "https://mc.shop.kaspi.kz").rstrip("/")
    env_url = os.getenv("KASPI_WAYBILLS_URL", "").strip()
    final_url = (cli_url or env_url).strip()
    if not final_url:
        logger.error(
            "Waybills URL not provided. Pass --url FULL_URL or set KASPI_WAYBILLS_URL in .env.local (copy from DevTools → Network)."
        )
        raise SystemExit(2)
    if final_url.startswith("/"):
        final_url = base + final_url
    return final_url


def main() -> int:
    args = parse_args()
    iso_date, ymd = date_to_stamp(args.date)

    merchant_id = (os.getenv("KASPI_MERCHANT_ID") or "").strip()
    cookie = (os.getenv("KASPI_MERCHANT_COOKIE") or "").strip()
    if not cookie:
        logger.error("Missing KASPI_MERCHANT_COOKIE in env (.env.local).")
        return 2
    url = pick_url(args.url)

    headers = {
        "Cookie": cookie,
        "Accept": "*/*",
        "User-Agent": "kaspi-etl/1.0 (+python-httpx)",
        "Referer": os.getenv("KASPI_MERCHANT_API_BASE", "https://mc.shop.kaspi.kz"),
    }

    out_zip = INPUTS_DIR / f"waybill_{ymd}.zip"

    logger.info("Downloading waybills: %s", url)
    try:
        with httpx.Client(timeout=httpx.Timeout(180.0)) as client:
            with client.stream("GET", url, headers=headers) as resp:
                resp.raise_for_status()
                with out_zip.open("wb") as f:
                    for chunk in resp.iter_bytes():
                        if chunk:
                            f.write(chunk)
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error %s: %s", e.response.status_code, e.response.text[:200])
        return 1
    except Exception as e:
        logger.error("Download failed: %s", e)
        return 1

    size = out_zip.stat().st_size if out_zip.exists() else 0
    if size <= 0:
        logger.error("Downloaded file is empty: %s", out_zip)
        return 1
    logger.info("Saved %s (size=%.1f KB)", out_zip, size / 1024.0)
    print(str(out_zip))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


