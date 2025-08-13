"""
Status report CLI.

Prints:
- Counts by workflows.state
- Orders waiting >3h in WAITING_SIZE_INFO and >1h in WAITING_CONFIRM
- Low-stock top-10 (from latest low_stock_*.csv if available)

Also writes docs/STATUS.md snapshot with timestamp.
"""

from __future__ import annotations

import glob
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "db" / "erp.db"
REPORTS_DIR = REPO_ROOT / "data_crm" / "reports"
STATUS_MD = REPO_ROOT / "docs" / "STATUS.md"


def utcnow() -> datetime:
    return datetime.now(UTC)


def parse_iso_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1]
        # Parse naive then set UTC
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except Exception:
        return None


def get_state_counts(conn: sqlite3.Connection) -> dict[str, int]:
    cur = conn.cursor()
    cur.execute("SELECT state, COUNT(*) FROM workflows GROUP BY state")
    return {state or "": int(cnt) for state, cnt in cur.fetchall()}


def get_waiting(conn: sqlite3.Connection) -> tuple[pd.DataFrame, pd.DataFrame]:
    cur = conn.cursor()
    cur.execute(
        "SELECT order_id, state, updated_at, store_name FROM workflows WHERE state IN ('WAITING_SIZE_INFO','WAITING_CONFIRM')"
    )
    rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=["order_id", "state", "updated_at", "store_name"])
    if df.empty:
        return df, df
    df["updated_at_parsed"] = df["updated_at"].apply(parse_iso_utc)
    df["age_hours"] = df["updated_at_parsed"].apply(lambda d: (utcnow() - d).total_seconds() / 3600 if d else 0)
    w3 = df[(df["state"] == "WAITING_SIZE_INFO") & (df["age_hours"] > 3)].copy()
    w1 = df[(df["state"] == "WAITING_CONFIRM") & (df["age_hours"] > 1)].copy()
    return w3, w1


def load_low_stock_top10() -> pd.DataFrame:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(glob.glob(str(REPORTS_DIR / "low_stock_*.csv")))
    if not files:
        return pd.DataFrame(columns=["sku_id/sku_key", "stock_now", "velocity_14d", "reorder_qty"])  # empty
    latest = files[-1]
    df = pd.read_csv(latest)
    # Normalize columns
    df.columns = [c.strip().lower() for c in df.columns]
    # Expected: 'sku_id/sku_key', 'stock_now', 'velocity_14d', 'reorder_qty'
    # Handle name variance
    col_map = {}
    for name in ["sku_id/sku_key", "sku_id_or_key", "sku_id", "sku_key"]:
        if name in df.columns:
            col_map[name] = "sku"
            break
    col_map.update({k: k for k in ["stock_now", "velocity_14d", "reorder_qty"] if k in df.columns})
    df2 = df.rename(columns=col_map)
    for col in ["reorder_qty", "velocity_14d", "stock_now"]:
        if col in df2.columns:
            df2[col] = pd.to_numeric(df2[col], errors="coerce").fillna(0)
    cols = [c for c in ["sku", "stock_now", "velocity_14d", "reorder_qty"] if c in df2.columns]
    if not cols:
        return pd.DataFrame(columns=["sku", "stock_now", "velocity_14d", "reorder_qty"]).head(0)
    return df2[cols].sort_values(["reorder_qty", "velocity_14d"], ascending=[False, False]).head(10)


def write_status_md(state_counts: dict[str, int], w3: pd.DataFrame, w1: pd.DataFrame, low_stock: pd.DataFrame) -> None:
    lines: list[str] = []
    lines.append(f"## Status — {utcnow().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("### Workflow counts")
    for k in sorted(state_counts.keys()):
        lines.append(f"- {k}: {state_counts[k]}")
    lines.append("")
    lines.append("### Waiting thresholds")
    lines.append(f"- WAITING_SIZE_INFO >3h: {len(w3)}")
    if not w3.empty:
        sample = ", ".join(w3["order_id"].astype(str).head(10).tolist())
        lines.append(f"  sample: {sample}")
    lines.append(f"- WAITING_CONFIRM >1h: {len(w1)}")
    if not w1.empty:
        sample = ", ".join(w1["order_id"].astype(str).head(10).tolist())
        lines.append(f"  sample: {sample}")
    lines.append("")
    lines.append("### Low-stock top-10")
    if low_stock.empty:
        lines.append("(none)")
    else:
        lines.append("sku, stock_now, velocity_14d, reorder_qty")
        for _, r in low_stock.iterrows():
            lines.append(
                f"{r.get('sku','')}, {int(r.get('stock_now',0))}, {int(r.get('velocity_14d',0))}, {int(r.get('reorder_qty',0))}"
            )
    lines.append("")
    STATUS_MD.parent.mkdir(parents=True, exist_ok=True)
    STATUS_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    with sqlite3.connect(DB_PATH) as conn:
        state_counts = get_state_counts(conn)
        w3, w1 = get_waiting(conn)
    low_stock = load_low_stock_top10()

    # Print stdout summary
    print("Workflow counts:")
    for k in sorted(state_counts.keys()):
        print(f"  {k}: {state_counts[k]}")
    print(f"Waiting >3h (WAITING_SIZE_INFO): {len(w3)}")
    print(f"Waiting >1h (WAITING_CONFIRM): {len(w1)}")
    if not low_stock.empty:
        print("Low-stock top-10:")
        print(low_stock.to_string(index=False))

    write_status_md(state_counts, w3, w1, low_stock)
    print(f"Wrote snapshot: {STATUS_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


