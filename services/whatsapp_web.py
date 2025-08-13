#!/usr/bin/env python3
"""
Semi-automatic WhatsApp Web helper (Playwright).

- Opens WhatsApp Web and waits for a logged-in session (QR if needed)
- Opens a chat by name or phone (fallback to config lookup)
- Prompts the user to drag a specified file into the chat (no auto-upload)

Usage:
  python -m services.whatsapp_web --to "Fulfillment Team" --attach outbox/exports_*.zip

Requirements:
  pip install playwright
  playwright install chromium

Notes:
  - This tool is intentionally semi-automatic. It will NOT send messages or upload files automatically.
  - It only navigates to the chat so you can drag/drop the file yourself.
"""
from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path
from typing import Optional

try:
    from playwright.sync_api import sync_playwright
except Exception as e:  # pragma: no cover
    print("Playwright not installed. Run: pip install playwright && playwright install chromium", file=sys.stderr)
    raise

import yaml

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "data_crm" / "state"
WA_TARGETS = STATE_DIR / "wa_targets.yaml"


def load_target_from_config(name_or_phone: str) -> Optional[str]:
    if not WA_TARGETS.exists():
        return None
    try:
        data = yaml.safe_load(WA_TARGETS.read_text(encoding="utf-8")) or {}
        # YAML can map names or phone keys to a normalized search string
        # Example:
        # Fulfillment Team: "Fulfillment Team"
        # +7701xxxxxxx: "+7701xxxxxxx"
        return data.get(name_or_phone)
    except Exception:
        return None


def resolve_attachment(pattern: str) -> Optional[Path]:
    matches = sorted(glob.glob(pattern))
    if not matches:
        return None
    return Path(matches[-1]).resolve()


def open_chat(page, target: str) -> None:
    # Click the search button and type target
    page.get_by_role("button", name="Search or start new chat").click()
    page.get_by_placeholder("Search or start new chat").fill(target)
    page.wait_for_timeout(500)
    # Press Enter to open the first search result
    page.keyboard.press("Enter")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open WhatsApp Web to a chat and prompt for file drag.")
    parser.add_argument("--to", required=True, help="Chat name or phone number to open")
    parser.add_argument("--attach", required=False, help="Path or glob to file to attach (prompt only)")
    args = parser.parse_args(argv)

    target = args.to
    target_from_cfg = load_target_from_config(target)
    search_text = target_from_cfg or target

    attach_path: Optional[Path] = None
    if args.attach:
        p = resolve_attachment(args.attach)
        if p is None:
            print(f"Attachment not found for pattern: {args.attach}", file=sys.stderr)
        else:
            attach_path = p

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://web.whatsapp.com/")

        # Wait for QR scan or loaded app
        # The QR canvas or app root can take time; we allow user interaction
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        # Try to open chat
        try:
            open_chat(page, search_text)
        except Exception:
            # Fallback: Let user click manually
            print("Please select the chat manually, then return to this window.")

        # Print instructions
        if attach_path:
            print(f"Drag file now in the chat: {attach_path}")
        else:
            print("Navigate to the chat and drag your ZIP/PDF now.")

        # Keep the window open for user to complete action
        print("Press Ctrl+C to exit when done.")
        try:
            while True:
                page.wait_for_timeout(5000)
        except KeyboardInterrupt:
            pass
        finally:
            context.close()
            browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
