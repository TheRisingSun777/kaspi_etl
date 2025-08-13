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
PROCESSED_LATEST = DATA_CRM / "processed_sales_latest.csv"


def find_orders() -> Optional[Path]:
    """Inputs priority:
    a) data_crm/processed_sales_latest.csv
    b) latest data_crm/processed/processed_sales_*.csv
    c) latest legacy active_orders_*.csv/xlsx
    """
    if PROCESSED_LATEST.exists():
        return PROCESSED_LATEST
    processed_dir = DATA_CRM / "processed"
    candidates: List[Path] = []
    candidates.extend(sorted(processed_dir.glob("processed_sales_*.csv")))
    if candidates:
        return candidates[-1]
    legacy: List[Path] = []
    legacy.extend(DATA_CRM.glob("active_orders_*.csv"))
    legacy.extend(DATA_CRM.glob("active_orders_*.xlsx"))
    if legacy:
        return max(legacy, key=lambda p: p.stat().st_mtime)
    return None


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
    """Take token before first underscore; uppercase; alnum only."""
    if not text:
        return None
    s = str(text).strip()
    token = s.split("_", 1)[0]
    token = re.sub(r"[^A-Za-z0-9]+", "", token)
    return token.upper() if token else None


def load_group_defaults() -> Optional[pd.DataFrame]:
    # Prefer by-model-group, then all-models
    for pattern in [
        DATA_CRM / "size_grid_by_model_group.xlsx",
        DATA_CRM / "size_grid_by_model_group.csv",
        DATA_CRM / "size_grid_all_models.xlsx",
        DATA_CRM / "size_grid_all_models.csv",
    ]:
        if pattern.exists():
            try:
                if pattern.suffix.lower() == ".csv":
                    df = pd.read_csv(pattern)
                else:
                    df = pd.read_excel(pattern)
                df = normalize_columns(df)
                # Expect columns like model_group, default_size (best-effort)
                have_cols = set(df.columns)
                if {"model_group", "default_size"}.issubset(have_cols):
                    return df[["model_group", "default_size"]].dropna()
            except Exception as e:
                logger.warning("Failed reading size grid %s: %s", pattern, e)
    return None


def _load_size_normalization() -> Optional[dict]:
    rules_csv = DATA_CRM / "rules" / "size_normalization.csv"
    if not rules_csv.exists():
        return None
    try:
        df = pd.read_csv(rules_csv)
        df = normalize_columns(df)
        # expect columns like raw, normalized or from,to
        for a, b in [("raw", "normalized"), ("from", "to")]:
            if {a, b}.issubset(df.columns):
                mapping = {
                    str(r[a]).strip().upper(): str(r[b]).strip().upper()
                    for _, r in df.iterrows()
                    if str(r[a]).strip()
                }
                return mapping
    except Exception as e:
        logger.warning("Failed reading size normalization CSV: %s", e)
    return None


def _apply_size_norm(val: Optional[str], mapping: Optional[dict]) -> Optional[str]:
    if not val:
        return val
    if not mapping:
        return str(val).upper()
    return mapping.get(str(val).upper(), str(val).upper())


def main() -> Tuple[Path, pd.DataFrame]:
    orders_path = find_orders()
    if not orders_path:
        raise SystemExit("No orders staging/processed file found in data_crm/")

    logger.info("Using orders file: %s", orders_path)

    if orders_path.suffix.lower() == ".csv":
        df = pd.read_csv(orders_path)
    else:
        df = pd.read_excel(orders_path)

    df = normalize_columns(df)

    # Ensure required columns exist (best-effort)
    for col in ["orderid", "date", "ksp_sku_id", "sku_key", "store_name", "qty"]:
        if col not in df.columns:
            df[col] = None

    # Map processed sales customer fields to unified names
    if "customer_height" in df.columns and "height" not in df.columns:
        df["height"] = df["customer_height"]
    if "customer_weight" in df.columns and "weight" not in df.columns:
        df["weight"] = df["customer_weight"]
    for col in ["height", "weight", "my_size"]:
        if col not in df.columns:
            df[col] = None

    # Populate missing sku_key: product_master_code -> ksp_sku_id
    if "product_master_code" in df.columns or "ksp_sku_id" in df.columns:
        def _fill_sku(row):
            val = str(row.get("sku_key", "") or "").strip()
            if val:
                return val
            pmc = str(row.get("product_master_code", "") or "").strip()
            if pmc:
                return pmc
            ksp = str(row.get("ksp_sku_id", "") or "").strip()
            return ksp if ksp else None
        df["sku_key"] = df.apply(_fill_sku, axis=1)

    # model_group from sku_key or product_master_code
    df["model_group"] = df["sku_key"].fillna("").map(infer_model_group)
    if df["model_group"].isna().any() and "product_master_code" in df.columns:
        mask = df["model_group"].isna() | (df["model_group"] == "")
        df.loc[mask, "model_group"] = (
            df.loc[mask, "product_master_code"].fillna("").map(infer_model_group)
        )

    # rec_size via engine if height & weight present, else grid default, else M
    rec_size: List[Optional[str]] = [None] * len(df)
    size_norm_map = _load_size_normalization()
    # Try optional engine(recommend)
    engine_recommend = None
    try:
        import size_recommendation_engine as sre  # type: ignore

        engine_recommend = getattr(sre, "recommend", None)
    except Exception:
        engine_recommend = None

    # Fallback to group defaults if available
    group_defaults = load_group_defaults()
    group_default_map = (
        dict(zip(group_defaults["model_group"], group_defaults["default_size"]))
        if group_defaults is not None
        else {}
    )

    for idx, row in df.iterrows():
        h = row.get("height", None)
        w = row.get("weight", None)
        mg = row.get("model_group", None)
        chosen = None
        try:
            hnum = float(h) if h is not None and str(h).strip() != "" else None
            wnum = float(w) if w is not None and str(w).strip() != "" else None
        except Exception:
            hnum = None
            wnum = None
        if engine_recommend and hnum is not None and wnum is not None and mg:
            try:
                # Expect engine.recommend(height_cm, weight_kg, model_group) -> str
                chosen = engine_recommend(hnum, wnum, str(mg))
            except Exception:
                chosen = None
        if not chosen and mg and mg in group_default_map:
            chosen = group_default_map.get(mg)
        if not chosen:
            chosen = "M"
        rec_size[idx] = _apply_size_norm(chosen, size_norm_map)
    df["rec_size"] = rec_size

    # Ensure non-null rec_size
    df["rec_size"] = df["rec_size"].fillna("M")

    # Prepare output view
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
        "model_group",
    ]
    present_cols = [c for c in out_cols if c in df.columns]
    out_df = df[present_cols].copy()

    # Write Excel
    OUTPUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_excel(OUTPUT_XLSX, index=False)
    logger.info("Wrote %s", OUTPUT_XLSX)

    preview_cols = [c for c in ["orderid", "sku_key", "height", "weight", "rec_size", "model_group"] if c in out_df.columns]
    print(out_df[preview_cols].head(20).to_string(index=False))
    # Value counts of rec_size
    try:
        print("\nrec_size counts:\n" + out_df["rec_size"].value_counts(dropna=False).to_string())
    except Exception:
        pass

    return OUTPUT_XLSX, out_df


if __name__ == "__main__":
    main()
