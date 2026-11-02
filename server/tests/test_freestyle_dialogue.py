"""Freestyle 3a (the Producer's six conditions): a Dialogue freestyle is made by the director
on its own hidden script and video. An editor's send waits for the owner as the run's first
turn; the OK covers the price shown, no more; nothing hidden shows in any list or count."""

import pytest

from app import credits, director
from app.models.brands import Brand
from app.models.freestyles import Freestyle
from app.models.jobs import Job
from app.models.projects import Project
from app.providers import get_providers
from app.worker import run_once

SCRIPT = "MIA: The market opened at nine.\nLEO: And we were ready."
BODY = {"type": "dialogue", "look": "house", "shape": "9:16", "text": SCRIPT}


def _run(app, db, ticks=60):
    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings, app.state.storage)
    for _ in range(ticks):
        run_once(db, providers, app.state.storage)
        db.expire_all()


def _hidden_nowhere(owner, editor):
    """Scripts, Videos, Needs you's videos, In production, the brand menu and Usage's rows
    and counts."""
    for who in (owner, editor):
        assert who.get("/scripts").json() == []
        assert who.get("/projects").json() == []
        assert who.get("/projects", params={"status": "needs_you"}).json() == []
        assert all(b["name"] != "Freestyle" for b in who.get("/brands").json())
    assert owner.get("/production").json() == []
    summary = owner.get("/production/summary").json()
    assert (summary["in_production"], summary["needs_attention"]) == (0, 0)
    rows = owner.get("/usage/brands").json()
    assert all(r["name"] != "Freestyle" for r in rows["items"])
    assert owner.get("/usage/summary").json()["in_progress"] == 0


@pytest.mark.usefixtures("roomy")
def test_an_editors_dialogue_waits_then_the_director_delivers_it_hidden(app, owner, editor, db):
    est = editor.get("/freestyles/estimate", params=BODY).json()["credits"]
    r = editor.post("/freestyles", json=BODY)
    assert r.status_code == 201, r.text
    fs = r.json()
    assert fs["status"] == "waiting" and fs["up_to"] == est > 0
    assert [(t["kind"], t["status"]) for t in fs["thread"]] == [("message", None), ("move", "held")]
    (held,) = owner.get("/jobs", params={"status": "needs_owner_approval"}).json()
    assert held["freestyle"]["id"] == fs["id"] and held["freestyle"]["up_to"] == est
    assert held["freestyle"]["said"] == SCRIPT and held["freestyle"]["change"] is False
    _hidden_nowhere(owner, editor)
    row = db.get(Freestyle, fs["id"])
    project = db.get(Project, row.project_id, execution_options={"see_hidden": True})
    assert project.hidden and credits.budget(db, project) == row.up_to  # the OK covers that

    assert owner.post(f"/jobs/{held['id']}/approve").status_code == 200
    _run(app, db)
    out = editor.get(f"/freestyles/{fs['id']}").json()
    assert out["status"] == "delivered", [t["text"] for t in out["thread"]]
    assert out["file_id"] and out["credits"] > 0
    assert out["thread"][0]["kind"] == "message" and out["thread"][-1]["status"] == "done"
    _hidden_nowhere(owner, editor)
    brand = db.query(Brand).execution_options(see_hidden=True).filter_by(hidden=True).one()
    assert brand.name == "Freestyle"
    assert editor.get(f"/projects/{project.id}/director").status_code == 404  # not a video


def test_the_owners_dialogue_starts_at_once_and_stop_stops_it(app, owner, editor, db):
    fs = owner.post("/freestyles", json=BODY).json()
    assert fs["status"] == "working"
    assert editor.get(f"/freestyles/{fs['id']}").status_code == 404
    stopped = owner.post(f"/freestyles/{fs['id']}/stop").json()
    assert stopped["status"] == "stopped"
    r = owner.post(f"/freestyles/{fs['id']}/messages", json={"text": "Slower."})
    assert r.status_code == 201 and r.json()["status"] == "working"  # the owner's: at once


def test_a_declined_or_withdrawn_dialogue_says_so_and_spends_nothing(app, owner, editor, db):
    one = editor.post("/freestyles", json=BODY).json()
    turn = db.query(Job).filter(Job.input["freestyle_id"].as_integer() == one["id"]).one()
    owner.post(f"/jobs/{turn.id}/decline", json={"reason": "Not this week."})
    out = editor.get(f"/freestyles/{one['id']}").json()
    assert out["status"] == "declined" and out["credits"] == 0
    assert out["thread"][-1]["text"] == "The owner declined: Not this week."
    two = editor.post("/freestyles", json={**BODY, "text": "BO: Again?"}).json()
    out = editor.post(f"/freestyles/{two['id']}/withdraw").json()
    assert out["status"] == "withdrawn" and out["thread"][-1]["text"] == "Withdrawn."
    assert director.STEP  # the run is the director's: nothing else was queued
    assert db.query(Job).filter(Job.status == "queued").count() == 0


def test_an_approved_run_never_spends_past_its_price_without_a_new_ok(app, owner, editor, db):
    """QA-3 on #1171: approved at 34.46, the run spent 80.53, its director's turns uncounted.
    The price shown includes the director's own limit, everything counts against it, and the
    step that would pass it waits for the owner again."""
    from decimal import Decimal

    from app.credits import COUNTED, PAST_APPROVED, usd_to_credits

    est = Decimal(str(editor.get("/freestyles/estimate", params=BODY).json()["credits"]))
    fs = editor.post("/freestyles", json=BODY).json()
    assert Decimal(str(fs["up_to"])) == est >= usd_to_credits(director.MAX_USD)  # its turns too
    (held,) = owner.get("/jobs", params={"status": "needs_owner_approval"}).json()
    row = db.get(Freestyle, fs["id"])
    row.up_to = Decimal(3)  # a small approved price, so the run reaches it
    row.chat = [{**row.chat[0], "price": "3"}]
    db.commit()
    owner.post(f"/jobs/{held['id']}/approve")
    _run(app, db)
    jobs = db.query(Job).filter(Job.project_id == row.project_id).all()
    spent = sum((j.credits for j in jobs if j.status in COUNTED), Decimal(0))
    waiting = [j for j in jobs if j.status == "needs_owner_approval"]
    assert waiting and waiting[0].input["held"] == PAST_APPROVED  # it paused, and says why
    assert spent <= Decimal(3), spent  # never past the price approved without a new OK
    assert editor.get(f"/freestyles/{fs['id']}").json()["status"] == "waiting"


def test_a_tight_run_never_spends_past_its_price_plus_what_the_owner_released(
    app, owner, editor, db, monkeypatch
):
    """QA-3 on #1171 (MAX_USD 0.50): turns, takes and the watch of the cut all wait for the
    owner past the price; checks are skipped, never queued unheld. Each step held mid-run
    shows in the thread."""
    from decimal import Decimal

    from app.credits import COUNTED, PAST_APPROVED

    monkeypatch.setattr(director, "MAX_USD", Decimal("0.50"))
    fs = editor.post("/freestyles", json=BODY).json()
    up_to, released = Decimal(str(fs["up_to"])), Decimal(0)
    pid = db.get(Freestyle, fs["id"]).project_id
    holds = 0
    for _ in range(12):  # the owner releases each step that waits, one at a time
        db.expire_all()
        waiting = db.query(Job).filter(Job.project_id == pid,
                                       Job.status == "needs_owner_approval").all()  # fmt: skip
        if not waiting:
            break
        job = waiting[0]
        if holds:  # past the first send: a step the approved price didn't cover
            assert job.input["held"] == PAST_APPROVED
            moves = editor.get(f"/freestyles/{fs['id']}").json()["thread"]
            assert any(m["status"] == "held" and m["text"] == PAST_APPROVED for m in moves)
            released += job.credits
        holds += 1
        assert owner.post(f"/jobs/{job.id}/approve").status_code == 200
        _run(app, db, ticks=40)
        db.expire_all()
        spent = sum((j.credits for j in db.query(Job).filter(Job.project_id == pid)
                     if j.status in COUNTED), Decimal(0))  # fmt: skip
        assert spent <= up_to + released, (spent, up_to, released)
    assert holds > 1  # the price ran out mid-run, and it waited
