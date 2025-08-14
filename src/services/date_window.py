from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os


def day_range_ms(day_iso: str | None = None) -> tuple[int, int]:
    tz = ZoneInfo(os.getenv("LOCAL_TZ", "Asia/Almaty"))
    if day_iso:
        d = datetime.fromisoformat(day_iso)
        if d.tzinfo is None:
            d = d.replace(tzinfo=tz)
        else:
            d = d.astimezone(tz)
    else:
        d = datetime.now(tz)
    start = d.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1) - timedelta(milliseconds=1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


