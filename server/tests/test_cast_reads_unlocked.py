"""Video 245 (7 Nov): the Cast tab sat on placeholders for 16 s and more. Opening Cast, Clips
or Storyboard runs complete_cast (free: every speaker a role, every role in its shots), which
took the video's row lock first, so each read waited while a turn or a take held it, and held
it for the rest of the read. It now looks first without the lock; only a change takes it. The
looks' cost reads only the looks' own jobs, never every turn's prompt."""

from sqlalchemy import event

from tests.test_director import _made, _run


def _locks(db, call) -> list[str]:
    """The video row locks (credits.lock's no-op UPDATE) a call takes."""
    seen = []

    def hook(conn, cursor, statement, *_):
        if statement.lstrip().upper().startswith("UPDATE PROJECTS SET ID"):
            seen.append(statement)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", hook)
    try:
        call()
    finally:
        event.remove(engine, "before_cursor_execute", hook)
    return seen


def test_opening_cast_clips_and_storyboard_takes_no_lock_with_nothing_to_change(
    app, db, owner, editor
):
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db)
    pages = [f"/projects/{pid}/{p}" for p in ("assets", "cast", "clips", "storyboard")]

    def read():
        for url in pages:
            assert owner.get(url).status_code == 200, url

    read()  # anything it had to complete is done once
    assert _locks(db, read) == []  # then every read, however often, takes no lock
