"""Database engine and session management.

We use SQLAlchemy's synchronous engine. SQLite is the default for frictionless
local development; the exact same models and queries run on Postgres in
production simply by changing ``DATABASE_URL`` — no code changes required.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()

# check_same_thread is a SQLite-only flag; harmless to compute conditionally.
_connect_args = (
    {"check_same_thread": False}
    if _settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    _settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create tables. In production this would be Alembic migrations."""
    from . import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a request-scoped session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
