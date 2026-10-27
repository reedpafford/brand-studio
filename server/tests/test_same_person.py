"""Kel's empty chair, video 12 (2026-10-27): the cast backstop made "Girl" and "Brad" roles
for the locked girlfriend (look "Goth GF") and the locked "Mogging BF", so clip 2 waited on a
look for Girl. A label that is a locked or cast role by another name is that role; a video
that already has such a role merges it there when that's certain, else flags it."""

import copy

from app.models.breakdowns import BreakdownVersion
from app.models.projects import Project
from app.models.script_library import ScriptCastSlot
from tests.test_breakdown import BREAKDOWN, _shot
from tests.test_script_library import _make
from tests.test_unknown_cast import _look

TEXT = ("INT. DINER — NIGHT\nOMAR: She's not coming.\nGIRL: Sorry I'm late, babe.\n"
        "BRAD: Who's this guy?\nGIRL: Nobody at all.\nBRAD: Whatever, man.")  # fmt: skip


def _video(owner, editor, db, shots=None):
    """Script 14's shape: Omar, the girlfriend locked to Goth GF, the Mogging BF locked to his
    look; the breakdown shows them where GIRL and BRAD speak."""
    made = _make(owner, title="The empty chair", text=TEXT)
    base = f"/scripts/{made['id']}"
    ids = {}
    for role, look in (("Omar", None), ("Girlfriend", "Goth GF"), ("Mogging BF", "Mogging BF")):
        cast = owner.post(f"{base}/cast", json={"role": role}).json()
        ids[role] = next(s["id"] for s in cast if s["role"] == role)
        if look:
            ids[f"look {look}"] = _look(owner, db, look)
            locked = {"library_item_id": ids[f"look {look}"]}
            owner.post(f"{base}/cast/{ids[role]}/lock", json=locked)
    gf, bf = f"char:{ids['look Goth GF']}", f"char:{ids['look Mogging BF']}"
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"] = shots or [
        _shot("1.1", [2], "Omar", "She's not coming.", 2),
        _shot("1.2", [3], "Girl", "Sorry I'm late, babe.", 2),
        _shot("1.3", [4], "Brad", "Who's this guy?", 2),
        _shot("1.4", [5], "Girl", "Nobody at all.", 2),
        _shot("1.5", [6], "Brad", "Whatever, man.", 2),
    ]
    for shot, who in zip(
        bd["scenes"][0]["shots"], [[], [gf], [bf, gf], [gf, bf], [bf]], strict=False
    ):
        shot["character_ids"] = who
    bd["clips"] = [{"id": "c1", "shot_ids": [s["id"] for s in bd["scenes"][0]["shots"]],
                    "seconds": 8, "seam": "End of scene."}]  # fmt: skip
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    return base, pid, ids


def test_girl_and_brad_are_the_locked_girlfriend_and_mogging_bf(owner, editor, db):
    base, pid, ids = _video(owner, editor, db)
    rows = editor.get(f"/projects/{pid}/assets").json()  # the backstop runs as Assets opens
    roles = [s["role"] for s in owner.get(base).json()["cast"]]
    assert "Girl" not in roles and "Brad" not in roles
    assert "Girl" not in [r["role"] for r in rows] and "Brad" not in [r["role"] for r in rows]
    shots = editor.get(f"/projects/{pid}/breakdown").json()["breakdown"]["scenes"][0]["shots"]
    assert not [i for s in shots for i in s["character_ids"] if i.startswith("slot:")
                and int(i[5:]) not in (ids["Omar"],)]  # fmt: skip
    refused = editor.post(f"/projects/{pid}/storyboard", json={}).json().get("detail", "")
    assert "Girl " not in refused and "Brad" not in refused  # only Omar's look is missing


def test_a_girl_role_already_made_is_merged_into_the_locked_slot(owner, editor, db):
    """The live state: the backstop already made Girl and Brad, and put them in the shots."""
    base, pid, ids = _video(owner, editor, db)
    project = db.get(Project, pid)
    script = owner.get(base).json()["id"]
    made = {n: ScriptCastSlot(script_id=script, role=n, kind="Helper", position=9)
            for n in ("Girl", "Brad", "Photographer")}  # fmt: skip
    db.add_all(made.values())
    db.flush()
    row = db.query(BreakdownVersion).filter_by(project_id=pid).order_by(BreakdownVersion.id.desc())
    row = row.first()
    data = copy.deepcopy(row.data)
    for shot in data["scenes"][0]["shots"][1:]:
        shot["speaker"] = "Brad" if shot["id"] in ("1.3", "1.5") else "Girl"
        name = shot["speaker"]
        shot["character_ids"] = [*shot["character_ids"], f"slot:{made[name].id}"]
    row.data = data
    db.commit()
    rows = {r["role"]: r for r in editor.get(f"/projects/{pid}/assets").json()}
    assert "Girl" not in rows and "Brad" not in rows
    assert rows["Photographer"]["shots"] == 0  # harmless: no look asked for
    assert "Photographer" not in editor.get(f"/projects/{pid}/assets/missing-looks").json()["roles"]
    db.refresh(project)
    assert project.slot_merged == {str(made["Girl"].id): ids["Girlfriend"],
                                   str(made["Brad"].id): ids["Mogging BF"]}  # fmt: skip
    shots = editor.get(f"/projects/{pid}/breakdown").json()
    problems = shots["problems"]
    assert "Advice: Girl is Girlfriend, one role in this video." in problems
    gf, bf = f"char:{ids['look Goth GF']}", f"char:{ids['look Mogging BF']}"
    who = [s["character_ids"] for s in shots["breakdown"]["scenes"][0]["shots"]]
    assert who[1:] == [[gf], [bf, gf], [gf, bf], [bf]]
    # Rule 9: the merge says so on Assets, with Undo; undone, it's never merged again here.
    url = f"/projects/{pid}/assets"
    notes = [p for p in editor.get(f"{url}/maybe-same").json() if p["undo_token"]]
    one = " in this video, so they're one role."
    assert [n["why"] for n in notes] == [f"Girl is Girlfriend{one}", f"Brad is Mogging BF{one}"]
    assert (
        editor.post(f"{url}/merge/undo", json={"token": notes[0]["undo_token"]}).status_code == 200
    )
    roles = [r["role"] for r in editor.get(url).json()]
    assert "Girl" in roles and "Brad" not in roles  # Brad merges again by himself
    db.expire_all()
    assert str(made["Girl"].id) not in (db.get(Project, pid).slot_merged or {})


def test_one_shot_is_not_enough_to_merge_so_it_is_flagged(owner, editor, db):
    """Never merged on an unsure match, never blocking: "These may be the same person"."""
    one = [_shot("1.1", [2, 3, 5], "Omar", "She's not coming.", 2),
           _shot("1.2", [4, 6], "Omar", "Who's this guy?", 2)]  # fmt: skip
    base, pid, ids = _video(owner, editor, db, shots=one)
    brad = ScriptCastSlot(script_id=owner.get(base).json()["id"], role="Brad", kind="Helper")
    db.add(brad)
    db.flush()
    row = db.query(BreakdownVersion).filter_by(project_id=pid).one()
    data = copy.deepcopy(row.data)  # only one shot has Brad's lines (Girl's: one, but GF)
    data["scenes"][0]["shots"][0]["character_ids"] = [f"char:{ids['look Goth GF']}"]
    data["scenes"][0]["shots"][1]["character_ids"] = [
        f"char:{ids['look Mogging BF']}",
        f"slot:{brad.id}",
    ]
    row.data = data
    db.commit()
    editor.get(f"/projects/{pid}/assets")
    assert not db.get(Project, pid).slot_merged
    pairs = editor.get(f"/projects/{pid}/assets/maybe-same").json()
    assert (ids["Mogging BF"], brad.id) in [(p["a_slot_id"], p["b_slot_id"]) for p in pairs]
