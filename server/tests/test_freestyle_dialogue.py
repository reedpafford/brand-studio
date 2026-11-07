"""Freestyle 3a (the Producer's six conditions): a Dialogue freestyle is made by the director
on its own hidden script and video. An editor's send writes its treatment, then its start
card waits for the owner; the OK covers the price shown, no more; nothing hidden shows in any
list or count."""

import pytest

from app import credits, director
from app.models.brands import Brand
from app.models.freestyles import Freestyle
from app.models.jobs import Job
from app.models.projects import Project
from app.providers import get_providers
from app.worker import run_once
from tests.conftest import first_brand
from tests.helpers import make_it, ok_when_asked

SCRIPT = "MIA: The market opened at nine.\nLEO: And we were ready."
BODY = {"type": "dialogue", "look": "house", "shape": "9:16", "text": SCRIPT, "brand_id": 1}  # fomo


def _run(app, db, ticks=60, start=True):
    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings, app.state.storage)
    for _ in range(ticks):
        run_once(db, providers, app.state.storage)
        db.expire_all()
        ok_when_asked(db)  # the person approves the cast and places when asked
        if start:  # Make it on each start card, as the owner (S3-02)
            make_it(db)


def _hidden_nowhere(owner, editor):
    """Scripts, Videos, Needs you's videos, In production, the brand menu and Usage's rows
    and counts."""
    for who in (owner, editor):
        assert who.get("/scripts").json() == []
        assert who.get("/projects").json() == []
        assert all(b["name"] != "Freestyle" for b in who.get("/brands").json())
    assert owner.get("/production").json() == []
    summary = owner.get("/production/summary").json()
    assert (summary["in_production"], summary["needs_attention"]) == (0, 0)
    rows = owner.get("/usage/brands").json()
    assert all(r["name"] != "Freestyle" for r in rows["items"])
    assert owner.get("/usage/summary").json()["in_progress"] == 0


def test_an_editors_dialogue_waits_then_the_director_delivers_it_in_its_brand(
    app, owner, editor, db, monkeypatch
):
    monkeypatch.setattr(director, "own_limit", lambda: director.OWN_CREDITS * 2)  # its looks
    est = editor.get("/freestyles/estimate", params=BODY).json()["credits"]
    r = editor.post("/freestyles", json=BODY)
    assert r.status_code == 201, r.text
    assert r.json()["up_to"] == est > 0
    _run(app, db, ticks=4, start=False)  # its treatment first, charged nothing (S3-02)
    fs = editor.get(f"/freestyles/{r.json()['id']}").json()
    assert fs["status"] == "waiting"
    assert [(t["kind"], t["status"]) for t in fs["thread"]][0] == ("message", None)
    assert "held" in [t["status"] for t in fs["thread"]]  # its run's card: the owner's OK
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
    assert project.id in [p["id"] for p in editor.get("/projects").json()]  # shown in fomo
    assert db.query(Brand).execution_options(see_hidden=True).filter_by(hidden=True).all() == []


def test_the_owners_dialogue_starts_at_once_and_stop_stops_it(app, owner, editor, db):
    fs = owner.post("/freestyles", json=BODY).json()
    assert fs["status"] == "working"
    assert editor.get(f"/freestyles/{fs['id']}").status_code == 404
    stopped = owner.post(f"/freestyles/{fs['id']}/stop").json()
    assert stopped["status"] == "stopped"
    r = owner.post(f"/freestyles/{fs['id']}/messages", json={"text": "Slower."})
    assert r.status_code == 201 and r.json()["status"] == "working"  # the owner's: at once


def test_a_declined_or_withdrawn_dialogue_says_so_and_generates_nothing(app, owner, editor, db):
    one = editor.post("/freestyles", json=BODY).json()
    _run(app, db, ticks=4, start=False)  # its plan (Reed, 4 Nov: allowed), then its start card
    (turn,) = db.query(Job).filter(Job.status == "needs_owner_approval").all()
    owner.post(f"/jobs/{turn.id}/decline", json={"reason": "Not this week."})
    out = editor.get(f"/freestyles/{one['id']}").json()
    made = {j.input.get("step") for j in db.query(Job).filter(Job.status.in_(credits.COUNTED))}
    assert out["status"] == "declined" and made == {"director", "treatment"}  # its plan only
    assert "The owner declined: Not this week." in [t["text"] for t in out["thread"]]
    two = editor.post("/freestyles", json={**BODY, "text": "BO: Again?"}).json()
    _run(app, db, ticks=4, start=False)
    out = editor.post(f"/freestyles/{two['id']}/withdraw").json()
    assert out["status"] == "withdrawn" and "Withdrawn." in [t["text"] for t in out["thread"]]
    assert director.STEP  # the run is the director's: nothing else was queued
    assert db.query(Job).filter(Job.status == "queued").count() == 0


def _approved_at(db, owner, price) -> int:
    """The owner's OK on a send's start card, as if its "up to" had been `price` credits: the
    run's approved price (asks.approved_run), whatever the video's budget. Its video id."""
    from app import asks

    (card,) = db.query(Job).filter(Job.status == "needs_owner_approval",
                                   Job.input[asks.START].as_boolean()).all()  # fmt: skip
    card.input = {**card.input, "price": str(price)}
    db.commit()
    assert owner.post(f"/jobs/{card.id}/approve").status_code == 200
    return card.project_id


def test_an_approved_run_never_spends_past_its_price_without_a_new_ok(app, owner, editor, db):
    """QA-3 on #1171: approved at 34.46, the run spent 80.53, its director's turns uncounted.
    The price the OK covers includes the director's own limit; past it, the step waits for the
    owner again. A send's video shows once it's OK'd, so this is the run's own guard (rule 34:
    asks.past_run), never the hidden video's budget."""
    from decimal import Decimal

    from app.credits import COUNTED, PAST_APPROVED

    sent = {**BODY, "brand_id": first_brand(owner)}
    est = Decimal(str(editor.get("/freestyles/estimate", params=sent).json()["credits"]))
    fs = editor.post("/freestyles", json=sent).json()
    assert Decimal(str(fs["up_to"])) == est >= director.OWN_CREDITS  # its turns too
    _run(app, db, ticks=4, start=False)  # its plan, then its start card
    pid = _approved_at(db, owner, 3)  # a small approved price, so the run reaches it
    assert not db.get(Project, pid).hidden  # shown from the OK: no hidden-budget guard
    _run(app, db)
    jobs = db.query(Job).filter(Job.project_id == pid).all()
    spent = sum((j.credits for j in jobs if j.status in COUNTED and not j.input.get("before_ok")),
                Decimal(0))  # its plan before Make it is on its own allowance  # fmt: skip
    waiting = [j for j in jobs if j.status == "needs_owner_approval"]
    assert waiting and waiting[0].input["held"] == PAST_APPROVED  # it paused, and says why
    assert spent <= Decimal(3), spent  # never past the price approved without a new OK


@pytest.mark.skip(
    reason="A video made from a send now always has a brand and shows once the owner OKs it, "
    "so this hidden-only price guard no longer applies; #1313's approved run price "
    "(asks.past_run) guards every run and carries these checks"
)
def test_a_tight_run_never_spends_past_its_price_plus_what_the_owner_released(
    app, owner, editor, db, monkeypatch
):
    """QA-3 on #1171 (a price the run reaches): turns, takes and the watch of the cut all wait
    for the owner past the price approved; each OK covers its own step."""
    from decimal import Decimal

    from app.credits import COUNTED, PAST_APPROVED

    editor.post("/freestyles", json={**BODY, "brand_id": first_brand(owner)})
    _run(app, db, ticks=4, start=False)  # its plan, then its start card
    up_to, released = Decimal(40), Decimal(0)  # about the video's own price: its turns pass it
    pid = _approved_at(db, owner, up_to)
    holds = 0
    for _ in range(40):  # the owner releases each step that waits, one at a time
        _run(app, db, ticks=40)
        db.expire_all()
        spent = sum((j.credits for j in db.query(Job).filter(Job.project_id == pid)
                     if j.status in COUNTED and not j.input.get("before_ok")),
                    Decimal(0))  # its plan is on its own allowance  # fmt: skip
        assert spent <= up_to + released, (spent, up_to, released)
        waiting = db.query(Job).filter(Job.project_id == pid,
                                       Job.status == "needs_owner_approval").all()  # fmt: skip
        if not waiting:
            break
        job = waiting[0]
        assert job.input["held"] == PAST_APPROVED  # a step the approved price didn't cover
        released += Decimal(str(owner.get(f"/jobs/{job.id}").json()["credits"]))  # as shown
        holds += 1
        assert owner.post(f"/jobs/{job.id}/approve").status_code == 200
    assert holds >= 1  # the price ran out mid-run, and it waited


def test_an_approved_run_with_every_redo_used_delivers_within_its_price(
    app, owner, editor, db, monkeypatch
):
    """QA on #1176: 80.898 shown, 82.03 charged, and an approved run held at the end. The price
    is the most one run may charge under its own limits: every redo with its check, at what
    this run was charged, and the director's own limit for its turns and watches."""
    from decimal import Decimal

    from app.credits import COUNTED

    monkeypatch.setattr("app.item_checks.on", lambda: True)  # as on the test site's stand-ins
    from app.providers.fake_local import FakeWriter

    def weak(self, prompt):  # every take's watch sees a fault in the frames: every redo used
        return {"seen": "A hand melts at 0:01.", "verdict": "redo", "note": "hands whole",
                "faults": [{"kind": "motion", "at": 1.0, "says": "A hand melts",
                            "evidence": "picture"}]}  # fmt: skip

    monkeypatch.setattr(FakeWriter, "_take_watch", weak)
    fs = editor.post("/freestyles", json=BODY).json()
    _run(app, db, ticks=4, start=False)  # the treatment, then its start card
    (held,) = owner.get("/jobs", params={"status": "needs_owner_approval"}).json()
    owner.post(f"/jobs/{held['id']}/approve")
    _run(app, db)
    assert editor.get(f"/freestyles/{fs['id']}").json()["status"] == "delivered"
    assert owner.get("/jobs", params={"status": "needs_owner_approval"}).json() == []  # no hold
    row = db.get(Freestyle, fs["id"])
    jobs = [j for j in db.query(Job).filter(Job.project_id == row.project_id)
            if j.status in COUNTED]  # fmt: skip

    def of(step):
        return [j.credits for j in jobs if j.input.get("step") == step]

    firsts, takes = {}, [j for j in jobs if j.input.get("step") == "clip_take"]
    for j in sorted(takes, key=lambda j: j.id):
        firsts.setdefault(j.input["project_clip_id"], j.credits)
    assert len(takes) == len(firsts) * (1 + director.MAX_REDOS)  # every redo was made
    check = max(of("take_watch"))  # the director's watch of each take
    spent = sum((j.credits for j in jobs), Decimal(0))
    redos = sum((j.credits for j in takes), Decimal(0)) - sum(firsts.values())
    redos += check * (len(takes) - len(firsts))
    once = spent - sum(of("director")) - sum(of("watch_cut")) - redos  # the video made once
    own = sum(of("director")) + sum(of("watch_cut"))
    assert own <= director.OWN_CREDITS  # the director's own: turns and watches, under its limit
    most = (once + director.OWN_CREDITS
            + director.MAX_REDOS * (sum(firsts.values()) + check * len(firsts)))  # fmt: skip
    assert spent <= most <= row.up_to, (spent, most, row.up_to)


def test_new_videos_saved_scripts_leave_out_the_scripts_its_pasted_sends_made(app, owner, db):
    """S2-06: every pasted send is a published script in Scripts; From a saved script asks
    with sends=false and gets only the library's own, a send made from one included."""
    from datetime import timedelta

    from app.db import utcnow
    from app.models.script_library import Script, ScriptDraft

    pasted = owner.post("/freestyles", json=BODY).json()
    kept = Script(workspace_id=1, brand_id=1, title="Beer gut doctor rant", kind="story",
                  format="dialogue", look="house", published=True, created_by_id=1,
                  created_at=utcnow() - timedelta(days=1))  # fmt: skip
    db.add(kept)
    db.flush()
    db.add(ScriptDraft(script_id=kept.id, slot=0, text=SCRIPT, status="approved"))
    db.commit()
    made = owner.post("/freestyles", json={**BODY, "text": None, "script_id": kept.id, "slot": 0})
    assert made.status_code == 201, made.text
    titles = lambda **q: sorted(s["title"] for s in owner.get("/scripts", params=q).json())  # noqa: E731
    assert titles() == ["Beer gut doctor rant", pasted["title"]]  # Scripts lists both
    assert titles(sends=False) == ["Beer gut doctor rant"]
    assert titles(sends=False, brand_id=1, limit=50, q="market") == ["Beer gut doctor rant"]
