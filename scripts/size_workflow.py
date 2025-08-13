"""
Size workflow engine (Phase 2).

States: NEW → WAITING_SIZE_INFO → PROPOSING_SIZE → WAITING_CONFIRM → CONFIRMED

Idempotent transitions:
- NEW: enqueue WA "size_check" message and move to WAITING_SIZE_INFO (skip if already sent)
- WAITING_SIZE_INFO: if inbound has height/weight, compute recommendation and send confirm → WAITING_CONFIRM
- WAITING_CONFIRM: on yes → write size_recommendations.final_size and move CONFIRMED; on no → ask again → WAITING_SIZE_INFO

Depends on:
- DB tables from migrations: customers, wa_outbox, wa_inbox, size_recommendations, workflows, events_log
- integrations.whatsapp_api.send_message
- scripts.size_recommendation_engine.SizeRecommendationEngine
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from integrations.whatsapp_api import send_message

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "db" / "erp.db"
STATE_PATH = REPO_ROOT / "STATE.json"


STATE_NEW = "NEW"
STATE_WAITING_SIZE_INFO = "WAITING_SIZE_INFO"
STATE_PROPOSING_SIZE = "PROPOSING_SIZE"
STATE_WAITING_CONFIRM = "WAITING_CONFIRM"
STATE_CONFIRMED = "CONFIRMED"


def load_flags() -> dict[str, Any]:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8")).get("flags", {})
    except Exception:
        return {"dry_run": True}


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def get_customer_phone(conn: sqlite3.Connection, order_id: str) -> str | None:
    cur = conn.cursor()
    cur.execute("SELECT phone FROM customers WHERE id=?", (order_id,))
    row = cur.fetchone()
    return row[0] if row and row[0] else None


def get_sku_key(conn: sqlite3.Connection, order_id: str) -> str | None:
    cur = conn.cursor()
    cur.execute("SELECT sku_key FROM sales WHERE orderid=? LIMIT 1", (order_id,))
    row = cur.fetchone()
    return row[0] if row and row[0] else None


def wa_outbox_sent(conn: sqlite3.Connection, order_id: str, template: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM wa_outbox WHERE order_id=? AND template=? LIMIT 1", (order_id, template))
    return cur.fetchone() is not None


def find_latest_inbox_with_measurements(conn: sqlite3.Connection, phone: str) -> dict[str, Any] | None:
    cur = conn.cursor()
    cur.execute(
        "SELECT text, parsed_json, created_at FROM wa_inbox WHERE from_phone=? ORDER BY created_at DESC LIMIT 50",
        (phone,),
    )
    rows = cur.fetchall()
    for text, parsed_json, created_at in rows:
        try:
            parsed = json.loads(parsed_json) if parsed_json else {}
        except Exception:
            parsed = {}
        if isinstance(parsed, dict) and ("height_cm" in parsed and "weight_kg" in parsed):
            return {"text": text, "parsed": parsed, "created_at": created_at}
    return None


def find_latest_confirmation(conn: sqlite3.Connection, phone: str) -> str | None:
    cur = conn.cursor()
    cur.execute(
        "SELECT parsed_json FROM wa_inbox WHERE from_phone=? ORDER BY created_at DESC LIMIT 50",
        (phone,),
    )
    for (parsed_json,) in cur.fetchall():
        try:
            parsed = json.loads(parsed_json) if parsed_json else {}
        except Exception:
            parsed = {}
        conf = parsed.get("confirmation") if isinstance(parsed, dict) else None
        if conf in {"yes", "no"}:
            return conf
    return None


def compute_recommendation(height_cm: int, weight_kg: int, sku_key: str | None) -> tuple[str, float]:
    # Heuristic mapping from sku_key prefix; defaults
    gender = "Men"
    product_type = "CL"
    try:
        from scripts.size_recommendation_engine import SizeRecommendationEngine

        engine = SizeRecommendationEngine()
        rec = engine.recommend_size(height_cm=height_cm, weight_kg=weight_kg, gender=gender, product_type=product_type)
        return rec.recommended_size, float(rec.confidence_score)
    except Exception:
        return "M", 0.2


def upsert_size_reco(conn: sqlite3.Connection, order_id: str, rec_size: str, confidence: float, height: int, weight: int, final_size: str | None = None) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO size_recommendations(order_id, recommended_size, confidence, height, weight, final_size, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (order_id, rec_size, confidence, height, weight, final_size, now_iso()),
    )
    conn.commit()


def update_workflow_state(conn: sqlite3.Connection, order_id: str, new_state: str) -> None:
    cur = conn.cursor()
    cur.execute("UPDATE workflows SET state=?, updated_at=? WHERE order_id=?", (new_state, now_iso(), order_id))
    conn.commit()


def process_once() -> dict[str, int]:
    flags = load_flags()
    dry_run = bool(flags.get("dry_run", True))
    counts = {STATE_NEW: 0, STATE_WAITING_SIZE_INFO: 0, STATE_PROPOSING_SIZE: 0, STATE_WAITING_CONFIRM: 0, STATE_CONFIRMED: 0}
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        # Count current states
        cur.execute("SELECT state, COUNT(*) FROM workflows GROUP BY state")
        for state, n in cur.fetchall():
            counts[state] = n

        # 1) NEW → WAITING_SIZE_INFO
        cur.execute("SELECT order_id FROM workflows WHERE state=?", (STATE_NEW,))
        for (order_id,) in cur.fetchall():
            phone = get_customer_phone(conn, order_id)
            if not phone:
                continue
            if not wa_outbox_sent(conn, order_id, template="size_check"):
                text = "Здравствуйте! Чтобы подобрать размер, пожалуйста, напишите ваш рост (см) и вес (кг)."
                send_message(to=phone, text=text, template_id="size_check", variables={"order_id": order_id}, dry_run=dry_run, order_id=order_id)
            update_workflow_state(conn, order_id, STATE_WAITING_SIZE_INFO)

        # 2) WAITING_SIZE_INFO → PROPOSING_SIZE → WAITING_CONFIRM
        cur.execute("SELECT order_id FROM workflows WHERE state=?", (STATE_WAITING_SIZE_INFO,))
        for (order_id,) in cur.fetchall():
            phone = get_customer_phone(conn, order_id)
            if not phone:
                continue
            inbound = find_latest_inbox_with_measurements(conn, phone)
            if not inbound:
                continue
            parsed = inbound["parsed"]
            height = int(parsed.get("height_cm"))
            weight = int(parsed.get("weight_kg"))
            sku_key = get_sku_key(conn, order_id)
            rec_size, confidence = compute_recommendation(height, weight, sku_key)
            # Save recommendation snapshot
            upsert_size_reco(conn, order_id, rec_size, confidence, height, weight, final_size=None)
            # Send confirm
            if not wa_outbox_sent(conn, order_id, template="size_confirm"):
                text = f"Спасибо! Рекомендуем размер {rec_size}. Подтвердите, пожалуйста: {rec_size}? (Да/Нет)"
                send_message(to=phone, text=text, template_id="size_confirm", variables={"order_id": order_id, "size": rec_size}, dry_run=dry_run, order_id=order_id)
            update_workflow_state(conn, order_id, STATE_WAITING_CONFIRM)

        # 3) WAITING_CONFIRM → CONFIRMED / back to WAITING_SIZE_INFO
        cur.execute("SELECT order_id FROM workflows WHERE state=?", (STATE_WAITING_CONFIRM,))
        for (order_id,) in cur.fetchall():
            phone = get_customer_phone(conn, order_id)
            if not phone:
                continue
            conf = find_latest_confirmation(conn, phone)
            if conf == "yes":
                # Set final_size from latest reco
                cur.execute(
                    "SELECT recommended_size, height, weight FROM size_recommendations WHERE order_id=? ORDER BY created_at DESC LIMIT 1",
                    (order_id,),
                )
                row = cur.fetchone()
                if row:
                    rec_size, height, weight = row
                    upsert_size_reco(conn, order_id, rec_size, confidence=1.0, height=int(height or 0), weight=int(weight or 0), final_size=rec_size)
                update_workflow_state(conn, order_id, STATE_CONFIRMED)
            elif conf == "no":
                # Ask again for measurements
                if not wa_outbox_sent(conn, order_id, template="size_check_again"):
                    text = "Пожалуйста, укажите точные рост (см) и вес (кг), чтобы подобрать другой размер."
                    send_message(to=phone, text=text, template_id="size_check_again", variables={"order_id": order_id}, dry_run=dry_run, order_id=order_id)
                update_workflow_state(conn, order_id, STATE_WAITING_SIZE_INFO)

    return counts


def main() -> int:
    counts = process_once()
    print("Workflow state counts:")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


