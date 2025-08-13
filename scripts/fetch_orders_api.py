"""
CLI to fetch orders via Kaspi API and save raw JSON.

Usage:
  ./venv/bin/python scripts/fetch_orders_api.py --from 2025-08-01 --to 2025-08-13 --state NEW

Saves to: data_crm/api_cache/orders_{from}_{to}.json
Token: KASPI_TOKEN env var.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from scripts.kaspi_api import KaspiAPI

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data_crm" / "api_cache"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD or ISO")
    p.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD or ISO")
    p.add_argument("--state", dest="state", default=None, help="Order state filter (e.g., NEW)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("KASPI_TOKEN")
    if not token:
        raise SystemExit("Missing KASPI_TOKEN in environment")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    api = KaspiAPI(token=token)
    try:
        result = api.get_orders(args.date_from, args.date_to, state=args.state, page_size=100)
    finally:
        api.close()

    out_path = OUT_DIR / f"orders_{args.date_from}_{args.date_to}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


