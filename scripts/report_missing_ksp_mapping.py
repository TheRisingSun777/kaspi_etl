#!/usr/bin/env python3

import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATA_CRM = Path("data_crm")
ORDERS_LATEST = DATA_CRM / "orders_api_latest.csv"
REPORTS_DIR = DATA_CRM / "reports"
REPORT_PATH = REPORTS_DIR / "missing_ksp_mapping.csv"


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def is_blank(val: object) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return True
    s = str(val).strip()
    return s == "" or s.lower() in {"nan", "none", "null", "-", "_"}


def infer_model_group(text: Optional[str]) -> str:
    if not text:
        return ""
    s = str(text)
    s = s.replace(" ", "_")
    for delim in ("-", "_", "/"):
        if delim in s:
            s = s.split(delim)[0]
            break
    s = re.sub(r"[^A-Za-z]+", "", s)
    return s.upper() if s else ""


def main() -> int:
    if not ORDERS_LATEST.exists():
        logger.info("No staging CSV found at %s; nothing to report", ORDERS_LATEST)
        return 0

    df = pd.read_csv(ORDERS_LATEST)
    df = normalize_columns(df)

    # Ensure columns exist
    for col in ["orderid", "ksp_sku_id", "store_name", "sku_key"]:
        if col not in df.columns:
            df[col] = ""

    missing = df[df["sku_key"].map(is_blank)].copy()
    if missing.empty:
        logger.info("No missing sku_key rows found; writing empty report headers")
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = pd.DataFrame(columns=["orderid", "ksp_sku_id", "store_name", "guessed_model_group"])
        out.to_csv(REPORT_PATH, index=False)
        print(str(REPORT_PATH))
        return 0

    # Guess model group from ksp_sku_id or sku_key
    missing["guessed_model_group"] = [
        infer_model_group(a) or infer_model_group(b)
        for a, b in zip(missing.get("ksp_sku_id", ""), missing.get("sku_key", ""))
    ]

    out = missing[["orderid", "ksp_sku_id", "store_name", "guessed_model_group"]].copy()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(REPORT_PATH, index=False)
    logger.info("Wrote missing KSP mapping report to %s (%d rows)", REPORT_PATH, len(out))
    print(str(REPORT_PATH))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
