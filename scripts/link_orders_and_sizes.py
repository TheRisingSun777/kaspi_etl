#!/usr/bin/env python3

import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATA_CRM = Path("data_crm")
OUTPUT_XLSX = DATA_CRM / "orders_kaspi_with_sizes.xlsx"
ORDERS_STAGING = DATA_CRM / "orders_api_latest.csv"


def find_latest_orders_file() -> Optional[Path]:
    # Prefer staging CSV written by api_orders_to_csv.py and enriched by join step
    if ORDERS_STAGING.exists():
        return ORDERS_STAGING
    candidates: List[Path] = []
    candidates.extend(DATA_CRM.glob("active_orders_*.csv"))
    candidates.extend(DATA_CRM.glob("active_orders_*.xlsx"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


SIZE_TOKEN_PATTERN = re.compile(
    r"(?i)(?:^|[^A-Z0-9])((?:3XL|XXXL|2XL|XXL|XL|L|M|S|XS|XXS|22|24|26|28|30|32|34))(?=$|[^A-Z0-9])"
)
SIZE_NORMALIZE = {
    "XXS": "XS",
    "XXL": "2XL",
    "XXXL": "3XL",
}


def extract_size_token(*texts: str) -> Optional[str]:
    for text in texts:
        if not text:
            continue
        match = SIZE_TOKEN_PATTERN.search(str(text))
        if match:
            size = match.group(1).upper()
            return SIZE_NORMALIZE.get(size, size)
    return None


def infer_model_group(text: str) -> Optional[str]:
    if not text:
        return None
    s = str(text)
    s = s.replace(" ", "_")
    for delim in ("-", "_", "/"):
        if delim in s:
            s = s.split(delim)[0]
            break
    s = re.sub(r"[^A-Za-z]+", "", s)
    if not s:
        return None
    return s.upper()


def load_group_defaults() -> Optional[pd.DataFrame]:
    for pattern in [
        DATA_CRM / "size_grid_all_models.xlsx",
        DATA_CRM / "size_grid_all_models.csv",
        DATA_CRM / "size_grid_by_model_group.xlsx",
        DATA_CRM / "size_grid_by_model_group.csv",
    ]:
        if pattern.exists():
            try:
                if pattern.suffix.lower() == ".csv":
                    df = pd.read_csv(pattern)
                else:
                    df = pd.read_excel(pattern)
                df = normalize_columns(df)
                have_cols = set(df.columns)
                if {"model_group", "default_size"}.issubset(have_cols):
                    return df[["model_group", "default_size"]].dropna()
            except Exception as e:
                logger.warning("Failed reading size grid %s: %s", pattern, e)
    return None


def main() -> Tuple[Path, pd.DataFrame]:
    orders_path = find_latest_orders_file()
    if not orders_path:
        raise SystemExit("No orders staging CSV/XLSX found in data_crm/")

    logger.info("Using orders file: %s", orders_path)

    if orders_path.suffix.lower() == ".csv":
        df = pd.read_csv(orders_path)
    else:
        df = pd.read_excel(orders_path)

    df = normalize_columns(df)

    for col in ["orderid", "date", "ksp_sku_id", "sku_key", "store_name", "qty"]:
        if col not in df.columns:
            df[col] = None

    for col in ["height", "weight"]:
        if col not in df.columns:
            df[col] = None

    df["model_group"] = df["sku_key"].fillna("").map(infer_model_group)

    df["rec_size"] = [
        extract_size_token(ksp, sku) for ksp, sku in zip(df["ksp_sku_id"].astype(str), df["sku_key"].astype(str))
    ]

    group_defaults = load_group_defaults()
    if group_defaults is not None:
        df = df.merge(
            group_defaults.rename(columns={"default_size": "group_default_size"}),
            how="left",
            left_on="model_group",
            right_on="model_group",
        )
        df["rec_size"] = df["rec_size"].fillna(df["group_default_size"]).astype(object)
        df.drop(columns=[c for c in ["group_default_size"] if c in df.columns], inplace=True)

    df["rec_size"] = df["rec_size"].fillna("M")

    out_cols = [
        "orderid",
        "date",
        "ksp_sku_id",
        "sku_key",
        "store_name",
        "qty",
        "height",
        "weight",
        "rec_size",
    ]
    present_cols = [c for c in out_cols if c in df.columns]
    out_df = df[present_cols].copy()

    OUTPUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_excel(OUTPUT_XLSX, index=False)
    logger.info("Wrote %s", OUTPUT_XLSX)

    print(out_df.head(20).to_string(index=False))

    return OUTPUT_XLSX, out_df


if __name__ == "__main__":
    main()


