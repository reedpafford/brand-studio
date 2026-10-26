"""Looks for one video only (gaps #19; Reed, 2026-10-26): a look made on Assets stays with its
video. It's never in Cast & places or another video's picker; Save to Cast & places copies it
(Reed, or editors with the Team setting on), and Undo puts the video back on its own look."""

import copy

from app.models.jobs import Job, JobStatus
from app.models.library import LibraryItem
from app.models.projects import Project
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_breakdown import BREAKDOWN
from tests.test_script_library import SCRIPT, _make


def _video(owner, editor, db):
    """A published script with Nate unlocked, and an editor's video made from it."""
    made = _make(owner, text=SCRIPT)
    base = f"/scripts/{made['id']}"
    nate = owner.post(f"{base}/cast", json={"role": "Nate, the son", "description": "teen, shy"})
    nate = nate.json()[0]["id"]
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][1]["character_ids"] = [f"slot:{nate}"]
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    return base, pid, nate


def _row(client, pid, slot):
    return next(r for r in client.get(f"/projects/{pid}/assets").json() if r["slot_id"] == slot)


def _drawn(db, client, look_id):
    """The sheet job finished: a sheet waiting for Approve."""
    for job in db.query(Job).all():
        if job.input.get("library_item_id") == look_id:
            job.status = JobStatus.succeeded
    db.get(LibraryItem, look_id).sheet_file_id = upload(client)
    db.commit()


def test_a_look_made_on_assets_stays_with_its_video(owner, editor, db):
    _, pid, nate = _video(owner, editor, db)
    made = editor.post(f"/projects/{pid}/assets/slots/{nate}/make-look")
    assert made.status_code == 200, made.text
    row = next(r for r in made.json() if r["slot_id"] == nate)
    look = row["library_item_id"]
    assert (row["only_here"], row["own_look_id"], row["sheet_status"]) == ("video", look, "drawing")
    item = db.get(LibraryItem, look)
    assert (item.name, item.notes, item.owner_project_id) == ("Nate", "teen, shy", pid)
    sheet = next(j for j in db.query(Job).all() if j.input.get("library_item_id") == look)
    assert sheet.project_id == pid  # paid from this video's budget
    assert editor.post(f"/projects/{pid}/assets/slots/{nate}/make-look").status_code == 409

    assert look not in [c["id"] for c in owner.get("/library/character").json()]  # not listed
    assert editor.get(f"/library/character/{look}").json()["owner_project_id"] == pid
    _, other, slot = _video(owner, editor, db)
    taken = editor.put(f"/projects/{other}/assets/slots/{slot}", json={"library_item_id": look})
    assert taken.status_code == 404  # never offered in another video
    assert editor.patch(f"/projects/{other}", json={"cast_ids": [look]}).status_code == 404
    mine = _make(owner, text=SCRIPT)
    slot = owner.post(f"/scripts/{mine['id']}/cast", json={"role": "Nate"}).json()[0]["id"]
    _drawn(db, editor, look)
    editor.post(f"/library/character/{look}/sheet/approve")
    locked = owner.post(f"/scripts/{mine['id']}/cast/{slot}/lock", json={"library_item_id": look})
    assert locked.status_code == 404  # nor in another script


def test_swapping_to_a_library_character_keeps_the_look_and_back_is_free(owner, editor, db):
    _, pid, nate = _video(owner, editor, db)
    editor.post(f"/projects/{pid}/assets/slots/{nate}/make-look")
    look = _row(editor, pid, nate)["own_look_id"]
    kid = editor.post(
        "/library/character", json={"name": "Kid", "image_file_ids": [upload(editor)]}
    )
    with_sheet(db, kid.json()["id"])
    editor.put(f"/projects/{pid}/assets/slots/{nate}", json={"library_item_id": kid.json()["id"]})
    row = _row(editor, pid, nate)
    assert (row["library_item_id"], row["own_look_id"], row["only_here"]) == (
        kid.json()["id"],
        look,
        None,
    )  # "Not used"
    jobs = db.query(Job).count()
    back = editor.put(f"/projects/{pid}/assets/slots/{nate}", json={"library_item_id": look})
    assert back.status_code == 200 and db.query(Job).count() == jobs
    assert _row(editor, pid, nate)["library_item_id"] == look


def test_save_to_cast_and_places_copies_the_look_and_undo_puts_it_back(owner, editor, db):
    _, pid, nate = _video(owner, editor, db)
    editor.post(f"/projects/{pid}/assets/slots/{nate}/make-look")
    look = _row(editor, pid, nate)["own_look_id"]
    url = f"/projects/{pid}/assets/slots/{nate}/save-to-library"

    refused = editor.post(url, json={"name": "Nate"})
    assert refused.status_code == 403  # the Team setting is off by default
    assert owner.get("/credits/limits").json()["editors_can_save_looks"] is False
    limits = owner.get("/credits/limits").json()
    owner.put("/credits/limits", json={**limits, "editors_can_save_looks": True})
    assert editor.post(url, json={"name": "Nate"}).json()["detail"] == "Approve the sheet first."
    _drawn(db, editor, look)
    editor.post(f"/library/character/{look}/sheet/approve")
    owner.post("/library/character", json={"name": "Bo"})
    taken = editor.post(url, json={"name": "bo"})
    assert (taken.status_code, taken.json()["detail"]) == (
        409,
        "bo is already in Cast & places. Pick another name.",
    )

    jobs = db.query(Job).count()
    saved = editor.post(url, json={"name": "Nate"})
    assert saved.status_code == 201, saved.text
    new = saved.json()["library_item_id"]
    assert db.query(Job).count() == jobs  # free: the same sheet
    row = next(r for r in saved.json()["assets"] if r["slot_id"] == nate)
    assert (row["library_item_id"], row["only_here"], row["sheet_status"]) == (
        new,
        None,
        "approved",
    )
    listed = {c["id"]: c for c in owner.get("/library/character").json()}
    assert new in listed and look not in listed
    assert listed[new]["sheet_file_id"] == db.get(LibraryItem, look).sheet_file_id

    assert editor.delete(f"/library/character/{new}").status_code == 204  # Undo
    db.expire_all()
    assert db.get(LibraryItem, new) is None  # removed, not left in the archive
    assert _row(editor, pid, nate)["library_item_id"] == look
    del limits["editors_can_save_looks"]  # an older screen's save leaves it as it is
    assert owner.put("/credits/limits", json=limits).json()["editors_can_save_looks"] is True


def test_a_scripts_own_look_is_used_by_its_videos_only_and_goes_with_it(app, owner, editor, db):
    from app.purge import purge_deleted
    from tests.test_purge import _deleted

    script = _make(owner, text=SCRIPT)["id"]
    body = {"name": "Nate", "image_file_ids": [upload(owner)], "owner_script_id": script}
    look = owner.post("/library/character", json=body).json()
    assert look["owner_script_id"] == script
    assert look["id"] not in [c["id"] for c in owner.get("/library/character").json()]
    with_sheet(db, look["id"])
    slot = owner.post(f"/scripts/{script}/cast", json={"role": "Nate"}).json()[0]["id"]
    locked = owner.post(f"/scripts/{script}/cast/{slot}/lock", json={"library_item_id": look["id"]})
    assert locked.status_code == 200  # its own script may use it
    gone = owner.delete(f"/library/character/{look['id']}")
    assert (gone.status_code, gone.json()["detail"]) == (
        409,
        "Swap the role to another look first.",
    )
    both = {**body, "owner_project_id": 1}
    assert owner.post("/library/character", json=both).status_code == 422

    _deleted(owner, db, 31, script)
    assert purge_deleted(db, app.state.storage) == 1
    db.expire_all()
    assert db.get(LibraryItem, look["id"]) is None


def test_a_videos_own_look_can_be_removed_once_no_role_uses_it_and_brought_back(owner, editor, db):
    """QA on #423: an owned look has its own delete; refused while the role uses it; Undo."""
    _, pid, nate = _video(owner, editor, db)
    editor.post(f"/projects/{pid}/assets/slots/{nate}/make-look")
    look = _row(editor, pid, nate)["own_look_id"]
    url = f"/library/character/{look}"
    in_use = editor.delete(url)
    assert (in_use.status_code, in_use.json()["detail"]) == (
        409, "Swap the role to another look first."
    )  # fmt: skip
    kid = editor.post(
        "/library/character", json={"name": "Kid", "image_file_ids": [upload(editor)]}
    )
    with_sheet(db, kid.json()["id"])
    editor.put(f"/projects/{pid}/assets/slots/{nate}", json={"library_item_id": kid.json()["id"]})

    assert editor.delete(url).status_code == 204
    assert _row(editor, pid, nate)["own_look_id"] is None  # gone from Assets
    assert editor.post(f"{url}/unarchive").json()["id"] == look  # Undo
    assert _row(editor, pid, nate)["own_look_id"] == look
    assert owner.delete(url).status_code == 204  # Reed may too
    again = editor.post(f"/projects/{pid}/assets/slots/{nate}/make-look")
    assert again.status_code == 200  # a removed look can be made again


def test_only_reed_or_the_videos_maker_removes_its_look(owner, editor, db):
    from app.models.accounts import User

    _, pid, nate = _video(owner, editor, db)
    editor.post(f"/projects/{pid}/assets/slots/{nate}/make-look")
    look = _row(editor, pid, nate)["own_look_id"]
    project = db.get(Project, pid)
    project.created_by_id = db.query(User).filter_by(role="owner").one().id  # someone else's
    project.slot_cast, project.cast_ids = {}, []
    db.commit()
    refused = editor.delete(f"/library/character/{look}")
    assert refused.status_code == 403


def test_undoing_a_save_after_the_original_was_removed_brings_the_original_back(owner, editor, db):
    """QA on #435: save to Cast & places, remove the (now unused) original, then Undo the save:
    the role goes back onto its own look, which is no longer removed."""
    _, pid, nate = _video(owner, editor, db)
    editor.post(f"/projects/{pid}/assets/slots/{nate}/make-look")
    look = _row(editor, pid, nate)["own_look_id"]
    _drawn(db, editor, look)
    editor.post(f"/library/character/{look}/sheet/approve")
    saved = owner.post(
        f"/projects/{pid}/assets/slots/{nate}/save-to-library", json={"name": "Nate"}
    )
    copy_id = saved.json()["library_item_id"]
    assert owner.delete(f"/library/character/{look}").status_code == 204  # nobody uses it now
    assert owner.delete(f"/library/character/{copy_id}").status_code == 204  # Undo the save
    row = _row(editor, pid, nate)
    assert (row["library_item_id"], row["own_look_id"]) == (look, look)
    assert db.get(LibraryItem, look).archived is False
