#!/usr/bin/env python3
"""
Group Kaspi label PDFs by (sku_key, my_size, color).

Inputs:
- data_crm/labels/YYYY-MM-DD/*.zip (Kaspi label ZIPs)
- data_crm/processed_sales_20250813.csv (to map orderid → sku_key, my_size)

Outputs (per date):
- data_crm/labels_grouped/YYYY-MM-DD/{sku_key}_{size}_{color}.pdf (merged labels)
- data_crm/labels_grouped/YYYY-MM-DD/manifest.csv (group → list of orderids)

Heuristics:
- Extract PDFs from ZIPs to a temp work dir.
- Parse orderid from the PDF filename (digits) or inside PDF text.
- Resolve sku_key/my_size from processed sales by orderid.
- Derive color from sku_key using the last color-like token or last token.
"""

from __future__ import annotations

import csv
import re
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
from pypdf import PdfReader, PdfWriter


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CRM = REPO_ROOT / "data_crm"
LABELS_DIR = DATA_CRM / "labels"
GROUPED_DIR = DATA_CRM / "labels_grouped"
PROCESSED_CSV = DATA_CRM / "processed_sales_20250813.csv"


ORDERID_RE = re.compile(r"\b(\d{6,12})\b")
COLOR_TOKENS = {
    "BLACK", "WHITE", "BLUE", "RED", "GREEN", "GREY", "GRAY", "PINK", "ORANGE",
    "YELLOW", "PURPLE", "BEIGE", "BROWN", "NAVY", "KHAKI", "BURGUNDY", "MAROON",
}


def _infer_date_dir(cli_date: Optional[str]) -> Path:
    if cli_date:
        return LABELS_DIR / cli_date
    # Pick latest YYYY-MM-DD directory
    candidates = [p for p in LABELS_DIR.glob("*/") if p.name[:4].isdigit()]
    if not candidates:
        raise FileNotFoundError(f"No date directories under {LABELS_DIR}")
    return sorted(candidates, key=lambda p: p.name)[-1]


def _extract_zips(zip_dir: Path, work_dir: Path) -> List[Path]:
    work_dir.mkdir(parents=True, exist_ok=True)
    pdfs: List[Path] = []
    for z in sorted(zip_dir.glob("*.zip")):
        try:
            with zipfile.ZipFile(z) as zf:
                for name in zf.namelist():
                    if not name.lower().endswith(".pdf"):
                        continue
                    target = work_dir / Path(name).name
                    with zf.open(name) as src, target.open("wb") as dst:
                        dst.write(src.read())
                    pdfs.append(target)
        except Exception:
            continue
    return pdfs


def _extract_orderid_from_filename(path: Path) -> Optional[str]:
    m = ORDERID_RE.search(path.stem)
    return m.group(1) if m else None


def _extract_orderid_from_pdf(path: Path) -> Optional[str]:
    try:
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        m = ORDERID_RE.search(text)
        return m.group(1) if m else None
    except Exception:
        return None


def _derive_color_from_sku_key(sku_key: str) -> str:
    tokens = [t for t in str(sku_key).split("_") if t]
    for tok in reversed(tokens):
        up = tok.upper()
        if up in COLOR_TOKENS:
            return up
    # fallback to last token if looks like a color-ish word
    return tokens[-1].upper() if tokens else "UNK"


def _load_processed_sales() -> pd.DataFrame:
    if not PROCESSED_CSV.exists():
        raise FileNotFoundError(f"Missing processed sales CSV: {PROCESSED_CSV}")
    df = pd.read_csv(PROCESSED_CSV, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def _build_orderid_map(df: pd.DataFrame) -> Dict[str, Tuple[str, str]]:
    mapping: Dict[str, Tuple[str, str]] = {}
    if "orderid" not in df.columns:
        return mapping
    for _, row in df.iterrows():
        orderid = str(row.get("orderid", "")).strip()
        if not orderid:
            continue
        mapping[orderid] = (
            str(row.get("sku_key", "")).strip(),
            str(row.get("my_size", "")).strip(),
        )
    return mapping


def _merge_pdfs(sources: List[Path], dest: Path) -> None:
    writer = PdfWriter()
    for src in sources:
        try:
            reader = PdfReader(str(src))
            for page in reader.pages:
                writer.add_page(page)
        except Exception:
            continue
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        writer.write(f)


def group_labels_for_date(date_str: Optional[str] = None) -> Tuple[int, Path]:
    date_dir = _infer_date_dir(date_str)
    out_dir = GROUPED_DIR / date_dir.name
    work_dir = date_dir / "_extracted"

    pdfs = _extract_zips(date_dir, work_dir)
    if not pdfs:
        print(f"No PDFs extracted from ZIPs in {date_dir}")
        return 0, out_dir

    processed_df = _load_processed_sales()
    order_map = _build_orderid_map(processed_df)

    groups: Dict[Tuple[str, str, str], List[Tuple[str, Path]]] = defaultdict(list)

    for pdf in pdfs:
        orderid = _extract_orderid_from_filename(pdf)
        if not orderid:
            orderid = _extract_orderid_from_pdf(pdf)
        if not orderid:
            continue
        sku_key, size = order_map.get(orderid, ("", ""))
        if not sku_key:
            # cannot resolve, skip
            continue
        color = _derive_color_from_sku_key(sku_key)
        groups[(sku_key, size, color)].append((orderid, pdf))

    # Write grouped PDFs and manifest
    manifest_rows: List[Dict[str, str]] = []
    for (sku_key, size, color), items in sorted(groups.items()):
        items_sorted = sorted(items, key=lambda t: t[0])
        target_pdf = out_dir / f"{sku_key}_{size}_{color}.pdf"
        _merge_pdfs([p for _, p in items_sorted], target_pdf)
        manifest_rows.append(
            {
                "sku_key": sku_key,
                "my_size": size,
                "color": color,
                "count": str(len(items_sorted)),
                "group_pdf": str(target_pdf.relative_to(REPO_ROOT)),
                "orders": ";".join([oid for oid, _ in items_sorted]),
            }
        )

    manifest_path = out_dir / "manifest.csv"
    out_dir.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["sku_key", "my_size", "color", "count", "group_pdf", "orders"])
        writer.writeheader()
        for row in manifest_rows:
            writer.writerow(row)

    print(f"Grouped {sum(int(r['count']) for r in manifest_rows)} labels into {len(manifest_rows)} PDFs → {out_dir}")
    return len(manifest_rows), out_dir


def main() -> int:
    # Optional env var or pass date via CLI in the future; for now autodetect latest
    try:
        _, _ = group_labels_for_date()
    except FileNotFoundError as exc:
        print(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


