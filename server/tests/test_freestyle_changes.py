"""Freestyle 3b (the Producer's rules): a change to a Dialogue freestyle. With no run going
the send is the press, quoted "up to" the whole video again, the running total under the
per-video cap: an editor's waits for the owner every time, the owner's runs at once, and the
new run reads every unread note. During a run it's only a note, read at the next turn."""

from decimal import Decimal

import pytest

from app import credits
from app.models.freestyles import Freestyle
from app.models.jobs import Job
from tests.test_freestyle_dialogue import BODY, _run

CHANGE = "Make clip 1 brighter."


def _held(owner):
    return owner.get("/jobs", params={"status": "needs_owner_approval"}).json()


def _delivered(app, owner, editor, db) -> dict:
    fs = editor.post("/freestyles", json=BODY).json()
    (first,) = _held(owner)
    owner.post(f"/jobs/{first['id']}/approve")
    _run(app, db)
    out = editor.get(f"/freestyles/{fs['id']}").json()
    assert out["status"] == "delivered"
    return out


@pytest.mark.usefixtures("roomy")
def test_an_editors_change_waits_for_the_owner_then_a_new_run_makes_it(app, owner, editor, db):
    fs = _delivered(app, owner, editor, db)
    first_cut, first_price = fs["file_id"], Decimal(str(fs["up_to"]))
    r = editor.post(f"/freestyles/{fs['id']}/messages", json={"text": CHANGE})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["status"] == "waiting" and out["file_id"] == first_cut  # the delivered cut stays
    (held,) = _held(owner)
    price = Decimal(str(held["freestyle"]["up_to"]))
    assert held["freestyle"]["change"] and held["freestyle"]["said"] == CHANGE
    assert Decimal(str(held["freestyle"]["total"])) == first_price + price  # running total
    assert Decimal(str(held["freestyle"]["spent"])) == Decimal(str(fs["credits"])) > 0  # so far
    owner.post(f"/jobs/{held['id']}/approve")
    _run(app, db)
    out = editor.get(f"/freestyles/{fs['id']}").json()
    assert out["status"] == "delivered", [t["text"] for t in out["thread"]]
    texts = [t["text"] for t in out["thread"]]
    assert [t["text"] for t in out["thread"] if t["kind"] == "message"][-1] == CHANGE
    assert any(t.startswith("Note 1:") for t in texts) or any(
        "Note 1:" in (t["why"] or "") for t in out["thread"]
    )  # the new run made the change
    assert out["file_id"] and out["file_id"] != first_cut  # delivered again


def test_the_owners_change_runs_at_once_and_one_during_a_run_is_only_a_note(
    app, owner, db, monkeypatch
):
    from datetime import timedelta

    from app import director

    monkeypatch.setattr(director, "GAP", timedelta(0))  # two notes in a few seconds: not a flood
    fs = owner.post("/freestyles", json=BODY).json()  # running now
    jobs = db.query(Job).count()
    r = owner.post(f"/freestyles/{fs['id']}/messages", json={"text": CHANGE})
    assert r.status_code == 201 and r.json()["status"] == "working"
    assert db.query(Job).count() == jobs  # a note for the next turn: nothing new queued or held
    assert db.get(Freestyle, fs["id"]).chat[-1]["job"] is None
    _run(app, db)
    done = owner.get(f"/freestyles/{fs['id']}").json()
    assert done["status"] == "delivered"
    r = owner.post(f"/freestyles/{fs['id']}/messages", json={"text": "Warmer light."})
    assert r.json()["status"] == "working" and _held(owner) == []  # the owner's: at once


@pytest.mark.usefixtures("roomy")
def test_a_change_past_the_cap_is_refused_and_a_declined_one_frees_its_price(
    app, owner, editor, db
):
    fs = _delivered(app, owner, editor, db)
    row = db.get(Freestyle, fs["id"])
    before = credits.approved(db, row)
    editor.post(f"/freestyles/{fs['id']}/messages", json={"text": CHANGE})
    (held,) = _held(owner)
    owner.post(f"/jobs/{held['id']}/decline", json={"reason": "Not now."})
    db.expire_all()
    out = editor.get(f"/freestyles/{fs['id']}").json()
    assert out["status"] == "declined" and out["file_id"]  # the first cut is still there
    assert credits.approved(db, db.get(Freestyle, fs["id"])) == before  # nothing ran on it
    shown = owner.get(f"/jobs/{held['id']}").json()["freestyle"]
    assert Decimal(str(shown["total"])) == before  # QA-3: the total drops it at once
    limits = owner.get("/credits/limits").json()
    owner.put("/credits/limits", json={**limits, "per_video_max_credits": int(before) + 1})
    r = editor.post(f"/freestyles/{fs['id']}/messages", json={"text": "Warmer."})
    assert r.status_code == 409 and "past its limit" in r.json()["detail"]


def test_an_owners_cancel_reads_stopped_and_a_repeat_after_the_first_is_new(owner, db):
    one_clip = {"type": "one_clip", "look": "house", "shape": "9:16", "text": "A cat at dawn."}
    fs = owner.post("/freestyles", json=one_clip).json()
    job = db.query(Job).one()
    assert owner.post(f"/jobs/{job.id}/cancel").status_code == 200
    out = owner.get(f"/freestyles/{fs['id']}").json()
    assert out["status"] == "stopped" and out["thread"][-1]["text"] == "Stopped."
    again = owner.post("/freestyles", json=one_clip).json()  # the first isn't waiting: a new one
    assert again["id"] != fs["id"]
