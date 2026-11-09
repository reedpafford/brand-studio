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
    """Every session tells open video pages what its commits changed (app/live.py)."""
    from app import live

    if not url.startswith("sqlite"):
        engine = create_engine(url)
    else:
        # SQLite (dev and the browser tests only): the API and worker share one file, so wait up
        # to 30 s for a lock instead of 5, and use WAL so reading never waits on worker writes.
        engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
        event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA journal_mode=WAL"))
    maker = sessionmaker(engine, expire_on_commit=False)
    live.watch(maker, url)
    return maker


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.sessionmaker() as session:
        _hold_rows(session)
        yield session


def _hold_rows(session: Session) -> None:
    """A request's session keeps hold of every row it reads until the request ends. The session
    alone lets go of a row nothing else holds, so `db.get` read the same script, draft or rate
    again and again (a video's clip list read them 30 times over). Rows still refresh as before
    when expired; the worker's long-lived sessions don't use this."""
    held: dict[int, object] = {}

    def keep(_s, row):
        held[id(row)] = row

    def drop(_s, row):
        held.pop(id(row), None)

    for name in ("loaded_as_persistent", "pending_to_persistent", "detached_to_persistent",
                 "deleted_to_persistent"):  # fmt: skip
        event.listen(session, name, keep)
    for name in ("persistent_to_detached", "persistent_to_deleted", "persistent_to_transient"):
        event.listen(session, name, drop)


def utcnow() -> datetime:
    """Naive UTC time. Stored without a zone so SQLite and Postgres behave the same."""
    return datetime.now(UTC).replace(tzinfo=None)


class Entity:
    """Columns every table has."""

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
