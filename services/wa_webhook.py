"""
FastAPI service handling WhatsApp inbound webhooks (Twilio or 360dialog/Meta).

POST /wa/inbound accepts vendor payload and normalizes to:
  { from, to, text, timestamp }

Additionally parses:
- height in cm: /(\d{2,3})\s*(см|cm)/i
- weight in kg: /(\d{2,3})\s*(кг|kg)/i
- confirmations: yes/no in RU (да/нет), KZ (иә/жоқ), EN (yes/no)

Persists rows into SQLite tables (created by migrations):
- wa_inbox
- events_log
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request


REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "db" / "erp.db"

app = FastAPI(title="WA Inbound Webhook", version="0.1.0")


def _utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _save_inbox_and_event(inbox_row: Dict[str, Any], event_row: Dict[str, Any]) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO wa_inbox (id, order_id, from_phone, text, parsed_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                inbox_row.get("id"),
                inbox_row.get("order_id"),
                inbox_row.get("from_phone"),
                inbox_row.get("text"),
                json.dumps(inbox_row.get("parsed"), ensure_ascii=False),
                inbox_row.get("created_at") or _utc_now(),
            ),
        )
        cur.execute(
            """
            INSERT INTO events_log (id, order_id, kind, data_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event_row.get("id"),
                event_row.get("order_id"),
                event_row.get("kind", "wa_inbound"),
                json.dumps(event_row.get("data"), ensure_ascii=False),
                event_row.get("created_at") or _utc_now(),
            ),
        )
        conn.commit()


HEIGHT_RE = re.compile(r"(\d{2,3})\s*(см|cm)", re.IGNORECASE)
WEIGHT_RE = re.compile(r"(\d{2,3})\s*(кг|kg)", re.IGNORECASE)


def parse_confirmation(text: str) -> Optional[str]:
    t = text.strip().lower()
    yes_words = {"да", "иә", "иа", "yes", "y"}
    no_words = {"нет", "жоқ", "joq", "no", "n"}
    tokens = re.findall(r"[\wёғқңөұүһ]+", t)
    for token in tokens:
        if token in yes_words:
            return "yes"
        if token in no_words:
            return "no"
    return None


def normalize_twilio(form: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if "From" not in form and "Body" not in form:
        return None
    from_phone = str(form.get("From", "")).replace("whatsapp:", "")
    to_phone = str(form.get("To", "")).replace("whatsapp:", "")
    text = str(form.get("Body", "")).strip()
    ts = form.get("Timestamp") or _utc_now()
    return {"from": from_phone, "to": to_phone, "text": text, "timestamp": ts}


def normalize_d360(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # Meta Cloud API shape via 360dialog
    # Expect { "entry": [ { "changes": [ { "value": { "messages": [ {"from": "..", "text": {"body": ".."}, "timestamp": "..." } ] } } ] } ] }
    try:
        entries = body.get("entry") or []
        for entry in entries:
            changes = entry.get("changes") or []
            for ch in changes:
                value = ch.get("value") or {}
                messages = value.get("messages") or []
                if not messages:
                    continue
                msg = messages[0]
                from_phone = msg.get("from", "")
                to_phone = (value.get("metadata") or {}).get("display_phone_number", "")
                text = ""
                if msg.get("type") == "text":
                    text = (msg.get("text") or {}).get("body", "")
                elif "button" in msg:  # interactive reply
                    text = (msg.get("button") or {}).get("text", "")
                ts = msg.get("timestamp")
                if ts and ts.isdigit():
                    ts = datetime.utcfromtimestamp(int(ts)).isoformat(timespec="seconds") + "Z"
                return {"from": from_phone, "to": to_phone, "text": text, "timestamp": ts or _utc_now()}
    except Exception:
        return None
    return None


def enrich_parsed(text: str) -> Dict[str, Any]:
    parsed: Dict[str, Any] = {}
    hm = HEIGHT_RE.search(text)
    wm = WEIGHT_RE.search(text)
    if hm:
        parsed["height_cm"] = int(hm.group(1))
    if wm:
        parsed["weight_kg"] = int(wm.group(1))
    conf = parse_confirmation(text)
    if conf:
        parsed["confirmation"] = conf
    return parsed


@app.post("/wa/inbound")
async def wa_inbound(request: Request) -> Dict[str, Any]:
    # Try Twilio form first
    normalized: Optional[Dict[str, Any]] = None
    try:
        form = dict((await request.form()).items())
        normalized = normalize_twilio(form)
    except Exception:
        normalized = None

    if normalized is None:
        try:
            body = await request.json()
        except Exception:
            body = {}
        normalized = normalize_d360(body)

    if normalized is None:
        # as last resort, read raw body as text
        raw = await request.body()
        normalized = {"from": "", "to": "", "text": raw.decode("utf-8", errors="replace"), "timestamp": _utc_now()}

    parsed = enrich_parsed(normalized.get("text", ""))

    inbox_row = {
        "id": normalized.get("timestamp") + ":" + (normalized.get("from") or ""),
        "order_id": None,
        "from_phone": normalized.get("from"),
        "text": normalized.get("text"),
        "parsed": parsed,
        "created_at": normalized.get("timestamp") or _utc_now(),
    }
    event_row = {
        "id": normalized.get("timestamp") + ":" + (normalized.get("from") or ""),
        "order_id": None,
        "kind": "wa_inbound",
        "data": {"normalized": normalized, "parsed": parsed},
        "created_at": _utc_now(),
    }
    _save_inbox_and_event(inbox_row, event_row)

    return {"ok": True, "parsed": parsed}


