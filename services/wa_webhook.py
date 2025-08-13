#!/usr/bin/env python3

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import Body, FastAPI, Request, Response, status


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CRM = REPO_ROOT / "data_crm"
REPORTS_DIR = DATA_CRM / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
RECEIPTS_PATH = REPORTS_DIR / "wa_receipts.jsonl"

WA_VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN", "")

app = FastAPI(title="WA Webhook Receiver")


@app.on_event("startup")
async def _on_startup() -> None:  # pragma: no cover
    logger.info("WA webhook starting. Verify Token = %s", WA_VERIFY_TOKEN or "<not set>")


@app.get("/webhooks/whatsapp")
async def verify_webhook(request: Request) -> Response:
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")
    if mode == "subscribe" and token == WA_VERIFY_TOKEN:
        logger.info("Webhook verified by provider")
        return Response(content=str(challenge), media_type="text/plain", status_code=status.HTTP_200_OK)
    logger.warning("Webhook verify failed: mode=%s token_match=%s", mode, token == WA_VERIFY_TOKEN)
    return Response(content="forbidden", media_type="text/plain", status_code=status.HTTP_403_FORBIDDEN)


def _append_jsonl(obj: Dict[str, Any]) -> None:
    try:
        with RECEIPTS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    except Exception as e:  # pragma: no cover
        logger.error("Failed to append receipts log: %s", e)


@app.post("/webhooks/whatsapp")
async def handle_webhook(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    """Parse WhatsApp webhook notifications and log status receipts.

    Focus on statuses: sent, delivered, read, failed
    """
    received = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        entries: List[Dict[str, Any]] = payload.get("entry", []) if isinstance(payload, dict) else []
        for entry in entries:
            changes = entry.get("changes", []) or []
            for ch in changes:
                value = ch.get("value", {}) or {}
                statuses = value.get("statuses", []) or []
                for st in statuses:
                    status_name = str(st.get("status", "")).lower()
                    if status_name in {"sent", "delivered", "read", "failed"}:
                        rec: Dict[str, Any] = {
                            "ts": now_iso,
                            "status": status_name,
                            "message_id": st.get("id") or st.get("message_id"),
                            "timestamp": st.get("timestamp"),
                            "recipient_id": st.get("recipient_id"),
                            "conversation": st.get("conversation"),
                            "pricing": st.get("pricing"),
                        }
                        if "errors" in st and st.get("errors"):
                            rec["errors"] = st.get("errors")
                        _append_jsonl(rec)
                        received += 1
    except Exception as e:
        logger.error("Webhook parse error: %s", e)
    return {"success": True, "logged_statuses": received}


