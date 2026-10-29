"""Projects (flows OR1): a brand's folders of scripts, videos and quick clips. Make, file
(with Undo), filter, rename, and delete (its items move to No project; Undo brings them
back), with the owner's and editors' rights. Free."""

from app import folders
from app.models.jobs import Job
from tests.test_breakdown import BREAKDOWN
from tests.test_script_produce import _published


def _brand(client):
    return client.get("/brands").json()[0]["id"]


def _file(client, kind, item_id, folder_id):
    return client.post("/folders/file", json={"kind": kind, "id": item_id, "folder_id": folder_id})


def test_a_script_is_filed_listed_and_undone(owner, editor):
    brand = _brand(owner)
    made = editor.post(f"/brands/{brand}/folders", json={"name": "November launch"})
    assert made.status_code == 201 and made.json()["can_manage"]
    again = owner.post(f"/brands/{brand}/folders", json={"name": "november launch"})
    assert (again.status_code, again.json()["detail"]) == (
        409,
        folders.TAKEN.format("november launch"),
    )
    fid = made.json()["id"]
    script = editor.post("/scripts", json={"brand_id": brand, "title": "Gut"}).json()["id"]
    filed = _file(editor, "script", script, fid).json()
    assert filed == {"folder_id": fid, "was_folder_id": None}
    assert [s["id"] for s in editor.get(f"/scripts?folder={fid}").json()] == [script]
    assert script not in [s["id"] for s in editor.get("/scripts?folder=none").json()]
    (row,) = editor.get(f"/brands/{brand}/folders").json()
    assert row["items"] == {"scripts": 1, "videos": 0, "clips": 0}
    assert _file(editor, "script", script, None).json()["was_folder_id"] == fid  # Undo


def test_deleting_a_project_moves_its_items_to_no_project_and_undo_brings_them_back(owner, editor):
    brand = _brand(owner)
    fid = owner.post(f"/brands/{brand}/folders", json={"name": "Spring"}).json()["id"]
    script = owner.post("/scripts", json={"brand_id": brand, "title": "S"}).json()["id"]
    _file(owner, "script", script, fid)
    assert editor.delete(f"/folders/{fid}").status_code == 403  # the owner's project
    assert editor.patch(f"/folders/{fid}", json={"name": "Mine"}).status_code == 403
    assert owner.delete(f"/folders/{fid}").json() == {"moved": 1}
    assert script in [s["id"] for s in owner.get("/scripts?folder=none").json()]
    shown = next(s for s in owner.get("/scripts").json() if s["id"] == script)
    assert shown["folder_id"] is None and owner.get(f"/brands/{brand}/folders").json() == []
    other = owner.post(
        f"/brands/{brand}/folders", json={"name": "Spring"}
    )  # a deleted one never blocks
    assert other.status_code == 201
    back = owner.post(f"/folders/{fid}/restore")
    assert (back.status_code, back.json()["detail"]) == (409, folders.TAKEN.format("Spring"))
    owner.patch(f"/folders/{other.json()['id']}", json={"name": "Spring 2"})
    assert owner.post(f"/folders/{fid}/restore").json()["items"]["scripts"] == 1  # Undo


def test_who_files_what_videos_and_quick_clips(app, owner, editor, db):
    brand = _brand(owner)
    fid = editor.post(f"/brands/{brand}/folders", json={"name": "Clips"}).json()["id"]
    me = editor.get("/auth/me").json()
    clip = Job(workspace_id=me["workspace_id"], kind="video", provider="fake", input={},
               credits=0, brand_id=brand, created_by_id=me["id"])  # fmt: skip
    theirs = Job(workspace_id=me["workspace_id"], kind="video", provider="fake", input={},
                 credits=0, brand_id=brand, created_by_id=None)  # fmt: skip
    db.add_all([clip, theirs])
    db.commit()
    assert _file(editor, "clip", clip.id, fid).status_code == 200
    assert _file(editor, "clip", theirs.id, fid).status_code == 403  # not theirs
    assert _file(owner, "clip", theirs.id, fid).status_code == 200  # the owner files anything
    shown = {j["id"]: j["folder_id"] for j in editor.get(f"/jobs?folder={fid}").json()}
    assert shown == {clip.id: fid, theirs.id: fid}

    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    assert _file(editor, "video", pid, fid).status_code == 200
    assert [p["id"] for p in editor.get(f"/projects?folder={fid}").json()] == [pid]
    step = Job(workspace_id=me["workspace_id"], kind="image", provider="fake", input={},
               credits=0, project_id=pid, created_by_id=me["id"])  # fmt: skip
    db.add(step)
    db.commit()
    no = _file(editor, "clip", step.id, fid)
    assert (no.status_code, no.json()["detail"]) == (409, folders.VIDEO_JOB)
    rows = editor.get(f"/brands/{brand}/folders").json()
    assert rows[0]["items"] == {"scripts": 0, "videos": 1, "clips": 2}
    other, _ = _published(owner, db, breakdown=BREAKDOWN)
    mine = owner.post(f"{other}/drafts/0/produce").json()["project_id"]
    assert _file(owner, "video", mine, fid).status_code == 200
    counted = {"editor": editor, "owner": owner}  # as each one's Videos list shows them
    assert {k: c.get(f"/brands/{brand}/folders").json()[0]["items"]["videos"]
            for k, c in counted.items()} == {"editor": 1, "owner": 2}  # fmt: skip
