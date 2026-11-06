"""Freestyle 3b (the Producer's rules): a change to a Dialogue freestyle. With no run going
the send is the press, quoted "up to" the whole video again: its treatment, then its start
card (an editor's waits for the owner every time), and the new run reads every unread note.
During a run it's only a note, read at the next turn."""

from decimal import Decimal

import pytest

from app import credits, director
from app.models.freestyles import Freestyle
from app.models.jobs import Job
from app.models.projects import Project
from tests.test_freestyle_dialogue import BODY, _run

CHANGE = "Make clip 1 brighter."


def _held(owner):
    return owner.get("/jobs", params={"status": "needs_owner_approval"}).json()


def _delivered(app, owner, editor, db, brand_id=None) -> dict:
    body = {**BODY, "brand_id": brand_id} if brand_id else BODY
    fs = editor.post("/freestyles", json=body).json()
    _run(app, db, ticks=4, start=False)  # the treatment, then its start card (S3-02)
    (first,) = _held(owner)
    owner.post(f"/jobs/{first['id']}/approve")
    _run(app, db)
    out = editor.get(f"/freestyles/{fs['id']}").json()
    assert out["status"] == "delivered"
    return out


def test_an_editors_change_waits_for_the_owner_then_a_new_run_makes_it(app, owner, editor, db):
    fs = _delivered(app, owner, editor, db)
    first_cut, first_price = fs["file_id"], Decimal(str(fs["up_to"]))
    r = editor.post(f"/freestyles/{fs['id']}/messages", json={"text": CHANGE})
    assert r.status_code == 201, r.text
    _run(app, db, ticks=4, start=False)  # the change's treatment, then its start card
    out = editor.get(f"/freestyles/{fs['id']}").json()
    assert out["status"] == "waiting" and out["file_id"] == first_cut  # the delivered cut stays
    (held,) = _held(owner)
    price = Decimal(str(held["freestyle"]["up_to"]))
    assert held["freestyle"]["change"] and held["freestyle"]["said"] == CHANGE
    assert Decimal(str(held["freestyle"]["total"])) == first_price + price  # running total
    spent = Decimal(str(held["freestyle"]["spent"]))  # so far: the cut, and the change's plan
    assert spent > Decimal(str(fs["credits"])) > 0
    owner.post(f"/jobs/{held['id']}/approve")
    _run(app, db)
    out = editor.get(f"/freestyles/{fs['id']}").json()
    assert out["status"] == "delivered", [t["text"] for t in out["thread"]]
    texts = [t["text"] for t in out["thread"]]
    assert [t["text"] for t in out["thread"] if t["kind"] == "message"][-1] == CHANGE
    turns = director.turns(db, db.get(Project, out["project_id"]))
    assert any((j.output or {}).get("why", "").startswith("Note 1:") for j in turns)  # the change
    assert any(t.startswith("The cut is made") for t in texts)  # its delivery note, as lines
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


def test_a_declined_change_frees_its_price(app, owner, editor, db):
    fs = _delivered(app, owner, editor, db)
    row = db.get(Freestyle, fs["id"])
    before = credits.approved(db, row)
    editor.post(f"/freestyles/{fs['id']}/messages", json={"text": CHANGE})
    _run(app, db, ticks=4, start=False)
    (held,) = _held(owner)
    owner.post(f"/jobs/{held['id']}/decline", json={"reason": "Not now."})
    db.expire_all()
    out = editor.get(f"/freestyles/{fs['id']}").json()
    assert out["status"] == "declined" and out["file_id"]  # the first cut is still there
    assert credits.approved(db, db.get(Freestyle, fs["id"])) == before  # nothing ran on it
    shown = owner.get(f"/jobs/{held['id']}").json()["freestyle"]
    assert Decimal(str(shown["total"])) == before  # QA-3: the total drops it at once


def test_an_owners_cancel_reads_stopped_and_a_repeat_after_the_first_is_new(owner, db):
    one_clip = {"type": "one_clip", "look": "house", "shape": "9:16", "text": "A cat at dawn."}
    fs = owner.post("/freestyles", json=one_clip).json()
    job = db.query(Job).one()
    assert owner.post(f"/jobs/{job.id}/cancel").status_code == 200
    out = owner.get(f"/freestyles/{fs['id']}").json()
    assert out["status"] == "stopped" and out["thread"][-1]["text"] == "Stopped."
    again = owner.post("/freestyles", json=one_clip).json()  # the first isn't waiting: a new one
    assert again["id"] != fs["id"]


def test_a_model_switch_before_the_run_moves_its_price_and_past_the_ok_only_the_owner_may(
    app, owner, editor, db
):
    """The dry run: switched to another model before the run, the "up to" kept the first one's."""
    import math

    from app.models.projects import Project
    from app.models.script_library import ScriptDraft
    from app.routes.estimate import run_price
    from app.video_settings import PAST_OK
    from tests.conftest import first_brand

    sent = editor.post("/freestyles", json={**BODY, "brand_id": first_brand(owner)}).json()
    _run(app, db, ticks=4, start=False)
    (held,) = _held(owner)
    owner.post(f"/jobs/{held['id']}/approve")  # the run hasn't asked for a take yet
    fs = db.get(Freestyle, sent["id"])
    video = db.get(Project, fs.project_id)
    draft = db.get(ScriptDraft, video.script_draft_id)

    def switch(who, model):
        return who.post(f"/projects/{video.id}/settings", json={"video_model": model})

    assert switch(owner, "seedance-2.0").status_code == 200
    db.expire_all()
    cheaper = run_price(db, draft, video)
    assert fs.up_to == cheaper  # the quote follows the model; so does what's covered
    assert Decimal(db.get(Job, held["id"]).input["price"]) == cheaper  # Needs you's figure
    r = switch(editor, "seedance-2.5")  # past what the owner said yes to: a new OK
    assert (r.status_code, r.json()["detail"]) == (409, PAST_OK.format(credits=math.ceil(cheaper)))
    assert switch(owner, "seedance-2.5").status_code == 200  # the owner's switch is that OK
    db.expire_all()
    assert fs.up_to == run_price(db, draft, video) > cheaper


@pytest.mark.parametrize("branded", [False, True])
def test_after_a_change_the_header_the_run_card_and_the_note_say_one_up_to(
    app, owner, editor, db, branded
):
    """A freestyle's "up to" is its sends' approved total: the header, the change's run card and
    its note agree (QA on #1354: the change's run alone read its own price), in a brand too."""
    from tests.conftest import first_brand

    fs = _delivered(app, owner, editor, db, first_brand(owner) if branded else None)
    editor.post(f"/freestyles/{fs['id']}/messages", json={"text": CHANGE})
    _run(app, db, ticks=4, start=False)
    (held,) = _held(owner)
    owner.post(f"/jobs/{held['id']}/approve")
    _run(app, db)
    from app import run_progress

    project = db.get(Project, fs["project_id"])
    top = owner.get(f"/freestyles/{fs['id']}").json()["up_to"]  # a freestyle's header reads it
    card = float(run_progress.run_up_to(db, project))  # the run card's
    note = [j.output["note"] for j in director.turns(db, project) if (j.output or {}).get("note")]
    assert abs(card - top) < 1 and abs(note[-1]["up_to"] - top) < 1, (top, card, note[-1]["up_to"])
    assert top >= float(held["freestyle"]["total"]) - 1  # every send approved, not the change alone
    from tests.test_asks import one_figure

    if branded:  # its video's page: header, run card and note say one spent, one up to
        one_figure(owner, editor, project.id)
