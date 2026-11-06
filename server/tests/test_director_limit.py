"""The director's own limit in credits (the Producer): a run's turns and watches are charged at
a flat price, so past the limit the quote shows (OWN_CREDITS) the next one waits for
the owner, the owner's own run too. One OK grants another limit's worth, not one step."""

from decimal import Decimal

from app import director
from app.credits import PAST_APPROVED
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from tests.test_director import _made, _run
from tests.test_freestyle_dialogue import _run as _run_fakes


def _held(db, pid) -> list[Job]:
    return (db.query(Job).filter(Job.project_id == pid,
                                 Job.status == JobStatus.needs_owner_approval).all())  # fmt: skip


def _own(db, pid) -> tuple[Decimal, int]:
    (run,) = {j.input[director.RUN]["id"] for j in db.query(Job).filter(Job.project_id == pid)
              if j.input.get(director.RUN)}  # fmt: skip
    return director.own_charged(db, run)


def _turns(db, pid) -> int:
    return db.query(Job).filter(Job.project_id == pid,
                                Job.input["step"].as_string() == director.STEP).count()  # fmt: skip


def test_a_run_at_its_limit_waits_and_the_owners_ok_lets_it_finish(
    app, db, owner, editor, monkeypatch
):
    monkeypatch.setattr(director, "own_limit", lambda: Decimal(35))  # this run's own is about 61
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")  # the owner's own run waits too
    _run(app, db)
    (held,) = _held(db, pid)
    limit = director.own_limit()
    assert held.input["held"] == ("Waiting for the owner's OK: the director has used its own "
                                  "limit of 35 credits.")  # fmt: skip
    charged, oks = _own(db, pid)
    assert (charged <= limit, oks) == (True, 0)  # never past it without an OK
    assert [j["id"] for j in owner.get("/jobs", params={"status": "needs_owner_approval"}).json()
            ] == [held.id]  # Needs you  # fmt: skip
    (card,) = [a for a in owner.get(f"/projects/{pid}/asks").json() if a["kind"] == "own"]
    assert card["state"] == "open"  # its card (rule 34)
    assert card["can"] == ["approve", "keep"] and card["money"]["held"] == held.input["held"]

    assert owner.post(f"/jobs/{held.id}/approve").status_code == 200
    _run(app, db)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    charged, oks = _own(db, pid)
    assert oks == 1 and limit < charged <= 2 * limit  # several turns on the one OK
    (card,) = [a for a in owner.get(f"/projects/{pid}/asks").json() if a["kind"] == "own"]
    assert (card["state"], card["can"]) == ("answered", [])  # the OK folds its card


def test_an_ok_grants_a_limits_worth_then_it_waits_again(app, db, owner, editor, monkeypatch):
    monkeypatch.setattr(director, "own_limit", lambda: Decimal(9))  # 3 steps: the run needs 4+ OKs
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    for oks in range(3):
        _run(app, db)
        (held,) = _held(db, pid)
        charged, given = _own(db, pid)
        assert given == oks and charged <= 9 * (1 + oks), (charged, oks)
        before = _turns(db, pid)
        assert owner.post(f"/jobs/{held.id}/approve").status_code == 200
        _run(app, db)
        assert _turns(db, pid) - before >= 2  # one OK lets more than one turn go
    assert len(_held(db, pid)) == 1  # and once that's spent, it waits again


def test_a_sends_director_waits_at_its_own_limit(app, owner, editor, db, monkeypatch):
    """A New video send's run, shown from the owner's OK: past the director's own limit it waits
    for the owner (rule 34), and never charges past that limit while it waits."""
    monkeypatch.setattr(director, "own_limit", lambda: Decimal(30))  # its run's own is about 58
    from app.models.freestyles import Freestyle
    from tests.conftest import first_brand
    from tests.test_freestyle_dialogue import BODY

    fs = editor.post("/freestyles", json={**BODY, "brand_id": first_brand(owner)}).json()
    _run_fakes(app, db, ticks=4, start=False)  # its plan, then its start card
    (first,) = owner.get("/jobs", params={"status": "needs_owner_approval"}).json()
    owner.post(f"/jobs/{first['id']}/approve")
    pid = db.get(Freestyle, fs["id"]).project_id
    _run_fakes(app, db)
    (held,) = _held(db, pid)
    assert held.input["held"] in (director.OWN_LIMIT.format(n=30), PAST_APPROVED)
    charged, _ = _own(db, pid)
    assert charged <= director.own_limit()
    assert not db.get(Project, pid).hidden  # shown from the OK
