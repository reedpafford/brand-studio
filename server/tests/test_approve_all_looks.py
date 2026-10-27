"""Approve all on Assets looks and on Variations (Reed, 2026-10-26; README rule 11): only
ready items are approved, the others are listed with why, and Undo takes back exactly those."""

from app.models.library import LibraryItem
from app.models.projects import Project
from app.models.script_library import Script, ScriptCastSlot, ScriptDraft
from tests.conftest import upload
from tests.test_script_library import SCRIPT, _make
from tests.test_video_looks import _drawn, _row, _video


def test_approve_all_looks_on_assets_and_undo(owner, editor, db):
    base, pid, nate = _video(owner, editor, db)
    script_id = db.get(ScriptDraft, db.get(Project, pid).script_draft_id).script_id
    mia, dad, kid_role = (ScriptCastSlot(script_id=script_id, role=r, position=n)
                          for n, r in ((2, "Mia"), (3, "Dad"), (4, "Kid")))  # fmt: skip
    db.add_all([mia, dad, kid_role])
    db.commit()
    url = f"/projects/{pid}/assets"
    editor.post(f"{url}/slots/{nate}/make-look")
    editor.post(f"{url}/slots/{mia.id}/make-look")
    look = _row(editor, pid, nate)["library_item_id"]
    _drawn(db, editor, look)  # Nate's sheet is drawn; Mia's is still being drawn
    kid = editor.post(
        "/library/character", json={"name": "Kid", "image_file_ids": [upload(editor)]}
    )
    db.get(LibraryItem, kid.json()["id"]).sheet_file_id = upload(editor)  # a library look:
    db.commit()  # approved in Cast & places, never here
    editor.put(f"{url}/slots/{kid_role.id}", json={"library_item_id": kid.json()["id"]})

    done = editor.post(f"{url}/approve-all").json()
    mia_look = _row(editor, pid, mia.id)["library_item_id"]
    assert done == {"approved": [look], "skipped": [
        {"id": mia_look, "slot_id": mia.id, "label": "Mia", "reason": "still drawing"},
        {"id": None, "slot_id": dad.id, "label": "Dad", "reason": "no look yet"},
    ]}  # fmt: skip
    assert _row(editor, pid, nate)["sheet_status"] == "approved"
    assert db.get(LibraryItem, kid.json()["id"]).sheet_approved is False
    undone = editor.post(
        f"{url}/approve-all/undo", json={"ids": [*done["approved"], kid.json()["id"]]}
    )
    row = next(r for r in undone.json() if r["slot_id"] == nate)
    assert row["sheet_status"] == "needs_approval"  # exactly that set: a library look untouched
    assert editor.post(f"{url}/approve-all").json()["approved"] == [look]  # again, the same


def test_approve_all_versions_and_undo(owner, db):
    made = _make(owner, text=SCRIPT)
    url = f"/scripts/{made['id']}/drafts"
    owner.put(f"{url}/1", json={"text": SCRIPT + "\nMOM: Again?"})
    db.add(ScriptDraft(script_id=made["id"], slot=2, text=""))  # C: no words yet
    db.commit()
    done = owner.post(f"{url}/approve-all").json()
    assert done == {
        "approved": [0, 1],
        "skipped": [{"id": 2, "label": "C", "reason": "no words yet"}],
    }
    shown = {v["slot"]: v["status"] for v in owner.get(f"/scripts/{made['id']}").json()["versions"]}
    assert shown == {0: "approved", 1: "approved", 2: "draft"}
    owner.post(f"{url}/0/approve")  # already approved: Undo still takes back only its own
    undone = owner.post(f"{url}/approve-all/undo", json={"ids": [1]}).json()
    assert {v["slot"]: v["status"] for v in undone["versions"]} == {
        0: "approved",
        1: "draft",
        2: "draft",
    }
    db.get(Script, made["id"]).published = True
    db.commit()
    assert owner.post(f"{url}/approve-all").status_code == 409  # published: final


def test_approve_all_skips_a_version_still_being_written(owner, db):
    from app.models.jobs import Job, JobStatus

    made = _make(owner, text=SCRIPT)
    url = f"/scripts/{made['id']}/drafts"
    owner.put(f"{url}/1", json={"text": SCRIPT})
    script = db.get(Script, made["id"])
    db.add(Job(workspace_id=script.workspace_id, kind="write-claude", provider="claude",
               status=JobStatus.running,
               input={"step": "variations", "script_id": script.id}, credits=0,
               created_by_id=script.created_by_id))  # fmt: skip
    db.commit()
    done = owner.post(f"{url}/approve-all").json()
    assert done["approved"] == [0]
    assert done["skipped"] == [{"id": 1, "label": "B", "reason": "still writing"}]
