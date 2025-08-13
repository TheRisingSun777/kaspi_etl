#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import logging
from pathlib import Path
import shutil
from typing import Dict, List, Optional, Tuple

import pandas as pd


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CRM = REPO_ROOT / "data_crm"
LABELS_DIR = DATA_CRM / "labels_grouped"
OUTBOX_DIR = REPO_ROOT / "outbox"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pack grouped label PDFs into outbox")
    p.add_argument("--date", dest="date", required=True, help="Date tag (YYYY-MM-DD)")
    return p.parse_args()


def to_stamp(date_str: str) -> Tuple[str, str]:
    d = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
    return d.isoformat(), d.strftime("%Y%m%d")


def safe_read_manifest(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["group_pdf", "count", "sku_key", "my_size", "orderids"])  # empty
    df = pd.read_csv(path)
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def copy_grouped_pdfs(src_dir: Path, dst_dir: Path) -> List[Path]:
    dst_dir.mkdir(parents=True, exist_ok=True)
    pdfs = sorted([p for p in src_dir.glob("*.pdf") if p.is_file()])
    copied: List[Path] = []
    for p in pdfs:
        target = dst_dir / p.name
        shutil.copy2(p, target)
        copied.append(target)
    return copied


def write_outbox_readme(dst_dir: Path, manifest_df: pd.DataFrame) -> Path:
    readme = dst_dir / "OUTBOX_README.txt"
    lines: List[str] = []
    lines.append("Kaspi Labels Outbox")
    lines.append("")
    total_groups = 0
    total_labels = 0

    if {"sku_key", "my_size", "count"}.issubset(set(manifest_df.columns)) and len(manifest_df) > 0:
        # Aggregate by (sku_key, my_size)
        agg = (
            manifest_df.groupby(["sku_key", "my_size"], dropna=False)["count"].sum().reset_index()
        )
        agg = agg.sort_values(by=["sku_key", "my_size"])  # stable order
        for _, r in agg.iterrows():
            sku_key = str(r.get("sku_key", "")).strip()
            my_size = str(r.get("my_size", "")).strip()
            cnt = int(r.get("count", 0) or 0)
            model = (sku_key.split("_", 1)[0] if sku_key else "")
            lines.append(f"{model or 'UNKNOWN'} {my_size or 'UNK'}: {cnt}")
            total_groups += 1
            total_labels += cnt
    else:
        lines.append("No manifest details available.")

    lines.append("")
    lines.append(f"Groups: {total_groups}")
    lines.append(f"Total labels: {total_labels}")

    readme.write_text("\n".join(lines), encoding="utf-8")
    return readme


def main() -> int:
    args = parse_args()
    iso_date, _ = to_stamp(args.date)

    src = LABELS_DIR / iso_date
    if not src.exists():
        raise SystemExit(f"Input labels dir not found: {src}")

    dst = OUTBOX_DIR / iso_date
    dst.mkdir(parents=True, exist_ok=True)

    # Copy grouped PDFs
    copied = copy_grouped_pdfs(src, dst)

    # Read manifest and write README summary
    manifest_df = safe_read_manifest(src / "manifest.csv")
    # Ensure 'count' numeric
    if "count" in manifest_df.columns:
        manifest_df["count"] = pd.to_numeric(manifest_df["count"], errors="coerce").fillna(0).astype(int)
    readme_path = write_outbox_readme(dst, manifest_df)

    logger.info("Outbox prepared: %s (copied %d PDFs)", dst, len(copied))
    logger.info("README: %s", readme_path)
    print(str(dst))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


