"""Audit 6 Nov (real providers): a run never hangs or dead-ends on a failure. A job that fails
before the provider answers tells what waits on it and wakes the director; a tool that breaks
is a refusal; the real-AI budget says itself and offers no press that would be refused again;
one cut-off or unreadable answer is asked again once."""

import json
from decimal import Decimal

from app import claude, director, director_tools
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.providers import Result, get_providers
from app.providers.fake_local import FakeWriter
from app.worker import RESTART, _fail, run_once
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

    pid = _made(app, owner, editor, db)
    split = {"tool": "split_clip", "clip_id": "c1", "why": "b1: too long"}
    monkeypatch.setattr("app.director.choose", started(lambda state: split))

    def boom(*a, **k):
        raise KeyError("clips")

    monkeypatch.setattr(director_tools, "_split", boom)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=12)
    results = [t.input.get("result") or "" for t in _turns(db, pid)]
    assert director_tools.STEP_BROKE in results  # plain words: no tool's name for a person
    card = owner.get(f"/projects/{pid}/director").json()
    assert "split_clip" not in json.dumps([t["result"] for t in card["turns"]])


def test_the_real_ai_budget_offers_no_press_only_while_it_would_refuse(db):
    """QA on #1397: a budget ending was a dead end for good (rule 22). No press only while the
    budget would still refuse the next step; once it allows, the usual fixes come back; and a
    clip that failed on the budget never hides another clip's Try again."""
    from app.credits import REAL_DONE
    from app.run_progress import _failed, priced

    used_up = REAL_DONE.format(20)
    assert director.turn_failed(Job(error=used_up, input={})) == used_up
    assert director.turn_failed(Job(error="Claude declined.", input={})) == director.TURN_FAILED
    budget = {"state": "failed", "number": 1, "clip_id": "c1", "credits": 3, "note": used_up}
    busy = {"state": "failed", "number": 2, "clip_id": "c2", "credits": 4,
            "note": "The service was busy. Nothing was charged."}  # fmt: skip
    shut = _failed(db, None, [budget], used_up, True, Decimal(5), blocked=used_up)
    assert shut["fixes"] == [] and shut["why"] == used_up
    open_ = _failed(db, None, [budget], used_up, True, Decimal(5))  # the budget was raised
    assert [f["kind"] for f in open_["fixes"]] == ["carry_on"]
    video = type("V", (), {"pk": staticmethod(lambda clip: 9)})()
    other = _failed(db, video, [budget, busy], "Clip 2's take failed 3 times", True, Decimal(5))
    assert [f["kind"] for f in other["fixes"]] == ["again", "carry_on"]  # clip 2's Try again
    assert priced(used_up, owner=False) == "The test site's real-AI budget is used up. Nothing " \
        "was charged."  # rule 4: never an editor's dollars  # fmt: skip


def test_needs_you_lists_a_run_ended_on_the_budget_with_no_press(app, db, owner, editor,
                                                                 monkeypatch):  # fmt: skip
    """QA on #1397: no fixes took the owner's whole inbox down (IndexError)."""
    from app import run_progress
    from app.credits import REAL_DONE

    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=6)
    last = _turns(db, pid)[-1]
    last.status, last.error = JobStatus.failed, REAL_DONE.format(20)
    last.input = {**last.input, "ended": REAL_DONE.format(20)}
    db.commit()
    monkeypatch.setattr(run_progress, "budget_now", lambda db, p, turns: REAL_DONE.format(20))
    got = owner.get("/needs-you")
    assert got.status_code == 200, got.text


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
            if len(calls) == 1:  # the first was put back in the queue once after a restart
                with app.state.sessionmaker() as other:
                    for t in other.query(Job).filter(Job.status == JobStatus.running):
                        t.input = {**t.input, RESTART: True}
                    other.commit()
            if len(calls) <= 2:
                return Result("failed", error=claude.RAN_OUT)
        return real(self, kind, input)

    monkeypatch.setattr(FakeWriter, "run", cut_off)
    _ticks(app, db)
    out = editor.get(f"/projects/{pid}/director").json()
    failed = [t for t in _turns(db, pid) if t.status == JobStatus.failed]
    assert len(failed) == 2 and failed[1].retry_of_id == failed[0].id  # asked again once
    assert failed[0].input.get(director.RETRIED) and not failed[1].input.get(director.RETRIED)
    assert failed[0].input.get(RESTART) and not failed[1].input.get(RESTART)  # a fresh turn's
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


def test_retried_answers_never_count_as_failures(app, db, owner, editor):
    """QA on #1397: three cut-off first answers, each asked again fine, ended the run as
    "failed 3 times"; a turn asked again isn't a failure."""
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=6)
    project = db.get(Project, pid)
    run = director.turns(db, project)[-1].input[director.RUN]
    for _ in range(3):
        db.add(Job(workspace_id=1, created_by_id=1, kind="write-claude", provider="claude",
                   input={"step": director.STEP, director.RUN: run, director.RETRIED: True},
                   project_id=pid, credits=Decimal(1), status=JobStatus.failed,
                   error_detail=claude.RAN_OUT))  # fmt: skip
    db.commit()
    assert director._failed_too_often(db, project, run) == ""
    said = director.turn_input(db, project, run)["prompt"]
    assert director.RETRIED_SAID in said  # its line in <last_actions>, never blank


def test_a_stop_during_a_retry_is_kept_and_nothing_more_is_asked(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=6)
    project = db.get(Project, pid)
    run = director.turns(db, project)[-1].input[director.RUN]
    bad = Job(workspace_id=1, created_by_id=1, kind="write-claude", provider="claude",
              input={"step": director.STEP, director.RUN: run, "ended": "Stopped."},
              project_id=pid, credits=Decimal(1), status=JobStatus.failed,
              error_detail=claude.UNREADABLE)  # fmt: skip
    db.add(bad)
    db.commit()
    before = db.query(Job).count()
    assert director._again(db, bad) is True  # handled: the Stop stays, no paid retry
    db.commit()
    db.expire_all()
    assert db.query(Job).count() == before and db.get(Job, bad.id).input["ended"] == "Stopped."


def test_a_cut_off_answer_and_its_retry_are_both_counted_once_charged(app, db, owner, editor,
                                                                      monkeypatch):  # fmt: skip
    """The spend on a failed answer and its retry: both calls' real cost is kept (Usage), and
    the turn is charged once (the failed one isn't counted)."""
    from app.credits import COUNTED
    from app.models.jobs import Usage
    from app.providers import UsageItem

    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=6)
    real, calls = FakeWriter.run, []

    def once(self, kind, input):
        if input["step"] == director.STEP and not calls:
            calls.append(1)
            return Result("failed", error=claude.RAN_OUT,
                          usage=[UsageItem(Decimal(1), "call", Decimal("0.30"))])  # fmt: skip
        return real(self, kind, input)

    monkeypatch.setattr(FakeWriter, "run", once)
    _ticks(app, db, n=12)  # its next Claude turn (the server takes the mechanical steps)
    failed = next(t for t in _turns(db, pid) if t.status == JobStatus.failed)
    retry = next(t for t in _turns(db, pid) if t.retry_of_id == failed.id)
    assert failed.status not in COUNTED and retry.status in COUNTED  # charged once
    paid = db.query(Usage).filter(Usage.job_id == failed.id).all()
    assert [float(u.cost_usd) for u in paid] == [0.3]  # its real cost is kept


def test_an_error_telling_what_waits_never_stops_the_worker(db, monkeypatch):
    def broken(db, job, again=True):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.worker.step_failed", broken)
    job = Job(workspace_id=1, created_by_id=1, kind="write-claude", provider="claude",
              input={"step": "take_watch"}, status=JobStatus.running,
              credits=Decimal(1))  # fmt: skip
    db.add(job)
    db.commit()
    _fail(db, job, "It failed.", "400")  # at boot (recover) too: it never raises
    assert db.get(Job, job.id).status == JobStatus.failed


def test_failures_count_again_from_a_carry_on(app, db, owner, editor):
    """Video 240: Carry on is a press to try again, so the failures before it don't end the
    carried run at its first turn."""
    from app.db import utcnow

    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=6)
    project = db.get(Project, pid)
    run = director.turns(db, project)[-1].input[director.RUN]
    for _ in range(3):
        db.add(Job(workspace_id=1, created_by_id=1, kind="write-claude", provider="claude",
                   input={"step": director.STEP, director.RUN: run}, project_id=pid,
                   credits=Decimal(1), status=JobStatus.failed))  # fmt: skip
    db.commit()
    assert director._failed_too_often(db, project, run)  # it gave up
    last = director.turns(db, project)[-1]
    last.input = {**last.input, director.WAS_STOPPED: {"carried_at": utcnow().isoformat()}}
    db.commit()
    assert director._failed_too_often(db, project, run) == ""  # carried on: counted afresh


def test_a_free_check_that_keeps_failing_never_ends_the_run(app, db, owner, editor):
    """Video 240 (7 Nov): "It stopped: The take words failed 3 times." Free checks on our own
    server (each take's words) failed under load, and the run ended with every paid take made
    and no cut. A check on our own server never counts; a paid call still does, even one that
    was free to the person (QA on #1424)."""
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=6)
    project = db.get(Project, pid)
    run = director.turns(db, project)[-1].input[director.RUN]
    for _ in range(3):
        db.add(Job(workspace_id=1, created_by_id=1, kind="take_listen", provider="local",
                   input={"step": "take_words"}, project_id=pid, credits=Decimal(0),
                   status=JobStatus.failed, error_detail="Timed out."))  # fmt: skip
    db.commit()
    assert director._failed_too_often(db, project, run) == ""  # free: it goes on
    for _ in range(3):  # a paid call that was free to them (a free fix, a free retry) counts
        db.add(Job(workspace_id=1, created_by_id=1, kind="check-claude", provider="claude",
                   input={"step": "watch_cut"}, project_id=pid, credits=Decimal(0),
                   status=JobStatus.failed))  # fmt: skip
    db.commit()
    assert director._failed_too_often(db, project, run) == "The watch of the cut failed 3 times"
