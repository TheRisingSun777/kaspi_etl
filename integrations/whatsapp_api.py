"""
WhatsApp API integration (Twilio or 360dialog) with dry-run support.

Configuration via environment (.env loaded by caller if needed):
- WHATSAPP_VENDOR=twilio|d360
- TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM
- D360_TOKEN, D360_PHONE_NUMBER_ID

send_message(to, text, template_id=None, variables=None, dry_run=True)
- If dry_run: writes JSON to outbox/api_calls/YYYYMMDD/wa_send_{uuid}.json and inserts into wa_outbox (status DRY_RUN)
- Else: calls vendor API, stores HTTP response JSON, and sets status SENT/ERROR accordingly
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import httpx


REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "db" / "erp.db"
OUTBOX_DIR = REPO_ROOT / "outbox" / "api_calls"


def _ensure_dirs() -> None:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)


def _today_dir() -> Path:
    d = OUTBOX_DIR / datetime.now().strftime("%Y%m%d")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _insert_wa_outbox(payload: Dict[str, Any], status: str) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO wa_outbox (id, order_id, to_phone, template, payload_json, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("id") or str(uuid.uuid4()),
                payload.get("order_id"),
                payload.get("to"),
                payload.get("template_id"),
                json.dumps(payload, ensure_ascii=False),
                status,
                datetime.utcnow().isoformat(timespec="seconds") + "Z",
            ),
        )
        conn.commit()


def send_message(
    to: str,
    text: str,
    template_id: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    dry_run: bool = True,
    order_id: Optional[str] = None,
) -> Dict[str, Any]:
    vendor = os.environ.get("WHATSAPP_VENDOR", "d360").strip().lower()
    _ensure_dirs()
    payload: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "to": to,
        "text": text,
        "template_id": template_id,
        "variables": variables or {},
        "vendor": vendor,
        "order_id": order_id,
        "dry_run": dry_run,
    }

    if dry_run:
        path = _today_dir() / f"wa_send_{payload['id']}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _insert_wa_outbox(payload, status="DRY_RUN")
        return {"status": "DRY_RUN", "path": str(path)}

    # Real send
    status = "ERROR"
    response_json: Dict[str, Any] = {}
    try:
        if vendor == "twilio":
            sid = os.environ["TWILIO_SID"]
            token = os.environ["TWILIO_TOKEN"]
            from_whatsapp = os.environ["TWILIO_FROM"]  # 'whatsapp:+123...'
            url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
            data = {
                "From": from_whatsapp,
                "To": f"whatsapp:{to}" if not to.startswith("whatsapp:") else to,
                "Body": text,
            }
            resp = httpx.post(url, data=data, auth=(sid, token), timeout=30.0)
            response_json = resp.json()
            resp.raise_for_status()
            status = "SENT"
        elif vendor == "d360":
            token = os.environ["D360_TOKEN"]
            phone_id = os.environ["D360_PHONE_NUMBER_ID"]
            url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            body = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text},
            }
            resp = httpx.post(url, headers=headers, json=body, timeout=30.0)
            response_json = resp.json()
            resp.raise_for_status()
            status = "SENT"
        else:
            response_json = {"error": f"Unknown vendor '{vendor}'"}
    except Exception as exc:  # capture error
        response_json = {"error": str(exc), **response_json}
        status = "ERROR"
    finally:
        payload["response"] = response_json
        _insert_wa_outbox(payload, status=status)

    return {"status": status, "response": response_json}


__all__ = ["send_message"]


