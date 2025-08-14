#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime
from typing import Tuple

import pytz


def today_range_ms(tz: str = "Asia/Almaty") -> Tuple[int, int]:
    """Return (from_ms, to_ms) for today's [00:00:00, 23:59:59] in given timezone.

    - tz: IANA timezone string, default Asia/Almaty
    - Returns epoch milliseconds (ints)
    """
    zone = pytz.timezone(tz)
    now = datetime.now(zone)
    start = zone.localize(datetime(now.year, now.month, now.day, 0, 0, 0))
    end = zone.localize(datetime(now.year, now.month, now.day, 23, 59, 59))
    to_ms = lambda d: int(d.timestamp() * 1000)
    return to_ms(start), to_ms(end)


