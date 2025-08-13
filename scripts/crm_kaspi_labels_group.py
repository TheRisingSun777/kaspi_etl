#!/usr/bin/env python3
"""
Group Kaspi PDF labels by (sku_key, my_size) using processed sales mapping.

Usage:
  ./venv/bin/python scripts/crm_kaspi_labels_group.py --input waybill-327.zip \
      [--processed data_crm/processed_sales_latest.csv] [--out-date 2025-08-13]

- Accepts either a ZIP archive of label PDFs or a directory containing PDFs.
- Reads processed sales CSV to map orderid -> (sku_key, my_size).
- For each group, merges PDFs into data_crm/labels_grouped/YYYY-MM-DD/{sku_key}_{my_size}.pdf
- Writes a manifest CSV with group counts and output paths.
"""

import argparse
import csv
import logging
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
from pypdf import PdfReader, PdfWriter


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CRM = REPO_ROOT / "data_crm"
DEFAULT_PROCESSED = DATA_CRM / "processed_sales_latest.csv"


def _lower_columns_inplace(df: pd.DataFrame) -> None:
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]


def _safe_slug(text: str) -> str:
    text = (text or "").strip()
    # Replace spaces with underscore, drop unsafe characters
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Za-z0-9_.-]", "", text)
    return text or "UNKNOWN"


def _extract_orderid_from_name(name: str) -> Optional[str]:
    """Extract order id from a label filename using 7+ digit sequence.

    Example: KASPI_SHOP-611444195.pdf -> 611444195
    """
    base = Path(name).stem
    matches = re.findall(r"(\d{7,})", base)
    if not matches:
        return None
    return matches[-1]


def _extract_orderid_from_pdf_text(pdf_path: Path) -> Optional[str]:
    try:
        reader = PdfReader(str(pdf_path))
        if len(reader.pages) == 0:
            return None
        text = reader.pages[0].extract_text() or ""
        m = re.search(r"(\d{7,})", text)
        return m.group(1) if m else None
    except Exception:
        return None


def _find_processed_csv(default_path: Path) -> Path:
    if default_path.exists():
        return default_path
    # Fallback to latest dated processed file
    candidates = sorted((DATA_CRM / "processed").glob("processed_sales_*.csv"))
    if candidates:
        return candidates[-1]
    raise FileNotFoundError(
        f"Processed sales CSV not found. Expected {default_path} or data_crm/processed/processed_sales_*.csv"
    )


def load_order_group_mapping(processed_csv: Path) -> Dict[str, Tuple[str, str]]:
    df = pd.read_csv(processed_csv)
    if df.empty:
        return {}
    _lower_columns_inplace(df)

    for col in ["orderid", "sku_key", "my_size"]:
        if col not in df.columns:
            df[col] = ""

    # Normalize types and whitespace
    df["orderid"] = df["orderid"].astype(str).str.replace(".0", "", regex=False).str.strip()
    df["sku_key"] = df["sku_key"].astype(str).str.strip()
    df["my_size"] = df["my_size"].astype(str).str.strip()

    mapping: Dict[str, Tuple[str, str]] = {}
    # Prefer first non-empty occurrence per orderid
    for _, row in df.iterrows():
        oid = row.get("orderid", "")
        if not oid or oid.lower() in {"nan", "none", "null"}:
            continue
        if oid in mapping:
            # Keep first mapping if existing has non-empty fields
            continue
        sku_key = row.get("sku_key", "") or ""
        my_size = row.get("my_size", "") or ""
        mapping[str(oid)] = (str(sku_key), str(my_size))
    return mapping


def load_api_orders_mapping() -> Dict[str, Tuple[str, str]]:
    """Best-effort mapping from orders_api_latest.csv when processed missing.

    Returns orderid -> (sku_key, my_size)
    """
    api_csv = DATA_CRM / "orders_api_latest.csv"
    if not api_csv.exists():
        return {}
    try:
        df = pd.read_csv(api_csv)
    except Exception:
        return {}
    _lower_columns_inplace(df)
    for col in ["orderid", "sku_key", "my_size", "product_master_code"]:
        if col not in df.columns:
            df[col] = ""
    df["orderid"] = df["orderid"].astype(str).str.replace(".0", "", regex=False).str.strip()
    df["sku_key"] = df["sku_key"].astype(str).str.strip()
    df["my_size"] = df["my_size"].astype(str).str.strip()
    # If sku_key empty but product_master_code present, use it
    df["sku_key"] = df.apply(
        lambda r: r["sku_key"] if str(r["sku_key"]).strip() else str(r.get("product_master_code", "")).strip(),
        axis=1,
    )
    mapping: Dict[str, Tuple[str, str]] = {}
    for _, r in df.iterrows():
        oid = r.get("orderid", "")
        if not oid or oid.lower() in {"nan", "none", "null"}:
            continue
        mapping[str(oid)] = (str(r.get("sku_key", "") or ""), str(r.get("my_size", "") or ""))
    return mapping


@dataclass
class GroupEntry:
    sku_key: str
    my_size: str
    pdf_paths: List[Path]


def merge_group_to_pdf(pdf_paths: Iterable[Path], output_pdf: Path) -> None:
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    for p in pdf_paths:
        reader = PdfReader(str(p))
        for page in reader.pages:
            writer.add_page(page)
    with output_pdf.open("wb") as f:
        writer.write(f)


def discover_label_pdfs_from_dir(input_dir: Path) -> Tuple[Path, List[Path]]:
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Directory not found: {input_dir}")
    pdfs = sorted([p for p in input_dir.rglob("*.pdf") if p.is_file()])
    return input_dir, pdfs


def group_labels(
    input_path: Path,
    processed_csv: Path,
    out_date: Optional[str] = None,
) -> Tuple[Path, List[GroupEntry], Path]:
    processed_csv = _find_processed_csv(processed_csv)
    order_to_group = load_order_group_mapping(processed_csv)
    # Enrich with API orders mapping for any missing orderids
    api_map = load_api_orders_mapping()
    for oid, tup in api_map.items():
        if oid not in order_to_group:
            order_to_group[oid] = tup
    if not order_to_group:
        logger.warning("Processed sales CSV has no mapping rows: %s", processed_csv)

    # Prepare source PDFs, handling ZIP extraction with a temp directory
    tmpdir_obj: Optional[TemporaryDirectory] = None
    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        tmpdir_obj = TemporaryDirectory()
        holder_dir = Path(tmpdir_obj.name)
        shutil.unpack_archive(str(input_path), extract_dir=str(holder_dir))
        pdfs = sorted([p for p in holder_dir.rglob("*.pdf") if p.is_file()])
    elif input_path.is_dir():
        holder_dir, pdfs = discover_label_pdfs_from_dir(input_path)
    else:
        raise FileNotFoundError(f"Input path not found or unsupported: {input_path}")
    logger.info("Found %d PDF labels", len(pdfs))

    # Collect PDFs per group
    group_map: Dict[Tuple[str, str], List[Path]] = {}
    unmatched: List[Path] = []
    for pdf in pdfs:
        oid = _extract_orderid_from_name(pdf.name) or _extract_orderid_from_pdf_text(pdf)
        if not oid or oid not in order_to_group:
            unmatched.append(pdf)
            continue
        sku_key, my_size = order_to_group[oid]
        key = (sku_key or "UNKNOWN", (my_size or "UNK"))
        group_map.setdefault(key, []).append(pdf)

    # Output directory
    date_tag = out_date or pd.Timestamp.utcnow().strftime("%Y-%m-%d")
    out_dir = DATA_CRM / "labels_grouped" / date_tag
    out_dir.mkdir(parents=True, exist_ok=True)

    # Merge and record manifest
    groups: List[GroupEntry] = []
    manifest_rows: List[Dict[str, str]] = []
    for (sku_key, my_size_key), paths in sorted(group_map.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        safe_name = f"{_safe_slug(sku_key)}_{_safe_slug(my_size_key)}".strip("_")
        output_pdf = out_dir / f"{safe_name}.pdf"
        merge_group_to_pdf(paths, output_pdf)
        groups.append(GroupEntry(sku_key=sku_key, my_size=my_size_key, pdf_paths=paths))
        for p in paths:
            oid = _extract_orderid_from_name(p.name) or _extract_orderid_from_pdf_text(p) or ""
            manifest_rows.append(
                {
                    "pdf_file": str(p.relative_to(REPO_ROOT)) if p.is_relative_to(REPO_ROOT) else str(p),
                    "orderid": oid,
                    "sku_key": sku_key,
                    "my_size": my_size_key if my_size_key else "UNK",
                    "group_file": str(output_pdf.relative_to(REPO_ROOT)),
                }
            )

    # Write manifest
    manifest_csv = out_dir / "manifest.csv"
    with manifest_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["pdf_file", "orderid", "sku_key", "my_size", "group_file"])
        writer.writeheader()
        for row in manifest_rows:
            writer.writerow(row)

    # Also write unmatched list for operator visibility
    if unmatched:
        unmatched_txt = out_dir / "unmatched_files.txt"
        unmatched_txt.write_text("\n".join(str(p) for p in unmatched), encoding="utf-8")
        logger.warning("Unmatched PDFs (no orderid or no mapping): %d (see %s)", len(unmatched), unmatched_txt)

    # Explicitly cleanup temp extraction directory if used
    if tmpdir_obj is not None:
        try:
            tmpdir_obj.cleanup()
        except Exception:
            pass

    return out_dir, groups, manifest_csv


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Group Kaspi PDF labels by SKU and size")
    p.add_argument("--input", "-i", required=True, help="ZIP file or directory with raw label PDFs")
    p.add_argument(
        "--processed",
        "-p",
        default=str(DEFAULT_PROCESSED),
        help="Processed sales CSV path (default: data_crm/processed_sales_latest.csv)",
    )
    p.add_argument(
        "--out-date",
        default=None,
        help="Override output date folder, e.g., 2025-08-13 (default: today UTC)",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    in_path = Path(args.input)
    processed = Path(args.processed)

    try:
        out_dir, groups, manifest_csv = group_labels(in_path, processed, args.out_date)
    except Exception as e:
        logger.exception("Failed to group labels: %s", e)
        return 1

    logger.info("Grouped %d buckets → %s", len(groups), out_dir)
    print(str(manifest_csv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


