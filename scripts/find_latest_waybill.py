#!/usr/bin/env python3
from pathlib import Path
import sys

base = Path("data_crm/inbox/waybills")
candidates = sorted(base.glob("*/*.zip"))
if not candidates:
    print("", end="")
    sys.exit(3)
print(str(candidates[-1]))


