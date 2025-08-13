#!/usr/bin/env python3

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATA_CRM_DIR = Path("data_crm")
CACHE_DIR = DATA_CRM_DIR / "api_cache"
INPUTS_DIR = DATA_CRM_DIR / "inputs"
OUT_CSV = DATA_CRM_DIR / "orders_api_latest.csv"


def find_most_recent_orders_json() -> Optional[Path]:
    candidates: list[Path] = []
    if CACHE_DIR.exists():
        candidates.extend(CACHE_DIR.glob("orders_*.json"))
    if INPUTS_DIR.exists():
        candidates.extend(INPUTS_DIR.glob("orders_active_*.json"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def load_orders_payload(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def flatten_payload_to_records(payload: Any) -> List[Dict[str, Any]]:
    # Accept dict with "data" list, raw list, or dict with any list value
    records: List[Any]
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            records = payload["data"]
        else:
            first_list = next((v for v in payload.values() if isinstance(v, list)), [])
            records = first_list if isinstance(first_list, list) else []
    elif isinstance(payload, list):
        records = payload
    else:
        records = []

    flat_rows: List[Dict[str, Any]] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        row: Dict[str, Any] = {}
        for k, v in rec.items():
            if isinstance(v, dict):
                for sk, sv in v.items():
                    row[f"{k}_{sk}"] = sv
            else:
                row[k] = v
        flat_rows.append(row)
    return flat_rows


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def to_staging(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_columns(df)
    cols = set(df.columns)
    candidates = {
        "orderid": ["id", "order_id", "orderid"],
        "date": ["date", "created_at", "order_date"],
        "store_name": ["store_name", "pickuppoint_name", "pickup_point_name", "shop_name"],
        "ksp_sku_id": ["code", "sku", "ksp_sku_id", "product_code"],
        "sku_key": ["sku_key", "mastercode", "master_code", "product_master_code"],
        "my_size": ["my_size", "variant_size", "size"],
        "qty": ["quantity", "qty", "count"],
        "sell_price": ["sell_price", "price", "unit_price", "amount"],
        "customer_phone": ["customer_phone", "phone", "customer_phone_number"],
    }

    def pick(options: List[str]) -> pd.Series:
        for opt in options:
            if opt in cols:
                return df[opt]
        return pd.Series([None] * len(df))

    out = pd.DataFrame({k: pick(v) for k, v in candidates.items()})

    # Coerce types best-effort
    out["qty"] = pd.to_numeric(out["qty"], errors="coerce")
    out["sell_price"] = pd.to_numeric(out["sell_price"], errors="coerce")
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.date

    return out


def main() -> int:
    path = find_most_recent_orders_json()
    if not path:
        logger.info("No orders JSON found under %s or %s; nothing to do", CACHE_DIR, INPUTS_DIR)
        return 0

    logger.info("Reading %s", path)
    payload = load_orders_payload(path)
    records = flatten_payload_to_records(payload)

    df = pd.DataFrame(records)
    if df.empty:
        logger.info("No records in payload; writing empty staging CSV with headers")
        empty = pd.DataFrame(
            columns=[
                "orderid",
                "date",
                "store_name",
                "ksp_sku_id",
                "sku_key",
                "my_size",
                "qty",
                "sell_price",
                "customer_phone",
            ]
        )
        empty.to_csv(OUT_CSV, index=False)
        print(str(OUT_CSV))
        return 0

    staging = to_staging(df)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    staging.to_csv(OUT_CSV, index=False)
    logger.info("Wrote %s (%d rows)", OUT_CSV, len(staging))
    print(str(OUT_CSV))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
