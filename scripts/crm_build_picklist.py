"""
Build warehouse picklist from processed sales (Phase 1).

Input:
- data_crm/processed_sales_20250813.csv

Output:
- data_crm/picklist/YYYY-MM-DD/picklist.csv
- Optional: picklist.pdf (one page per 40 rows) with total items (if reportlab is installed)

Run:
  ./venv/bin/python scripts/crm_build_picklist.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = REPO_ROOT / "data_crm" / "processed_sales_20250813.csv"
PICKLIST_ROOT = REPO_ROOT / "data_crm" / "picklist"


def load_sales(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing processed sales CSV: {path}")
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    # Ensure required columns
    for col in ["sku_key", "my_size", "qty"]:
        if col not in df.columns:
            df[col] = pd.NA
    df["sku_key"] = df["sku_key"].astype(str)
    df["my_size"] = df["my_size"].astype(str)
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0).astype(int)
    return df


def build_picklist(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby(["sku_key", "my_size"], dropna=False)["qty"].sum().reset_index()
        .rename(columns={"qty": "total_qty"})
        .sort_values(["sku_key", "my_size"])
    )
    return grouped


def write_csv(df: pd.DataFrame, day_dir: Path) -> Path:
    out_csv = day_dir / "picklist.csv"
    day_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    return out_csv


def write_pdf_if_possible(df: pd.DataFrame, day_dir: Path) -> Path | None:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except Exception:
        return None

    pdf_path = day_dir / "picklist.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4

    rows_per_page = 40
    y_start = height - 20 * mm
    line_height = 6 * mm

    total_items = int(pd.to_numeric(df["total_qty"], errors="coerce").fillna(0).sum())
    page = 1
    row_idx = 0
    while row_idx < len(df):
        c.setFont("Helvetica-Bold", 14)
        c.drawString(20 * mm, y_start, f"Picklist — {datetime.now().strftime('%Y-%m-%d')} (Total items: {total_items})")
        c.setFont("Helvetica", 10)
        y = y_start - 10 * mm
        c.drawString(20 * mm, y, "SKU_KEY")
        c.drawString(100 * mm, y, "SIZE")
        c.drawString(140 * mm, y, "QTY")
        y -= 6 * mm

        for _ in range(rows_per_page):
            if row_idx >= len(df):
                break
            r = df.iloc[row_idx]
            c.drawString(20 * mm, y, str(r["sku_key"]))
            c.drawString(100 * mm, y, str(r["my_size"]))
            c.drawRightString(150 * mm, y, str(int(r["total_qty"])) )
            y -= line_height
            row_idx += 1

        c.setFont("Helvetica", 8)
        c.drawRightString(200 * mm, 10 * mm, f"Page {page}")
        c.showPage()
        page += 1

    c.save()
    return pdf_path


def main() -> int:
    df = load_sales(INPUT_CSV)
    pick = build_picklist(df)
    day_dir = PICKLIST_ROOT / datetime.now().strftime("%Y-%m-%d")
    out_csv = write_csv(pick, day_dir)
    out_pdf = write_pdf_if_possible(pick, day_dir)
    if out_pdf is not None:
        print(f"Picklist written: {out_csv} and {out_pdf}")
    else:
        print(f"Picklist written: {out_csv} (PDF skipped — reportlab not installed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


