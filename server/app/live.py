"""Push updates (follow-up to #1485's quick UI): an open video page hears the moment something on
it changes, instead of asking every few seconds. The news is only a kind name, "this part of the
video changed"; the page reads that part again through its usual reads (web/src/videos/live.ts).

Every session `db.make_sessionmaker` makes (the API's and each worker's) notes, as it flushes,
which videos' jobs, cards or own rows changed; a status set by one UPDATE statement, which the
session never sees, is noted where it's set (`note`). The API and the workers are separate
processes, so the news goes through the database: on Postgres (live and the test site) a
NOTIFY, sent with the commit, that the API listens for; on SQLite (dev and the browser tests)
a line added to a file beside the database once the commit lands, which the API reads. Each
API process listens once for all its open pages, and only while one is open (`Hub`)."""

import asyncio
import logging
import os
import signal
import threading
import time
from itertools import chain

import psycopg
from sqlalchemy import event, func, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

log = logging.getLogger(__name__)
CHANNEL = "bs_live"
NOTED = "live"  # in Session.info: what this transaction changed, sent when it commits
# The kinds a page hears (web/src/videos/live.ts says what each reads again):
JOBS = "jobs"  # one of the video's jobs was queued, started or held (its live card)
MADE = "made"  # one finished: a still, take, cut or director move (the whole page)
CARDS = "cards"  # a card was asked, answered or changed
VIDEO = "video"  # its run, own row or freestyle changed (a move's words, the run's end, a note)
BYE = "bye"  # the stream ends (a restart, or its 10 minutes): the page opens a new one at once


def _kind(status: str) -> str:
    from app.models.jobs import WAITING

    return JOBS if status in WAITING else MADE


def _change(session: Session, row) -> tuple[int, str] | None:
    from app.models.asks import Ask
    from app.models.freestyles import Freestyle
    from app.models.jobs import Job
    from app.models.projects import Project

    if isinstance(row, Job):
        if row in session.new or inspect(row).attrs.status.history.has_changes():
            return row.project_id, _kind(row.status)
        return row.project_id, VIDEO  # a turn's words or the run's end, kept on its job
    if isinstance(row, Ask):
        return row.project_id, CARDS
    if isinstance(row, Project):
        return row.id, VIDEO
    if isinstance(row, Freestyle):
        return row.project_id, VIDEO
    return None


def _add(session: Session, found: set[tuple[int, str]]) -> None:
    """Noted for this transaction. On Postgres its NOTIFY goes at once, on the session's own
    connection: Postgres sends it when the commit lands, drops it on a rollback, and sends a
    repeat once."""
    noted = session.info.setdefault(NOTED, set())
    new = found - noted
    noted |= new
    if new and session.get_bind().dialect.name == "postgresql":
        conn = session.connection()
        for project, kind in new:
            conn.execute(select(func.pg_notify(CHANNEL, f"{project} {kind}")))


def _flushed(session: Session, _context) -> None:
    rows = chain(session.new, session.deleted, (r for r in session.dirty if session.is_modified(r)))
    _add(session, {c for r in rows if (c := _change(session, r)) and c[0]})


def note(db: Session, project_id: int | None, status: str | None = None) -> None:
    """A change made by one UPDATE statement (a status set only if nobody set it first), which
    the session never sees: noted like any other. `status`: the job status it set."""
    if project_id:
        _add(db, {(project_id, _kind(status) if status else VIDEO)})


def _file(url: str) -> str | None:
    """SQLite's news file, beside the database (none for an in-memory one)."""
    path = make_url(url).database
    return f"{path}-live" if path and path != ":memory:" else None


def watch(maker: sessionmaker, url: str) -> None:
    """Note what each flush changes (`make_sessionmaker` calls this for every session). On SQLite
    the news is written once the commit lands, in one small write, so lines from the API and
    the worker never interleave."""
    path = _file(url) if url.startswith("sqlite") else None

    def committed(session: Session) -> None:
        noted = session.info.pop(NOTED, None)
        if noted and path:
            try:
                with open(path, "a") as f:
                    f.write("".join(f"{project} {kind}\n" for project, kind in noted))
            except OSError:  # never fails the commit
                log.exception("live: couldn't write %s", noted)

    event.listen(maker, "after_flush", _flushed)
    event.listen(maker, "after_commit", committed)
    event.listen(maker, "after_rollback", lambda session: session.info.pop(NOTED, None))


Page = tuple[asyncio.AbstractEventLoop, asyncio.Queue]


class Hub:
    """One API process's open video pages, and the listener that hears the news for them: a
    thread, started by the first page and ended when the last one closes."""

    def __init__(self, url: str):
        self.url = url
        self.pages: dict[int, set[Page]] = {}
        self.lock = threading.Lock()
        self.listening = False
        self.ready = threading.Event()  # the listener hears: a page opened now misses nothing
        self.stopping = False

    def join(self, project_id: int) -> Page:
        page = (asyncio.get_running_loop(), asyncio.Queue())
        with self.lock:
            self.pages.setdefault(project_id, set()).add(page)
            if not self.listening:
                self.listening = True
                self.ready = threading.Event()
                threading.Thread(target=self._listen, name="live", daemon=True).start()
        self._end_on_stop()
        return page

    def leave(self, project_id: int, page: Page) -> None:
        with self.lock:
            here = self.pages.get(project_id, set())
            here.discard(page)
            if not here:
                self.pages.pop(project_id, None)

    def tell(self, line: str, everyone: bool = False) -> None:
        project, _, kind = line.strip().partition(" ")
        with self.lock:
            pages = [p for k, ps in self.pages.items() if everyone or str(k) == project for p in ps]
        for loop, queue in pages:
            try:
                loop.call_soon_threadsafe(queue.put_nowait, kind)
            except RuntimeError:  # that page's loop has closed
                pass

    def _end_on_stop(self) -> None:
        """A restart (SIGTERM) ends every stream at once, so the server never waits on them and
        every other request still finishes as before; the pages open new ones. Chained before
        uvicorn's own handler, from the main thread (the server's), once."""
        if self.stopping or threading.current_thread() is not threading.main_thread():
            return
        self.stopping = True
        before = signal.getsignal(signal.SIGTERM)

        def stop(sig, frame):
            self.tell(f"0 {BYE}", everyone=True)
            if callable(before):
                before(sig, frame)
            else:  # no server's own handler: as the signal would have done
                signal.signal(sig, before)
                signal.raise_signal(sig)

        signal.signal(signal.SIGTERM, stop)

    def _watched(self) -> bool:
        with self.lock:
            self.listening = bool(self.pages)
            return self.listening

    def _listen(self) -> None:
        hear = self._tail if self.url.startswith("sqlite") else self._notified
        again = False
        while True:  # a hearer returns once no page is open; the next page starts a new thread
            try:
                return hear(again)
            except Exception:  # the database restarted: listen again, and every page catches up
                log.warning("live: listening again", exc_info=True)
                time.sleep(1)
                again = True
            if not self._watched():
                return

    def _notified(self, again: bool) -> None:
        url = make_url(self.url).set(drivername="postgresql")
        with psycopg.connect(url.render_as_string(hide_password=False), autocommit=True) as conn:
            conn.execute(f"LISTEN {CHANNEL}")
            self.ready.set()
            if again:
                self.tell(f"0 {MADE}", everyone=True)
            while self._watched():
                for note in conn.notifies(timeout=1):
                    self.tell(note.payload)

    def _tail(self, _again: bool) -> None:
        with open(_file(self.url) or os.devnull, "ab+") as f:
            f.seek(0, os.SEEK_END)
            self.ready.set()
            while self._watched():
                line = f.readline()
                if line.endswith(b"\n"):
                    self.tell(line.decode())
                else:  # nothing new, or half a line: read it again whole
                    f.seek(-len(line), os.SEEK_CUR)
                    time.sleep(0.1)
