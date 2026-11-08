"""Cost analysis, session 35 (pure waste, quality kept): a run's turn never starts twice (A5),
Usage keeps a Claude call's token counts (A8), and a take its provider refused counts $0 in
what was really spent (X1). The 1-hour cache (A1) is in test_claude.py."""

from decimal import Decimal

from app import credits, director
from app.models.jobs import Job, JobStatus, Usage
from app.models.projects import Project
from app.providers import Result, UsageItem
from app.worker import _usage
from tests.test_director import _made, _run


def _turns(db, pid):
    return db.query(Job).filter(Job.project_id == pid,
                                Job.input["step"].as_string() == director.STEP).count()  # fmt: skip


def test_two_wakers_start_one_turn(app, db, owner, editor, monkeypatch):
    """A5: the worker's finish and its sweep both saw the run idle and each started a turn. The
    second now waits on the video's lock, reads the turn the first queued, and stops."""
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=2)  # its second turn queued (the server takes the mechanical steps)
    project = db.get(Project, pid)
    last = director.turns(db, project)[-1]
    last.status, last.input = JobStatus.succeeded, {**last.input, "result": "Made the plan."}
    db.commit()
    before = _turns(db, pid)
    real = director.lock

    def raced(db_, model, row_id):  # while this one waits for the lock, the other wakes it
        monkeypatch.setattr(director, "lock", real)
        director.wake(db_, db_.get(Project, row_id))  # the first waker: queues its turn
        real(db_, model, row_id)

    monkeypatch.setattr(director, "lock", raced)
    director.wake(db, project)  # the second: it read the run idle before the lock
    db.commit()
    assert _turns(db, pid) == before + 1  # one turn, never two


def test_usage_keeps_a_claude_calls_token_counts():
    job = Job(id=7, workspace_id=1, provider="claude", kind="write-claude", credits=Decimal(1))
    tokens = {"input": 812, "output": 340, "cache_read": 30100, "cache_write": 0,
              "cache_write_1h": 0, "images": 3}  # fmt: skip
    result = Result(
        "succeeded", usage=[UsageItem(Decimal(1), "call", Decimal("0.05"), tokens=tokens)]
    )
    (row,) = _usage(job, type("P", (), {"paid": True})(), result)
    assert (row.input_tokens, row.output_tokens, row.cache_read_tokens, row.cache_write_tokens,
            row.images) == (812, 340, 30100, 0, 3)  # fmt: skip
    plain = Result("succeeded", usage=[UsageItem(Decimal(5), "second", Decimal("0.5"))])
    (media,) = _usage(job, type("P", (), {"paid": True})(), plain)
    assert media.input_tokens is None and media.images is None  # other providers: none


def test_a_take_its_provider_refused_counts_nothing_spent(app, db, owner, editor):
    """X1: Replicate's copyright refusal (E005) charges nothing; it was counted at its credits.
    A failure that may have been billed (sent, no figure) still counts."""
    pid = _made(app, owner, editor, db)
    base = {"workspace_id": 1, "created_by_id": 1, "project_id": pid, "kind": "video",
            "provider": "replicate", "input": {"step": "clip_take"}, "provider_ref": "p1",
            "credits": Decimal(6), "status": JobStatus.failed}  # fmt: skip
    refused = Job(**base, error_detail="E005: The input may be related to copyright restrictions")
    db.add(refused)
    db.commit()
    assert credits.never_billed(refused)
    assert credits.actual_usd(db, pid).usd == 0
    lost = Job(**{**base, "provider_ref": "p2"}, error_detail="Prediction failed: CUDA error")
    db.add(lost)
    db.commit()
    assert credits.actual_usd(db, pid).usd == (6 * credits.USD_PER_CREDIT).quantize(Decimal("0.01"))
    detail = owner.get(f"/jobs/{refused.id}").json()
    assert detail.get("cost_usd", 0) == 0
    assert db.query(Usage).count() == 0
