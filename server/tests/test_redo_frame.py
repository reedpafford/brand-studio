"""Redo this frame (audit LW3): a still out of date because the breakdown changed is written
again from the new breakdown for that frame alone, then drawn, at one price; the earlier still
stays. Only when its clip still has the same shots. Claude and the image model are mocked."""

import copy

from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job
from app.models.storyboards import StoryboardFrame
from app.redo_frame import CHANGED
from tests.test_breakdown import BREAKDOWN
from tests.test_change_notes import _frame
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture


def _new_breakdown(app, db, editor, setup, data=None):  # noqa: F811
    editor.post(f"/projects/{setup['project']}/breakdown")
    _run(app, db, FakeClaude(data or BREAKDOWN))


def test_an_out_of_date_frame_is_written_again_then_drawn(app, db, editor, setup):  # noqa: F811
    url, frame = _frame(app, db, editor, setup)
    still, old = frame.file_id, frame.breakdown_id
    _new_breakdown(app, db, editor, setup)
    (shown,) = editor.get(url).json()
    assert shown["stale"] is True and shown["redo_blocked"] is None
    assert shown["redo_credits"] > shown["still_credits"]  # writing it, plus its still
    assert editor.post(f"{url}/frames/{frame.id}/render").status_code == 409  # never bare

    job = editor.post(f"{url}/frames/{frame.id}/redo")
    assert job.status_code == 201, job.text
    queued = db.get(Job, job.json()["id"])
    assert queued.input["redo_frame_id"] == frame.id and "<redo_frame>" in queued.input["prompt"]
    assert editor.post(f"{url}/frames/{frame.id}/redo").status_code == 409  # one at a time
    redone = {"frames": [{"clip_id": "c1", "shot_id": "1.1", "prompt": "Mom, from the new plan.",
                          "reference_ids": list(frame.reference_ids)}]}  # fmt: skip
    _run(app, db, FakeClaude(redone))
    db.expire_all()
    row = db.get(StoryboardFrame, frame.id)
    assert row.breakdown_id != old and "Mom, from the new plan." in row.prompt
    assert row.change["status"] == "changing" and row.change["note"] == "Redo this frame"
    assert row.file_id == still  # the earlier still stays until the new one lands
    draw = next(j for j in db.query(Job).all() if j.input.get("frame_id") == frame.id)
    assert draw.status == "queued" and draw.input["was_prompt"] != row.prompt  # Undo: pick it
    assert row.change["made_job_id"] == draw.id
    (shown,) = editor.get(url).json()
    assert shown["stale"] is False and shown["redo_credits"] is None
    assert (shown["change"]["status"], shown["drawing"]) == ("changing", True)  # still coming

    from app.storyboard import save_still
    from tests.conftest import upload

    draw.status, draw.output = "succeeded", {"file_ids": [upload(editor)]}
    save_still(db, draw)  # the new still lands: now it's done, the earlier one kept for Undo
    db.commit()
    (shown,) = editor.get(url).json()
    assert shown["change"]["status"] == "done" and shown["earlier"][-1]["file_id"] == still


def test_a_redo_whose_still_fails_says_so(app, db, editor, setup):  # noqa: F811
    from app.redo_frame import STILL_UNFINISHED

    url, frame = _frame(app, db, editor, setup)
    _new_breakdown(app, db, editor, setup)
    editor.post(f"{url}/frames/{frame.id}/redo")
    redone = {"frames": [{"clip_id": "c1", "shot_id": "1.1", "prompt": "Mom, again.",
                          "reference_ids": list(frame.reference_ids)}]}  # fmt: skip
    _run(app, db, FakeClaude(redone))
    db.expire_all()
    draw = next(j for j in db.query(Job).all() if j.input.get("frame_id") == frame.id)
    draw.status = "failed"  # the still didn't finish
    db.commit()
    (shown,) = editor.get(url).json()
    assert (shown["change"]["status"], shown["change"]["error"]) == ("failed", STILL_UNFINISHED)


def test_a_frame_whose_clip_changed_redoes_the_storyboard(app, db, editor, setup):  # noqa: F811
    url, frame = _frame(app, db, editor, setup)
    data = copy.deepcopy(BREAKDOWN)
    data["clips"][0]["shot_ids"] = data["clips"][0]["shot_ids"][:1]  # c1 split: shot 1.2 moved
    data["clips"].append({**data["clips"][0], "id": "c2",
                          "shot_ids": BREAKDOWN["clips"][0]["shot_ids"][1:]})  # fmt: skip
    _new_breakdown(app, db, editor, setup, data)
    newest = db.query(BreakdownVersion).order_by(BreakdownVersion.id.desc()).first()
    assert newest.id != frame.breakdown_id
    (shown,) = editor.get(url).json()
    assert shown["redo_credits"] is None and shown["redo_blocked"] == CHANGED
    refused = editor.post(f"{url}/frames/{frame.id}/redo")
    assert refused.status_code == 409 and "Redo storyboard" in refused.json()["detail"]


def test_a_moved_script_says_to_make_the_breakdown_again(app, db, editor, setup):  # noqa: F811
    url, frame = _frame(app, db, editor, setup)
    script = f"/projects/{setup['project']}/script"
    editor.put(script, json={"text": editor.get(script).json()["text"] + "\nMOM: Fine."})
    refused = editor.post(f"{url}/frames/{frame.id}/redo")
    assert refused.status_code == 409 and "Make the breakdown again" in refused.json()["detail"]


def test_a_redo_between_its_rewrite_and_its_still_is_still_changing(app, db, editor, setup):  # noqa: F811
    from datetime import timedelta

    from app.db import utcnow

    url, frame = _frame(app, db, editor, setup)
    _new_breakdown(app, db, editor, setup)
    wrote = db.get(Job, editor.post(f"{url}/frames/{frame.id}/redo").json()["id"])
    wrote.status, wrote.finished_at = "succeeded", utcnow()  # saved; the still not queued yet
    db.commit()
    (shown,) = editor.get(url).json()
    assert shown["change"]["status"] == "changing"
    wrote.finished_at = utcnow() - timedelta(minutes=2)  # it never got there
    db.commit()
    (shown,) = editor.get(url).json()
    assert shown["change"]["status"] == "failed"
