from __future__ import annotations

from typing import Dict, List


ALIASES: Dict[str, List[str]] = {
    "orderid": ["orderid", "order_id", "id_order", "order no", "order_no", "номер заказа", "заказ"],
    "date": ["date", "order_date", "created_at", "order_datetime", "order_date_time", "дата"],
    "price": ["sell_price", "price", "unit_price", "price_total", "amount", "цена"],
    "height": ["customer_height", "height", "рост", "рост, см", "рост (см)"],
    "weight": ["customer_weight", "weight", "вес", "вес, кг", "вес (кг)"],
    "phone": ["phone", "customer_phone", "phone_number"],
    "qty": ["qty", "quantity", "qty_sold", "count", "amount", "pieces", "кол-во", "количество"],
    "stock_qty": ["qty", "quantity", "stock", "on_hand", "stock_on_hand", "available", "qty_available"],
    "sku_key": ["sku_key", "sku", "model", "product_key", "товар", "product"],
    "my_size": ["my_size", "size", "размер"],
    "ksp_sku_id": ["ksp_sku_id", "sku_id_ksp", "ksp_sku"],
}


def alias_candidates(key: str, extra: list[str] | None = None) -> List[str]:
    seen = []
    for v in ALIASES.get(key, []):
        if v not in seen:
            seen.append(v)
    if extra:
        for v in extra:
            if v not in seen:
                seen.append(v)
    return seen


