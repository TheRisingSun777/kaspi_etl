#!/usr/bin/env python3

import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATA_CRM = Path("data_crm")
PROCESSED_LATEST = DATA_CRM / "processed_sales_latest.csv"
EXPORTS_DIR = DATA_CRM / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    HAVE_REPORTLAB = True
except Exception:
    HAVE_REPORTLAB = False


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def sanitize(value: str) -> str:
    if value is None:
        return ""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())[:80]


def group_key_columns(df: pd.DataFrame) -> List[str]:
    cols = ["sku_key", "my_size"]
    if "color" in df.columns:
        cols.append("color")
    return cols


def build_group_title(key: Tuple) -> str:
    # key order: sku_key, my_size[, color]
    if len(key) == 3:
        return f"{key[0]}  |  size {key[1]}  |  color {key[2]}"
    return f"{key[0]}  |  size {key[1]}"


def write_group_csv(df: pd.DataFrame, key: Tuple) -> Path:
    sku_key = sanitize(key[0])
    my_size = sanitize(key[1])
    color_suffix = f"_{sanitize(key[2])}" if len(key) == 3 and key[2] else ""
    out_csv = EXPORTS_DIR / f"pack_{sku_key}_{my_size}{color_suffix}.csv"
    # Keep practical columns for packers
    cols = [
        "orderid",
        "date",
        "store_name",
        "qty",
        "sell_price",
        "sku_id",
        "ksp_sku_id",
    ]
    present = [c for c in cols if c in df.columns]
    df[present].to_csv(out_csv, index=False)
    return out_csv


def draw_table_page(
    c: canvas.Canvas, title: str, rows: List[Tuple[str, str, str, int, float]], page: int
) -> None:
    width, height = A4
    y_start = height - 20 * mm
    line_height = 6 * mm

    c.setFont("Helvetica-Bold", 13)
    c.drawString(20 * mm, y_start, f"Pack list — {title}")

    c.setFont("Helvetica", 10)
    y = y_start - 10 * mm
    c.drawString(20 * mm, y, "ORDERID")
    c.drawString(60 * mm, y, "STORE")
    c.drawRightString(140 * mm, y, "QTY")
    c.drawRightString(190 * mm, y, "PRICE")
    y -= 5 * mm

    rows_per_page = int((y - 15 * mm) // line_height)
    idx = 0
    while idx < len(rows):
        c.setFont("Helvetica", 10)
        for _ in range(rows_per_page):
            if idx >= len(rows):
                break
            orderid, date, store, qty, price = rows[idx]
            c.drawString(20 * mm, y, str(orderid))
            c.drawString(60 * mm, y, str(store)[:40])
            c.drawRightString(140 * mm, y, str(int(qty)))
            c.drawRightString(190 * mm, y, f"{price:,.0f}")
            y -= line_height
            idx += 1
        c.setFont("Helvetica", 8)
        c.drawRightString(200 * mm, 10 * mm, f"Page {page}")
        page += 1
        if idx < len(rows):
            c.showPage()
            y = y_start - 10 * mm
        else:
            break


def write_group_pdf(df: pd.DataFrame, key: Tuple) -> Optional[Path]:
    if not HAVE_REPORTLAB:
        return None
    sku_key = sanitize(key[0])
    my_size = sanitize(key[1])
    color_suffix = f"_{sanitize(key[2])}" if len(key) == 3 and key[2] else ""
    pdf_path = EXPORTS_DIR / f"pack_{sku_key}_{my_size}{color_suffix}.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    title = build_group_title(key)
    rows = [
        (
            str(r.get("orderid", "")),
            str(r.get("date", "")),
            str(r.get("store_name", "")),
            int(pd.to_numeric(r.get("qty", 1), errors="coerce") or 1),
            float(pd.to_numeric(r.get("sell_price", 0), errors="coerce") or 0),
        )
        for _, r in df.iterrows()
    ]
    draw_table_page(c, title, rows, page=1)
    c.save()
    return pdf_path


def write_combined_pdf(
    pages: List[Tuple[str, List[Tuple[str, str, str, int, float]]]],
) -> Optional[Path]:
    if not HAVE_REPORTLAB:
        return None
    out_pdf = EXPORTS_DIR / "pack_all_groups.pdf"
    c = canvas.Canvas(str(out_pdf), pagesize=A4)
    page_no = 1
    for title, rows in pages:
        draw_table_page(c, title, rows, page=page_no)
        c.showPage()
        page_no += 1
    c.save()
    return out_pdf


def main() -> int:
    if not PROCESSED_LATEST.exists():
        logger.error("Processed sales CSV not found: %s", PROCESSED_LATEST)
        return 1

    df = pd.read_csv(PROCESSED_LATEST)
    df = normalize_columns(df)

    for col in ["sku_key", "my_size"]:
        if col not in df.columns:
            df[col] = ""

    group_cols = group_key_columns(df)
    grouped = df.groupby(group_cols, dropna=False)

    combined_pages: List[Tuple[str, List[Tuple[str, str, str, int, float]]]] = []
    manifest_lines: List[str] = []

    for key, gdf in grouped:
        key_tuple = key if isinstance(key, tuple) else (key,)
        title = build_group_title(key_tuple)
        out_csv = write_group_csv(gdf, key_tuple)
        manifest_lines.append(f"CSV: {out_csv.name} — {len(gdf)} rows — {title}")
        if HAVE_REPORTLAB:
            pdf_path = write_group_pdf(gdf, key_tuple)
            manifest_lines.append(f"PDF: {pdf_path.name}")
        rows = [
            (
                str(r.get("orderid", "")),
                str(r.get("date", "")),
                str(r.get("store_name", "")),
                int(pd.to_numeric(r.get("qty", 1), errors="coerce") or 1),
                float(pd.to_numeric(r.get("sell_price", 0), errors="coerce") or 0),
            )
            for _, r in gdf.iterrows()
        ]
        combined_pages.append((title, rows))

    combined_pdf: Optional[Path] = None
    if HAVE_REPORTLAB:
        combined_pdf = write_combined_pdf(combined_pages)

    manifest_path = EXPORTS_DIR / "pack_manifest.txt"
    with manifest_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(manifest_lines) + "\n")
        if combined_pdf:
            f.write(f"COMBINED: {combined_pdf.name}\n")

    print(str(manifest_path))
    if combined_pdf:
        print(str(combined_pdf))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
