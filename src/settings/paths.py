from __future__ import annotations

from pathlib import Path
import os


ROOT = Path(os.getenv("PROJECT_ROOT", Path(__file__).resolve().parents[2]))
DATA_CRM = ROOT / os.getenv("DATA_CRM_DIR", "data_crm")
INBOX = DATA_CRM / "inbox"
WAYBILLS = INBOX / "waybills"
LABELS_GROUPED = DATA_CRM / "labels_grouped"
REPORTS = DATA_CRM / "reports"
DB_DIR = ROOT / "db"

for p in (DATA_CRM, INBOX, WAYBILLS, LABELS_GROUPED, REPORTS, DB_DIR):
    p.mkdir(parents=True, exist_ok=True)
