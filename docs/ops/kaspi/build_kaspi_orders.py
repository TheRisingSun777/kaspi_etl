#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kaspi order bundler

Input (any names):
  - 1 Excel (.xlsx) with columns: Date, STORE_NAME, OrderID, Quantity, Kaspi_name_core, MY_SIZE
  - N waybill ZIPs with files like KASPI_SHOP-<OrderID>.pdf

Logic (for a chosen send date):
  SPECIAL multi-qty (Quantity>1):
    - Group ACROSS orders by Kaspi_name_core.
    - Merge found waybills.
    - Name: "<core>___qnt<sum>.pdf" (sum = Excel Quantity total).
  SPECIAL multi-line (OrderID appears on multiple rows):
    - One PDF per OrderID (the single waybill for that order).
    - Filename shows what to pack: "core1-size1-qnt1(1/N)___core2-size2-qnt2(2/N)... .pdf"
  NORMAL singles (Quantity==1 and not multi-line):
    - Group by (Kaspi_name_core, MY_SIZE).
    - Merge waybills.
    - Name: "<core>___<size>-<count>.pdf" (count = number of orders in that group).

Output:
  OUTBASE/Today/<d.m.yy>_<STORE>_qnt<sum>/
    SPECIAL_multi_qty/, SPECIAL_multi_line/, NORMAL_singles/
    manifest_*.csv, build_log.csv, missing_orders.csv (if any)
  OUTBASE/Today/kaspi_orders_<d.m.yy>.zip

Rotation:
  If Today/ has content, it’s moved to OUTBASE/Archive/<yesterday>.
"""

import argparse, io, os, re, sys, zipfile, shutil, json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import pandas as pd
from dateutil import parser as dateparser

# PDF merger (pure python)
try:
    from pypdf import PdfMerger
except Exception:
    print("Missing dependency: pypdf. Install with: python3 -m pip install pypdf")
    sys.exit(1)

REQUIRED_COLS = {"Date", "STORE_NAME", "OrderID", "Quantity", "Kaspi_name_core", "MY_SIZE"}

def log(msg: str) -> None:
    print(msg, flush=True)

def sanitize(s: str) -> str:
    s = re.sub(r"\s+", " ", str(s)).strip()
    s = s.replace("/", "-").replace("\\", "-")
    s = s.replace(":", " -").replace("*", "-").replace("?", "")
    s = s.replace('"', "'").replace("<", "(").replace(">", ")").replace("|", "-")
    s = re.sub(r"_+", "_", s)
    s = re.sub(r"\s*_\s*", "_", s)
    return s

def ensure_pdf(name: str) -> str:
    return name if name.lower().endswith(".pdf") else f"{name}.pdf"

from collections import defaultdict

def prefix_name(base_name: str, counters: dict, prefix_text: str = "Местовая") -> str:
    """Return 'Местовая-<n>_<base_name>' where n counts identical base names."""
    n = counters[base_name] + 1
    counters[base_name] = n
    return f"{prefix_text}-{n}_{base_name}"

def date_label(d: datetime) -> str:
    return f"{d.day}.{d.month}.{str(d.year)[-2:]}"  # 5.9.25

def parse_input_date(date_str: str | None) -> datetime:
    """Robust date parser:
       - 'today', 'yesterday', 'tomorrow'
       - ISO 'YYYY-MM-DD' parsed strictly
       - otherwise parse with dayfirst=True (handles '04.09.2025', '4/9/25', etc.)
    """
    from datetime import datetime, timedelta
    import re

    if not date_str:
        now = datetime.now()
        return datetime(now.year, now.month, now.day)

    s = str(date_str).strip().lower()
    now = datetime.now()

    if s in {"today"}:
        return datetime(now.year, now.month, now.day)
    if s in {"yesterday"}:
        d = now - timedelta(days=1)
        return datetime(d.year, d.month, d.day)
    if s in {"tomorrow"}:
        d = now + timedelta(days=1)
        return datetime(d.year, d.month, d.day)

    # ISO strict
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        dt = datetime.fromisoformat(s)
        return datetime(dt.year, dt.month, dt.day)

    # Fallback: parse with dayfirst semantics
    from dateutil import parser as dateparser
    dt = dateparser.parse(s, dayfirst=True)
    return datetime(dt.year, dt.month, dt.day)


def find_files(input_dir: Path) -> Tuple[Path, List[Path]]:
    excels = sorted([p for p in input_dir.glob("*.xlsx") if not p.name.startswith("~")],
                    key=lambda p: p.stat().st_mtime, reverse=True)
    zips = sorted(list(input_dir.glob("*.zip")))
    if not excels:
        raise FileNotFoundError(f"No .xlsx found in {input_dir}")
    if not zips:
        raise FileNotFoundError(f"No .zip waybill files found in {input_dir}")
    return excels[0], zips  # pick newest Excel + all zips

def pick_sheet_with_required_cols(xlsx: Path) -> str:
    xl = pd.ExcelFile(xlsx)
    for sh in xl.sheet_names:
        df = pd.read_excel(xlsx, sheet_name=sh, nrows=1)
        cols = set(c.strip() for c in df.columns if isinstance(c, str))
        if REQUIRED_COLS.issubset(cols):
            return sh
    raise ValueError(f"No sheet in {xlsx.name} has required columns: {sorted(REQUIRED_COLS)}")

def load_df(xlsx: Path, sheet: str) -> pd.DataFrame:
    df = pd.read_excel(xlsx, sheet_name=sheet)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["OrderID"] = df["OrderID"].astype(str).str.strip()
    df["Kaspi_name_core"] = df["Kaspi_name_core"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    df["MY_SIZE"] = df["MY_SIZE"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    df["STORE_NAME"] = df["STORE_NAME"].astype(str).str.strip()
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(1).astype(int)
    return df

def map_waybills(zips: List[Path]) -> Dict[str, Tuple[Path, zipfile.ZipInfo]]:
    """Return first found PDF per OrderID across zips."""
    mapping: Dict[str, Tuple[Path, zipfile.ZipInfo]] = {}
    for z in zips:
        with zipfile.ZipFile(z, "r") as zf:
            for m in zf.infolist():
                if m.is_dir():
                    continue
                name = Path(m.filename).name
                if not name.lower().endswith(".pdf"):
                    continue
                m_order = re.search(r"(\d+)", name)
                if not m_order:
                    continue
                oid = m_order.group(1)
                if oid not in mapping:  # keep first occurrence
                    mapping[oid] = (z, m)
    return mapping

def merge_members(members: List[Tuple[Path, zipfile.ZipInfo]], out_path: Path) -> None:
    merger = PdfMerger()
    # deterministic order by filename
    members_sorted = sorted(members, key=lambda t: Path(t[1].filename).name)
    for z, mem in members_sorted:
        with zipfile.ZipFile(z, "r") as zf:
            with zf.open(mem) as fh:
                merger.append(io.BytesIO(fh.read()))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        merger.write(f)
    merger.close()

def rotate_today(outbase: Path, target_date: datetime) -> Tuple[Path, Path]:
    today_dir = outbase / "Today"
    archive_dir = outbase / "Archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    if today_dir.exists() and any(today_dir.iterdir()):
        y = target_date - timedelta(days=1)
        dest = archive_dir / f"{y.strftime('%Y-%m-%d')}"
        i = 1
        while dest.exists():
            dest = archive_dir / f"{y.strftime('%Y-%m-%d')}_{i}"
            i += 1
        shutil.move(str(today_dir), str(dest))
    today_dir.mkdir(parents=True, exist_ok=True)
    return today_dir, archive_dir

def pick_sheet_for_date(xlsx: Path, target_date: datetime) -> str:
    xl = pd.ExcelFile(xlsx)
    fallback = None
    for sh in xl.sheet_names:
        df = pd.read_excel(xlsx, sheet_name=sh)
        cols = set(c.strip() for c in df.columns if isinstance(c, str))
        if not REQUIRED_COLS.issubset(cols):
            continue
        if fallback is None:
            fallback = sh  # first valid structure
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        if (df["Date"].dt.date == target_date.date()).any():
            return sh
    if fallback:
        return fallback
    raise ValueError(f"No sheet in {xlsx.name} has required columns {sorted(REQUIRED_COLS)}")

def main():
    ap = argparse.ArgumentParser(description="Kaspi order bundler")
    ap.add_argument("--input", required=True, help="Folder with 1 xlsx + N zip waybills")
    ap.add_argument("--outbase", required=True, help="Base folder with Today/ and Archive/")
    ap.add_argument("--date", default="today", help="Send date: 'today' or 'YYYY-MM-DD' or 'DD.MM.YYYY'")
    ap.add_argument("--zip-mode", choices=["one","per-store"], default="one", help="One big zip or per-store zips")
    ap.add_argument("--fail-below-match", type=float, default=0.0, help="Fail if match rate (%) below this threshold")
    args = ap.parse_args()

    input_dir = Path(args.input)
    outbase = Path(args.outbase)
    target_date = parse_input_date(args.date)

    log(f"⏱  Date: {target_date.strftime('%Y-%m-%d')}")
    log(f"📥 Input: {input_dir}")
    xlsx, zips = find_files(input_dir)
    sheet = pick_sheet_for_date(xlsx, target_date)
    log(f"📄 Excel: {xlsx.name} (sheet: {sheet})")
    log(f"🗜  ZIPs: {', '.join(p.name for p in zips)}")

    df = load_df(xlsx, sheet)
    day_df = df[df["Date"].dt.date == target_date.date()].copy()
    if day_df.empty:
        # Show available dates to help debug
        avail = sorted(set(d.date() for d in df["Date"].dropna()))
        raise SystemExit(f"No rows for {target_date.date()} in {xlsx.name} ({sheet}). "
                         f"Available dates: {', '.join(str(a) for a in avail[:20])}{' ...' if len(avail)>20 else ''}")

    wb_map = map_waybills(zips)
    if not wb_map:
        raise SystemExit("No PDFs found in provided ZIPs.")

    # classification
    dup_counts = day_df["OrderID"].value_counts()
    multi_line_ids = set(dup_counts[dup_counts > 1].index.tolist())
    multi_qty_df = day_df[day_df["Quantity"] > 1].copy()

    # match rate vs available PDFs
    excel_orders = set(day_df["OrderID"])
    pdf_orders = set(wb_map.keys())
    matched = excel_orders & pdf_orders
    match_rate = (len(matched) / len(excel_orders)) * 100 if excel_orders else 100.0
    log(f"🔎 Match rate: {match_rate:.1f}% ({len(matched)}/{len(excel_orders)})")
    if args.fail_below_match > 0 and match_rate < args.fail_below_match:
        raise SystemExit(f"Match rate {match_rate:.1f}% below threshold {args.fail_below_match}%.")

    # prepare output
    today_dir, archive_dir = rotate_today(outbase, target_date)
    label = date_label(target_date)

    build_events = []
    missing_rows = []
    prefix_counters_multi_qty = defaultdict(int)
    prefix_counters_multi_line = defaultdict(int)

    stores = sorted(day_df["STORE_NAME"].unique().tolist())
    for store in stores:
        s_df = day_df[day_df["STORE_NAME"] == store].copy()
        total_items = int(s_df["Quantity"].sum())
        store_folder = today_dir / sanitize(f"{label}_{store}_qnt{total_items}")
        store_folder.mkdir(parents=True, exist_ok=True)

        # SPECIAL multi-qty -> one PDF per OrderID (size-aware; no cross-order grouping)
        # exclude multi-line orders here to avoid double-processing
        mqty_store = s_df[(s_df["Quantity"] > 1) & (~s_df["OrderID"].isin(multi_line_ids))]
        if not mqty_store.empty:
            out_dir = store_folder / "SPECIAL_multi_qty"
            out_dir.mkdir(parents=True, exist_ok=True)

            for oid, rows in mqty_store.groupby("OrderID"):
                if oid not in wb_map:
                    missing_rows.append({
                        "STORE_NAME": store,
                        "reason": "multi_qty_missing_pdf",
                        "order_id": oid
                    })
                    continue

                # Usually one line; if more slipped in, still sum qty & take first core/size
                core = sanitize(rows["Kaspi_name_core"].iloc[0])
                size = sanitize(rows["MY_SIZE"].iloc[0])
                qnt  = int(rows["Quantity"].sum())

                base_name = ensure_pdf(sanitize(f"{core}___{size}-{qnt}"))
                prefixed  = prefix_name(base_name, prefix_counters_multi_qty, "Местовая")
                out_path  = out_dir / prefixed

                merge_members([wb_map[oid]], out_path)

                build_events.append({
                    "type": "special_multi_qty",
                    "store": store,
                    "order_id": oid,
                    "core": core,
                    "size": size,
                    "quantity": qnt,
                    "output": str(out_path)
                })



        # SPECIAL multi-line -> one PDF per OrderID (segments in filename)
        mline_store = s_df[s_df["OrderID"].isin(multi_line_ids)]
        if not mline_store.empty:
            out_dir = store_folder / "SPECIAL_multi_line"
            out_dir.mkdir(parents=True, exist_ok=True)
            for oid, g in mline_store.groupby("OrderID"):
                if oid not in wb_map:
                    missing_rows.append({"STORE_NAME": store, "reason": "multi_line_missing_pdf", "order_id": oid})
                    continue
                N = g.shape[0]
                segs = []
                for i, (_, row) in enumerate(g.iterrows(), start=1):
                    core = sanitize(row["Kaspi_name_core"])
                    size = sanitize(row["MY_SIZE"])
                    qnt  = int(row["Quantity"])
                    segs.append(f"{core}-{size}-{qnt}({i}/{N})")

                base_name = ensure_pdf(sanitize("___".join(segs)))
                prefixed  = prefix_name(base_name, prefix_counters_multi_line, "Местовая")
                out_path  = out_dir / prefixed

                merge_members([wb_map[oid]], out_path)

                build_events.append({
                    "type":"special_multi_line",
                    "store":store,
                    "order_id":oid,
                    "lines":N,
                    "output":str(out_path)
                })

        # NORMAL singles -> group by (core, size)
        singles_store = s_df[(s_df["Quantity"] == 1) & (~s_df["OrderID"].isin(multi_line_ids))]
        if not singles_store.empty:
            out_dir = store_folder / "NORMAL_singles"
            out_dir.mkdir(parents=True, exist_ok=True)
            for (core, size), g in singles_store.groupby(["Kaspi_name_core","MY_SIZE"]):
                order_ids = sorted(g["OrderID"].tolist(), key=lambda x: int(re.sub(r"\D","",x)))
                members = [(wb_map[oid][0], wb_map[oid][1]) for oid in order_ids if oid in wb_map]
                if not members:
                    missing_rows.append({"STORE_NAME": store, "reason": "singles_no_pdfs",
                                         "core": core, "size": size, "order_ids": ",".join(order_ids)})
                    continue
                out_name = ensure_pdf(sanitize(f"{core}___{size}-{len(order_ids)}"))
                out_path = out_dir / out_name
                merge_members(members, out_path)
                build_events.append({"type":"singles_group","store":store,"core":core,
                                     "size":size,"count":len(order_ids),"output":str(out_path)})

        # per-store manifests
        pd.DataFrame([e for e in build_events if e["type"]=="special_multi_qty" and e["store"]==store]) \
            .to_csv(store_folder/"manifest_special_multi_qty.csv", index=False)
        pd.DataFrame([e for e in build_events if e["type"]=="special_multi_line" and e["store"]==store]) \
            .to_csv(store_folder/"manifest_special_multi_line.csv", index=False)
        pd.DataFrame([e for e in build_events if e["type"]=="singles_group" and e["store"]==store]) \
            .to_csv(store_folder/"manifest_normal_singles.csv", index=False)

    # root logs
    pd.DataFrame(build_events).to_csv(today_dir/"build_log.csv", index=False)
    if missing_rows:
        pd.DataFrame(missing_rows).to_csv(today_dir/"missing_orders.csv", index=False)

    # zips
    label = date_label(target_date)
    if args.zip_mode == "one":
        zip_path = today_dir / f"kaspi_orders_{label}.zip"
        if zip_path.exists(): zip_path.unlink()
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", root_dir=today_dir)
        log(f"✅ Done. One ZIP: {zip_path}")
    else:
        for store_path in [p for p in today_dir.iterdir() if p.is_dir()]:
            z = store_path.with_suffix(".zip")
            if z.exists(): z.unlink()
            shutil.make_archive(str(z.with_suffix("")), "zip", root_dir=store_path)
        log("✅ Done. Per-store ZIPs created.")

    summary = {
        "date": target_date.strftime("%Y-%m-%d"),
        "stores": stores,
        "rows_today": int(day_df.shape[0]),
        "orders_today": int(day_df["OrderID"].nunique()),
        "match_rate_percent": round((len(excel_orders & set(wb_map.keys()))/len(excel_orders))*100, 1)
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()