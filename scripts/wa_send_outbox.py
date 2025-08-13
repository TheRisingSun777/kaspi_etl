#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LABELS_GROUPED = REPO_ROOT / "data_crm" / "labels_grouped"


def find_latest_labels_dir() -> Path | None:
    if not LABELS_GROUPED.exists():
        return None
    dated = sorted([p for p in LABELS_GROUPED.iterdir() if p.is_dir()])
    return dated[-1] if dated else None


def main() -> int:
    phone = os.environ.get("WA_EMPLOYEE_PHONE", "").strip()
    if not phone:
        print("WA_EMPLOYEE_PHONE not set")
        return 1
    folder = find_latest_labels_dir()
    if not folder:
        print("No labels_grouped directory found")
        return 1
    script = REPO_ROOT / "scripts" / "wa_send_files.applescript"
    if not script.exists():
        print("AppleScript not found:", script)
        return 1
    cmd = ["osascript", str(script), phone, str(folder)]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())


