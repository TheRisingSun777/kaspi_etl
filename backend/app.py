#!/usr/bin/env python3
"""
Lightweight application stub.

FastAPI will back the service in later phases; for now we expose a simple
healthcheck so tooling can import the module without side effects.
"""
from __future__ import annotations

from typing import Dict

try:
    from fastapi import FastAPI

    app = FastAPI(title="Kaspi ETL Backend")

    @app.get("/health", tags=["health"])
    def healthcheck() -> Dict[str, str]:
        """Minimal liveness probe."""
        return {"status": "ok"}

except ImportError:  # pragma: no cover - FastAPI not available yet
    FastAPI = None  # type: ignore
    app = None

    def healthcheck() -> Dict[str, str]:
        """Fallback healthcheck used when FastAPI is not installed."""
        return {"status": "ok"}

    def create_app() -> None:
        """Signal to the caller that FastAPI must be installed to serve HTTP."""
        raise ImportError(
            "FastAPI is not installed. Install `fastapi` to enable the web app."
        )

