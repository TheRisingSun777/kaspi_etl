"""
Daily operations orchestrator for Phase 1.

Reads flags from STATE.json and runs, with timing:
- crm_repair_sales.py
- crm_process_sales.py
- crm_build_packing_pdfs.py (if present) or scripts/run_build_labels.sh (fallback) if present
- crm_load_to_db.py

Writes a run log to logs/daily/YYYY-MM-DDTHHMM.log.

Run:
  ./venv/bin/python scripts/daily_operations.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = REPO_ROOT / "STATE.json"
LOGS_DIR = REPO_ROOT / "logs" / "daily"


def load_state() -> dict:
    if STATE_PATH.exists():
        with STATE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "flags": {
            "use_fixed_sales": True,
            "dry_run": True,
        }
    }


def timestamp_for_filename() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H%M")


def run_step(cmd: list[str], log_lines: list[str], name: str) -> int:
    start = time.monotonic()
    log_lines.append(f"==> START {name} at {datetime.now().isoformat(timespec='seconds')}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        duration = time.monotonic() - start
        log_lines.append(f"{name} returncode={result.returncode} duration_sec={duration:.2f}")
        if result.stdout:
            log_lines.append(f"{name} stdout:\n{result.stdout.strip()}")
        if result.stderr:
            log_lines.append(f"{name} stderr:\n{result.stderr.strip()}")
        return result.returncode
    except Exception as exc:  # pragma: no cover
        duration = time.monotonic() - start
        log_lines.append(f"{name} exception after {duration:.2f}s: {exc}")
        return 1


def main() -> int:
    state = load_state()
    flags = state.get("flags", {})
    use_fixed_sales = bool(flags.get("use_fixed_sales", True))
    dry_run = bool(flags.get("dry_run", True))

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"{timestamp_for_filename()}.log"
    log_lines: list[str] = []
    log_lines.append(f"Daily ops started at {datetime.now().isoformat(timespec='seconds')}")
    log_lines.append(f"Flags: use_fixed_sales={use_fixed_sales}, dry_run={dry_run}")

    py = sys.executable
    scripts_dir = REPO_ROOT / "scripts"

    rc = 0
    # 1) Repair
    rc |= run_step([py, str(scripts_dir / "crm_repair_sales.py")], log_lines, "crm_repair_sales")
    # 2) Process
    rc |= run_step([py, str(scripts_dir / "crm_process_sales.py")], log_lines, "crm_process_sales")
    # 3) Build PDFs (optional)
    build_pdfs_py = scripts_dir / "crm_build_packing_pdfs.py"
    build_labels_sh = scripts_dir / "run_build_labels.sh"
    if build_pdfs_py.exists():
        rc |= run_step([py, str(build_pdfs_py)], log_lines, "crm_build_packing_pdfs")
    elif build_labels_sh.exists():
        rc |= run_step([str(build_labels_sh)], log_lines, "run_build_labels.sh")
    else:
        log_lines.append("Skipping packing PDFs step (no script found)")
    # 4) Picklist (warehouse)
    rc |= run_step([py, str(scripts_dir / "crm_build_picklist.py")], log_lines, "crm_build_picklist")
    # 5) Export for Business_model
    rc |= run_step([py, str(scripts_dir / "export_for_business_model.py")], log_lines, "export_for_business_model")
    # 6) Validate data
    rc |= run_step([py, str(scripts_dir / "validate_phase1_data.py")], log_lines, "validate_phase1_data")
    # 7) Load DB
    rc |= run_step([py, str(scripts_dir / "crm_load_to_db.py")], log_lines, "crm_load_to_db")

    log_lines.append(f"Daily ops finished at {datetime.now().isoformat(timespec='seconds')} rc={rc}")
    log_file.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print(f"Run log written: {log_file}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())


