#!/usr/bin/env python3

"""
CI Sanity Checks for Kaspi ETL workspace (strict mode ready).

Usage:
  ./venv/bin/python scripts/ci_sanity.py [--strict]

Strict checks:
- orders_api_latest.csv: required columns present (orderid,ksp_sku_id,sku_key,my_size,qty,sell_price); non-null >= 95%.
- processed_sales: prefer data_crm/processed_sales_latest.csv else latest under data_crm/processed/.
- sku_id rule: in processed_sales, sku_id must equal f"{sku_key}_{my_size}" after normalization.
- size-recs: data_crm/orders_kaspi_with_sizes.xlsx exists and rec_size non-null ratio >= 90% (null-rate < 10%).
Additional gates:
- orders_api_latest.csv exists and has at least 1 row
- missing_ksp_mapping.csv row count == 0 OR < 5% of orders

Also keeps earlier checks (KSP map schema presence, size grids present and non-empty).
Prints one line per check and final PASS/FAIL.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import os
import re

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
from settings.paths import DATA_CRM


@dataclass
class CheckResult:
    name: str
    ok: bool
    message: str
    level: str  # "CRITICAL" | "IMPORTANT" | "CHECK"


def percent_notnull(series: pd.Series) -> float:
    total = len(series)
    if total == 0:
        return 0.0
    return float(series.notna().sum()) / float(total) * 100.0


def find_processed_sales_csv() -> Path:
    latest = DATA_CRM / "processed_sales_latest.csv"
    if latest.exists():
        return latest
    proc_dir = DATA_CRM / "processed"
    candidates = sorted(proc_dir.glob("processed_sales_*.csv"))
    if candidates:
        return candidates[-1]
    return latest


def check_paths(strict: bool) -> Tuple[List[CheckResult], Dict[str, Path]]:
    paths: Dict[str, Path] = {
        "orders_csv": DATA_CRM / "orders_api_latest.csv",
        "ksp_map_xlsx": DATA_CRM / "mappings" / "ksp_sku_map_updated.xlsx",
        "processed_sales": find_processed_sales_csv(),
        "sizes_xlsx": DATA_CRM / "orders_kaspi_with_sizes.xlsx",
        "size_grid_all": DATA_CRM / "size_grid_all_models.xlsx",
        "size_grid_group": DATA_CRM / "size_grid_by_model_group.xlsx",
        "missing_map": DATA_CRM / "reports" / "missing_ksp_mapping.csv",
    }

    results: List[CheckResult] = []

    # Critical
    for key, label in [
        ("orders_csv", "orders_api_latest.csv"),
        ("ksp_map_xlsx", "mappings/ksp_sku_map_updated.xlsx"),
    ]:
        ok = paths[key].exists()
        results.append(CheckResult(name=f"CRITICAL file {label}", ok=ok, message=str(paths[key]), level="CRITICAL"))

    # Important
    size_grid_ok = paths["size_grid_all"].exists() or paths["size_grid_group"].exists()
    results.append(CheckResult(name="IMPORTANT size grid (one of all/group)", ok=size_grid_ok, message=f"{paths['size_grid_all']} OR {paths['size_grid_group']}", level="IMPORTANT"))
    for key, label in [("processed_sales", "processed_sales_latest or processed/*.csv"), ("sizes_xlsx", "orders_kaspi_with_sizes.xlsx")]:
        results.append(CheckResult(name=f"IMPORTANT file {label}", ok=paths[key].exists(), message=str(paths[key]), level="IMPORTANT"))

    return results, paths


def validate_orders_schema(df: pd.DataFrame) -> List[CheckResult]:
    required = ["orderid", "ksp_sku_id", "sku_key", "my_size", "qty", "sell_price"]
    optional = ["date", "store_name", "product_master_code", "customer_phone", "height", "weight", "join_code", "sku_id"]

    results: List[CheckResult] = []
    have = set(df.columns)
    missing_required = [c for c in required if c not in have]
    results.append(CheckResult(name="orders: required columns present", ok=len(missing_required) == 0, message=("ok" if not missing_required else f"missing: {missing_required}"), level="CHECK"))

    # Non-null thresholds
    threshold = 95.0
    for col in required:
        pct = percent_notnull(df[col]) if col in df.columns else 0.0
        results.append(CheckResult(name=f"orders: non-null {col} >= {threshold:.1f}%", ok=pct >= threshold, message=f"{pct:.1f}%", level="CHECK"))
    return results


def load_size_norm_map() -> Optional[Dict[str, str]]:
    rules = DATA_CRM / "rules" / "size_normalization.csv"
    if not rules.exists():
        return None
    try:
        df = pd.read_csv(rules)
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        for a, b in [("raw", "normalized"), ("from", "to")]:
            if {a, b}.issubset(df.columns):
                mp = {}
                for _, r in df.iterrows():
                    k = str(r.get(a, "")).strip().upper()
                    v = str(r.get(b, "")).strip().upper()
                    if k:
                        mp[k] = v
                return mp
    except Exception:
        return None
    return None


def normalize_size(val: str, mp: Optional[Dict[str, str]]) -> str:
    base = str(val or "").strip().upper()
    return mp.get(base, base) if mp else base


def processed_sku_id_rule_check(processed_csv: Path) -> List[CheckResult]:
    results: List[CheckResult] = []
    try:
        df = pd.read_csv(processed_csv)
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        needed = {"sku_id", "sku_key", "my_size"}
        if not needed.issubset(df.columns):
            results.append(CheckResult(name="processed_sales: sku_id rule", ok=False, message=f"missing cols: {sorted(list(needed - set(df.columns)))}", level="CHECK"))
            return results
        mp = load_size_norm_map()
        present = df["sku_key"].notna() & df["my_size"].notna()
        expected = (
            df.loc[present, "sku_key"].astype(str).str.strip()
            + "_"
            + df.loc[present, "my_size"].astype(str).map(lambda s: normalize_size(s, mp))
        )
        actual = df.loc[present, "sku_id"].astype(str).str.strip()
        mismatches = int((expected != actual).sum())
        results.append(CheckResult(name="processed_sales: sku_id == sku_key_my_size", ok=(mismatches == 0), message=f"mismatches={mismatches}", level="CHECK"))
    except Exception as exc:
        results.append(CheckResult(name="processed_sales: sku_id rule", ok=False, message=str(exc), level="CHECK"))
    return results


def size_recs_checks(path: Path, min_non_null_pct: float = 95.0) -> List[CheckResult]:
    results: List[CheckResult] = []
    name = f"size-recs: rec_size non-null >= {min_non_null_pct:.0f}%"
    if not path.exists():
        results.append(CheckResult(name=name, ok=False, message="missing file", level="CHECK"))
        return results
    try:
        df = pd.read_excel(path)
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        pct = percent_notnull(df.get("rec_size", pd.Series(index=df.index)))
        results.append(CheckResult(name=name, ok=(pct >= min_non_null_pct), message=f"{pct:.1f}%", level="CHECK"))
    except Exception as exc:
        results.append(CheckResult(name=name, ok=False, message=str(exc), level="CHECK"))
    return results


def size_recs_coverage(path: Path, min_pct: float = 70.0) -> List[CheckResult]:
    results: List[CheckResult] = []
    name = f"size-recs: coverage sku_key&rec_size >= {min_pct:.0f}%"
    if not path.exists():
        results.append(CheckResult(name=name, ok=False, message="missing file", level="CHECK"))
        return results
    try:
        df = pd.read_excel(path)
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        total = len(df)
        if total == 0:
            results.append(CheckResult(name=name, ok=False, message="rows=0", level="CHECK"))
            return results
        both = (
            df.get("sku_key", pd.Series([None] * total)).astype(str).str.strip().str.len().gt(0)
            & df.get("rec_size", pd.Series([None] * total)).astype(str).str.strip().str.len().gt(0)
        )
        pct = float(both.sum()) / float(total) * 100.0
        results.append(CheckResult(name=name, ok=(pct >= min_pct), message=f"{pct:.1f}% of {total}", level="CHECK"))
    except Exception as exc:
        results.append(CheckResult(name=name, ok=False, message=str(exc), level="CHECK"))
    return results


def env_quotes_check(repo_root: Path) -> List[CheckResult]:
    results: List[CheckResult] = []
    env_path = repo_root / ".env.local"
    if not env_path.exists():
        return results
    try:
        text = env_path.read_text(encoding="utf-8", errors="ignore")
        # Fail if any KASPI_*URL is single-quoted
        bad = re.findall(r"^\s*(KASPI_\w*URL)\s*=\s*'[^']*'\s*$", text, flags=re.MULTILINE)
        if bad:
            results.append(
                CheckResult(
                    name="ENV: single-quoted URLs detected",
                    ok=False,
                    message=", ".join(sorted(set(bad))),
                    level="CRITICAL",
                )
            )
    except Exception as exc:
        results.append(CheckResult(name="ENV: parse .env.local", ok=False, message=str(exc), level="IMPORTANT"))
    return results


def time_drift_check(paths: Dict[str, Path], repo_root: Path, threshold_seconds: int = 1800) -> List[CheckResult]:
    results: List[CheckResult] = []
    name = "time drift: orders vs labels zip <= 30m"
    try:
        orders_csv = paths.get("orders_csv")
        # find latest waybills zip under inbox
        waybills_root = repo_root / "data_crm" / "inbox" / "waybills"
        latest_zip: Optional[Path] = None
        if waybills_root.exists():
            zips: List[Path] = sorted(waybills_root.glob("**/*.zip"), key=lambda p: p.stat().st_mtime)
            if zips:
                latest_zip = zips[-1]
        if not orders_csv or not orders_csv.exists() or not latest_zip:
            results.append(CheckResult(name=name, ok=True, message="skipped (missing orders or labels)", level="IMPORTANT"))
            return results
        dt_orders = orders_csv.stat().st_mtime
        dt_zip = latest_zip.stat().st_mtime
        drift = abs(dt_orders - dt_zip)
        ok = drift <= threshold_seconds
        minutes = drift / 60.0
        results.append(CheckResult(name=name, ok=ok, message=f"drift={minutes:.1f}m", level="IMPORTANT"))
    except Exception as exc:
        results.append(CheckResult(name=name, ok=False, message=str(exc), level="IMPORTANT"))
    return results


def ksp_map_checks(path: Path) -> List[CheckResult]:
    results: List[CheckResult] = []
    name = "ksp_sku_map_updated.xlsx columns"
    if not path.exists():
        results.append(CheckResult(name=name, ok=False, message="missing", level="CHECK"))
        return results
    try:
        df = pd.read_excel(path, nrows=1000)
        df.columns = [str(c).strip().lower() for c in df.columns]
        required = {"ksp_sku_id", "store_name", "sku_key"}
        ok = required.issubset(set(df.columns))
        results.append(CheckResult(name=name, ok=ok, message=f"have={sorted(df.columns)}", level="CHECK"))
    except Exception as exc:
        results.append(CheckResult(name=name, ok=False, message=str(exc), level="CHECK"))
    return results


def size_grids_checks(paths: Dict[str, Path]) -> List[CheckResult]:
    results: List[CheckResult] = []
    ok_any = False
    for key in ["size_grid_all", "size_grid_group"]:
        p = paths[key]
        if p.exists():
            try:
                df = pd.read_excel(p)
                ok = len(df) > 0
                ok_any = ok_any or ok
                results.append(CheckResult(name=f"size grid non-empty: {p.name}", ok=ok, message=f"rows={len(df)}", level="CHECK"))
            except Exception as exc:
                results.append(CheckResult(name=f"size grid readable: {p.name}", ok=False, message=str(exc), level="CHECK"))
    if not ok_any:
        results.append(CheckResult(name="size grids present", ok=False, message="none present", level="CHECK"))
    return results


def print_summary(results: List[CheckResult], strict: bool) -> bool:
    overall_ok = True
    for r in results:
        emoji = "✅" if r.ok else ("⚠️" if r.level == "IMPORTANT" and not strict else "❌")
        if not r.ok and (r.level == "CRITICAL" or strict or r.level == "CHECK"):
            overall_ok = False
        print(f"{emoji} {r.name} {r.message}")
    print("\n" + ("✅ PASS" if overall_ok else "❌ FAIL"))
    return overall_ok


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CI sanity checks for Kaspi ETL")
    parser.add_argument("--strict", action="store_true", help="Treat IMPORTANT as critical")
    args = parser.parse_args(argv)

    path_results, paths = check_paths(strict=args.strict)
    overall_results: List[CheckResult] = []
    overall_results.extend(path_results)
    overall_results.extend(env_quotes_check(REPO_ROOT))

    # Orders checks
    orders_csv = paths["orders_csv"]
    orders_count: Optional[int] = None
    if orders_csv.exists():
        try:
            orders_df = pd.read_csv(orders_csv)
            orders_df.columns = [str(c).strip().lower().replace(" ", "_") for c in orders_df.columns]
            # Gate: at least 1 row present
            orders_count = len(orders_df)
            overall_results.append(CheckResult(name="orders: non-empty (>=1 row)", ok=(orders_count >= 1), message=f"rows={orders_count}", level="CHECK"))
            overall_results.extend(validate_orders_schema(orders_df))
        except Exception as exc:
            overall_results.append(CheckResult(name="orders: readable", ok=False, message=str(exc), level="CHECK"))
    else:
        overall_results.append(CheckResult(name="orders: readable", ok=False, message="missing", level="CHECK"))

    # Processed sales checks
    processed_csv = paths["processed_sales"]
    if processed_csv.exists():
        overall_results.extend(processed_sku_id_rule_check(processed_csv))
    else:
        overall_results.append(CheckResult(name="processed_sales: present", ok=False, message=str(processed_csv), level="CHECK"))

    # Size recs checks (null-rate < 10% => non-null >= 90%)
    overall_results.extend(size_recs_checks(paths["sizes_xlsx"], min_non_null_pct=90.0))
    # Coverage check: >=70% rows have both sku_key and rec_size
    overall_results.extend(size_recs_coverage(paths["sizes_xlsx"], min_pct=70.0))

    # Missing KSP mapping gate: row count == 0 OR < 5% of orders
    miss_path = paths.get("missing_map")
    if miss_path and miss_path.exists():
        try:
            miss_df = pd.read_csv(miss_path)
            miss_rows = len(miss_df)
            denom = float(orders_count) if orders_count is not None and orders_count > 0 else 0.0
            ratio = (miss_rows / denom * 100.0) if denom > 0 else (0.0 if miss_rows == 0 else 100.0)
            ok_gate = (miss_rows == 0) or (ratio < 5.0)
            overall_results.append(CheckResult(name="missing_ksp_mapping.csv: rows == 0 or <5% of orders", ok=ok_gate, message=f"rows={miss_rows}, ratio={ratio:.1f}%", level="CHECK"))
        except Exception as exc:
            overall_results.append(CheckResult(name="missing_ksp_mapping.csv: readable", ok=False, message=str(exc), level="CHECK"))
    else:
        overall_results.append(CheckResult(name="missing_ksp_mapping.csv: present", ok=False, message=str(miss_path), level="CHECK"))

    # KSP map schema + size grid presence
    overall_results.extend(ksp_map_checks(paths["ksp_map_xlsx"]))
    overall_results.extend(size_grids_checks(paths))

    # Time drift warning
    overall_results.extend(time_drift_check(paths, REPO_ROOT, threshold_seconds=1800))
    ok = print_summary(overall_results, strict=args.strict)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
