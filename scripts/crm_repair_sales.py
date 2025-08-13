"""
Repair/normalize the CRM sales export for Phase 1.

Functions:
- Normalize sizes using `data_crm/rules/size_normalization.csv`.
- Derive `sku_key` from the most informative name when missing (prefer `kaspi_name_core`, else `kaspi_name_source`).
  Remove trailing size tokens (S/M/L/XL/2XL/3XL/4XL and 48–64), collapse spaces, uppercase with underscores.
- Drop rows where `sku_key` starts with any prefix from `data_crm/rules/ignore_prefixes.txt` (e.g., `ELS_`).
- Write repaired file to `data_crm/sales_ksp_crm_fixed.xlsx` and delta report to
  `data_crm/reports/repair_changes.csv` (old vs new for `sku_key`, `my_size`, `sku_id`).
- Print counts changed for `sku_key` and `my_size`.

Run with the project's virtual environment:
  /Users/adil/Docs/kaspi_etl/venv/bin/python scripts/crm_repair_sales.py
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CRM = REPO_ROOT / "data_crm"
RULES_DIR = DATA_CRM / "rules"
REPORTS_DIR = DATA_CRM / "reports"

SALES_INPUT_XLSX = DATA_CRM / "sales_ksp_crm_20250813_v1.xlsx"
SALES_FIXED_XLSX = DATA_CRM / "sales_ksp_crm_fixed.xlsx"
DELTA_REPORT_CSV = REPORTS_DIR / "repair_changes.csv"

SIZE_RULES_CSV = RULES_DIR / "size_normalization.csv"
IGNORE_PREFIXES_TXT = RULES_DIR / "ignore_prefixes.txt"


def _read_excel(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, engine="openpyxl")


def _lower_columns_inplace(df: pd.DataFrame) -> None:
    df.columns = [str(c).strip().lower() for c in df.columns]


def load_size_rules(path: Path) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not path.exists():
        return mapping
    rules_df = pd.read_csv(path, comment="#", dtype=str)
    rules_df.columns = [c.strip().lower() for c in rules_df.columns]
    for _, row in rules_df.iterrows():
        raw = str(row.get("raw", "")).strip().lower()
        normalized = str(row.get("normalized", "")).strip()
        if raw:
            mapping[raw] = normalized
    return mapping


def load_ignore_prefixes(path: Path) -> List[str]:
    if not path.exists():
        return []
    prefixes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        token = line.strip()
        if not token:
            continue
        prefixes.append(token)
    return prefixes


SIZE_TOKEN_RE = re.compile(r"(?:^|[\s\-_/])(?:(?:[2-4]?XL|XL|L|M|S)|(4[4-9]|5[0-9]|6[0-4]))$", re.IGNORECASE)


def strip_trailing_size_tokens(name: str) -> str:
    if not name:
        return name
    working = name.strip()
    # Iteratively remove trailing size tokens or numeric sizes
    while True:
        # Split by whitespace to examine last token
        parts = working.split()
        if not parts:
            break
        last = parts[-1]
        if SIZE_TOKEN_RE.match(last):
            working = " ".join(parts[:-1]).rstrip()
            continue
        # Also handle separators like '_' or '-' between base and size token at end
        working = re.sub(r"([_\-\s])(?:[2-4]?XL|XL|L|M|S|4[4-9]|5[0-9]|6[0-4])\s*$", "", working, flags=re.IGNORECASE)
        # Check if changed
        if working and working.split() and working.split()[-1] != last:
            continue
        break
    # Collapse multiple spaces
    working = re.sub(r"\s+", " ", working).strip()
    return working


def to_upper_underscored(text: str) -> str:
    if text is None:
        return ""
    # Replace separators to spaces first, collapse, then replace with underscores
    s = str(text).replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = s.upper().replace(" ", "_")
    s = re.sub(r"_+", "_", s)
    return s


def derive_sku_key(row: pd.Series) -> str:
    name_source_cols = ["kaspi_name_core", "kaspi_name_source"]
    for col in name_source_cols:
        if col in row and pd.notna(row[col]) and str(row[col]).strip():
            base = strip_trailing_size_tokens(str(row[col]))
            return to_upper_underscored(base)
    # Fallback to ksp/kaspi SKU id if present
    for col in ["sku_key", "ksp_sku_id", "sku_id_ksp"]:
        if col in row and pd.notna(row[col]) and str(row[col]).strip():
            return to_upper_underscored(str(row[col]))
    return ""


def normalize_my_size(val: object, rules: Dict[str, str]) -> str:
    if pd.isna(val):
        return ""
    raw = str(val).strip()
    if not raw:
        return ""
    mapped = rules.get(raw.lower())
    if mapped:
        return mapped
    # Heuristic: standardize common tokens
    token = raw.upper()
    if token in {"S", "M", "L", "XL", "2XL", "3XL", "4XL"}:
        return token
    return token


def main() -> int:
    if not SALES_INPUT_XLSX.exists():
        raise FileNotFoundError(f"Missing sales input file: {SALES_INPUT_XLSX}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    df = _read_excel(SALES_INPUT_XLSX)
    _lower_columns_inplace(df)

    # Preserve originals for delta report
    original_sku_key = df["sku_key"].copy() if "sku_key" in df.columns else pd.Series([pd.NA] * len(df))
    original_my_size = df["my_size"].copy() if "my_size" in df.columns else pd.Series([pd.NA] * len(df))

    # Normalize my_size
    size_rules = load_size_rules(SIZE_RULES_CSV)
    df["my_size"] = df.get("my_size", "").apply(lambda v: normalize_my_size(v, size_rules))

    # Derive sku_key where missing/blank
    if "sku_key" not in df.columns:
        df["sku_key"] = ""
    missing_key_mask = df["sku_key"].isna() | (df["sku_key"].astype(str).str.strip() == "")
    derived_keys = df[missing_key_mask].apply(derive_sku_key, axis=1)
    df.loc[missing_key_mask, "sku_key"] = derived_keys

    # Ensure canonical format
    df["sku_key"] = df["sku_key"].astype(str).apply(to_upper_underscored)

    # Drop rows by ignore prefixes
    ignore_prefixes = load_ignore_prefixes(IGNORE_PREFIXES_TXT)
    dropped_count = 0
    if ignore_prefixes:
        pattern = re.compile(rf"^(?:{'|'.join(map(re.escape, ignore_prefixes))})")
        match_mask = df["sku_key"].astype(str).str.match(pattern)
        keep_mask = ~match_mask
        dropped_count = int(match_mask.sum())
        # Compute top 10 dropped prefixes
        try:
            dropped_prefixes = (
                df.loc[match_mask, "sku_key"]
                .astype(str)
                .str.extract(rf"^({'|'.join(map(re.escape, ignore_prefixes))})", expand=False)
                .value_counts()
                .head(10)
            )
        except Exception:
            dropped_prefixes = None
        df = df[keep_mask].copy()

    # Compute new sku_id
    df["sku_id"] = df["sku_key"].astype(str) + "_" + df["my_size"].astype(str)

    # Prepare delta report
    old_sku_id = original_sku_key.astype(str).fillna("") + "_" + original_my_size.astype(str).fillna("")
    delta = pd.DataFrame(
        {
            "old_sku_key": original_sku_key,
            "new_sku_key": df["sku_key"],
            "old_my_size": original_my_size,
            "new_my_size": df["my_size"],
            "old_sku_id": old_sku_id,
            "new_sku_id": df["sku_id"],
        }
    )

    # Changed counts
    changed_sku_key = int((delta["old_sku_key"].astype(str).fillna("") != delta["new_sku_key"].astype(str).fillna("")).sum())
    changed_my_size = int((delta["old_my_size"].astype(str).fillna("") != delta["new_my_size"].astype(str).fillna("")).sum())

    # Write outputs
    df.to_excel(SALES_FIXED_XLSX, index=False)
    delta.to_csv(DELTA_REPORT_CSV, index=False)

    print(f"Repaired sales written: {SALES_FIXED_XLSX}")
    print(f"Delta report written: {DELTA_REPORT_CSV}")
    if ignore_prefixes:
        print(f"Rows dropped by ignore prefixes: {dropped_count}")
        if 'dropped_prefixes' in locals() and dropped_prefixes is not None:
            print("Top dropped prefixes (prefix: count):")
            for pref, cnt in dropped_prefixes.items():
                print(f"  {pref}: {int(cnt)}")
    print(f"sku_key changed: {changed_sku_key}")
    print(f"my_size changed: {changed_my_size}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


