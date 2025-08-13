#!/usr/bin/env python3

import asyncio
import datetime as dt
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx
import pandas as pd
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

# Load environment (.env.local preferred, then .env)
load_dotenv(".env.local", override=False)
load_dotenv(override=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

KASPI_BASE = (
    os.getenv("KASPI_BASE") or os.getenv("KASPI_API_BASE_URL") or "https://kaspi.kz/shop/api/v2"
)
KASPI_TOKEN = os.getenv("KASPI_TOKEN") or os.getenv("X_AUTH_TOKEN") or os.getenv("KASPI_API_TOKEN")

DATA_CRM_DIR = Path("data_crm")
INPUTS_DIR = DATA_CRM_DIR / "inputs"
CACHE_DIR = DATA_CRM_DIR / "api_cache"
INPUTS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _today_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
async def fetch_active_orders() -> Dict[str, Any]:
    if not KASPI_TOKEN:
        raise RuntimeError("Missing API token. Set KASPI_TOKEN/X_AUTH_TOKEN/KASPI_API_TOKEN in env")

    headers = {
        "X-Auth-Token": KASPI_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "kaspi-etl/1.0 (+python-httpx)",
    }

    url = f"{KASPI_BASE}/orders"
    # Allow paging/filters via env (fallback to small page to reduce load/timeouts)
    page = int(os.getenv("KASPI_ORDERS_PAGE", "0"))
    size = int(os.getenv("KASPI_ORDERS_SIZE", "50"))
    status = os.getenv("KASPI_ORDERS_STATUS", "")  # e.g., ACCEPTED_BY_MERCHANT
    params = {"page": page, "size": size}
    if status:
        params["status"] = status
    logger.info("Fetching active orders from %s with params %s", url, params)

    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()


def normalize_orders(payload: Dict[str, Any]) -> pd.DataFrame:
    # Assume structure like {"data": [{order...}, ...]} or fallback to list
    records: List[Dict[str, Any]]
    if isinstance(payload, dict):
        if "data" in payload and isinstance(payload["data"], list):
            records = payload["data"]
        else:
            # search for first list in dict values
            list_like = next((v for v in payload.values() if isinstance(v, list)), [])
            records = list_like if isinstance(list_like, list) else []
    elif isinstance(payload, list):
        records = payload
    else:
        records = []

    # Flatten nested structures best-effort
    flat_rows: List[Dict[str, Any]] = []
    for rec in records:
        row: Dict[str, Any] = {}
        if not isinstance(rec, dict):
            continue
        for key, value in rec.items():
            if isinstance(value, dict):
                for sub_k, sub_v in value.items():
                    row[f"{key}_{sub_k}"] = sub_v
            else:
                row[key] = value
        flat_rows.append(row)

    df = pd.DataFrame(flat_rows)
    if df.empty:
        return df

    # Normalize columns: lowercase with underscores
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    # Best-effort mapping to CRM schema
    # Expected CRM columns: orderid, date, ksp_sku_id, sku_key (if derivable), store_name, qty, price
    candidates = {
        "orderid": ["id", "order_id", "orderid"],
        "date": ["date", "created_at", "order_date"],
        "ksp_sku_id": ["code", "sku", "ksp_sku_id", "product_code"],
        "sku_key": ["sku_key", "mastercode", "master_code", "product_master_code"],
        "store_name": ["store_name", "pickupPoint_name", "pickup_point_name", "shop_name"],
        "qty": ["quantity", "qty", "count"],
        "price": ["price", "unit_price", "amount"],
    }

    def pick(series: pd.Series, options: List[str]) -> pd.Series:
        for opt in options:
            if opt in df.columns:
                return df[opt]
        return pd.Series([None] * len(df))

    normalized = pd.DataFrame(
        {
            "orderid": pick(df, candidates["orderid"]),
            "date": pick(df, candidates["date"]),
            "ksp_sku_id": pick(df, candidates["ksp_sku_id"]),
            "sku_key": pick(df, candidates["sku_key"]),
            "store_name": pick(df, candidates["store_name"]),
            "qty": pick(df, candidates["qty"]),
            "price": pick(df, candidates["price"]),
        }
    )

    # Coerce types where possible
    if "date" in normalized.columns:
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.date
    if "qty" in normalized.columns:
        normalized["qty"] = pd.to_numeric(normalized["qty"], errors="coerce")
    if "price" in normalized.columns:
        normalized["price"] = pd.to_numeric(normalized["price"], errors="coerce")

    return normalized


async def main() -> Tuple[Path, Path]:
    stamp = _today_stamp()
    json_path = INPUTS_DIR / f"orders_active_{stamp}.json"
    cache_copy = CACHE_DIR / f"orders_{stamp}.json"
    csv_path = DATA_CRM_DIR / f"active_orders_{stamp}.csv"
    xlsx_path = DATA_CRM_DIR / f"active_orders_{stamp}.xlsx"

    payload = await fetch_active_orders()

    # Save raw JSON
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info("Saved raw orders JSON to %s", json_path)

    # Also save a copy to api_cache for staging consumers
    try:
        with cache_copy.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info("Saved cache copy to %s", cache_copy)
    except Exception as e:
        logger.warning("Could not save cache copy: %s", e)

    # Normalize and save CSV
    df = normalize_orders(payload)
    df.to_csv(csv_path, index=False)
    # Optional XLSX for spreadsheet users
    try:
        df.to_excel(xlsx_path, index=False)
    except Exception as e:
        logger.warning("Could not write XLSX: %s", e)
    logger.info("Saved normalized orders CSV to %s", csv_path)

    return json_path, csv_path


if __name__ == "__main__":
    try:
        j, c = asyncio.run(main())
        print(str(j))
        print(str(c))
    except Exception as exc:
        logger.error("Orders ETL failed: %s", exc)
        raise
