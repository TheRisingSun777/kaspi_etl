#!/usr/bin/env python3

import sys, asyncio
import datetime as dt
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx
import pandas as pd
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from services.http_client import async_client, get_json

# Load environment (.env.local preferred, then .env)
load_dotenv(".env.local", override=False)
load_dotenv(override=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

_BASE_ENV = os.getenv("KASPI_BASE") or os.getenv("KASPI_API_BASE_URL") or "https://kaspi.kz/shop/api/v2"
KASPI_BASE = _BASE_ENV if _BASE_ENV.startswith("http") else f"https://{_BASE_ENV}"
KASPI_TOKEN = os.getenv("KASPI_TOKEN") or os.getenv("X_AUTH_TOKEN") or os.getenv("KASPI_API_TOKEN")
KASPI_ORDERS_STATUS = os.getenv("KASPI_ORDERS_STATUS", "").strip()
KASPI_ORDERS_SIZE = int(os.getenv("KASPI_ORDERS_SIZE", "25"))
KASPI_ORDERS_PAGES = int(os.getenv("KASPI_ORDERS_PAGES", "5"))
# allow running even if token missing (script writes empty staging CSV on failure)
    
DATA_CRM_DIR = Path("data_crm")
INPUTS_DIR = DATA_CRM_DIR / "inputs"
CACHE_DIR = DATA_CRM_DIR / "api_cache"
INPUTS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _today_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d")


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or 500 <= code < 600
    return isinstance(exc, (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.TransportError))


@retry(retry=retry_if_exception(_is_retryable), stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=30), reraise=True)
async def fetch_orders_page(page: int, size: int, status: str) -> Dict[str, Any]:
    if not KASPI_TOKEN:
        raise RuntimeError("Missing API token. Set KASPI_TOKEN/X_AUTH_TOKEN/KASPI_API_TOKEN in env")

    headers = {
        "X-Auth-Token": KASPI_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "kaspi-etl/1.0 (+python-httpx)",
    }

    url = f"{KASPI_BASE}/orders"
    params: Dict[str, Any] = {"page": page, "size": size}
    if status:
        params["status"] = status
    logger.info("Fetching orders: %s params=%s", url, params)

    async with async_client() as client:
        # Respect header token if present
        return await get_json(client, url, headers=headers, params=params)


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


def _extract_records(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        if "data" in payload and isinstance(payload["data"], list):
            return payload["data"]
        # first list in values
        for v in payload.values():
            if isinstance(v, list):
                return v
        return []
    if isinstance(payload, list):
        return payload
    return []


async def main() -> Tuple[Path, Path]:
    stamp = _today_stamp()
    json_path = INPUTS_DIR / f"orders_active_{stamp}.json"
    cache_copy = CACHE_DIR / f"orders_{stamp}.json"
    csv_path = DATA_CRM_DIR / f"active_orders_{stamp}.csv"
    xlsx_path = DATA_CRM_DIR / f"active_orders_{stamp}.xlsx"

    # Page loop
    all_records: List[Dict[str, Any]] = []
    fetched_pages = 0
    import random
    for page in range(0, max(1, KASPI_ORDERS_PAGES)):
        payload = await fetch_orders_page(page=page, size=KASPI_ORDERS_SIZE, status=KASPI_ORDERS_STATUS)
        recs = _extract_records(payload)
        if not recs:
            break
        all_records.extend(recs)
        fetched_pages += 1
        if page + 1 >= KASPI_ORDERS_PAGES:
            break
        # polite pacing between pages (200–400 ms)
        await asyncio.sleep(random.uniform(0.2, 0.4))

    # Save raw JSON
    merged_payload: Dict[str, Any] = {"data": all_records, "pages": fetched_pages}
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(merged_payload, f, ensure_ascii=False, indent=2)
    logger.info("Saved raw orders JSON to %s", json_path)

    # Also save a copy to api_cache for staging consumers
    try:
        with cache_copy.open("w", encoding="utf-8") as f:
            json.dump(merged_payload, f, ensure_ascii=False, indent=2)
        logger.info("Saved cache copy to %s", cache_copy)
    except Exception as e:
        logger.warning("Could not save cache copy: %s", e)

    # Normalize and save CSV
    df = normalize_orders(merged_payload)
    # Log first 5 order ids and sku codes
    try:
        ids_preview = (
            df.get("orderid").astype(str).head(5).tolist() if "orderid" in df.columns else []
        )
        sku_preview = (
            df.get("ksp_sku_id").astype(str).head(5).tolist() if "ksp_sku_id" in df.columns else []
        )
        logger.info("Sample orderids(5): %s", ids_preview)
        logger.info("Sample ksp_sku_id(5): %s", sku_preview)
    except Exception:
        pass

    df.to_csv(csv_path, index=False)
    # Optional XLSX for spreadsheet users
    try:
        df.to_excel(xlsx_path, index=False)
    except Exception as e:
        logger.warning("Could not write XLSX: %s", e)
    # Also write staging latest CSV for downstream consumers
    latest_csv = DATA_CRM_DIR / "orders_api_latest.csv"
    df.to_csv(latest_csv, index=False)
    logger.info("Saved normalized orders CSV to %s and %s", csv_path, latest_csv)

    return json_path, csv_path


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted by user, exiting 130", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        logger.error("Orders ETL failed: %s", exc)
        # Write empty staging CSV to keep pipeline moving
        try:
            OUT_CSV = Path("data_crm/orders_api_latest.csv")
            OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                columns=[
                    "orderid",
                    "date",
                    "store_name",
                    "ksp_sku_id",
                    "sku_key",
                    "my_size",
                    "qty",
                    "sell_price",
                ]
            ).to_csv(OUT_CSV, index=False)
            print(str(OUT_CSV))
        except Exception:
            pass
