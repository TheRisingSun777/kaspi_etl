"""
Build packing PDFs for CONFIRMED orders, split by store_name.

Filters only workflows.state = 'CONFIRMED'.
Outputs under data_crm/labels/<store_name>/packing_YYYY-MM-DD.pdf
Adds barcode/QR for order_id if reportlab barcode is available; otherwise skips.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "db" / "erp.db"
OUT_ROOT = REPO_ROOT / "data_crm" / "labels"


def load_confirmed_orders() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            """
            SELECT o.order_id, o.order_date, o.store_name, o.sku_name_raw, o.qty
            FROM orders o
            JOIN workflows w ON w.order_id = o.order_id
            WHERE w.state = 'CONFIRMED'
            ORDER BY o.store_name, o.order_date, o.order_id
            """,
            conn,
        )
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def ensure_pkg() -> tuple:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
        try:
            from reportlab.graphics.barcode import code128, qr
        except Exception:
            code128 = None
            qr = None
        return A4, mm, canvas, code128, qr
    except Exception as exc:
        raise SystemExit("reportlab is required to build PDFs. Install via requirements.txt") from exc


def draw_label(c, mm, order_id: str, sku_name: str, qty: int, store_name: str, code128, qr):
    c.setFont("Helvetica-Bold", 16)
    c.drawString(10 * mm, 270 * mm, f"Store: {store_name}")
    c.setFont("Helvetica", 12)
    c.drawString(10 * mm, 260 * mm, f"Order: {order_id}")
    c.drawString(10 * mm, 250 * mm, f"Item: {sku_name}")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(10 * mm, 238 * mm, f"Qty: {int(qty)}")

    # Barcodes if available
    y_bar = 220 * mm
    if code128 is not None:
        try:
            bc = code128.Code128(order_id, barHeight=15 * mm, barWidth=0.4)
            bc.drawOn(c, 10 * mm, y_bar)
            y_bar -= 20 * mm
        except Exception:
            pass
    if qr is not None:
        try:
            q = qr.QrCodeWidget(order_id)
            from reportlab.graphics.shapes import Drawing
            b = 30 * mm
            d = Drawing(b, b)
            d.add(q)
            # render to canvas
            from reportlab.graphics import renderPDF
            renderPDF.draw(d, c, 10 * mm, y_bar)
        except Exception:
            pass


def build_pdfs(df: pd.DataFrame) -> list[Path]:
    A4, mm, canvas, code128, qr = ensure_pkg()
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    out_files: list[Path] = []
    today = datetime.now().strftime("%Y-%m-%d")
    for store, g in df.groupby("store_name", dropna=False):
        store_dir = OUT_ROOT / (store or "UNKNOWN")
        store_dir.mkdir(parents=True, exist_ok=True)
        out_path = store_dir / f"packing_{today}.pdf"
        c = canvas.Canvas(str(out_path), pagesize=A4)
        for _, row in g.iterrows():
            draw_label(
                c,
                mm,
                order_id=str(row.get("order_id", "")),
                sku_name=str(row.get("sku_name_raw", "")),
                qty=int(row.get("qty", 0)),
                store_name=str(row.get("store_name", "")),
                code128=code128,
                qr=qr,
            )
            c.showPage()
        c.save()
        out_files.append(out_path)
    return out_files


def main() -> int:
    df = load_confirmed_orders()
    if df.empty:
        print("No CONFIRMED orders found. Skipping PDFs.")
        return 0
    paths = build_pdfs(df)
    for p in paths:
        print(f"Written: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


