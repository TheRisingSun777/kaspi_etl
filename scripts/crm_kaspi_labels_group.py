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
from pypdf import PdfMerger


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
    """Extract order id from a label file name like 'KASPI_SHOP-12345.pdf'.

    Strategy: pick the last 4+ digit run.
    """
    base = Path(name).stem
    matches = re.findall(r"(\d{4,})", base)
    if not matches:
        return None
    return matches[-1]


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


@dataclass
class GroupEntry:
    sku_key: str
    my_size: str
    pdf_paths: List[Path]


def merge_group_to_pdf(pdf_paths: Iterable[Path], output_pdf: Path) -> None:
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    merger = PdfMerger()
    try:
        for p in pdf_paths:
            merger.append(str(p))
        with output_pdf.open("wb") as f:
            merger.write(f)
    finally:
        merger.close()


def discover_label_pdfs(input_path: Path) -> Tuple[Path, List[Path]]:
    """Return a directory that holds PDFs and the list of PDF paths inside it.

    If input_path is a ZIP, extract to a temp dir and return its PDFs.
    If it's a directory, search recursively for PDFs.
    """
    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        tmpdir = TemporaryDirectory()
        tmp_path = Path(tmpdir.name)
        shutil.unpack_archive(str(input_path), extract_dir=str(tmp_path))
        pdfs = sorted([p for p in tmp_path.rglob("*.pdf") if p.is_file()])
        return tmp_path, pdfs  # caller must keep tmpdir alive by holding reference
    elif input_path.is_dir():
        pdfs = sorted([p for p in input_path.rglob("*.pdf") if p.is_file()])
        return input_path, pdfs
    else:
        raise FileNotFoundError(f"Input path not found or unsupported: {input_path}")


def group_labels(
    input_path: Path,
    processed_csv: Path,
    out_date: Optional[str] = None,
) -> Tuple[Path, List[GroupEntry], Path]:
    processed_csv = _find_processed_csv(processed_csv)
    order_to_group = load_order_group_mapping(processed_csv)
    if not order_to_group:
        logger.warning("Processed sales CSV has no mapping rows: %s", processed_csv)

    holder_dir, pdfs = discover_label_pdfs(input_path)
    logger.info("Found %d PDF labels", len(pdfs))

    # Collect PDFs per group
    group_map: Dict[Tuple[str, str], List[Path]] = {}
    unmatched: List[Path] = []
    for pdf in pdfs:
        oid = _extract_orderid_from_name(pdf.name)
        if not oid or oid not in order_to_group:
            unmatched.append(pdf)
            continue
        sku_key, my_size = order_to_group[oid]
        key = (sku_key or "UNKNOWN", my_size or "")
        group_map.setdefault(key, []).append(pdf)

    # Output directory
    date_tag = out_date or pd.Timestamp.utcnow().strftime("%Y-%m-%d")
    out_dir = DATA_CRM / "labels_grouped" / date_tag
    out_dir.mkdir(parents=True, exist_ok=True)

    # Merge and record manifest
    groups: List[GroupEntry] = []
    manifest_rows: List[Dict[str, str]] = []
    for (sku_key, my_size), paths in sorted(group_map.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        safe_name = f"{_safe_slug(sku_key)}_{_safe_slug(my_size)}".strip("_")
        output_pdf = out_dir / f"{safe_name}.pdf"
        merge_group_to_pdf(paths, output_pdf)
        groups.append(GroupEntry(sku_key=sku_key, my_size=my_size, pdf_paths=paths))
        manifest_rows.append(
            {
                "sku_key": sku_key,
                "my_size": my_size,
                "count": str(len(paths)),
                "output_pdf": str(output_pdf.relative_to(REPO_ROOT)),
                "orderids": ",".join(
                    [
                        _extract_orderid_from_name(p.name) or ""
                        for p in paths
                    ]
                ),
            }
        )

    # Write manifest
    manifest_csv = out_dir / "manifest.csv"
    with manifest_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["sku_key", "my_size", "count", "output_pdf", "orderids"])
        writer.writeheader()
        for row in manifest_rows:
            writer.writerow(row)

    # Also write unmatched list for operator visibility
    if unmatched:
        unmatched_txt = out_dir / "unmatched_files.txt"
        unmatched_txt.write_text("\n".join(str(p) for p in unmatched), encoding="utf-8")
        logger.warning("Unmatched PDFs (no orderid or no mapping): %d (see %s)", len(unmatched), unmatched_txt)

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


