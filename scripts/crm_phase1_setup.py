"""
Phase 1 CRM setup script

Purpose:
- Build and update a mapping between KSP SKU IDs and store names using the latest CRM sales export.
- If an existing mapping file exists at `data_crm/mappings/ksp_sku_map.xlsx`, it will be loaded and merged.
- The script reads `data_crm/sales_ksp_crm_20250813_v1.xlsx`, extracts the necessary columns,
  normalizes column names to lowercase, merges with the existing data, removes duplicates
  by the pair (ksp_sku_id, store_name), and writes the result to
  `data_crm/mappings/ksp_sku_map_updated.xlsx`.

Outputs:
- `data_crm/mappings/ksp_sku_map_updated.xlsx`

Notes:
- This script assumes the CRM sales file exists at `data_crm/sales_ksp_crm_20250813_v1.xlsx`.
- No credentials are needed. All processing is local.
"""

from pathlib import Path
import sys

import pandas as pd


DATA_DIR = Path("data_crm")
MAPPINGS_DIR = DATA_DIR / "mappings"
EXISTING_MAP_PATH = MAPPINGS_DIR / "ksp_sku_map.xlsx"
UPDATED_MAP_PATH = MAPPINGS_DIR / "ksp_sku_map_updated.xlsx"
CRM_SALES_PATH = DATA_DIR / "sales_ksp_crm_20250813_v1.xlsx"


def ensure_directories_exist() -> None:
    MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)


def load_existing_mapping(existing_map_path: Path) -> pd.DataFrame:
    if existing_map_path.exists():
        df = pd.read_excel(existing_map_path)
        df.columns = [c.strip().lower() for c in df.columns]
        # Ensure expected columns exist; create if missing
        for col in ["ksp_sku_id", "store_name", "sku_key"]:
            if col not in df.columns:
                df[col] = pd.Series(dtype="object")
        return df[["ksp_sku_id", "store_name", "sku_key"]]
    # Create empty mapping with required columns
    return pd.DataFrame(columns=["ksp_sku_id", "store_name", "sku_key"])


def load_crm_sales(crm_sales_path: Path) -> pd.DataFrame:
    if not crm_sales_path.exists():
        raise FileNotFoundError(
            f"CRM sales file not found at: {crm_sales_path}. "
            "Please place the file before running this script."
        )

    df_raw = pd.read_excel(crm_sales_path)
    # Normalize column names to lowercase and strip spaces
    df_raw.columns = [c.strip().lower() for c in df_raw.columns]

    # Expected source columns from CRM: 'SKU_ID_KSP', 'SKU_key', 'STORE_NAME' (case-insensitive)
    rename_map = {
        "sku_id_ksp": "ksp_sku_id",
        "sku_key": "sku_key",
        "store_name": "store_name",
    }

    # Keep only columns we need
    required_source_cols = list(rename_map.keys())
    missing = [c for c in required_source_cols if c not in df_raw.columns]
    if missing:
        raise KeyError(
            "Missing expected columns in CRM sales file: " + ", ".join(missing)
        )

    df = df_raw[required_source_cols].rename(columns=rename_map)

    # Basic cleanup: drop rows missing critical identifiers
    df = df.dropna(subset=["ksp_sku_id", "store_name"]).copy()

    # Standardize text fields
    df["store_name"] = df["store_name"].astype(str).str.strip()
    # Keep sku_key as-is; if present, cast to string to avoid Excel numeric formatting quirks
    if "sku_key" in df.columns:
        df["sku_key"] = df["sku_key"].astype(str).str.strip()

    return df[["ksp_sku_id", "store_name", "sku_key"]]


def merge_mappings(existing_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    combined = pd.concat([existing_df, new_df], ignore_index=True)
    # Remove duplicates based on (ksp_sku_id, store_name)
    combined = combined.drop_duplicates(subset=["ksp_sku_id", "store_name"], keep="first")
    return combined[["ksp_sku_id", "store_name", "sku_key"]]


def main() -> int:
    ensure_directories_exist()

    existing_map_df = load_existing_mapping(EXISTING_MAP_PATH)
    crm_sales_df = load_crm_sales(CRM_SALES_PATH)

    updated_df = merge_mappings(existing_map_df, crm_sales_df)

    # Save updated mapping
    updated_df.to_excel(UPDATED_MAP_PATH, index=False)

    unique_pairs_count = (
        updated_df.drop_duplicates(subset=["ksp_sku_id", "store_name"]).shape[0]
    )
    print(f"Unique (ksp_sku_id, store_name) pairs: {unique_pairs_count}")
    print(f"Updated mapping written to: {UPDATED_MAP_PATH}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # Avoid silent failures; surface clear message
        print(f"Error: {exc}")
        sys.exit(1)


