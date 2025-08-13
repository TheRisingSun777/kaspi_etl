"""
Phase 1 data validation.

Checks:
- Processed sales completeness: percent rows with non-empty sku_id ≥ 95%
- No negative stock in stock_on_hand_updated.csv
- Unknown sku_id count from missing_skus.csv (informational)

Outputs:
- data_crm/reports/validation_report.md (PASS/FAIL summary)
- Exits non-zero if any critical check fails (completeness or negative stock)

Run:
  ./venv/bin/python scripts/validate_phase1_data.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CRM = REPO_ROOT / "data_crm"
PROCESSED_CSV = DATA_CRM / "processed_sales_20250813.csv"
STOCK_UPDATED_CSV = DATA_CRM / "stock_on_hand_updated.csv"
MISSING_SKUS_CSV = DATA_CRM / "missing_skus.csv"
REPORTS_DIR = DATA_CRM / "reports"
REPORT_MD = REPORTS_DIR / "validation_report.md"


def choose_stock_qty_column(df: pd.DataFrame) -> str:
    candidates = [
        "qty",
        "quantity",
        "stock",
        "on_hand",
        "stock_on_hand",
        "available",
        "qty_available",
    ]
    for name in candidates:
        if name in df.columns:
            return name
    df["qty"] = 0
    return "qty"


@dataclass
class ValidationResult:
    completeness_ok: bool
    completeness_pct: float
    negative_stock_ok: bool
    negative_stock_rows: int
    unknown_sku_count: int


def load_processed() -> pd.DataFrame:
    if not PROCESSED_CSV.exists():
        raise FileNotFoundError(f"Missing processed sales: {PROCESSED_CSV}")
    df = pd.read_csv(PROCESSED_CSV)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def load_stock() -> pd.DataFrame:
    if not STOCK_UPDATED_CSV.exists():
        raise FileNotFoundError(f"Missing updated stock: {STOCK_UPDATED_CSV}")
    df = pd.read_csv(STOCK_UPDATED_CSV)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def load_missing_skus() -> Optional[pd.DataFrame]:
    if not MISSING_SKUS_CSV.exists():
        return None
    df = pd.read_csv(MISSING_SKUS_CSV)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def is_non_empty_sku(s: str) -> bool:
    if s is None:
        return False
    val = str(s).strip()
    if not val:
        return False
    if val.lower() in {"nan", "none", "null", "_", "-"}:
        return False
    return True


def validate() -> ValidationResult:
    processed = load_processed()
    stock = load_stock()
    missing_df = load_missing_skus()

    # Completeness
    total_rows = len(processed)
    non_empty = processed.get("sku_id").apply(is_non_empty_sku).sum() if "sku_id" in processed.columns else 0
    completeness_pct = (non_empty / total_rows) * 100 if total_rows > 0 else 0.0
    completeness_ok = completeness_pct >= 95.0

    # Negative stock
    qty_col = choose_stock_qty_column(stock)
    stock[qty_col] = pd.to_numeric(stock[qty_col], errors="coerce").fillna(0)
    negative_rows = int((stock[qty_col] < 0).sum())
    negative_ok = negative_rows == 0

    # Unknown sku count (informational)
    unknown_count = int(len(missing_df)) if missing_df is not None else 0

    return ValidationResult(
        completeness_ok=completeness_ok,
        completeness_pct=completeness_pct,
        negative_stock_ok=negative_ok,
        negative_stock_rows=negative_rows,
        unknown_sku_count=unknown_count,
    )


def write_report(result: ValidationResult) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append(f"# Phase 1 Validation — {datetime.utcnow().isoformat(timespec='seconds')}Z")
    lines.append("")
    lines.append(f"- Processed sales completeness (sku_id present ≥95%): {'✅ PASS' if result.completeness_ok else '❌ FAIL'} — {result.completeness_pct:.2f}%")
    lines.append(f"- Negative stock present: {'✅ PASS (none)' if result.negative_stock_ok else f'❌ FAIL ({result.negative_stock_rows} rows)'}")
    lines.append(f"- Unknown sku_id (from missing_skus.csv): {result.unknown_sku_count}")
    lines.append("")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    result = validate()
    write_report(result)
    # Exit non-zero on critical failures
    if not result.completeness_ok or not result.negative_stock_ok:
        print("Validation failed. See report:", REPORT_MD)
        return 1
    print("Validation passed. See report:", REPORT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


