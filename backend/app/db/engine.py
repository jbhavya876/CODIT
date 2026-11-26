"""SQLAlchemy 2 engine & session management with production Postgres guard."""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import Config
from backend.app.db.models import Base

_LOCK = threading.Lock()
_ENGINE: Optional[Engine] = None
_SESSION_FACTORY: Optional[sessionmaker[Session]] = None
_CURRENT_DB_URL: Optional[str] = None


def resolve_database_url(database_url: Optional[str] = None, env: Optional[str] = None) -> str:
    url = database_url or os.getenv("DATABASE_URL") or Config.DATABASE_URL
    runtime_env = (env or os.getenv("ENV") or Config.ENV).lower()
    if runtime_env == "production" and url.startswith("sqlite"):
        raise RuntimeError(
            "Refusing to start in ENV=production with SQLite DATABASE_URL; configure PostgreSQL."
        )
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _ensure_sqlite_parent(url: str) -> None:
    if not url.startswith("sqlite:///"):
        return
    raw_path = url[len("sqlite:///"):]
    if raw_path == ":memory:":
        return
    db_path = Path(raw_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)


def _configure_sqlite_pragmas(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


def get_engine(database_url: Optional[str] = None, env: Optional[str] = None) -> Engine:
    global _ENGINE, _SESSION_FACTORY, _CURRENT_DB_URL
    url = resolve_database_url(database_url, env)
    with _LOCK:
        if _ENGINE is not None and _CURRENT_DB_URL == url:
            return _ENGINE
        if _ENGINE is not None:
            _ENGINE.dispose()

        _ensure_sqlite_parent(url)
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        engine = create_engine(
            url,
            future=True,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        if url.startswith("sqlite"):
            _configure_sqlite_pragmas(engine)

        _ENGINE = engine
        _CURRENT_DB_URL = url
        _SESSION_FACTORY = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
        return _ENGINE


def init_db(database_url: Optional[str] = None, env: Optional[str] = None) -> Engine:
    engine = get_engine(database_url=database_url, env=env)
    Base.metadata.create_all(bind=engine)
    return engine


def get_session_factory(database_url: Optional[str] = None, env: Optional[str] = None) -> sessionmaker[Session]:
    init_db(database_url=database_url, env=env)
    assert _SESSION_FACTORY is not None
    return _SESSION_FACTORY


@contextmanager
def session_scope(database_url: Optional[str] = None, env: Optional[str] = None) -> Iterator[Session]:
    factory = get_session_factory(database_url=database_url, env=env)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine_for_tests() -> None:
    global _ENGINE, _SESSION_FACTORY, _CURRENT_DB_URL
    with _LOCK:
        if _ENGINE is not None:
            _ENGINE.dispose()
        _ENGINE = None
        _SESSION_FACTORY = None
        _CURRENT_DB_URL = None
