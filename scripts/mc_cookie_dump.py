#!/usr/bin/env python3

from __future__ import annotations

import json
import logging
from pathlib import Path

from playwright.sync_api import sync_playwright


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CRM = REPO_ROOT / "data_crm"
STATE_DIR = DATA_CRM / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
COOKIES_JSON = STATE_DIR / "mc_cookies.json"
PW_PROFILE = REPO_ROOT / ".pw_profile"


def main() -> int:
    print("Launching Chromium with persistent profile .pw_profile ...")
    print("Login if needed, then press Enter in this terminal to save cookies.")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PW_PROFILE),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://mc.shop.kaspi.kz/orders", wait_until="load")
        try:
            input("When you see you are logged in (orders page loaded), press Enter to save cookies...")
        except KeyboardInterrupt:
            pass
        cookies = context.cookies()
        COOKIES_JSON.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved cookies to {COOKIES_JSON}")
        context.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


