"""api/database/session.py — Database engine and session management (v5.3-02).

Supports two backends via the DATABASE_URL environment variable:
  - PostgreSQL (API production): postgresql+asyncpg://...
  - SQLite     (CLI / tests):    sqlite:///path/to/db.sqlite

When DATABASE_URL is not set, defaults to a local SQLite file in outputs/.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.database.models import Base

_DEFAULT_SQLITE_PATH = Path(__file__).resolve().parent.parent.parent / "outputs" / "groundtruth.db"

_DATABASE_URL: str | None = None
_engine = None
_SessionLocal: sessionmaker | None = None


def get_database_url() -> str:
    """Resolve the database URL from environment or default to SQLite."""
    return os.environ.get("DATABASE_URL", f"sqlite:///{_DEFAULT_SQLITE_PATH}")


def _get_engine():
    """Lazy-create the SQLAlchemy engine."""
    global _engine
    if _engine is None:
        url = get_database_url()
        connect_args = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    return _engine


def _get_session_factory() -> sessionmaker:
    """Lazy-create the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine(), autoflush=False, expire_on_commit=False)
    return _SessionLocal


def get_db() -> Session:
    """FastAPI dependency: yield a database session, close on teardown."""
    factory = _get_session_factory()
    session = factory()
    try:
        return session
    except Exception:
        session.close()
        raise


def init_db() -> None:
    """Create all tables. Used for dev/test setup — production uses Alembic.

    Also runs lightweight column migrations for SQLite (which doesn't support
    adding columns via create_all on existing tables).
    """
    engine = _get_engine()
    Base.metadata.create_all(bind=engine)
    _migrate_columns(engine)


def _migrate_columns(engine) -> None:
    """Add columns that create_all can't add to existing SQLite tables."""
    migrations = [
        ("users", "clerk_user_id", "VARCHAR(255)"),
        ("users", "deleted_at", "DATETIME"),
    ]
    with engine.connect() as conn:
        for table, column, col_type in migrations:
            try:
                conn.execute(
                    __import__("sqlalchemy").text(
                        f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                    )
                )
                conn.commit()
            except Exception:
                # Column already exists — expected on repeat runs
                conn.rollback()


def reset_engine() -> None:
    """Tear down the engine and session factory. Used in tests."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
