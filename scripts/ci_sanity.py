#!/usr/bin/env python3

"""
CI Sanity Checks for Kaspi ETL workspace.

Usage:
  ./venv/bin/python scripts/ci_sanity.py [--strict]

Checks:
- Critical files exist (fail if missing)
- Important files exist (warn; with --strict they also fail)
- Validate orders_api_latest.csv required/optional columns
- Quality thresholds on non-nullness and sku_id integrity
- If processed_sales_latest.csv exists, ensure it contains all sku_id from orders
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CRM = REPO_ROOT / "data_crm"


# Load environment
load_dotenv(REPO_ROOT / ".env.local", override=False)
load_dotenv(REPO_ROOT / ".env", override=False)


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


def read_orders_csv(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        return df
    except Exception as exc:
        print(f"❌ Failed to read {path}: {exc}")
        return None


def check_paths(strict: bool) -> Tuple[List[CheckResult], Dict[str, Path]]:
    paths: Dict[str, Path] = {
        "orders_csv": DATA_CRM / "orders_api_latest.csv",
        "ksp_map_xlsx": DATA_CRM / "mappings" / "ksp_sku_map_updated.xlsx",
        "processed_sales": DATA_CRM / "processed_sales_latest.csv",
        "sizes_xlsx": DATA_CRM / "orders_kaspi_with_sizes.xlsx",
        "size_grid_all": DATA_CRM / "size_grid_all_models.xlsx",
        "size_grid_group": DATA_CRM / "size_grid_by_model_group.xlsx",
    }

    results: List[CheckResult] = []

    # Critical
    for key, label in [
        ("orders_csv", "orders_api_latest.csv"),
        ("ksp_map_xlsx", "mappings/ksp_sku_map_updated.xlsx"),
    ]:
        ok = paths[key].exists()
        results.append(
            CheckResult(
                name=f"CRITICAL file {label}",
                ok=ok,
                message=str(paths[key]),
                level="CRITICAL",
            )
        )

    # Important (warn or fail in strict)
    important_defs = [
        ("processed_sales", "processed_sales_latest.csv"),
        ("sizes_xlsx", "orders_kaspi_with_sizes.xlsx"),
    ]
    # At least one size grid
    size_grid_ok = paths["size_grid_all"].exists() or paths["size_grid_group"].exists()
    results.append(
        CheckResult(
            name="IMPORTANT size grid (one of all/group)",
            ok=size_grid_ok,
            message=f"{paths['size_grid_all']} OR {paths['size_grid_group']}",
            level="IMPORTANT",
        )
    )
    for key, label in important_defs:
        results.append(
            CheckResult(
                name=f"IMPORTANT file {label}",
                ok=paths[key].exists(),
                message=str(paths[key]),
                level="IMPORTANT",
            )
        )

    return results, paths


def validate_orders_schema(df: pd.DataFrame) -> List[CheckResult]:
    required = [
        "orderid",
        "date",
        "store_name",
        "ksp_sku_id",
        "sku_key",
        "my_size",
        "qty",
        "sell_price",
        "sku_id",
    ]
    optional = [
        "product_master_code",
        "customer_phone",
        "height",
        "weight",
        "join_code",
    ]

    results: List[CheckResult] = []
    have = set(df.columns)
    missing_required = [c for c in required if c not in have]
    if missing_required:
        results.append(
            CheckResult(
                name="Required columns present",
                ok=False,
                message=f"missing: {missing_required}",
                level="CHECK",
            )
        )
    else:
        results.append(
            CheckResult(
                name="Required columns present",
                ok=True,
                message="ok",
                level="CHECK",
            )
        )

    missing_optional = [c for c in optional if c not in have]
    if missing_optional:
        results.append(
            CheckResult(
                name="Optional columns present",
                ok=False,
                message=f"missing optional: {missing_optional}",
                level="CHECK",
            )
        )
    else:
        results.append(
            CheckResult(
                name="Optional columns present",
                ok=True,
                message="ok",
                level="CHECK",
            )
        )

    return results


def quality_checks(
    df_orders: pd.DataFrame, processed_csv: Optional[Path]
) -> List[CheckResult]:
    results: List[CheckResult] = []

    # Non-null rates
    threshold = 95.0
    for col in ["orderid", "ksp_sku_id", "sku_key", "my_size"]:
        pct = percent_notnull(df_orders[col]) if col in df_orders.columns else 0.0
        ok = pct >= threshold
        results.append(
            CheckResult(
                name=f"Non-null {col} >= {threshold:.1f}%",
                ok=ok,
                message=f"{pct:.1f}%",
                level="CHECK",
            )
        )

    # sku_id integrity
    if {"sku_id", "sku_key", "my_size"}.issubset(df_orders.columns):
        present_mask = df_orders["sku_key"].notna() & df_orders["my_size"].notna()
        expected = (
            df_orders.loc[present_mask, "sku_key"].astype(str).str.strip()
            + "_"
            + df_orders.loc[present_mask, "my_size"].astype(str).str.strip()
        )
        actual = df_orders.loc[present_mask, "sku_id"].astype(str).str.strip()
        mismatches = expected != actual
        mismatch_count = int(mismatches.sum())
        ok = mismatch_count <= 5
        msg = f"mismatches={mismatch_count}"
        if mismatch_count:
            samples = df_orders.loc[present_mask & mismatches].head(5)[
                [
                    c
                    for c in ["orderid", "sku_key", "my_size", "sku_id"]
                    if c in df_orders.columns
                ]
            ]
            msg += f"; first5=\n{samples.to_string(index=False)}"
        results.append(
            CheckResult(
                name="sku_id format matches sku_key+my_size",
                ok=ok,
                message=msg,
                level="CHECK",
            )
        )

    # Processed sales coverage
    if processed_csv and processed_csv.exists():
        try:
            ps = pd.read_csv(processed_csv)
            ps.columns = [str(c).strip().lower().replace(" ", "_") for c in ps.columns]
            if "sku_id" not in ps.columns:
                results.append(
                    CheckResult(
                        name="processed_sales has sku_id column",
                        ok=False,
                        message="missing sku_id",
                        level="CHECK",
                    )
                )
            else:
                df_orders_sku = (
                    set(df_orders["sku_id"].dropna().astype(str).str.strip())
                    if "sku_id" in df_orders.columns
                    else set()
                )
                ps_sku = set(ps["sku_id"].dropna().astype(str).str.strip())
                missing = df_orders_sku - ps_sku
                ok = len(missing) == 0
                msg = f"missing_count={len(missing)}"
                results.append(
                    CheckResult(
                        name="processed_sales contains all orders sku_id",
                        ok=ok,
                        message=msg,
                        level="CHECK",
                    )
                )
        except Exception as exc:
            results.append(
                CheckResult(
                    name="processed_sales readable",
                    ok=False,
                    message=str(exc),
                    level="CHECK",
                )
            )

    return results


def print_summary(results: List[CheckResult], strict: bool) -> bool:
    overall_ok = True
    for r in results:
        emoji = (
            "✅" if r.ok else ("⚠️" if r.level == "IMPORTANT" and not strict else "❌")
        )
        if not r.ok and (r.level == "CRITICAL" or strict or r.level == "CHECK"):
            overall_ok = False
        print(f"{emoji} {r.name:45} {r.message}")
    print("\n" + ("✅ PASS" if overall_ok else "❌ FAIL"))
    return overall_ok


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CI sanity checks for Kaspi ETL")
    parser.add_argument(
        "--strict", action="store_true", help="Treat IMPORTANT as critical"
    )
    args = parser.parse_args(argv)

    path_results, paths = check_paths(strict=args.strict)

    # Early exit if critical missing
    overall_results: List[CheckResult] = []
    overall_results.extend(path_results)

    orders_df = (
        read_orders_csv(paths["orders_csv"]) if paths["orders_csv"].exists() else None
    )
    if orders_df is not None:
        overall_results.extend(validate_orders_schema(orders_df))
        overall_results.extend(quality_checks(orders_df, paths["processed_sales"]))
    else:
        overall_results.append(
            CheckResult(
                name="orders_api_latest.csv readable",
                ok=False,
                message="missing or unreadable",
                level="CHECK",
            )
        )

    ok = print_summary(overall_results, strict=args.strict)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
