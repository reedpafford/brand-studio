"""Database engine, session factory and the declarative base."""

from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

# Stable constraint names so Alembic migrations work the same on SQLite and Postgres.
NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def make_sessionmaker(url: str) -> sessionmaker[Session]:
    if not url.startswith("sqlite"):
        return sessionmaker(create_engine(url), expire_on_commit=False)
    # SQLite (dev and the browser tests only): the API and worker share one file, so wait up to
    # 30 s for a lock instead of 5, and use WAL so reading never waits on the worker's writes.
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA journal_mode=WAL"))
    return sessionmaker(engine, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.sessionmaker() as session:
        yield session


def utcnow() -> datetime:
    """Naive UTC time. Stored without a zone so SQLite and Postgres behave the same."""
    return datetime.now(UTC).replace(tzinfo=None)


class Entity:
    """Columns every table has."""

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
