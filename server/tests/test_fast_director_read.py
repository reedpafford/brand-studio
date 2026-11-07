"""Video 240 (7 Nov): GET /director took 11-30 s (then 50 s) on the test site and starved the
narration's timing. Each director turn keeps its whole prompt, and a read loaded every turn of
the video some 30 times (`turns`, `runs`, `leftover`, `answered` a run), while `over` and
`spent` scanned the whole jobs table by run id. Now a page read loads the video's turns once,
and every run-id query reads only its video's jobs."""

from decimal import Decimal

from sqlalchemy import event

from app import director
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from tests.test_director import _made, _run


def _runs(db, pid: int, n: int, start: int = 0) -> None:
    """`n` more runs that ended, ten turns each, every turn with a long prompt."""
    run = director.turns(db, db.get(Project, pid))[-1].input[director.RUN]
    for r in range(start, start + n):
        for t in range(10):
            db.add(Job(workspace_id=1, created_by_id=1, project_id=pid, kind="write-claude",
                       provider="fake", credits=Decimal(1), status=JobStatus.succeeded,
                       input={"step": director.STEP, director.RUN: {**run, "id": f"old{r}",
                              "turn": t + 1}, "prompt": "p" * 20000, "result": "ok",
                              **({"ended": "Stopped."} if t == 9 else {})},
                       output={"tool": "make_take", "why": "Note 1"}))  # fmt: skip
    db.commit()


def _reads(db, call) -> tuple[int, int]:
    """(every query, the loads of the video's director turns) a read makes."""
    seen, turns = [0], [0]

    def hook(conn, cursor, statement, params, *_):
        seen[0] += 1
        whole = statement.lstrip().startswith("SELECT jobs.") and "(" not in statement.split(
            "FROM")[0]  # whole rows, not a count or a sum  # fmt: skip
        turns[0] += whole and director.STEP in [p for p in (params or ()) if isinstance(p, str)]

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", hook)
    try:
        call()
    finally:
        event.remove(engine, "before_cursor_execute", hook)
    return seen[0], turns[0]


def test_a_page_read_loads_the_videos_turns_once_however_many_runs(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db)

    def read():
        for url in (f"/projects/{pid}/director", f"/projects/{pid}/director/progress"):
            assert owner.get(url).status_code == 200

    _runs(db, pid, 2)
    few, loads = _reads(db, read)
    assert loads <= 2, loads  # once a read (/director, /progress)
    _runs(db, pid, 10, start=2)
    many, loads = _reads(db, read)
    assert loads <= 2, loads
    assert many - few <= 12, (few, many)  # not ten turns' worth of queries a run


def test_run_id_queries_read_only_the_videos_own_jobs(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db)
    run = director.turns(db, db.get(Project, pid))[-1].input[director.RUN]
    statements = []
    engine = db.get_bind()
    hook = lambda conn, cursor, statement, *_: statements.append(statement)  # noqa: E731
    event.listen(engine, "before_cursor_execute", hook)
    try:
        director.over(db, run["id"], pid)
        director.spent(db, run["id"], pid)
        director.own_charged(db, run["id"], pid)
    finally:
        event.remove(engine, "before_cursor_execute", hook)
    assert statements and all("jobs.project_id" in s for s in statements), statements
