"""
Generate mapping coverage reports for processed sales.

Inputs:
- data_crm/processed_sales_20250813.csv
- data_crm/sku_map_crm_*.xlsx (optional, any number)
- data_crm/mappings/ksp_sku_map_updated.xlsx (optional)

Outputs:
- data_crm/reports/mapping_coverage.csv with columns:
  level, key, total_rows, known_sku_id_rows, unknown_rows, coverage_pct
  Levels: "store" (key = store_name) and "sku_key" (key = sku_key)
- data_crm/reports/missing_by_store.csv with columns:
  store_name, sku_key, missing_rows

The notion of "known" is conservative and defined as rows where sku_id is
non-empty and does not contain the token "nan" (case-insensitive) and does
not look like a spreadsheet formula artifact (e.g. contains "XLOOKUP").
If mapping files are present, the row is also considered "known" when the
sku_key or sku_id appear in any mapping.

Run:
  ./venv/bin/python scripts/crm_reports_mapping_coverage.py
"""

from __future__ import annotations

import glob
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CRM = REPO_ROOT / "data_crm"
REPORTS_DIR = DATA_CRM / "reports"

SALES_CSV = DATA_CRM / "processed_sales_20250813.csv"
CRM_MAP_GLOB = str(DATA_CRM / "sku_map_crm_*.xlsx")
KSP_MAP_XLSX = DATA_CRM / "mappings" / "ksp_sku_map_updated.xlsx"


def _lower_columns_inplace(df: pd.DataFrame) -> None:
    df.columns = [str(c).strip().lower() for c in df.columns]


def read_sales(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)
    _lower_columns_inplace(df)
    return df


def load_mapping_sets() -> tuple[set[str], set[str]]:
    """Return (mapped_sku_keys, mapped_sku_ids) from any present mapping files.

    This function best-effort reads mapping files with unknown schemas. It looks
    for columns named like 'sku_key' and 'sku_id'.
    """
    mapped_keys: set[str] = set()
    mapped_ids: set[str] = set()

    def harvest(df: pd.DataFrame) -> None:
        _lower_columns_inplace(df)
        if "sku_key" in df.columns:
            mapped_keys.update(str(v).strip() for v in df["sku_key"].dropna().astype(str) if str(v).strip())
        if "sku_id" in df.columns:
            mapped_ids.update(str(v).strip() for v in df["sku_id"].dropna().astype(str) if str(v).strip())

    # CRM map files
    for path in glob.glob(CRM_MAP_GLOB):
        try:
            df = pd.read_excel(path, engine="openpyxl")
            harvest(df)
        except Exception:
            continue

    # KSP updated mapping
    if KSP_MAP_XLSX.exists():
        try:
            df = pd.read_excel(KSP_MAP_XLSX, engine="openpyxl")
            harvest(df)
        except Exception:
            pass

    return mapped_keys, mapped_ids


def is_known_sku_id(sku_id: object) -> bool:
    if pd.isna(sku_id):
        return False
    text = str(sku_id).strip()
    if not text:
        return False
    lower = text.lower()
    if "nan" in lower:
        return False
    if "xlookup" in lower:
        return False
    return True


def compute_coverage(df: pd.DataFrame, mapped_keys: set[str], mapped_ids: set[str]) -> pd.DataFrame:
    # Base known flag from sku_id
    known = df["sku_id"].apply(is_known_sku_id)

    # Augment known if present in mapping sets
    if "sku_key" in df.columns and mapped_keys:
        known = known | df["sku_key"].astype(str).isin(mapped_keys)
    if mapped_ids:
        known = known | df["sku_id"].astype(str).isin(mapped_ids)

    df = df.copy()
    df["__known__"] = known

    rows = []

    def add_group(level: str, key_series: pd.Series) -> None:
        group = df.groupby(key_series, dropna=False)["__known__"]
        total = group.size()
        known_counts = group.sum()
        # Align indexes
        known_counts = known_counts.reindex(total.index).fillna(0).astype(int)
        unknown = (total - known_counts).astype(int)
        coverage = (known_counts / total.replace(0, pd.NA) * 100).round(2)
        for k in total.index.tolist():
            key_str = "" if pd.isna(k) else str(k)
            rows.append(
                {
                    "level": level,
                    "key": key_str,
                    "total_rows": int(total.loc[k]),
                    "known_sku_id_rows": int(known_counts.loc[k]),
                    "unknown_rows": int(unknown.loc[k]),
                    "coverage_pct": float(coverage.loc[k]) if pd.notna(coverage.loc[k]) else 0.0,
                }
            )

    # Store-level coverage
    store_series = df.get("store_name", pd.Series([pd.NA] * len(df)))
    add_group("store", store_series)

    # SKU_KEY-level coverage
    sku_key_series = df.get("sku_key", pd.Series([pd.NA] * len(df)))
    add_group("sku_key", sku_key_series)

    return pd.DataFrame(rows, columns=[
        "level",
        "key",
        "total_rows",
        "known_sku_id_rows",
        "unknown_rows",
        "coverage_pct",
    ])


def write_missing_by_store(df: pd.DataFrame, mapped_keys: set[str], mapped_ids: set[str]) -> pd.DataFrame:
    known = df["sku_id"].apply(is_known_sku_id)
    if "sku_key" in df.columns and mapped_keys:
        known = known | df["sku_key"].astype(str).isin(mapped_keys)
    if mapped_ids:
        known = known | df["sku_id"].astype(str).isin(mapped_ids)

    missing_df = df.loc[~known].copy()
    store_series = missing_df.get("store_name", pd.Series([pd.NA] * len(missing_df)))
    sku_key_series = missing_df.get("sku_key", pd.Series([pd.NA] * len(missing_df)))
    grp = missing_df.groupby([store_series, sku_key_series]).size().reset_index(name="missing_rows")
    grp.columns = ["store_name", "sku_key", "missing_rows"]
    return grp


def main() -> int:
    if not SALES_CSV.exists():
        raise FileNotFoundError(f"Missing input sales CSV: {SALES_CSV}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    sales_df = read_sales(SALES_CSV)
    mapped_keys, mapped_ids = load_mapping_sets()

    coverage_df = compute_coverage(sales_df, mapped_keys, mapped_ids)
    coverage_path = REPORTS_DIR / "mapping_coverage.csv"
    coverage_df.to_csv(coverage_path, index=False)

    missing_df = write_missing_by_store(sales_df, mapped_keys, mapped_ids)
    missing_path = REPORTS_DIR / "missing_by_store.csv"
    missing_df.to_csv(missing_path, index=False)

    # Print quick summary: top 5 worst coverage by store and by sku_key
    worst_store = (
        coverage_df[coverage_df["level"] == "store"]
        .sort_values(["coverage_pct", "unknown_rows"], ascending=[True, False])
        .head(5)
    )
    worst_sku = (
        coverage_df[coverage_df["level"] == "sku_key"]
        .sort_values(["coverage_pct", "unknown_rows"], ascending=[True, False])
        .head(5)
    )

    def fmt_rows(rows: Iterable[pd.Series]) -> str:
        return ", ".join(f"{r['key']} ({r['coverage_pct']}%)" for _, r in rows)

    print(f"Coverage report written: {coverage_path}")
    print(f"Missing-by-store report written: {missing_path}")
    print("Worst coverage stores (top 5): " + fmt_rows(worst_store.iterrows()))
    print("Worst coverage models (top 5): " + fmt_rows(worst_sku.iterrows()))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


