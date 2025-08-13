"""
Alert generation (Phase 2).

Rules:
- Any order stuck in WAITING_SIZE_INFO > 12h → alert
- Any SKU with days_cover < 5 in latest low-stock report → alert

Writes alerts/YYYYMMDD_HHMM.md with actionable bullets.
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
ALERTS_DIR = REPO_ROOT / "alerts"


def utcnow() -> datetime:
    return datetime.now(UTC)


def parse_iso_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1]
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except Exception:
        return None


def find_stuck_orders(hours_threshold: float = 12.0) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            "SELECT order_id, state, updated_at, store_name FROM workflows WHERE state='WAITING_SIZE_INFO'",
            conn,
        )
    if df.empty:
        return df
    df["updated_at_parsed"] = df["updated_at"].apply(parse_iso_utc)
    df["age_hours"] = df["updated_at_parsed"].apply(
        lambda d: (utcnow() - d).total_seconds() / 3600 if d else 0
    )
    return df[df["age_hours"] > hours_threshold].copy()


def load_low_stock_below(days_cover_threshold: float = 5.0) -> pd.DataFrame:
    files = sorted(glob.glob(str(REPORTS_DIR / "low_stock_*.csv")))
    if not files:
        return pd.DataFrame(columns=["sku", "days_cover", "velocity_14d", "stock_now", "reorder_qty"]).head(0)
    latest = files[-1]
    df = pd.read_csv(latest)
    df.columns = [c.strip().lower() for c in df.columns]
    # Harmonize column names
    sku_col = None
    for cand in ("sku_id/sku_key", "sku_id_or_key", "sku_id", "sku_key"):
        if cand in df.columns:
            sku_col = cand
            break
    if sku_col is None:
        return pd.DataFrame(columns=["sku", "days_cover", "velocity_14d", "stock_now", "reorder_qty"]).head(0)
    df = df.rename(columns={sku_col: "sku"})
    for col in ("days_cover", "velocity_14d", "stock_now", "reorder_qty"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "days_cover" not in df.columns:
        return pd.DataFrame(columns=["sku", "days_cover", "velocity_14d", "stock_now", "reorder_qty"]).head(0)
    return df[df["days_cover"] < days_cover_threshold].copy().sort_values("days_cover")


def write_alerts(stuck: pd.DataFrame, low_stock: pd.DataFrame) -> Path:
    ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = utcnow().strftime("%Y%m%d_%H%M")
    out_path = ALERTS_DIR / f"{ts}.md"
    lines: list[str] = []
    lines.append(f"# Alerts — {utcnow().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("## Stuck orders (>12h in WAITING_SIZE_INFO)")
    if stuck.empty:
        lines.append("- None")
    else:
        for _, r in stuck.iterrows():
            lines.append(
                f"- Order {r.get('order_id')} at store '{r.get('store_name','')}', age ~ {r.get('age_hours'):.1f}h — action: remind customer and escalate"
            )
    lines.append("")
    lines.append("## Low stock (<5 days cover)")
    if low_stock.empty:
        lines.append("- None")
    else:
        for _, r in low_stock.iterrows():
            lines.append(
                f"- {r.get('sku')} cover {r.get('days_cover'):.1f}d, v14d={int(r.get('velocity_14d') or 0)}, stock={int(r.get('stock_now') or 0)}, reorder={int(r.get('reorder_qty') or 0)} — action: reorder plan"
            )
    lines.append("")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def main() -> int:
    stuck = find_stuck_orders(12.0)
    low = load_low_stock_below(5.0)
    path = write_alerts(stuck, low)
    print(f"Alerts written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


