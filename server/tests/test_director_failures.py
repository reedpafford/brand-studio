"""Audit 6 Nov (real providers): a run never hangs or dead-ends on a failure. A job that fails
before the provider answers tells what waits on it and wakes the director; a tool that breaks
is a refusal; the real-AI budget says itself and offers no press that would be refused again;
one cut-off or unreadable answer is asked again once."""

from decimal import Decimal

from app import claude, director
from app.models.jobs import Job, JobStatus
from app.providers import Result, get_providers
from app.providers.fake_local import FakeWriter
from app.worker import _fail, run_once
from tests.helpers import make_it, ok_when_asked
from tests.test_director import _made, _run, started


def _turns(db, pid):
    step = Job.input["step"].as_string()
    return (db.query(Job).filter(Job.project_id == pid, step == director.STEP)
            .order_by(Job.id).all())  # fmt: skip


def test_a_turn_refused_before_its_answer_ends_the_run_at_once(app, db, owner, editor,
                                                                monkeypatch):  # fmt: skip
    """A 400 (or any error) from the call itself failed the job in `_fail`, which never told
    the director: the run said "running" until the next sweep. Now it ends on that tick."""
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=6)  # its treatment, then Make it
    real = FakeWriter.run

    def broken(self, kind, input):
        if input["step"] == director.STEP:
            raise RuntimeError("400 too many optional parameters")
        return real(self, kind, input)

    monkeypatch.setattr(FakeWriter, "run", broken)
    monkeypatch.setattr(director, "sweep", lambda db: None)  # only `_fail` can end it now
    _run(app, db, ticks=4)
    out = editor.get(f"/projects/{pid}/director").json()
    assert (out["status"], out["ended"]) == ("ended", director.TURN_FAILED), out["ended"]


def test_a_take_watch_that_fails_before_its_answer_isnt_left_watching(db, monkeypatch):
    from app import steps

    told = []
    monkeypatch.setattr("app.take_watch.failed", lambda db, job: told.append(job.id))
    monkeypatch.setattr(steps, "explain", lambda db, job: None)
    job = Job(workspace_id=1, created_by_id=1, kind="write-claude", provider="claude",
              input={"step": "take_watch"}, status=JobStatus.running,
              credits=Decimal(1))  # fmt: skip
    db.add(job)
    db.commit()
    _fail(db, job, "It failed.", "400")
    assert told == [job.id] and db.get(Job, job.id).status == JobStatus.failed


def test_a_failed_take_before_its_answer_is_never_tried_again_on_its_own(db, monkeypatch):
    from app import steps

    tried = []
    monkeypatch.setattr("app.clip_takes.retry", lambda db, job: tried.append(job.id))
    monkeypatch.setattr(steps, "explain", lambda db, job: None)
    job = Job(workspace_id=1, created_by_id=1, kind="video", provider="replicate",
              input={"step": "clip_take"}, status=JobStatus.running,
              credits=Decimal(3))  # fmt: skip
    db.add(job)
    db.commit()
    _fail(db, job, "We can't tell if it ran.", "network")
    assert tried == []  # it may already have been charged


def test_a_tool_that_breaks_is_a_refusal_and_the_run_goes_on(app, db, owner, editor,
                                                            monkeypatch):  # fmt: skip
    from app import director_tools

    pid = _made(app, owner, editor, db)
    split = {"tool": "split_clip", "clip_id": "c1", "why": "b1: too long"}
    monkeypatch.setattr("app.director.choose", started(lambda state: split))

    def boom(*a, **k):
        raise KeyError("clips")

    monkeypatch.setattr(director_tools, "_split", boom)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=12)
    results = [t.input.get("result") or "" for t in _turns(db, pid)]
    assert any(r.startswith("Refused: split_clip hit an error on our side") for r in results)


def test_the_real_ai_budget_says_itself_and_offers_nothing_to_press(db):
    from app.credits import REAL_DONE
    from app.run_progress import _failed

    assert director.turn_failed(Job(error=REAL_DONE.format(20), input={})) == REAL_DONE.format(20)
    assert director.turn_failed(Job(error="Claude declined.", input={})) == director.TURN_FAILED
    cells = [{"state": "failed", "number": 1, "clip_id": "c1", "credits": 3,
              "note": REAL_DONE.format(20)}]  # fmt: skip
    got = _failed(db, None, cells, REAL_DONE.format(20), True, Decimal(5))
    assert got["fixes"] == [] and got["why"].startswith("The test site's real-AI budget")


def _ticks(app, db, n=4):
    providers = get_providers(app.state.settings, app.state.storage)
    for _ in range(n):
        run_once(db, providers, app.state.storage)
        db.expire_all()
        ok_when_asked(db)
        make_it(db)


def test_a_cut_off_answer_is_asked_again_once_then_the_run_ends(app, db, owner, editor,
                                                                monkeypatch):  # fmt: skip
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=6)
    real, calls = FakeWriter.run, []

    def cut_off(self, kind, input):
        if input["step"] == director.STEP:
            calls.append(1)
            if len(calls) <= 2:
                return Result("failed", error=claude.RAN_OUT)
        return real(self, kind, input)

    monkeypatch.setattr(FakeWriter, "run", cut_off)
    _ticks(app, db)
    out = editor.get(f"/projects/{pid}/director").json()
    failed = [t for t in _turns(db, pid) if t.status == JobStatus.failed]
    assert len(failed) == 2 and failed[1].retry_of_id == failed[0].id  # asked again once
    assert failed[0].input.get(director.RETRIED) and not failed[1].input.get(director.RETRIED)
    assert (out["status"], out["ended"]) == ("ended", director.TURN_FAILED)  # then it ends


def test_one_unreadable_answer_is_asked_again_and_the_run_goes_on(app, db, owner, editor,
                                                                  monkeypatch):  # fmt: skip
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=6)
    real, calls = FakeWriter.run, []

    def once(self, kind, input):
        if input["step"] == director.STEP and not calls:
            calls.append(1)
            return Result("failed", error=claude.UNREADABLE)
        return real(self, kind, input)

    monkeypatch.setattr(FakeWriter, "run", once)
    _run(app, db)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]


def test_the_stills_review_and_the_cut_watch_have_room_to_answer():
    import inspect

    from app import still_review, watch_cut

    for module in (still_review, watch_cut):
        assert '"max_tokens": 16000' in inspect.getsource(module), module.__name__
