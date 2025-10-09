"""
XLSX ingestion utilities for baseline dimensions.
"""
from __future__ import annotations

import logging
import math
import re
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import DeliveryBand, Product, SizeMix

logger = logging.getLogger(__name__)

NormalizedName = str

SKU_KEY_CANDIDATES = {
    "sku_key",
    "sku",
    "sku id",
    "sku-id",
    "sku id.",
    "sku id #",
    "sku_key_new",
    "артикул",
    "артикул продавца",
}
WEIGHT_COLUMNS = {
    "weight_kg",
    "weight",
    "вес, кг",
    "вес_кг",
    "weight (kg)",
}
BASE_COST_COLUMNS = {
    "base_cost_cny",
    "basecost_cny",
    "base_cost_cny",
    "закуп в cny",
    "закуп в cny ",
    "basecost",
}
TITLE_COLUMNS = {
    "kaspi_name_core",
    "kaspi name core",
    "name",
    "title",
    "model",
    "product",
    "название",
}
CATEGORY_COLUMNS = {
    "product_type",
    "category",
    "категория",
}

NUMERIC_SIZES = {str(n) for n in range(22, 35)} | {str(n) for n in range(40, 61)}
LETTER_SIZES = {
    "XXXS",
    "XXS",
    "XS",
    "S",
    "M",
    "L",
    "XL",
    "XXL",
    "XXXL",
    "XXXXL",
    "2XL",
    "3XL",
    "4XL",
    "5XL",
    "6XL",
}
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

DELIVERY_HEADER_MAP = {
    "price_min": [
        "Item_Price_min",
        "price_min",
        "price-min",
        "price min",
        "цена_мин",
        "цена мин",
        "цена от",
        "min price",
        "min_price",
        "price from",
        "from_price",
    ],
    "price_max": [
        "Item_Price_max",
        "price_max",
        "price-max",
        "price max",
        "цена_макс",
        "цена макс",
        "цена до",
        "max price",
        "max_price",
        "price to",
        "to_price",
    ],
    "weight_min_kg": [
        "Item_weight_kg_min",
        "weight_min_kg",
        "weight_min",
        "weight min",
        "вес_мин",
        "вес мин",
        "вес от",
        "min weight",
        "min_weight",
        "weight from",
        "from_weight",
        "вес, кг от",
    ],
    "weight_max_kg": [
        "Item_weight_kg_max",
        "weight_max_kg",
        "weight_max",
        "weight max",
        "вес_макс",
        "вес макс",
        "вес до",
        "max weight",
        "max_weight",
        "weight to",
        "to_weight",
        "вес, кг до",
    ],
    "fee_city_pct": [
        "PlatformDLVPct_innercity",
        "inner_city_pct",
        "innercity_pct",
        "город %",
        "внутригород %",
    ],
    "fee_country_pct": [
        "PlatformDLVPct_Country",
        "country_pct",
        "страна %",
        "межгород %",
    ],
    "fee_city_kzt": [
        "City_Fee_KZT",
        "city_fee_kzt",
        "city_kzt",
        "inner_city",
        "city_fee",
        "город",
        "внутригород",
        "город (kzt)",
        "city",
        "item_inner_city",
    ],
    "fee_country_kzt": [
        "Country_Fee_KZT",
        "country_fee_kzt",
        "country_kzt",
        "country",
        "country_fee",
        "страна",
        "межгород",
        "country (kzt)",
        "item_country",
    ],
    "platform_fee_pct": ["PlatformFeePct", "platform_fee_pct"],
    "fx_rate_kzt": ["FX_Rate_KZT", "fx_rate_kzt", "fx_rate", "fx", "fx kzt"],
    "vat_rate": ["VAT_Rate", "vat_rate", "vat", "nds", "vat pct", "vat%"],
    "channel_id": ["ChannelID", "channelid", "channel_id", "channel"],
    "channel_name": ["ChannelName", "channelname", "channel_name", "channel name", "канал"],
    "currency_code": ["currency_code", "currency", "валюта"],
}


def _normalize_header(header: str) -> NormalizedName:
    return re.sub(r"\s+", " ", str(header or "")).strip().lower()


def _find_column(columns: Mapping[NormalizedName, str], candidates: Iterable[str]) -> Optional[str]:
    for candidate in candidates:
        alias = candidate.strip().lower()
        if alias in columns:
            return columns[alias]
    return None


def _coerce_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        cleaned = cleaned.replace(" ", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _normalize_size_label(label: str) -> Optional[str]:
    if not label:
        return None
    raw = label.strip().upper()
    if raw in SIZE_SYNONYMS:
        return SIZE_SYNONYMS[raw]
    if raw in LETTER_SIZES:
        return raw
    if raw.isdigit():
        return raw
    return None


def _extract_size_label(column_name: str) -> Optional[str]:
    tokens = re.split(r"[^\w]+", str(column_name).upper())
    for token in tokens:
        if not token:
            continue
        if token in SIZE_SYNONYMS or token in LETTER_SIZES:
            return _normalize_size_label(token)
        if token.isdigit() and len(token) == 2 and 22 <= int(token) <= 60:
            return token
    return None


def _is_share_column(name: str) -> bool:
    norm = name.upper()
    return any(token in norm for token in ("SHARE", "%", "PCT"))


def _is_units_column(name: str) -> bool:
    norm = name.upper()
    return any(token in norm for token in ("_D", " UNITS", "_UNITS", "UNITS_", "UNIT_", "_UNIT"))


def _parse_share_value(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value < 0:
        return None
    if value > 1:
        if value > 100:
            return None
        # treat as percent
        return value / 100.0
    return value


def _log_size_stock_preview(df: pd.DataFrame, size_columns: Sequence[str]) -> None:
    if not size_columns:
        return
    preview: Dict[str, float] = {}
    for col in size_columns:
        label = _extract_size_label(col)
        if not label:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        if series.notna().sum() == 0:
            continue
        total = float(series.fillna(0).sum())
        if total:
            preview[label] = preview.get(label, 0.0) + total
    if preview:
        logger.info("Stock preview (sum by size columns): %s", preview)


def load_sku_map_to_db(path: Union[str, Path], session: Session) -> int:
    """
    Load SKU map XLSX and upsert product rows.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"SKU map not found: {file_path}")

    df = pd.read_excel(file_path, engine="openpyxl")
    column_lookup = {_normalize_header(col): col for col in df.columns}

    sku_col = _find_column(column_lookup, SKU_KEY_CANDIDATES)
    if not sku_col:
        raise ValueError("Could not locate sku_key column in SKU map.")

    weight_col = _find_column(column_lookup, WEIGHT_COLUMNS)
    base_cost_col = _find_column(column_lookup, BASE_COST_COLUMNS)
    title_col = _find_column(column_lookup, TITLE_COLUMNS)
    category_col = _find_column(column_lookup, CATEGORY_COLUMNS)

    df = df.dropna(subset=[sku_col])
    df[sku_col] = df[sku_col].astype(str).str.strip()
    df = df[df[sku_col] != ""]
    df = df.drop_duplicates(subset=[sku_col], keep="last")

    size_columns = [
        col
        for col in df.columns
        if col not in {sku_col, weight_col, base_cost_col, title_col, category_col}
        and _extract_size_label(col)
    ]
    _log_size_stock_preview(df, size_columns)

    processed = 0
    for _, row in df.iterrows():
        sku_key = str(row[sku_col]).strip()
        if not sku_key:
            continue

        weight = _coerce_float(row[weight_col]) if weight_col else None
        base_cost = _coerce_float(row[base_cost_col]) if base_cost_col else None
        title = (
            str(row[title_col]).strip()
            if title_col and not pd.isna(row[title_col])
            else sku_key
        )
        if not title:
            title = sku_key
        category = (
            str(row[category_col]).strip()
            if category_col and not pd.isna(row[category_col])
            else None
        )

        product = session.get(Product, sku_key)
        if product is None:
            product = Product(sku_key=sku_key, title=title, active=True)
            session.add(product)
        else:
            if title and product.title != title:
                product.title = title

        if category:
            product.category = category
        if weight is not None:
            product.weight_kg = weight
        if base_cost is not None:
            product.base_cost_cny = base_cost
        product.active = True
        processed += 1

    session.flush()
    return processed


def load_size_mix_to_db(path: Union[str, Path], session: Session) -> int:
    """
    Load size mix file and upsert size_mix rows.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Size mix file not found: {file_path}")

    df = pd.read_excel(file_path, engine="openpyxl")
    column_lookup = {_normalize_header(col): col for col in df.columns}

    sku_col = _find_column(column_lookup, SKU_KEY_CANDIDATES)
    if not sku_col:
        raise ValueError("Could not locate sku_key column in size mix file.")

    df = df.dropna(subset=[sku_col])
    df[sku_col] = df[sku_col].astype(str).str.strip()
    df = df[df[sku_col] != ""]

    total_rows = 0
    for _, row in df.iterrows():
        sku_key = str(row[sku_col]).strip()
        if not sku_key:
            continue

        share_values: Dict[str, float] = {}
        units_values: Dict[str, float] = {}

        for col in df.columns:
            if col == sku_col:
                continue
            size_label = _extract_size_label(col)
            if not size_label:
                continue
            value = _coerce_float(row[col])
            if value is None:
                continue
            if _is_share_column(col):
                parsed = _parse_share_value(value)
                if parsed is not None:
                    share_values[size_label] = parsed
            elif _is_units_column(col):
                if value >= 0:
                    units_values[size_label] = value

        if not share_values and units_values:
            total_units = sum(units_values.values())
            if total_units > 0:
                share_values = {k: v / total_units for k, v in units_values.items()}

        if not share_values:
            continue

        # map duplicates by choosing latest non-null share
        normalized_shares: Dict[str, float] = {}
        for size_label, share in share_values.items():
            normalized = _normalize_size_label(size_label)
            if normalized is None or share is None:
                continue
            normalized_shares[normalized] = share

        if not normalized_shares:
            continue

        has_numeric = any(label.isdigit() or label in NUMERIC_SIZES for label in normalized_shares)
        if has_numeric:
            filtered = {k: v for k, v in normalized_shares.items() if k.isdigit() or k in NUMERIC_SIZES}
        else:
            filtered = {k: v for k, v in normalized_shares.items() if not (k.isdigit() or k in NUMERIC_SIZES)}

        if not filtered:
            continue

        total_share = sum(filtered.values())
        if total_share <= 0:
            continue
        if abs(total_share - 1.0) > 0.01:
            logger.warning(
                "Size mix shares for %s sum to %.3f; renormalizing.", sku_key, total_share
            )
        normalized = {k: v / total_share for k, v in filtered.items()}

        session.query(SizeMix).filter_by(sku_key=sku_key).delete(synchronize_session=False)
        for size_label, share in normalized.items():
            session.add(SizeMix(sku_key=sku_key, size_label=size_label, share=share))
            total_rows += 1

    session.flush()
    return total_rows


def _coerce_pct(value: Optional[float]) -> Optional[float]:
    pct = _coerce_float(value)
    if pct is None:
        return None
    if pct < 0:
        return None
    if pct > 1:
        if pct <= 100:
            return pct / 100.0
        return None
    return pct


def _preferred_alias(key: str) -> str:
    aliases = DELIVERY_HEADER_MAP.get(key)
    if not aliases:
        return key
    if isinstance(aliases, (list, tuple)):
        return aliases[0]
    try:
        return sorted(aliases)[0]
    except Exception:  # pragma: no cover - defensive fallback
        return str(next(iter(aliases)))


def _validate_delivery_row(row: Mapping[str, float], original_index: int) -> Optional[Dict[str, Optional[float]]]:
    price_min = _coerce_float(row.get("price_min"))
    price_max = _coerce_float(row.get("price_max"))
    weight_min = _coerce_float(row.get("weight_min_kg"))
    weight_max = _coerce_float(row.get("weight_max_kg"))
    city_fee = _coerce_float(row.get("fee_city_kzt"))
    country_fee = _coerce_float(row.get("fee_country_kzt"))
    city_pct = _coerce_pct(row.get("fee_city_pct"))
    country_pct = _coerce_pct(row.get("fee_country_pct"))
    platform_pct = _coerce_pct(row.get("platform_fee_pct"))
    fx_rate = _coerce_float(row.get("fx_rate_kzt"))
    vat_rate = _coerce_pct(row.get("vat_rate"))
    currency_code = row.get("currency_code")
    channel_id = row.get("channel_id")
    channel_name = row.get("channel_name")

    required_values = {
        "price_min": price_min,
        "price_max": price_max,
        "weight_min_kg": weight_min,
        "weight_max_kg": weight_max,
    }
    missing_required = [
        _preferred_alias(field)
        for field, value in required_values.items()
        if value is None
    ]
    if missing_required:
        logger.warning(
            "Skipping delivery band row %s due to missing: %s",
            original_index,
            ", ".join(missing_required),
        )
        return None

    fee_fields = {
        "fee_city_kzt": city_fee,
        "fee_country_kzt": country_fee,
        "fee_city_pct": city_pct,
        "fee_country_pct": country_pct,
    }
    if all(value is None for value in fee_fields.values()):
        logger.warning(
            "Skipping delivery band row %s due to missing: %s",
            original_index,
            ", ".join(_preferred_alias(field) for field in fee_fields.keys()),
        )
        return None
    if price_max < price_min or weight_max < weight_min:
        logger.warning("Skipping delivery band row %s due to invalid ranges.", original_index)
        return None
    currency = (
        str(currency_code).strip()
        if isinstance(currency_code, str) and str(currency_code).strip()
        else None
    )
    channel_id_val = (
        str(channel_id).strip()
        if isinstance(channel_id, str) and str(channel_id).strip()
        else None
    )
    channel_name_val = (
        str(channel_name).strip()
        if isinstance(channel_name, str) and str(channel_name).strip()
        else None
    )

    if platform_pct is None:
        platform_pct = 0.12

    return {
        "price_min": price_min,
        "price_max": price_max,
        "weight_min_kg": weight_min,
        "weight_max_kg": weight_max,
        "fee_city_kzt": city_fee,
        "fee_country_kzt": country_fee,
        "fee_city_pct": city_pct,
        "fee_country_pct": country_pct,
        "platform_fee_pct": platform_pct,
        "currency_code": currency,
        "fx_rate_kzt": fx_rate,
        "vat_rate": vat_rate,
        "channel_id": channel_id_val,
        "channel_name": channel_name_val,
    }


def load_delivery_bands_to_db(path: Union[str, Path], session: Session) -> int:
    """
    Load delivery bands workbook into the database.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Delivery bands file not found: {file_path}")

    sheets = pd.read_excel(file_path, engine="openpyxl", sheet_name=None)

    required_keys = {"price_min", "price_max", "weight_min_kg", "weight_max_kg"}
    fee_keys = {"fee_city_kzt", "fee_country_kzt", "fee_city_pct", "fee_country_pct"}

    resolved_columns: Dict[str, Optional[str]] = {}
    df = None
    best_rows = -1
    for sheet_name, sheet_df in sheets.items():
        column_lookup = {_normalize_header(col): col for col in sheet_df.columns}
        candidate: Dict[str, Optional[str]] = {key: None for key in DELIVERY_HEADER_MAP}
        missing_required = False
        for canonical, aliases in DELIVERY_HEADER_MAP.items():
            column = _find_column(column_lookup, aliases)
            if canonical in required_keys and column is None:
                missing_required = True
                break
            candidate[canonical] = column
        if missing_required:
            continue
        if not any(candidate.get(key) for key in fee_keys):
            continue
        filtered = sheet_df.dropna(subset=[candidate[k] for k in required_keys if candidate[k]])
        row_count = len(filtered)
        if row_count > best_rows:
            resolved_columns = candidate
            df = sheet_df
            best_rows = row_count

    if df is None or not resolved_columns:
        raise ValueError("Could not locate delivery bands sheet with required columns.")

    processed = 0
    skipped = 0
    for idx, row in df.iterrows():
        payload = {}
        for key, col_name in resolved_columns.items():
            if col_name is not None:
                payload[key] = row.get(col_name)
        validated = _validate_delivery_row(payload, idx)
        if not validated:
            skipped += 1
            continue

        existing_id = session.execute(
            select(DeliveryBand.id).where(
                DeliveryBand.price_min == validated["price_min"],
                DeliveryBand.price_max == validated["price_max"],
                DeliveryBand.weight_min_kg == validated["weight_min_kg"],
                DeliveryBand.weight_max_kg == validated["weight_max_kg"],
            )
        ).scalar_one_or_none()

        if existing_id is not None:
            existing = session.get(DeliveryBand, existing_id)
            existing.fee_city_kzt = validated["fee_city_kzt"]
            existing.fee_country_kzt = validated["fee_country_kzt"]
            existing.fee_city_pct = validated["fee_city_pct"]
            existing.fee_country_pct = validated["fee_country_pct"]
            existing.platform_fee_pct = validated["platform_fee_pct"]
            existing.currency_code = validated["currency_code"]
            existing.fx_rate_kzt = validated["fx_rate_kzt"]
            existing.vat_rate = validated["vat_rate"]
            existing.channel_id = validated["channel_id"]
            existing.channel_name = validated["channel_name"]
        else:
            session.add(DeliveryBand(**validated))
        processed += 1

    session.flush()
    logger.info("Accepted %d delivery rows (skipped %d)", processed, skipped)
    return processed
