"""Kel's empty chair (2026-10-27): shot 1.4 kept "a character that isn't part of this video" on
every Redo. Its role ("Her friend") was cast to a Cast & places look that was later deleted:
the prompt still offered the look, the check didn't know it, and the fixes put it back. A
deleted look now counts as no look everywhere; a shot naming someone the video doesn't have
shows their role instead (made from the script if the cast read missed it), else they're
taken out, said as advice by name."""

import copy

from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.script_library import ScriptCastSlot
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_breakdown import BREAKDOWN
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture
from tests.test_script_library import SCRIPT, _make


def _look(client, db, name: str) -> int:
    item = client.post(
        "/library/character", json={"name": name, "image_file_ids": [upload(client)]}
    )
    with_sheet(db, item.json()["id"])
    return item.json()["id"]


def _naming(ref: str, shot: int = 1) -> dict:
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][shot]["character_ids"] = [ref]
    return bd


def _newest(db, project_id: int) -> BreakdownVersion:
    query = db.query(BreakdownVersion).filter_by(project_id=project_id)
    return query.order_by(BreakdownVersion.id.desc()).first()


def _kels_video(owner, editor, db):
    """A library video whose role "Her friend" is cast at Assets to a look that is then
    deleted from Cast & places (QA-Live 5: video 12, slot 26, char:6)."""
    made = _make(owner, text="SCENE 1 — INT. KITCHEN — DAY\nHER FRIEND: Hi.")  # her only
    base = f"/scripts/{made['id']}"
    friend = owner.post(f"{base}/cast", json={"role": "Her friend"}).json()[0]["id"]
    owner.put(f"{base}/drafts/0/breakdown", json=_naming(f"slot:{friend}"))
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    girlfriend = _look(owner, db, "The girlfriend")
    editor.put(f"/projects/{pid}/assets/slots/{friend}", json={"library_item_id": girlfriend})
    assert _newest(db, pid).data["scenes"][0]["shots"][1]["character_ids"] == [f"char:{girlfriend}"]
    db.get(LibraryItem, girlfriend).archived = True  # deleted while still cast
    db.commit()
    return pid, friend, girlfriend


def test_kels_deleted_look_leaves_the_role_uncast_and_a_redo_puts_the_role_back(
    app,
    db,
    owner,
    editor,  # fmt: skip
):
    pid, friend, girlfriend = _kels_video(owner, editor, db)
    url = f"/projects/{pid}"
    # The role has no look now: Assets says the look was deleted and offers to make one.
    row = next(r for r in editor.get(f"{url}/assets").json() if r["slot_id"] == friend)
    assert (row["ref"], row["library_deleted"], row["ready"]) == (f"slot:{friend}", True, False)
    assert editor.get(f"{url}/assets/missing-looks").json()["slot_ids"] == [friend]
    # A Redo offers the role, never the deleted look; the cast fix doesn't put it back.
    editor.post(f"{url}/breakdown")
    prompt = (
        db.query(Job).filter(Job.input["step"].as_string() == "breakdown").one().input["prompt"]
    )
    assert f"slot:{friend} | Her friend" in prompt and f"char:{girlfriend}" not in prompt
    _run(app, db, FakeClaude(_naming(f"char:{girlfriend}")))  # named anyway
    shots = editor.get(f"{url}/breakdown").json()["breakdown"]["scenes"][0]["shots"]
    assert shots[1]["character_ids"] == [f"slot:{friend}"]
    assert editor.post(f"{url}/breakdown/fix-cast").status_code == 409  # nothing to put back


def test_a_speaker_with_no_role_gets_one_from_the_script(app, db, owner, editor):
    # Reed's FRIEND rule: someone who speaks gets a per-video role, never "not part of this".
    made = _make(owner, text=SCRIPT)
    base = f"/scripts/{made['id']}"
    owner.put(f"{base}/drafts/0/breakdown", json=BREAKDOWN)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    landed = editor.put(f"/projects/{pid}/breakdown", json=_naming("char:999")).json()  # Nate's
    nate = db.query(ScriptCastSlot).filter_by(script_id=made["id"], role="Nate").one()
    assert landed["breakdown"]["scenes"][0]["shots"][1]["character_ids"] == [f"slot:{nate.id}"]
    assert "Advice: Shot 1.2 now shows Nate, a role in this video." in landed["problems"]


def test_a_deleted_look_in_a_plain_video_is_never_offered_and_is_taken_out_by_name(
    app,
    db,
    editor,
    setup,  # noqa: F811
):
    pid = setup["project"]
    mia = _look(editor, db, "Mia")
    editor.patch(f"/projects/{pid}", json={"cast_ids": [mia]})
    look = db.get(LibraryItem, mia)
    look.owner_project_id, look.archived = pid, True  # this video's own look, deleted
    db.commit()
    editor.post(f"/projects/{pid}/breakdown")
    job = db.query(Job).filter(Job.input["step"].as_string() == "breakdown").one()
    assert f"char:{mia}" not in job.input["prompt"]  # never offered
    _run(app, db, FakeClaude(_naming(f"char:{mia}")))
    shown = editor.get(f"/projects/{pid}/breakdown").json()["problems"]
    assert "Advice: Removed Mia from shot 1.2. Nobody by that name is in this video." in shown
    assert not [p for p in shown if "isn't part of this video" in p]


def test_another_workspaces_look_is_never_named(db, editor, outsider, setup):  # noqa: F811
    pid = setup["project"]
    theirs = outsider.post("/library/character", json={"name": "Secret"}).json()["id"]
    editor.post(f"/projects/{pid}/breakdown")
    saved = editor.put(f"/projects/{pid}/breakdown", json=_naming(f"char:{theirs}"))
    assert saved.status_code == 200 and "Secret" not in saved.text
    assert "Advice: Removed an unnamed character from shot 1.2." in " ".join(
        saved.json()["problems"]
    )
