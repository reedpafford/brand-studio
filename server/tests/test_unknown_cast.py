"""Kel's empty chair (2026-10-27): "shot 1.4: a character that isn't part of this video" came
back on every Redo. The breakdown's prompt and its check now take the cast from one place, a
name the video doesn't have is taken out wherever a breakdown lands (said as advice, by its
name), and a free repair clears saved ones."""

import copy

from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.projects import Project
from app.seed import repair_unknown_cast
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


def _naming(ref: str) -> dict:
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][1]["character_ids"] = [ref]  # shot 1.2
    return bd


def _newest(db, project_id: int) -> BreakdownVersion:
    return (
        db.query(BreakdownVersion)
        .filter_by(project_id=project_id)
        .order_by(BreakdownVersion.id.desc())
        .first()
    )


def test_a_deleted_cast_look_is_never_offered_and_is_taken_out_by_name(app, db, editor, setup):  # noqa: F811
    # (a) and (c): a look deleted from Cast & places (or a per-video one removed) still sat in
    # the video's cast, so the AI was told about it while the check didn't know it.
    pid = setup["project"]
    mia = _look(editor, db, "Mia")
    editor.patch(f"/projects/{pid}", json={"cast_ids": [mia]})
    look = db.get(LibraryItem, mia)
    look.owner_project_id, look.archived = pid, True  # this video's own look, deleted
    db.commit()
    editor.post(f"/projects/{pid}/breakdown")
    job = db.query(Job).filter(Job.input["step"].as_string() == "breakdown").one()
    assert f"char:{mia}" not in job.input["prompt"]  # never offered
    _run(app, db, FakeClaude(_naming(f"char:{mia}")))  # named anyway
    shown = editor.get(f"/projects/{pid}/breakdown").json()
    assert not [p for p in shown["problems"] if "isn't part of this video" in p]
    assert (
        "Advice: Removed Mia from shot 1.2. Nobody by that name is in this video."
        in shown["problems"]
    )
    assert shown["breakdown"]["scenes"][0]["shots"][1]["character_ids"] == []


def test_a_library_plan_drops_a_deleted_look_and_keeps_a_live_one(app, db, owner, setup):  # noqa: F811
    # (b): a role locked to a look from another video, then that look deleted; plans are Redone
    # from Scripts, where there is no Remove button, so the landing has to take it out.
    made = _make(owner, text=SCRIPT)
    base = f"/scripts/{made['id']}"
    gone, live = _look(owner, db, "Grad photo"), _look(owner, db, "Bo")
    db.get(LibraryItem, gone).owner_project_id = setup["project"]  # another video's own look
    db.commit()
    slot = owner.post(f"{base}/cast", json={"role": "Mom"}).json()[0]["id"]
    owner.post(f"{base}/cast/{slot}/lock", json={"library_item_id": gone})
    owner.delete(f"/library/character/{gone}")
    owner.post(f"{base}/drafts/0/breakdown")
    job = db.query(Job).filter(Job.input["step"].as_string() == "breakdown").one()
    assert f"char:{gone}" not in job.input["prompt"]
    bd = _naming(f"char:{gone}")
    bd["scenes"][0]["shots"][0]["character_ids"] = [f"char:{live}"]
    _run(app, db, FakeClaude(bd))
    plan = owner.get(f"{base}/drafts/0/breakdown").json()
    shots = plan["breakdown"]["scenes"][0]["shots"]
    assert (shots[0]["character_ids"], shots[1]["character_ids"]) == ([f"char:{live}"], [])
    assert any("Removed Grad photo from shot 1.2" in p for p in plan["problems"])
    assert not [p for p in plan["problems"] if "isn't part of this video" in p]


def test_a_swapped_look_is_repaired_free_and_named(app, db, editor, setup):  # noqa: F811
    # (d): a look swapped out of the cast, its old char:N left in the saved breakdown.
    pid = setup["project"]
    old, new = _look(editor, db, "Old Nate"), _look(editor, db, "Nate")
    editor.patch(f"/projects/{pid}", json={"cast_ids": [new]})
    editor.post(f"/projects/{pid}/breakdown")
    _run(app, db, FakeClaude(BREAKDOWN))
    row = _newest(db, pid)
    row.data = _naming(f"char:{old}")  # saved before the fix
    row.problems = [f"shot 1.2: unknown char:{old}"]
    db.commit()
    shown = editor.get(f"/projects/{pid}/breakdown").json()["problems"]
    assert "shot 1.2: Old Nate that isn't part of this video" in shown  # named, not "a character"
    assert repair_unknown_cast(db) == (1, [])
    assert repair_unknown_cast(db) == (0, [])  # running it again changes nothing
    shown = editor.get(f"/projects/{pid}/breakdown").json()["problems"]
    assert "Advice: Removed Old Nate from shot 1.2. Nobody by that name is in this video." in shown
    assert not [p for p in shown if "isn't part of this video" in p]


def test_someone_with_no_name_left_is_an_unnamed_character(app, db, editor, outsider, setup):  # noqa: F811
    pid = setup["project"]
    theirs = outsider.post("/library/character", json={"name": "Secret"}).json()["id"]
    editor.post(f"/projects/{pid}/breakdown")
    _run(app, db, FakeClaude(BREAKDOWN))
    refused = editor.put(f"/projects/{pid}/breakdown", json=_naming(f"char:{theirs}"))
    assert refused.json()["detail"].startswith("shot 1.2: an unnamed character that isn't")
    assert "Secret" not in refused.text  # never another workspace's name
    assert db.get(Project, pid).cast_ids == []
