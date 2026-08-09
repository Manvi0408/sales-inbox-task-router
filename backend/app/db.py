"""SQLAlchemy engine/session + idempotent init_db().

Configured for a free-tier Postgres instance: pool_pre_ping to survive the
connection drops that come with a spun-down / idle DB, and a small pool.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    kwargs: dict = {"pool_pre_ping": True, "future": True}
    if settings.is_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # Small pool for a free-tier Postgres; recycle to dodge stale connections.
        kwargs.update(pool_size=5, max_overflow=2, pool_recycle=280)
    return create_engine(settings.sqlalchemy_url, **kwargs)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every boot."""
    from . import models  # noqa: F401 - register mappers

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
