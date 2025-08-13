"""
Apply order status transitions from order_status_plan.csv (dry-run by default).

Args:
  --apply  Perform real API calls; otherwise only write results CSV

Output:
  data_crm/reports/order_status_results.csv
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "data_crm" / "reports"
PLAN_CSV = REPORTS_DIR / "order_status_plan.csv"
RESULTS_CSV = REPORTS_DIR / "order_status_results.csv"
KASPI_BASE = "https://kaspi.kz/shop/api/v2"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    return p.parse_args()


def send_with_retries(url: str, headers: dict[str, str], body: dict[str, Any], max_retries: int = 5) -> httpx.Response:
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
            time.sleep(min(2 ** (attempt - 1), 10) + 0.1 * attempt)
    assert last_exc is not None
    raise last_exc


def main() -> int:
    args = parse_args()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if not PLAN_CSV.exists():
        raise SystemExit(f"Missing plan: {PLAN_CSV}")
    plan = pd.read_csv(PLAN_CSV)

    results: list[dict[str, Any]] = []

    if not args.apply:
        for _, r in plan.iterrows():
            results.append(
                {
                    "order_id": r.get("order_id"),
                    "proposed_status": r.get("proposed_status"),
                    "mode": "DRY_RUN",
                    "status_code": "-",
                    "message": r.get("reason", ""),
                }
            )
        pd.DataFrame(results).to_csv(RESULTS_CSV, index=False)
        print(f"Dry-run: wrote {RESULTS_CSV}")
        return 0

    token = os.environ.get("KASPI_TOKEN")
    if not token:
        raise SystemExit("Missing KASPI_TOKEN in environment for --apply")
    headers = {
        "X-Auth-Token": token,
        "Accept": "application/vnd.api+json;charset=UTF-8",
        "Content-Type": "application/json",
        "User-Agent": "kaspi-etl/phase2 (+https://github.com/TheRisingSun777/kaspi_etl)",
    }

    for _, r in plan.iterrows():
        order_id = str(r.get("order_id"))
        new_status = str(r.get("proposed_status"))
        body = {
            "data": [
                {"type": "orders", "id": order_id, "attributes": {"state": new_status}}
            ]
        }
        try:
            resp = send_with_retries(f"{KASPI_BASE}/orders", headers=headers, body=body)
            results.append(
                {
                    "order_id": order_id,
                    "proposed_status": new_status,
                    "mode": "APPLY",
                    "status_code": resp.status_code,
                    "message": json.dumps(resp.json(), ensure_ascii=False),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "order_id": order_id,
                    "proposed_status": new_status,
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


