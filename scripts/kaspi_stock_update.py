"""
Kaspi stock update (safe): dry-run by default, optional --apply to PUT.

Reads data_crm/reports/kaspi_stock_update_payload.json and either:
- Dry-run: writes a results CSV summarizing what would be sent
- Apply: PUTs to https://kaspi.kz/shop/api/v2/stocks with retries and rate-limit

Outputs:
- data_crm/reports/stock_update_results.csv

Usage:
  ./venv/bin/python scripts/kaspi_stock_update.py           # dry run
  ./venv/bin/python scripts/kaspi_stock_update.py --apply   # real PUT
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

import httpx
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_PATH = REPO_ROOT / "data_crm" / "reports" / "kaspi_stock_update_payload.json"
RESULTS_CSV = REPO_ROOT / "data_crm" / "reports" / "stock_update_results.csv"

KASPI_BASE = "https://kaspi.kz/shop/api/v2"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="Perform real PUT (default: dry-run)")
    return p.parse_args()


def load_payload(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing payload JSON: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def send_with_retries(url: str, headers: Dict[str, str], body: Dict[str, Any], max_retries: int = 5) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = httpx.put(url, headers=headers, json=body, timeout=30.0)
            if resp.status_code in (429, 500, 502, 503, 504):
                raise httpx.HTTPStatusError(
                    f"retryable {resp.status_code}", request=resp.request, response=resp
                )
            resp.raise_for_status()
            return resp
        except Exception as exc:
            last_exc = exc
            sleep_s = min(2 ** (attempt - 1), 10) + 0.1 * attempt
            time.sleep(sleep_s)
    assert last_exc is not None
    raise last_exc


def to_rows_from_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in payload.get("data", []):
        rows.append(
            {
                "id": item.get("id"),
                "attributes": item.get("attributes", {}),
            }
        )
    return rows


def main() -> int:
    args = parse_args()
    payload = load_payload(PAYLOAD_PATH)
    rows = to_rows_from_payload(payload)
    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []

    if not args.apply:
        for r in rows:
            results.append(
                {
                    "id": r["id"],
                    "mode": "DRY_RUN",
                    "status_code": "-",
                    "message": json.dumps(r["attributes"], ensure_ascii=False),
                }
            )
        pd.DataFrame(results).to_csv(RESULTS_CSV, index=False)
        print(f"Dry-run: wrote {RESULTS_CSV}")
        return 0

    # Real apply
    token = os.environ.get("KASPI_TOKEN")
    if not token:
        raise SystemExit("Missing KASPI_TOKEN in environment for --apply")

    headers = {
        "X-Auth-Token": token,
        "Accept": "application/vnd.api+json;charset=UTF-8",
        "Content-Type": "application/json",
        "User-Agent": "kaspi-etl/phase2 (+https://github.com/TheRisingSun777/kaspi_etl)",
    }

    try:
        resp = send_with_retries(f"{KASPI_BASE}/stocks", headers=headers, body=payload)
        body = resp.json()
        # Attempt to map response per item; fallback to global status
        if isinstance(body, dict) and body.get("data"):
            for item in body.get("data", []):
                results.append(
                    {
                        "id": item.get("id"),
                        "mode": "APPLY",
                        "status_code": resp.status_code,
                        "message": json.dumps(item.get("attributes") or item, ensure_ascii=False),
                    }
                )
        else:
            # No per-item data; record a single line per requested row with global status
            for r in rows:
                results.append(
                    {
                        "id": r.get("id"),
                        "mode": "APPLY",
                        "status_code": resp.status_code,
                        "message": json.dumps(body, ensure_ascii=False),
                    }
                )
    except Exception as exc:
        for r in rows:
            results.append(
                {
                    "id": r.get("id"),
                    "mode": "APPLY",
                    "status_code": "ERR",
                    "message": str(exc),
                }
            )

    pd.DataFrame(results).to_csv(RESULTS_CSV, index=False)
    print(f"Applied results written: {RESULTS_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


