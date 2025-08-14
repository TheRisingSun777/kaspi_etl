#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv

from services.waba_client import (
    WABAApiError,
    is_session_window_error,
    send_document,
    send_template,
    upload_media,
)


load_dotenv(".env.local", override=False)
load_dotenv(override=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
from settings.paths import DATA_CRM, REPORTS as REPORTS_DIR
OUTBOX_DIR = REPO_ROOT / "outbox"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Send grouped label PDFs via WhatsApp Cloud API")
    p.add_argument("--date", default=None, help="Date tag YYYY-MM-DD (default: today)")
    return p.parse_args()


def date_iso(date_str: Optional[str]) -> str:
    if date_str:
        return dt.datetime.strptime(date_str, "%Y-%m-%d").date().isoformat()
    return dt.date.today().isoformat()


def list_recipients() -> List[str]:
    raw = os.getenv("WA_TO_EMPLOYEE", "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace(";", ",").split(",")]
    return [p for p in parts if p]


def load_manifest(src_dir: Path) -> pd.DataFrame:
    m = src_dir / "manifest.csv"
    if m.exists():
        try:
            df = pd.read_csv(m)
            df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
            return df
        except Exception:
            pass
    return pd.DataFrame(columns=["group_pdf", "count", "sku_key", "my_size", "orderids"])  # empty


def log_path() -> Path:
    return REPORTS_DIR / "wa_send_log.csv"


def read_sent_log() -> pd.DataFrame:
    p = log_path()
    if p.exists():
        try:
            df = pd.read_csv(p)
            df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
            return df
        except Exception:
            pass
    return pd.DataFrame(columns=["ts", "to", "file", "size_bytes", "media_id", "message_id", "status", "error_code", "error_title"])  # empty


def append_log(row: Dict[str, str]) -> None:
    p = log_path()
    header = not p.exists()
    import csv

    with p.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["ts", "to", "file", "size_bytes", "media_id", "message_id", "status", "error_code", "error_title"],
        )
        if header:
            w.writeheader()
        w.writerow(row)


def file_already_sent(sent_df: pd.DataFrame, to: str, file: str) -> bool:
    if sent_df.empty:
        return False
    subset = sent_df[(sent_df["to"] == to) & (sent_df["file"] == file) & (sent_df["status"] == "sent")]
    return len(subset) > 0


def main() -> int:
    args = parse_args()
    iso_date = date_iso(args.date)
    src_dir = OUTBOX_DIR / iso_date
    if not src_dir.exists():
        logger.error("Outbox directory not found: %s", src_dir)
        return 2

    pdfs = sorted([p for p in src_dir.glob("*.pdf") if p.is_file()])
    recipients = list_recipients()

    # Dry run if token missing
    if not os.getenv("WA_TOKEN"):
        logger.info("Dry-run: WA_TOKEN missing. Listing files and recipients only.")
        print("Recipients:", ", ".join(recipients) or "<none>")
        for p in pdfs:
            print(p.name)
        return 0

    manifest_df = load_manifest(src_dir)
    sent_df = read_sent_log()

    for to in recipients:
        for pdf in pdfs:
            rel = str(pdf.relative_to(REPO_ROOT)) if pdf.is_relative_to(REPO_ROOT) else str(pdf)
            if file_already_sent(sent_df, to, rel):
                logger.info("Skip already sent: %s -> %s", pdf.name, to)
                continue
            size_bytes = pdf.stat().st_size
            ts = dt.datetime.utcnow().isoformat()
            media_id = ""
            message_id = ""
            status = "error"
            error_code = ""
            error_title = ""
            try:
                media_id = upload_media(pdf)
                resp = send_document(to, media_id=media_id, filename=pdf.name)
                message_id = str(resp.get("messages", [{}])[0].get("id", ""))
                status = "sent"
            except Exception as e:
                # Check for session window error; attempt template then retry
                if is_session_window_error(e):
                    try:
                        # Template name from env, default 'labels_ready'
                        tmpl_name = os.getenv("WA_TEMPLATE_LABELS", "labels_ready")
                        # components: body params [date, count], count from filename pattern (*-N.pdf)
                        import re

                        m = re.search(r"-(\d+)\.pdf$", pdf.name)
                        cnt = m.group(1) if m else "0"
                        comps = [
                            {
                                "type": "body",
                                "parameters": [
                                    {"type": "text", "text": iso_date},
                                    {"type": "text", "text": str(cnt)},
                                ],
                            }
                        ]
                        send_template(to, tmpl_name, "ru", comps)
                        # retry document
                        media_id = upload_media(pdf)
                        resp = send_document(to, media_id=media_id, filename=pdf.name)
                        message_id = str(resp.get("messages", [{}])[0].get("id", ""))
                        status = "sent"
                    except Exception as e2:
                        if isinstance(e2, WABAApiError):
                            error_code = str(e2.error_code or "")
                            error_title = str(e2.error_title or "")
                        else:
                            error_title = str(e2)
                else:
                    if isinstance(e, WABAApiError):
                        error_code = str(e.error_code or "")
                        error_title = str(e.error_title or "")
                    else:
                        error_title = str(e)

            append_log(
                {
                    "ts": ts,
                    "to": to,
                    "file": rel,
                    "size_bytes": size_bytes,
                    "media_id": media_id,
                    "message_id": message_id,
                    "status": status,
                    "error_code": error_code,
                    "error_title": error_title,
                }
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


