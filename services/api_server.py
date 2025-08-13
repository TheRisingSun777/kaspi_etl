#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request

APP_ROOT = Path(__file__).resolve().parents[1]
API_CACHE = APP_ROOT / "data_crm" / "api_cache"
API_CACHE.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Kaspi ETL Webhook Stub", version="0.1.0")


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/orders/ingest")
async def ingest_orders(request: Request) -> dict[str, Any]:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    out_path = API_CACHE / f"webhook_{ts}.json"

    # Try to parse JSON; if not JSON, save raw body
    raw = await request.body()
    try:
        payload = await request.json()
        # Pretty save
        import json

        with out_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        size = len(raw)
        saved_as = "json"
    except Exception:
        # Save raw bytes
        out_path.write_bytes(raw)
        size = len(raw)
        saved_as = "bytes"

    return {"saved": str(out_path), "bytes": size, "mode": saved_as}
