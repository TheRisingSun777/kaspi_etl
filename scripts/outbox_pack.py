#!/usr/bin/env python3

"""
Pack fulfillment bundle for a given OUT_DATE (YYYY-MM-DD).

Collects:
- data_crm/picklist/{OUT_DATE}/picklist.pdf
- data_crm/orders_kaspi_with_sizes.xlsx
- data_crm/labels_grouped/{OUT_DATE}/ (grouped PDFs + manifest.csv)

Writes:
- outbox/{OUT_DATE}/bundle_{OUT_DATE}.zip
- outbox/{OUT_DATE}/README.txt (print order guide)

Prints the absolute zip path.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd  # noqa: F401 (not strictly needed; kept for potential future csv previews)


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CRM = REPO_ROOT / "data_crm"
OUTBOX = REPO_ROOT / "outbox"


def gather_files(out_date: str) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []

    # Picklist PDF
    pick_pdf = DATA_CRM / "picklist" / out_date / "picklist.pdf"
    if pick_pdf.exists():
        files.append((pick_pdf, f"picklist/{pick_pdf.name}"))

    # Orders with sizes
    orders_xlsx = DATA_CRM / "orders_kaspi_with_sizes.xlsx"
    if orders_xlsx.exists():
        files.append((orders_xlsx, orders_xlsx.name))

    # Grouped labels
    labels_dir = DATA_CRM / "labels_grouped" / out_date
    if labels_dir.exists():
        for p in sorted(labels_dir.rglob("*")):
            if p.is_file() and p.suffix.lower() in {".pdf", ".csv"}:
                files.append((p, f"labels/{p.name}"))

    return files


def write_readme(out_dir: Path) -> Path:
    text = (
        "print order: grouped labels then picklist\n\n"
        "1) Open labels/*.pdf and print\n"
        "2) Open picklist/picklist.pdf and print\n"
    )
    readme = out_dir / "README.txt"
    out_dir.mkdir(parents=True, exist_ok=True)
    readme.write_text(text, encoding="utf-8")
    return readme


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pack fulfillment bundle to outbox")
    p.add_argument("--out-date", dest="out_date", default=None, help="YYYY-MM-DD (default: today)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_date = args.out_date or os.getenv("OUT_DATE") or pd.Timestamp.utcnow().strftime("%Y-%m-%d")

    files = gather_files(out_date)

    out_dir = OUTBOX / out_date
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"bundle_{out_date}.zip"

    # README outside zip and also include inside
    readme_path = write_readme(out_dir)

    with ZipFile(zip_path, "w", ZIP_DEFLATED) as z:
        for src, arc in files:
            try:
                z.write(src, arcname=arc)
            except Exception:
                # Skip unreadable files
                pass
        # Include readme in zip root
        try:
            z.write(readme_path, arcname="README.txt")
        except Exception:
            pass

    print(str(zip_path.resolve()))
    return 0 if files else 1


if __name__ == "__main__":
    raise SystemExit(main())


