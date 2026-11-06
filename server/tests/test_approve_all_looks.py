"""Approve all on Variations (Reed, 2026-10-26; README rule 11): only ready items are approved,
the others are listed with why, and Undo takes back exactly those. Looks made for a video have
no Approve all: Approve cast & places covers them (tests/test_cast_gate.py)."""

from app.models.script_library import Script, ScriptDraft
from tests.test_script_library import SCRIPT, _make


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
