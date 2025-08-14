#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
from urllib.parse import urlencode

from services.date_window import day_range_ms


def strip_quotes(s: str) -> str:
    s = s.strip()
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        return s[1:-1]
    return s


def today_orders_url() -> str:
    out_date = os.getenv("OUT_DATE")
    from_ms, to_ms = day_range_ms(out_date)
    merchant_id = strip_quotes(os.getenv("KASPI_MERCHANT_ID", ""))
    preset = strip_quotes(os.getenv("KASPI_PRESET_FILTER", "KASPI_DELIVERY_WAIT_FOR_COURIER"))
    archived = strip_quotes(os.getenv("KASPI_ARCHIVED_STATUSES", "RETURNING,RETURNED"))
    base = strip_quotes(os.getenv("KASPI_MERCHANT_API_BASE", "https://mc.shop.kaspi.kz"))
    path = "/order/view/mc/order/export"
    qs = urlencode(
        {
            "presetFilter": preset,
            "merchantId": merchant_id,
            "fromDate": str(from_ms),
            "toDate": str(to_ms),
            "archivedOrderStatusFilter": archived,
            "_m": merchant_id,
        }
    )
    return f"{base}{path}?{qs}"


def today_waybills_url() -> str:
    out_date = os.getenv("OUT_DATE")
    from_ms, to_ms = day_range_ms(out_date)
    merchant_id = strip_quotes(os.getenv("KASPI_MERCHANT_ID", ""))
    base = strip_quotes(os.getenv("KASPI_MERCHANT_API_BASE", "https://mc.shop.kaspi.kz"))
    path = "/merchantcabinet/api/order/downloadWaybills"
    qs = urlencode({"fromDate": str(from_ms), "toDate": str(to_ms), "_m": merchant_id})
    return f"{base}{path}?{qs}"


def main() -> int:
    if len(sys.argv) < 2:
        print("")
        return 2
    kind = sys.argv[1]
    if kind == "orders":
        print(today_orders_url())
        return 0
    if kind == "waybills":
        print(today_waybills_url())
        return 0
    print("")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())


