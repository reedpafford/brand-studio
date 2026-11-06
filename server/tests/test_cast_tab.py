"""The video's Cast tab (v6 S5, S-gaps-07): each role's clips, where its look came from, Upload
(free, this video only), Lock in this video and Unlock on the script. A drawn look and the combined
"Approve cast & places" are v6-castgate's (#1331). Free: no paid calls."""

from app.models.library import LibraryItem
from app.models.projects import Project
from app.models.script_library import Script, ScriptCastSlot
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_cast_roles import _video


def _rows(client, pid):
    return {r["role"]: r for r in client.get(f"/projects/{pid}/assets").json()}


def test_each_role_says_its_clips_its_saved_version_and_who_may_unlock_it(owner, editor, db):
    pid, mia, kid = _video(owner, editor, db)
    rows = _rows(editor, pid)
    assert rows["Mom"]["clip_ids"] == rows["Nate"]["clip_ids"] == ["c1"]  # "in 1 of 1 clips"
    item = db.get(LibraryItem, mia)
    assert rows["Mom"]["library_version"] == item.version  # "Saved in …: “Mia” v1"
    assert rows["Mom"]["locked"] and not rows["Mom"]["script_unlock"]  # published: final
    assert not _rows(owner, pid)["Mom"]["script_unlock"]
    refused = owner.delete(f"/projects/{pid}/assets/slots/{rows['Mom']['slot_id']}/script-lock")
    assert refused.status_code == 403 and "published" in refused.json()["detail"]

    script = db.get(Script, db.get(ScriptCastSlot, rows["Mom"]["slot_id"]).script_id)
    script.published = False  # before publishing, its author or the owner may unlock it
    db.commit()
    assert _rows(owner, pid)["Mom"]["script_unlock"] and not _rows(editor, pid)["Mom"][
        "script_unlock"]  # fmt: skip
    url = f"/projects/{pid}/assets/slots/{rows['Mom']['slot_id']}/script-lock"
    assert editor.delete(url).status_code == 403
    after = {r["role"]: r for r in owner.delete(url).json()}["Mom"]
    assert not after["locked"] and after["library_item_id"] == mia  # still Mia in this video
    assert owner.delete(url).status_code == 404  # nothing locked any more


def test_upload_makes_the_picture_this_videos_look_free_and_never_the_brands(owner, editor, db):
    pid, mia, kid = _video(owner, editor, db)
    nate = _rows(editor, pid)["Nate"]["slot_id"]
    url = f"/projects/{pid}/assets/slots/{nate}/upload"
    photo = upload(editor)
    row = {r["role"]: r for r in editor.post(url, json={"file_id": photo}).json()}["Nate"]
    look = db.get(LibraryItem, row["library_item_id"])
    assert (row["photo_file_id"], row["only_here"], row["sheet_status"]) == (photo, "video", "none")
    assert look.owner_project_id == pid and look.source_photo_file_id == photo
    assert look.brands == []  # rule 12: never saved to the brand
    assert row["library_version"] is None  # not a saved character
    assert editor.get(f"/projects/{pid}").json()["credits_used"] == 0  # free
    mom = _rows(editor, pid)["Mom"]["slot_id"]
    locked = editor.post(f"/projects/{pid}/assets/slots/{mom}/upload", json={"file_id": photo})
    assert locked.status_code == 409  # locked on the script


def test_lock_fixes_a_roles_look_in_this_video_once_approved(owner, editor, db):
    pid, mia, kid = _video(owner, editor, db)
    nate = _rows(editor, pid)["Nate"]["slot_id"]
    url = f"/projects/{pid}/locks"
    early = editor.put(url, json={"locks": {"roles": [f"slot:{nate}"]}})
    assert early.status_code == 422 and "Approve Nate" in early.json()["detail"]
    assert editor.put(url, json={"locks": {"roles": ["slot:999"]}}).status_code == 422
    with_sheet(db, kid)
    assert editor.put(url, json={"locks": {"roles": [f"slot:{nate}"]}}).json()["locks"][
        "roles"] == [f"slot:{nate}"]  # fmt: skip
    slot = f"/projects/{pid}/assets/slots/{nate}"
    for refused in (editor.post(f"{slot}/make-look"),
                    editor.put(slot, json={"library_item_id": mia}),
                    editor.post(f"{slot}/upload", json={"file_id": upload(editor)})):  # fmt: skip
        assert refused.status_code == 409 and "Unlock it first" in refused.json()["detail"]
    assert editor.put(url, json={"locks": {"roles": []}}).json()["locks"]["roles"] == []
    assert editor.put(slot, json={"library_item_id": mia}).status_code == 200  # unlocked


def test_a_locked_role_merged_away_never_stops_another_lock_being_saved(owner, editor, db):
    pid, mia, kid = _video(owner, editor, db)
    project = db.get(Project, pid)
    project.locks = {"roles": ["slot:999"]}  # a role locked here, since merged into another
    db.commit()
    url = f"/projects/{pid}/locks"
    saved = editor.put(url, json={"locks": {"cast": True, "roles": ["slot:999"]}})
    assert saved.status_code == 200
    assert saved.json()["locks"]["roles"] == [] and saved.json()["locks"]["cast"]
