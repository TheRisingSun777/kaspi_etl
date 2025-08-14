#!/usr/bin/env python3
"""
Group Kaspi label PDFs by (sku_key, my_size) using orders staging.

Changes:
- Extract order number from PDF filename: longest run of 7–12 digits
- Normalize orders_api_latest.csv.orderid and left-join to get (sku_key, my_size)
- Group by (sku_key, my_size); merge PDFs in stable sort by orderid ascending
- Output under data_crm/labels_grouped/${OUT_DATE}/ with file name pattern:
  {clean_model}_{my_size}-{count}.pdf where clean_model is the first token of sku_key
- Write manifest.csv: [group_pdf, count, sku_key, my_size, orderids]
- Write unmatched_files.txt for PDFs with no order match
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List, Optional, Tuple

import pandas as pd
from pypdf import PdfReader, PdfWriter


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CRM = REPO_ROOT / "data_crm"


FILENAME_ORDER_RE = re.compile(r"(\d{9,})")


def find_orders_csv() -> Optional[Path]:
    latest = DATA_CRM / "orders_api_latest.csv"
    if latest.exists():
        return latest
    # Fallbacks: newest active_orders CSV/XLSX
    cands = sorted(DATA_CRM.glob("active_orders_*.csv"))
    if cands:
        return cands[-1]
    cands_x = sorted(DATA_CRM.glob("active_orders_*.xlsx"))
    if cands_x:
        return cands_x[-1]
    return None


def lower_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def load_orders_staging() -> pd.DataFrame:
    p = find_orders_csv()
    if not p:
        return pd.DataFrame()
    if p.suffix.lower() == ".xlsx":
        df = pd.read_excel(p, dtype=str)
    else:
        df = pd.read_csv(p, dtype=str)
    df = lower_cols(df)
    for col in ["orderid", "sku_key", "my_size"]:
        if col not in df.columns:
            df[col] = ""
    for c in ["orderid", "sku_key", "my_size"]:
        df[c] = df[c].astype(str).str.strip()
    return df


def extract_orderid_from_filename(pdf_path: Path) -> Optional[str]:
    name = pdf_path.name
    matches = FILENAME_ORDER_RE.findall(name)
    if not matches:
        return None
    # Choose the longest; if tie, first occurrence
    matches.sort(key=lambda s: (-len(s), name.find(s)))
    return matches[0]


def extract_first_page_text(pdf_path: Path) -> str:
    # No longer used for order id extraction; retained for potential diagnostics
    try:
        reader = PdfReader(str(pdf_path))
        if not reader.pages:
            return ""
        return reader.pages[0].extract_text() or ""
    except Exception:
        return ""


def safe_slug(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9_.-]", "", s)
    return s or "UNKNOWN"


@dataclass
class MatchResult:
    orderid: str
    sku_key: str
    my_size: str


def merge_group(paths: List[Path], dest: Path) -> None:
    writer = PdfWriter()
    for p in paths:
        try:
            reader = PdfReader(str(p))
            for page in reader.pages:
                writer.add_page(page)
        except Exception:
            continue
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        writer.write(f)


def group_labels(input_path: Path, out_date: Optional[str], verbose: bool = False) -> Tuple[Path, Path]:
    orders_df = load_orders_staging()
    if orders_df.empty:
        raise FileNotFoundError("Orders staging file not found (orders_api_latest.csv or active_orders_*)")

    # Prepare source PDFs
    tmpdir_obj: Optional[TemporaryDirectory] = None
    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        tmpdir_obj = TemporaryDirectory()
        holder_dir = Path(tmpdir_obj.name)
        shutil.unpack_archive(str(input_path), extract_dir=str(holder_dir))
        pdfs = sorted([p for p in holder_dir.rglob("*.pdf") if p.is_file()])
    elif input_path.is_dir():
        holder_dir = input_path
        pdfs = sorted([p for p in holder_dir.rglob("*.pdf") if p.is_file()])
    else:
        raise FileNotFoundError(f"Input path not found or unsupported: {input_path}")

    out_dir = DATA_CRM / "labels_grouped" / (out_date or pd.Timestamp.utcnow().strftime("%Y-%m-%d"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build mapping from orderid -> (sku_key, my_size)
    orders_map: Dict[str, Tuple[str, str]] = {}
    for _, r in orders_df.iterrows():
        oid = str(r.get("orderid", "")).strip()
        if not oid:
            continue
        sku_key = str(r.get("sku_key", "")).strip()
        my_size = str(r.get("my_size", "")).strip()
        if oid not in orders_map:
            orders_map[oid] = (sku_key, my_size)

    # Collect matches
    groups: Dict[Tuple[str, str], List[Tuple[str, Path]]] = {}
    manifest_rows: List[Dict[str, str]] = []
    unmatched: List[str] = []
    for pdf in pdfs:
        oid = extract_orderid_from_filename(pdf)
        if not oid or oid not in orders_map:
            unmatched.append(pdf.name)
            continue
        sku_key, my_size = orders_map[oid]
        groups.setdefault((sku_key, my_size), []).append((oid, pdf))
        manifest_rows.append(
            {
                "pdf_file": pdf.name,
                "orderid": oid,
                "sku_key": sku_key,
                "my_size": my_size,
            }
        )

    # Write merged PDFs with specified naming and order
    for (sku_key, my_size), items in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        # Stable sort by orderid ascending (numeric if possible)
        def sort_key(t: Tuple[str, Path]):
            oid = t[0]
            try:
                return int(oid)
            except Exception:
                return oid
        items_sorted = sorted(items, key=sort_key)
        count = len(items_sorted)
        out_name = f"{safe_slug(sku_key)}_{safe_slug(my_size or 'UNK')}-{count}.pdf"
        dest = out_dir / out_name
        merge_group([p for _, p in items_sorted], dest)

    # Write manifest
    manifest_csv = out_dir / "manifest.csv"
    with manifest_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["orderid", "filename", "sku_key", "my_size", "group_pdf", "matched"],
        )
        writer.writeheader()
        # matched rows
        for (sku_key, my_size), items in sorted(groups.items()):
            count = len(items)
            group_pdf = f"{safe_slug(sku_key)}_{safe_slug(my_size or 'UNK')}-{count}.pdf"
            for oid, pdf in items:
                writer.writerow(
                    {
                        "orderid": oid,
                        "filename": pdf.name,
                        "sku_key": sku_key,
                        "my_size": my_size,
                        "group_pdf": group_pdf,
                        "matched": True,
                    }
                )
        # unmatched rows
        for name in sorted(unmatched):
            writer.writerow(
                {
                    "orderid": "",
                    "filename": name,
                    "sku_key": "",
                    "my_size": "",
                    "group_pdf": "",
                    "matched": False,
                }
            )

    # Write unmatched
    if unmatched:
        (out_dir / "unmatched_files.txt").write_text("\n".join(sorted(unmatched)), encoding="utf-8")

    if tmpdir_obj is not None:
        try:
            tmpdir_obj.cleanup()
        except Exception:
            pass

    return out_dir, manifest_csv


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Group Kaspi label PDFs by (sku_key, my_size)")
    p.add_argument("--input", required=True, help="Path to ZIP file or directory of PDFs")
    p.add_argument("--out-date", default=None, help="Output date tag (YYYY-MM-DD)")
    p.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    in_path = Path(args.input)
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    try:
        out_dir, manifest_csv = group_labels(in_path, args.out_date, verbose=args.verbose)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    print(str(manifest_csv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


