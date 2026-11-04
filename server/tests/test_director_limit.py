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
    (card,) = [m for m in editor.get(f"/projects/{pid}/director").json()["thread"] if m.get("run")]
    assert card["status"] == "held"  # its card waits, saying why
    assert card["text"] == ("Waiting for the owner's OK · the director has used its own limit of "
                            "35 credits")  # fmt: skip

    assert owner.post(f"/jobs/{held.id}/approve").status_code == 200
    _run(app, db)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    charged, oks = _own(db, pid)
    assert oks == 1 and limit < charged <= 2 * limit  # several turns on the one OK
    texts = [m["text"] for m in out["thread"]]
    assert "OK'd: up to 35 more credits of the director's time." in texts


def test_an_ok_grants_a_limits_worth_then_it_waits_again(app, db, owner, editor, monkeypatch):
    monkeypatch.setattr(director, "own_limit", lambda: Decimal(12))  # 4 steps (turns, treatment)
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    for oks in range(3):
        _run(app, db)
        (held,) = _held(db, pid)
        charged, given = _own(db, pid)
        assert given == oks and charged <= 12 * (1 + oks), (charged, oks)
        before = _turns(db, pid)
        assert owner.post(f"/jobs/{held.id}/approve").status_code == 200
        _run(app, db)
        assert _turns(db, pid) - before >= 2  # one OK lets more than one turn go
    assert len(_held(db, pid)) == 1  # and once that's spent, it waits again


def test_a_freestyles_director_waits_at_its_limit_as_past_its_price(
    app, owner, editor, db, monkeypatch
):
    monkeypatch.setattr(director, "own_limit", lambda: Decimal(30))  # its run's own is about 58
    from app.models.freestyles import Freestyle
    from tests.test_freestyle_dialogue import BODY

    fs = editor.post("/freestyles", json=BODY).json()
    (first,) = owner.get("/jobs", params={"status": "needs_owner_approval"}).json()
    owner.post(f"/jobs/{first['id']}/approve")
    pid = db.get(Freestyle, fs["id"]).project_id
    _run_fakes(app, db)
    (held,) = _held(db, pid)
    assert held.input["held"] == PAST_APPROVED  # a freestyle's own words for a step past its price
    charged, _ = _own(db, pid)
    assert charged <= director.own_limit()
    assert db.get(Project, pid, execution_options={"see_hidden": True}).hidden
