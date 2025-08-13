"""
Plan safe order status transitions based on DB state and label readiness.

Rules:
- NEW → ACCEPTED_BY_MERCHANT (we decide to proceed)
- ACCEPTED_BY_MERCHANT → ASSEMBLE when workflows.state=CONFIRMED and label ready

Label readiness heuristic:
- A store-level PDF exists at data_crm/labels/<store_name>/packing_<YYYY-MM-DD>.pdf

Output:
- data_crm/reports/order_status_plan.csv with columns:
  order_id, current_status, workflow_state, store_name, proposed_status, reason
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "db" / "erp.db"
LABELS_ROOT = REPO_ROOT / "data_crm" / "labels"
REPORTS_DIR = REPO_ROOT / "data_crm" / "reports"


def load_orders_and_workflows() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            """
            SELECT o.order_id, o.status AS current_status, o.store_name, w.state AS workflow_state
            FROM orders o
            LEFT JOIN workflows w ON w.order_id = o.order_id
            """,
            conn,
        )
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def label_ready(store_name: str) -> bool:
    if not store_name:
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    path = LABELS_ROOT / store_name / f"packing_{today}.pdf"
    return path.exists()


def build_plan(df: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict] = []
    for _, r in df.iterrows():
        order_id = str(r.get("order_id"))
        status = (r.get("current_status") or "").upper()
        wf = (r.get("workflow_state") or "").upper()
        store = r.get("store_name") or ""

        if status == "NEW":
            rows.append(
                {
                    "order_id": order_id,
                    "current_status": status,
                    "workflow_state": wf,
                    "store_name": store,
                    "proposed_status": "ACCEPTED_BY_MERCHANT",
                    "reason": "proceed_by_rule",
                }
            )
        if status == "ACCEPTED_BY_MERCHANT" and wf == "CONFIRMED" and label_ready(store):
            rows.append(
                {
                    "order_id": order_id,
                    "current_status": status,
                    "workflow_state": wf,
                    "store_name": store,
                    "proposed_status": "ASSEMBLE",
                    "reason": "confirmed_with_label",
                }
            )

    return pd.DataFrame(rows)


def main() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    df = load_orders_and_workflows()
    plan = build_plan(df)
    out_path = REPORTS_DIR / "order_status_plan.csv"
    plan.to_csv(out_path, index=False)
    print(f"Wrote plan: {out_path} ({len(plan)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


