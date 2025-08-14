#!/usr/bin/env python3
"""
Group Kaspi label PDFs by (sku_key, my_size, color) with robust matching.

Inputs:
- data_crm/labels/YYYY-MM-DD/*.zip (Kaspi label ZIPs)
- data_crm/processed_sales_20250813.csv (to map orderid → sku_key, my_size, ksp_sku_id)

Outputs (per date):
- data_crm/labels_grouped/YYYY-MM-DD/{sku_key}_{size}_{color}.pdf (merged labels)
- data_crm/labels_grouped/YYYY-MM-DD/manifest.csv (one row per source PDF)

Matching order:
1) orderid: Extract from filename or PDF text; map via processed sales
2) join_code: If column exists in CSV, try exact token match from filename/text
3) ksp_sku_id: Case-insensitive substring match from filename/text; prefer rows with qty == 1

Manifest columns:
- pdf_file, orderid, sku_key, my_size, ksp_sku_id, match_method
"""

from __future__ import annotations

import csv
import re
import zipfile
from collections import defaultdict
from pathlib import Path

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


def _infer_date_dir(cli_date: str | None) -> Path:
    if cli_date:
        return LABELS_DIR / cli_date
    # Pick latest YYYY-MM-DD directory
    candidates = [p for p in LABELS_DIR.glob("*/") if p.name[:4].isdigit()]
    if not candidates:
        raise FileNotFoundError(f"No date directories under {LABELS_DIR}")
    return sorted(candidates, key=lambda p: p.name)[-1]


def _extract_zips(zip_dir: Path, work_dir: Path) -> list[Path]:
    work_dir.mkdir(parents=True, exist_ok=True)
    pdfs: list[Path] = []
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


def _extract_orderid_from_filename(path: Path) -> str | None:
    m = ORDERID_RE.search(path.stem)
    return m.group(1) if m else None


def _extract_orderid_from_pdf(path: Path) -> str | None:
    try:
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        m = ORDERID_RE.search(text)
        return m.group(1) if m else None
    except Exception:
        return None


def _extract_text_safe(path: Path) -> str:
    try:
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


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
    # Ensure expected columns exist
    for col in ["orderid", "sku_key", "my_size", "ksp_sku_id", "qty", "join_code"]:
        if col not in df.columns:
            df[col] = pd.NA
    # Normalize text fields
    df["orderid"] = df["orderid"].astype(str).str.strip()
    df["sku_key"] = df["sku_key"].astype(str).str.strip()
    df["my_size"] = df["my_size"].astype(str).str.strip()
    df["ksp_sku_id"] = df["ksp_sku_id"].astype(str).str.strip()
    df["join_code"] = df["join_code"].astype(str).str.strip()
    # qty numeric helper
    try:
        df["qty_num"] = pd.to_numeric(df["qty"], errors="coerce").fillna(1).astype(int)
    except Exception:
        df["qty_num"] = 1
    return df


def _build_lookup_structures(df: pd.DataFrame):
    order_map: dict[str, dict] = {}
    join_code_map: dict[str, list[dict]] = defaultdict(list)
    ksp_sku_map: dict[str, list[dict]] = defaultdict(list)

    for _, row in df.iterrows():
        row_dict = {
            "orderid": str(row.get("orderid", "") or "").strip(),
            "sku_key": str(row.get("sku_key", "") or "").strip(),
            "my_size": str(row.get("my_size", "") or "").strip(),
            "ksp_sku_id": str(row.get("ksp_sku_id", "") or "").strip(),
            "join_code": str(row.get("join_code", "") or "").strip(),
            "qty_num": int(row.get("qty_num", 1) or 1),
        }
        if row_dict["orderid"]:
            order_map.setdefault(row_dict["orderid"], row_dict)
        if row_dict["join_code"]:
            join_code_map[row_dict["join_code"].lower()].append(row_dict)
        if row_dict["ksp_sku_id"]:
            ksp_sku_map[row_dict["ksp_sku_id"].lower()].append(row_dict)
    return order_map, join_code_map, ksp_sku_map


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_\-]+", text or "")


def _choose_ksp_row(candidates: list[dict]) -> dict | None:
    if not candidates:
        return None
    qty1 = [r for r in candidates if int(r.get("qty_num", 0)) == 1]
    if len(qty1) == 1:
        return qty1[0]
    # prefer unique (sku_key, my_size)
    by_key = {(r.get("sku_key", ""), r.get("my_size", "")): r for r in candidates}
    if len(by_key) == 1:
        return next(iter(by_key.values()))
    return candidates[0]


def _merge_pdfs(sources: list[Path], dest: Path) -> None:
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


def group_labels_for_date(date_str: str | None = None) -> tuple[int, Path]:
    date_dir = _infer_date_dir(date_str)
    out_dir = GROUPED_DIR / date_dir.name
    work_dir = date_dir / "_extracted"

    pdfs = _extract_zips(date_dir, work_dir)
    if not pdfs:
        print(f"No PDFs extracted from ZIPs in {date_dir}")
        return 0, out_dir

    processed_df = _load_processed_sales()
    order_map, join_code_map, ksp_sku_map = _build_lookup_structures(processed_df)

    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)

    for pdf in pdfs:
        matched_row: dict | None = None
        matched_orderid: str | None = None
        match_method = ""

        # 1) Strict orderid
        orderid = _extract_orderid_from_filename(pdf) or _extract_orderid_from_pdf(pdf)
        if orderid and orderid in order_map:
            matched_row = order_map[orderid]
            matched_orderid = orderid
            match_method = "orderid"
        else:
            # Build text and tokens once
            fname_lc = pdf.name.lower()
            text = _extract_text_safe(pdf)
            text_lc = text.lower() if text else ""
            tokens = set(t.lower() for t in (_tokenize(pdf.name) + _tokenize(text)))

            # 2) join_code exact token match if available
            if join_code_map:
                code_hits = [code for code in tokens if code in join_code_map]
                if len(code_hits) == 1:
                    chosen = _choose_ksp_row(join_code_map[code_hits[0]])
                    if chosen:
                        matched_row = chosen
                        matched_orderid = chosen.get("orderid", "") or None
                        match_method = "join_code"

            # 3) ksp_sku_id substring match (filename first, then text)
            if not matched_row and ksp_sku_map:
                filename_hits = [k for k in ksp_sku_map.keys() if k and k in fname_lc]
                search_hits = filename_hits
                if not search_hits and text_lc:
                    text_hits = [k for k in ksp_sku_map.keys() if k and k in text_lc]
                    search_hits = text_hits
                if len(search_hits) == 1:
                    chosen = _choose_ksp_row(ksp_sku_map[search_hits[0]])
                    if chosen:
                        matched_row = chosen
                        matched_orderid = chosen.get("orderid", "") or None
                        match_method = "ksp_sku_id"

        if not matched_row:
            continue

        sku_key = matched_row.get("sku_key", "")
        size = matched_row.get("my_size", "")
        ksp_id = matched_row.get("ksp_sku_id", "")
        color = _derive_color_from_sku_key(sku_key)
        groups[(sku_key, size, color)].append(
            {
                "orderid": matched_orderid or "",
                "pdf": pdf,
                "ksp_sku_id": ksp_id,
                "match_method": match_method,
            }
        )

    # Write grouped PDFs and per-file manifest
    manifest_rows: list[dict[str, str]] = []
    total_labels = 0
    for (sku_key, size, color), items in sorted(groups.items()):
        items_sorted = sorted(items, key=lambda t: t.get("orderid", ""))
        target_pdf = out_dir / f"{sku_key}_{size}_{color}.pdf"
        _merge_pdfs([t["pdf"] for t in items_sorted], target_pdf)
        for it in items_sorted:
            total_labels += 1
            pdf_path = it["pdf"]
            try:
                rel = str(pdf_path.relative_to(REPO_ROOT))
            except Exception:
                rel = str(pdf_path)
            manifest_rows.append(
                {
                    "pdf_file": rel,
                    "orderid": it.get("orderid", ""),
                    "sku_key": sku_key,
                    "my_size": size,
                    "ksp_sku_id": it.get("ksp_sku_id", ""),
                    "match_method": it.get("match_method", ""),
                }
            )

    manifest_path = out_dir / "manifest.csv"
    out_dir.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["pdf_file", "orderid", "sku_key", "my_size", "ksp_sku_id", "match_method"],
        )
        writer.writeheader()
        for row in manifest_rows:
            writer.writerow(row)

    print(f"Grouped {total_labels} labels into {len(groups)} PDFs → {out_dir}")
    return len(groups), out_dir


def main() -> int:
    # Optional env var or pass date via CLI in the future; for now autodetect latest
    try:
        _, _ = group_labels_for_date()
    except FileNotFoundError as exc:
        print(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


