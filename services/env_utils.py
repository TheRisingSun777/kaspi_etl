#!/usr/bin/env python3

from __future__ import annotations

import os


def get_env_stripped(name: str, default: str = "") -> str:
    val = os.getenv(name)
    if val is None:
        return default
    s = val.strip()
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        s = s[1:-1]
    return s


