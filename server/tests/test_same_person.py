"""Kel's empty chair, video 12 (2026-10-27): the cast backstop made "Girl" and "Brad" roles
for the locked girlfriend (look "Goth GF") and the locked "Mogging BF", so clip 2 waited on a
look for Girl. A role that is a locked one by another name (its name, "GF", or the same line
in another version) is merged into it on the video, with Undo; one only the shots suggest is
flagged as maybe the same person; neither ever blocks."""

import copy

from app.models.projects import Project
from app.models.script_library import ScriptCastSlot
from tests.test_breakdown import BREAKDOWN, _shot
from tests.test_script_library import _make
from tests.test_unknown_cast import _look

TEXT = ("INT. DINER — NIGHT\nOMAR: She's not coming.\nGIRL: Sorry I'm late, babe.\n"
        "BRAD: Who's this guy?\nGIRL: Nobody at all.\nBRAD: Whatever, man.")  # fmt: skip


def _video(owner, editor, db, other=""):
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
    if other:  # another version of the script
        owner.put(f"{base}/drafts/1", json={"text": other})
    bd["scenes"][0]["shots"] = [
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
    for n in (0, 1) if other else (0,):
        owner.put(f"{base}/drafts/{n}/breakdown", json=bd)
        owner.post(f"{base}/drafts/{n}/approve")
    published = owner.post(f"{base}/publish")
    assert published.status_code == 200, published.text
    video = editor.post(f"{base}/drafts/0/produce")
    assert video.status_code == 201, video.text
    pid = video.json()["project_id"]
    return base, pid, ids


def _pairs(editor, pid):
    pairs = editor.get(f"/projects/{pid}/assets/maybe-same").json()
    return {(p["a_slot_id"], p["b_slot_id"], p["undo_token"]): p["why"] for p in pairs}


def test_girl_and_brad_only_the_shots_show_are_flagged_and_never_block(owner, editor, db):
    base, pid, ids = _video(owner, editor, db)
    rows = editor.get(f"/projects/{pid}/assets").json()  # the backstop runs as Assets opens
    cast = {s["role"]: s["id"] for s in owner.get(base).json()["cast"]}
    assert not db.get(Project, pid).slot_merged  # never merged on the shots alone
    assert _pairs(editor, pid) == {
        (ids["Girlfriend"], cast["Girl"], None): "Their shots show the same person.",
        (ids["Mogging BF"], cast["Brad"], None): "Their shots show the same person.",
    }
    # QA-2: counted as the role they may be (Next isn't held up), and no look made by itself
    assert [r["role"] for r in rows if not r["ready"]] == ["Omar"]
    assert editor.get(f"/projects/{pid}/assets/missing-looks").json()["roles"] == ["Omar"]
    refused = editor.post(f"/projects/{pid}/storyboard", json={}).json()["detail"]
    assert refused == "Omar has no approved look yet. Approve one in Assets."  # not Girl, Brad


def test_a_same_line_merges_girl_into_the_locked_girlfriend_with_undo(owner, editor, db):
    """Version B says GIRLFRIEND for the same line; the 0-shot Photographer stays harmless."""
    other = "INT. DINER — NIGHT\nGIRLFRIEND: Sorry I'm late, babe."
    base, pid, ids = _video(owner, editor, db, other)
    script = owner.get(base).json()["id"]
    db.add(ScriptCastSlot(script_id=script, role="Photographer", kind="Helper", position=9))
    db.commit()
    url = f"/projects/{pid}/assets"
    rows = {r["role"]: r for r in editor.get(url).json()}
    assert "Girl" not in rows and rows["Photographer"]["shots"] == 0
    assert "Photographer" not in editor.get(f"{url}/missing-looks").json()["roles"]
    girl = next(s["id"] for s in owner.get(base).json()["cast"] if s["role"] == "Girl")
    assert db.get(Project, pid).slot_merged == {str(girl): ids["Girlfriend"]}
    plan = editor.get(f"/projects/{pid}/breakdown").json()
    assert "Advice: Girl is Girlfriend, one role in this video." in plan["problems"]
    gf = f"char:{ids['look Goth GF']}"
    assert [gf in s["character_ids"] for s in plan["breakdown"]["scenes"][0]["shots"]] == [
        False, True, True, True, False]  # fmt: skip
    # Rule 9: it says so on Assets with Undo, still after a look is picked (QA-2); undone, it's
    # never merged by itself again here.
    omar = {"library_item_id": _look(owner, db, "Omar look")}
    assert editor.put(f"{url}/slots/{ids['Omar']}", json=omar).status_code == 200
    (token,) = [t for (_, b, t) in _pairs(editor, pid) if t]
    assert _pairs(editor, pid)[(ids["Girlfriend"], girl, token)] == (
        "Girl is Girlfriend in this video, so they're one role."
    )
    assert editor.post(f"{url}/merge/undo", json={"token": token}).status_code == 200
    assert "Girl" in [r["role"] for r in editor.get(url).json()]
    db.expire_all()
    assert str(girl) not in (db.get(Project, pid).slot_merged or {})


def test_a_short_name_is_the_role_and_never_a_second_one(owner, editor, db):
    from app.cast_roles import labels

    assert labels("GF", "Girlfriend") and labels("BF", "Mogging BF")
    assert not labels("GIRL", "Girlfriend")
