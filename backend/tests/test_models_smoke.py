"""
Simple smoke test ensuring metadata can be created on an in-memory SQLite DB.
"""
from __future__ import annotations

from sqlalchemy import create_engine

from backend.db.models import Base


def test_metadata_create_all() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    # No assertion needed—if create_all succeeds without exceptions the schema is sound.
