#!/usr/bin/env python3

"""
Fetch Kaspi Merchant Cabinet "Распечатать все накладные" ZIP using Playwright.

Auth: Reads KASPI_MERCHANT_COOKIE and KASPI_MERCHANT_ID from .env.local/.env.

Example:
  ./venv/bin/python scripts/fetch_waybills_mc.py \
    --status ACCEPTED_BY_MERCHANT \
    --status KASPI_DELIVERY_WAIT_FOR_COURIER \
    --out-date 2025-08-14

Writes ZIP to data_crm/labels_inbox/YYYY-MM-DD/waybill-<N>.zip and prints the path.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download waybills ZIP from merchant cabinet")
    p.add_argument(
        "--status",
        action="append",
        default=[],
        help="Order status filter (repeatable)",
    )
    p.add_argument("--out-date", default=None, help="YYYY-MM-DD (default: today)")
    return p.parse_args()


def parse_cookie_header(cookie_header: str, domain: str) -> List[dict]:
    cookies: List[dict] = []
    for part in cookie_header.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        cookies.append({"name": name.strip(), "value": value.strip(), "domain": domain, "path": "/"})
    return cookies


def get_output_path(base: Path, out_date: str) -> Path:
    day_dir = base / out_date
    day_dir.mkdir(parents=True, exist_ok=True)
    # Next index
    idx = 1
    while True:
        candidate = day_dir / f"waybill-{idx}.zip"
        if not candidate.exists():
            return candidate
        idx += 1


def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env.local", override=False)
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

    args = parse_args()
    out_date = args.out_date or os.getenv("OUT_DATE")
    if not out_date:
        import pandas as pd

        out_date = pd.Timestamp.utcnow().strftime("%Y-%m-%d")

    merchant_cookie = os.getenv("KASPI_MERCHANT_COOKIE", "").strip()
    merchant_id = os.getenv("KASPI_MERCHANT_ID", "").strip()
    if not merchant_cookie or not merchant_id:
        print("Missing KASPI_MERCHANT_COOKIE or KASPI_MERCHANT_ID in env")
        return 2

    inbox_dir = Path("data_crm/labels_inbox")
    out_zip = get_output_path(inbox_dir, out_date)

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except Exception as e:
        print("Playwright not installed. Run: pip install playwright && python -m playwright install chromium")
        return 2

    orders_url = f"https://kaspi.kz/merchantcabinet/#/orders?merchantId={merchant_id}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)

        # Set cookies
        cookies = parse_cookie_header(merchant_cookie, domain=".kaspi.kz")
        if cookies:
            context.add_cookies(cookies)

        page = context.new_page()
        page.set_default_timeout(30000)
        page.goto(orders_url)

        # Try to apply status filters best-effort (UI text-based)
        for status in args.status:
            try:
                # open filter panel if any common toggle exists
                page.locator("text=Статус").first.click(timeout=2000)
            except Exception:
                pass
            try:
                # Click checkbox or tag by text
                page.locator(f"text={status}").first.click(timeout=2000)
            except Exception:
                pass

        # Click the print-all-waybills button by visible text
        download = None
        try:
            with page.expect_download(timeout=60000) as dl_info:
                page.locator("text=Распечатать все накладные").first.click()
            download = dl_info.value
        except PWTimeout:
            print("Timed out waiting for waybills download")
            context.close()
            browser.close()
            return 1
        except Exception as e:
            print(f"Failed to trigger download: {e}")
            context.close()
            browser.close()
            return 1

        # Save the downloaded zip
        try:
            download.save_as(str(out_zip))
        except Exception:
            # Fallback: stream to path
            out_zip.write_bytes(download.read())

        print(str(out_zip.resolve()))
        context.close()
        browser.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())


