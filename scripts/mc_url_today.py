#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from services.date_window import today_range_ms


def strip_quotes(s: str) -> str:
    s = s.strip()
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        return s[1:-1]
    return s


def today_orders_url() -> str:
    base = strip_quotes(os.getenv("KASPI_ACTIVEORDERS_URL", ""))
    if not base:
        return ""
    from_ms, to_ms = today_range_ms("Asia/Almaty")
    u = urlparse(base)
    qs = parse_qs(u.query)
    qs["fromDate"] = [str(from_ms)]
    qs["toDate"] = [str(to_ms)]
    new_q = urlencode(qs, doseq=True)
    return urlunparse((u.scheme or "https", u.netloc, u.path, u.params, new_q, u.fragment))


def today_waybills_url() -> str:
    base = strip_quotes(os.getenv("KASPI_WAYBILLS_URL", ""))
    if not base:
        return ""
    # pass-through; vendors sometimes ignore date params for bulk download
    u = urlparse(base)
    qs = parse_qs(u.query)
    new_q = urlencode(qs, doseq=True)
    return urlunparse((u.scheme or "https", u.netloc, u.path, u.params, new_q, u.fragment))


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


