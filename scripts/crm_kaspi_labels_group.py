#!/usr/bin/env python3
"""
Group Kaspi label PDFs by (sku_key, my_size or rec_size) using processed sales.

Features:
- Accepts INPUT path: ZIP of PDFs or a folder containing PDFs
- Builds orderid -> row mapping from processed_sales_latest.csv or newest processed/ file
- Extracts order id from first-page text via regex (digits 6-9, and Russian prefixes)
- Fallback matching by join_code or product_master_code if present in processed CSV and detected in text
- Groups by f"{sku_key}_{my_size or rec_size}", merges into one PDF per group
- Writes manifest.csv and unmatched_files.txt with reasons
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


ORDER_RE = re.compile(r"\b(\d{6,9})\b")
PREFIX_RE = re.compile(r"(?i)(?:№\s*заказа|номер\s*заказа)\D{0,5}(\d{6,9})")


def find_processed_csv() -> Optional[Path]:
    latest = DATA_CRM / "processed_sales_latest.csv"
    if latest.exists():
        return latest
    proc_dir = DATA_CRM / "processed"
    cands = sorted(proc_dir.glob("processed_sales_*.csv"))
    return cands[-1] if cands else None


def lower_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def load_processed() -> pd.DataFrame:
    p = find_processed_csv()
    if not p:
        return pd.DataFrame()
    df = pd.read_csv(p, dtype=str)
    df = lower_cols(df)
    for col in ["orderid", "sku_key", "my_size", "join_code", "product_master_code", "rec_size"]:
        if col not in df.columns:
            df[col] = ""
    # Normalize
    for c in ["orderid", "sku_key", "my_size", "join_code", "product_master_code", "rec_size"]:
        df[c] = df[c].astype(str).str.strip()
    return df


def load_rec_size_map() -> Dict[str, str]:
    x = DATA_CRM / "orders_kaspi_with_sizes.xlsx"
    if not x.exists():
        return {}
    try:
        df = pd.read_excel(x, dtype=str)
        df = lower_cols(df)
        if "orderid" in df.columns and "rec_size" in df.columns:
            df["orderid"] = df["orderid"].astype(str).str.strip()
            df["rec_size"] = df["rec_size"].astype(str).str.strip()
            mp = {}
            for _, r in df.iterrows():
                oid = str(r.get("orderid", "")).strip()
                rec = str(r.get("rec_size", "")).strip()
                if oid and rec:
                    mp[oid] = rec
            return mp
    except Exception:
        return {}
    return {}


def extract_first_page_text(pdf_path: Path) -> str:
    try:
        reader = PdfReader(str(pdf_path))
        if not reader.pages:
            return ""
        return reader.pages[0].extract_text() or ""
    except Exception:
        return ""


def find_orderid_in_text(text: str) -> Optional[str]:
    if not text:
        return None
    m = PREFIX_RE.search(text)
    if m:
        return m.group(1)
    m2 = ORDER_RE.search(text)
    if m2:
        return m2.group(1)
    return None


def safe_slug(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9_.-]", "", s)
    return s or "UNKNOWN"


@dataclass
class MatchResult:
    orderid: str
    sku_key: str
    size: str
    method: str


def match_pdf_to_row(text: str, processed_df: pd.DataFrame, rec_map: Dict[str, str]) -> Tuple[Optional[MatchResult], Optional[str]]:
    # 1) Strict order id
    oid = find_orderid_in_text(text)
    if oid:
        row = processed_df.loc[processed_df["orderid"] == oid]
        if not row.empty:
            r = row.iloc[0]
            size = str(r.get("my_size", "")).strip() or rec_map.get(oid, "")
            return MatchResult(orderid=oid, sku_key=str(r.get("sku_key", "")).strip(), size=str(size or ""), method="orderid"), None
        # oid found but not in processed
        return None, "order id not in processed"

    # 2) Fallback tokens: join_code or product_master_code found in text
    text_lc = text.lower()
    for col, method in [("join_code", "join_code"), ("product_master_code", "product_master_code")]:
        if col in processed_df.columns:
            # collect unique non-empty tokens
            tokens = processed_df[col].astype(str).str.strip()
            tokens = tokens[tokens != ""].drop_duplicates()
            # check which tokens appear in text
            hits = [t for t in tokens if t.lower() in text_lc]
            if len(hits) == 1:
                row = processed_df.loc[processed_df[col].astype(str).str.strip().str.lower() == hits[0].lower()]
                if not row.empty:
                    r = row.iloc[0]
                    oid2 = str(r.get("orderid", "")).strip()
                    size = str(r.get("my_size", "")).strip() or (rec_map.get(oid2, "") if oid2 else "")
                    return MatchResult(orderid=oid2, sku_key=str(r.get("sku_key", "")).strip(), size=str(size or ""), method=method), None
    return None, "no order id found"


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


def group_labels(input_path: Path, out_date: Optional[str]) -> Tuple[Path, Path]:
    processed_df = load_processed()
    if processed_df.empty:
        raise FileNotFoundError("Processed sales CSV not found")
    rec_map = load_rec_size_map()

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

    # Collect matches
    groups: Dict[str, List[Path]] = {}
    manifest_rows: List[Dict[str, str]] = []
    unmatched: List[str] = []
    for pdf in pdfs:
        text = extract_first_page_text(pdf)
        match, reason = match_pdf_to_row(text, processed_df, rec_map)
        if match:
            size_key = match.size or rec_map.get(match.orderid, "") or "UNK"
            group_key = f"{match.sku_key}_{size_key}"
            groups.setdefault(group_key, []).append(pdf)
            manifest_rows.append(
                {
                    "pdf_file": str(pdf.relative_to(REPO_ROOT)) if pdf.is_relative_to(REPO_ROOT) else str(pdf),
                    "orderid": match.orderid,
                    "sku_key": match.sku_key,
                    "my_size": str(processed_df.loc[processed_df["orderid"] == match.orderid].iloc[0].get("my_size", "")) if match.orderid else "",
                    "rec_size": rec_map.get(match.orderid, ""),
                    "group_key": group_key,
                    "match_method": match.method,
                }
            )
        else:
            unmatched.append(f"{pdf.name}\t{reason or 'unknown'}")

    # Write merged PDFs
    for group_key, paths in sorted(groups.items()):
        dest = out_dir / f"{safe_slug(group_key)}.pdf"
        merge_group(paths, dest)

    # Write manifest
    manifest_csv = out_dir / "manifest.csv"
    with manifest_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["pdf_file", "orderid", "sku_key", "my_size", "rec_size", "group_key", "match_method"],
        )
        writer.writeheader()
        for row in manifest_rows:
            writer.writerow(row)

    # Write unmatched
    if unmatched:
        (out_dir / "unmatched_files.txt").write_text("\n".join(unmatched), encoding="utf-8")

    if tmpdir_obj is not None:
        try:
            tmpdir_obj.cleanup()
        except Exception:
            pass

    return out_dir, manifest_csv


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Group Kaspi label PDFs by processed sales")
    p.add_argument("--input", required=True, help="Path to ZIP file or directory of PDFs")
    p.add_argument("--out-date", default=None, help="Output date tag (YYYY-MM-DD)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    in_path = Path(args.input)
    try:
        out_dir, manifest_csv = group_labels(in_path, args.out_date)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    print(str(manifest_csv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


