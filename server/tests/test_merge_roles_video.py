"""Merge roles on a video's Assets (merge-roles.md §1): it changes this video only. The merged
role's shots (who's in them and who speaks) go to the role kept, its look is left unused, and
it leaves the video's Assets; the script's cast stays as it is. Every later save of the plan
(an edit, a Redo) keeps it merged. Undo puts it all back. Free: no model call, no redraw."""

import copy

from app.models.jobs import Job
from app.models.projects import Project
from tests.test_breakdown import BREAKDOWN
from tests.test_merge_roles import TEXT
from tests.test_script_library import _make
from tests.test_unknown_cast import _look


def _video(owner, editor, db):
    """Mom and His mother, one person in two roles, each cast at Assets to a look."""
    made = _make(owner, text=TEXT)
    base = f"/scripts/{made['id']}"
    ids = {}
    for role in ("Mom", "His mother"):
        cast = owner.post(
            f"{base}/cast", json={"role": role, "description": "Nate's mother"}
        ).json()
        ids[role] = next(s["id"] for s in cast if s["role"] == role)
    mom, mother = ids["Mom"], ids["His mother"]
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][0]["character_ids"] = [f"slot:{mom}"]
    bd["scenes"][0]["shots"][1].update(character_ids=[f"slot:{mother}"], speaker="His mother",
                                       line="Dinner's ready, Nate.")  # fmt: skip
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    looks = {}
    for slot, name in ((mom, "Mom look"), (mother, "Mother look")):
        looks[slot] = _look(owner, db, name)
        r = editor.put(
            f"/projects/{pid}/assets/slots/{slot}", json={"library_item_id": looks[slot]}
        )
        assert r.status_code == 200, r.text
    return base, pid, mom, mother, looks


def _shots(editor, pid):
    plan = editor.get(f"/projects/{pid}/breakdown").json()["breakdown"]
    return [(s["speaker"], s["character_ids"]) for s in plan["scenes"][0]["shots"]]


def test_merge_on_a_video_moves_its_shots_and_leaves_the_script_alone(owner, editor, db):
    base, pid, mom, mother, looks = _video(owner, editor, db)
    url = f"/projects/{pid}/assets"
    before = _shots(editor, pid)
    jobs = db.query(Job).count()

    preview = editor.get(f"{url}/slots/{mother}/merge/preview", params={"into": mom}).json()
    assert preview == {"moved": {"shots": ["1.2"], "lines": [{"version": "A", "line": 4}]},
                       "look_unused": {"name": "Mother look"}}  # fmt: skip
    done = editor.post(f"{url}/slots/{mother}/merge", json={"into_slot_id": mom}).json()
    assert done["moved"] == preview["moved"]
    assert [r["slot_id"] for r in done["assets"] if r["slot_id"]] == [mom]
    assert _shots(editor, pid) == [("Mom", [f"char:{looks[mom]}"])] * 2
    assert [s["role"] for s in owner.get(base).json()["cast"]] == ["Mom", "His mother"]
    assert looks[mother] not in db.get(Project, pid).cast_ids  # unused, never deleted
    assert db.query(Job).count() == jobs  # free: nothing drawn or written

    # An edit naming the merged role (as an old plan or a Redo would) lands on the role kept.
    plan = editor.get(f"/projects/{pid}/breakdown").json()["breakdown"]
    plan["scenes"][0]["shots"][1].update(character_ids=[f"slot:{mother}"], speaker="His mother")
    assert editor.put(f"/projects/{pid}/breakdown", json=plan).status_code == 200
    assert _shots(editor, pid) == [("Mom", [f"char:{looks[mom]}"])] * 2

    editor.post(f"{url}/merge/undo", json={"token": done["token"]})
    assert _shots(editor, pid) == before
    assert [r["slot_id"] for r in editor.get(url).json() if r["slot_id"]] == [mom, mother]
    gone = editor.post(f"{url}/merge/undo", json={"token": done["token"]})
    assert gone.status_code == 404


def test_a_video_merge_refuses_itself_and_roles_it_doesnt_have(owner, editor, db):
    _, pid, mom, mother, _ = _video(owner, editor, db)
    url = f"/projects/{pid}/assets/slots"
    assert editor.post(f"{url}/{mom}/merge", json={"into_slot_id": mom}).status_code == 422
    assert editor.post(f"{url}/{mom}/merge", json={"into_slot_id": 9999}).status_code == 404
    flagged = editor.get(f"/projects/{pid}/assets/maybe-same").json()
    assert [(p["a_slot_id"], p["b_slot_id"]) for p in flagged] == [(mom, mother)]
    editor.post(f"{url}/{mother}/merge", json={"into_slot_id": mom})
    # Merged here, it can't be merged into or merged again, and its pair isn't flagged.
    assert editor.post(f"{url}/{mom}/merge", json={"into_slot_id": mother}).status_code == 404
    assert editor.get(f"/projects/{pid}/assets/maybe-same").json() == []
