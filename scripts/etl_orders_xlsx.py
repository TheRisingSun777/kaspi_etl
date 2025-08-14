#!/usr/bin/env python3

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

import pandas as pd


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from settings.paths import DATA_CRM
INPUT_XLSX = DATA_CRM / "active_orders_latest.xlsx"
OUT_CSV = DATA_CRM / "orders_api_latest.csv"


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def pick(df: pd.DataFrame, options: List[str]) -> pd.Series:
    for opt in options:
        if opt in df.columns:
            return df[opt]
    return pd.Series([None] * len(df))


def main() -> int:
    if not INPUT_XLSX.exists():
        logger.error("Input not found: %s", INPUT_XLSX)
        return 2

    df = pd.read_excel(INPUT_XLSX)
    df = normalize_columns(df)

    # Typical Kaspi export columns examples (ru):
    # 'Номер заказа', 'Код товара'/'Артикул', 'Магазин', 'Количество', 'Цена'
    out = pd.DataFrame()
    out["orderid"] = pick(df, ["номер_заказа", "orderid", "заказ", "id"]).astype(str)
    out["date"] = pick(df, ["дата", "date", "создан", "создано"]).astype(str)
    out["store_name"] = pick(df, ["магазин", "пункт_выдачи", "store_name"]).astype(str)
    out["ksp_sku_id"] = pick(df, ["код_товара", "артикул", "sku", "code"]).astype(str)
    out["sku_key"] = pick(df, ["sku_key", "mastercode", "master_code", "product_master_code"]).astype(str)
    out["product_master_code"] = pick(df, ["product_master_code", "mastercode", "master_code"]).astype(str)
    out["my_size"] = pick(df, ["размер", "size", "variant_size", "my_size"]).astype(str)
    out["qty"] = pd.to_numeric(pick(df, ["количество", "qty", "quantity"]), errors="coerce").fillna(1).astype(int)
    out["sell_price"] = pd.to_numeric(pick(df, ["цена", "стоимость", "price", "amount"]), errors="coerce")
    out["customer_phone"] = pick(df, ["телефон", "phone", "customer_phone"]).astype(str)
    out["height"] = ""
    out["weight"] = ""
    out["join_code"] = out["ksp_sku_id"].astype(str)
    out["sku_id"] = ""

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)
    logger.info("Wrote %s rows=%d", OUT_CSV, len(out))
    print(str(OUT_CSV))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


