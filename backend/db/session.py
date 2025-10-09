"""
Database engine and session utilities.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from backend.utils.config import load_config

ROOT_DIR = Path(__file__).resolve().parents[2]

_ENGINE: Optional[Engine] = None
_SESSION_FACTORY: Optional[sessionmaker] = None
_DATABASE_URL: Optional[URL] = None


def _resolve_database_url(raw_uri: str) -> URL:
    """
    Normalise the configured database URI.

    Converts relative SQLite file paths into absolute ones rooted at the repo so
    scripts can run from any working directory.
    """
    url = make_url(raw_uri)
    if url.get_backend_name() == "sqlite":
        database = url.database
        if database and database not in {":memory:", ""}:
            db_path = Path(database)
            if not db_path.is_absolute():
                db_path = ROOT_DIR / db_path
            url = url.set(database=str(db_path))
    return url


def _get_database_url() -> URL:
    global _DATABASE_URL
    if _DATABASE_URL is None:
        cfg = load_config()
        _DATABASE_URL = _resolve_database_url(cfg.db.uri)
    return _DATABASE_URL


def get_database_url() -> URL:
    """Expose the resolved SQLAlchemy URL for callers that need metadata."""
    return _get_database_url()


def get_engine(echo: bool = False) -> Engine:
    """Return a singleton SQLAlchemy engine."""
    global _ENGINE
    if _ENGINE is None:
        url = _get_database_url()
        connect_args = {"check_same_thread": False} if url.get_backend_name() == "sqlite" else {}
        _ENGINE = create_engine(url, echo=echo, future=True, connect_args=connect_args)
    return _ENGINE


def _get_session_factory() -> sessionmaker:
    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        engine = get_engine()
        _SESSION_FACTORY = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return _SESSION_FACTORY


@contextmanager
def get_session() -> Iterator[Session]:
    """
    Context manager yielding a transactional SQLAlchemy session.

    Rolls back on exceptions and ensures the session is closed.
    """
    session = _get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["get_engine", "get_session", "get_database_url"]
