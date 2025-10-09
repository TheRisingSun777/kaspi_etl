"""XLSX loader for Kaspi offers roster."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Union

import pandas as pd
from sqlalchemy.orm import Session

from backend.db.models import Offer, Product
from backend.utils.config import load_config

logger = logging.getLogger(__name__)


SKU_KEY_HEADERS = {
    "sku_id_ksp",
    "sku_key",
    "артикул",
    "артикул продавца",
    "sku",
}
KASPI_CODE_HEADERS = {
    "kaspi_art_1",
    "product_id",
    "product code",
    "product_code",
}
SIZE_HEADERS = {"size_kaspi", "размер", "size"}
COLOR_HEADERS = {"color", "цвет", "цвет (основной)"}
TITLE_HEADERS = {"kaspi_name_core", "model", "название (короткое)", "title"}
STORE_HEADERS = {"склад передачи кд", "store", "warehouse", "store_name", "store name", "магазин"}
NAME_SOURCE_HEADERS = {"kaspi_name_source", "название в системе продавца"}

SIZE_SYNONYMS = {
    "XXL": "2XL",
    "XXXL": "3XL",
    "XXXXL": "4XL",
    "XXXXX": "5XL",
    "XXXXXL": "5XL",
    "2XL": "2XL",
    "3XL": "3XL",
    "4XL": "4XL",
    "5XL": "5XL",
    "6XL": "6XL",
}


def _normalize_header(name: str) -> str:
    return re.sub(r"\s+", " ", str(name).strip().lower())


def _find_column(columns: Mapping[str, str], candidates: Iterable[str]) -> Optional[str]:
    for candidate in candidates:
        if candidate.lower() in columns:
            return columns[candidate.lower()]
    return None


def load_store_name_to_id_map(config=None) -> Dict[str, str]:
    cfg = config or load_config()
    mapping: Dict[str, str] = {}
    for account in cfg.kaspi.accounts:
        name_key = account.name.strip().lower()
        id_key = account.account_id.strip().lower()
        mapping[name_key] = account.account_id
        mapping[id_key] = account.account_id
    return mapping


def canonicalize_account_id(
    store_cell: str,
    store_map: Optional[Dict[str, str]] = None,
    *,
    log_missing: bool = True,
) -> str:
    value = str(store_cell or "").strip()
    if not value:
        return ""
    store_map = store_map or {}
    lowered = {k.lower(): v for k, v in store_map.items()}
    candidates = [
        value,
        value.replace(" ", ""),
        value.split("_")[0],
        value.split()[0],
    ]

    for candidate in candidates:
        key = candidate.strip().lower()
        if key and key in lowered:
            return lowered[key]

    match = re.search(r"\d+", value)
    if match:
        return match.group(0)

    if log_missing:
        logger.warning("Unmapped store name '%s'", value)
    return ""


def normalize_size(label: Optional[str]) -> Optional[str]:
    if label is None:
        return None
    text = str(label).strip().upper()
    if not text:
        return None
    return SIZE_SYNONYMS.get(text, text)


def load_offers_to_db(path: Union[str, Path], session: Session) -> int:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Offers file not found: {file_path}")

    sheets = pd.read_excel(file_path, sheet_name=None, engine="openpyxl")
    store_map = load_store_name_to_id_map()

    best_df = None
    best_meta = None
    best_rows = -1

    for sheet_name, sheet_df in sheets.items():
        column_lookup = {_normalize_header(col): col for col in sheet_df.columns}
        sku_col = _find_column(column_lookup, SKU_KEY_HEADERS)
        store_col = _find_column(column_lookup, STORE_HEADERS)
        code_col = _find_column(column_lookup, KASPI_CODE_HEADERS)
        if not (sku_col and store_col and code_col):
            continue
        size_col = _find_column(column_lookup, SIZE_HEADERS)
        color_col = _find_column(column_lookup, COLOR_HEADERS)
        title_col = _find_column(column_lookup, TITLE_HEADERS)

        candidate = sheet_df.copy()
        candidate = candidate.dropna(subset=[sku_col, store_col, code_col])
        candidate[sku_col] = candidate[sku_col].astype(str).str.strip()
        candidate[code_col] = candidate[code_col].astype(str).str.strip()
        candidate[store_col] = candidate[store_col].astype(str).str.strip()
        candidate = candidate[(candidate[sku_col] != "") & (candidate[code_col] != "") & (candidate[store_col] != "")]
        candidate = candidate.drop_duplicates(subset=[store_col, code_col], keep="last")

        row_count = len(candidate)
        if row_count > best_rows:
            best_rows = row_count
            best_df = candidate
            best_meta = {
                "sku_col": sku_col,
                "store_col": store_col,
                "code_col": code_col,
                "size_col": size_col,
                "color_col": color_col,
                "title_col": title_col,
                "sheet_name": sheet_name,
            }

    if best_df is None or best_meta is None:
        raise ValueError("Required headers missing from offers catalog.")

    logger.info(
        "offers: using sheet '%s' with %d rows; matched headers: {sku_key: %s, store: %s, code: %s, size: %s, color: %s, title: %s}",
        best_meta["sheet_name"],
        best_rows,
        best_meta["sku_col"],
        best_meta["store_col"],
        best_meta["code_col"],
        best_meta["size_col"],
        best_meta["color_col"],
        best_meta["title_col"],
    )

    df = best_df
    sku_col = best_meta["sku_col"]
    store_col = best_meta["store_col"]
    code_col = best_meta["code_col"]
    size_col = best_meta["size_col"]
    color_col = best_meta["color_col"]
    title_col = best_meta["title_col"]

    processed = 0
    seen_products: Dict[str, Product] = {}
    for _, row in df.iterrows():
        sku_key = str(row[sku_col]).strip()
        kaspi_code = str(row[code_col]).strip()
        store_value = str(row[store_col]).strip()
        account_id = canonicalize_account_id(store_value, store_map, log_missing=True)

        if not kaspi_code:
            logger.warning("Skipping offer without kaspi_product_code for sku %s", sku_key)
            continue
        if not account_id:
            logger.warning("Skipping offer %s due to missing account id.", kaspi_code)
            continue

        offer_id = f"{account_id}:{kaspi_code}"

        size_value = normalize_size(row[size_col]) if size_col else None
        color_value = (
            str(row[color_col]).strip()
            if color_col and not pd.isna(row[color_col])
            else None
        )

        product = seen_products.get(sku_key) or session.get(Product, sku_key)
        if product is None:
            title_value = (
                str(row[title_col]).strip()
                if title_col and not pd.isna(row[title_col])
                else sku_key
            )
            product = Product(sku_key=sku_key, title=title_value or sku_key, active=True)
            session.add(product)
            seen_products[sku_key] = product

        offer = session.get(Offer, offer_id)
        if offer is None:
            offer = Offer(
                offer_id=offer_id,
                account_id=account_id,
                sku_key=sku_key,
                color=color_value,
                size_label=size_value,
                kaspi_product_code=kaspi_code,
            )
            session.add(offer)
        else:
            offer.account_id = account_id
            offer.sku_key = sku_key
            offer.color = color_value or offer.color
            offer.size_label = size_value or offer.size_label
            offer.kaspi_product_code = kaspi_code

        processed += 1

    session.flush()
    return processed
