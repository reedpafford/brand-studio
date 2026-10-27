"""Merge roles (merge-roles.md; Reed, 2026-10-27): one person never becomes two roles. A role
merged into another moves its shots and its lines there (only the name changes, never the
words); Undo puts everything back. "These may be the same person" is suggested from the cast
read and from two roles described the same way that never share a shot; "They're different"
keeps a pair apart for good. Free: no model call."""

import copy

from app.models.script_library import ScriptCastSlot
from tests.test_breakdown import BREAKDOWN
from tests.test_script_library import _make

TEXT = (
    "SCENE 1 — INT. KITCHEN — DAY\nMOM: Nate, where is all your money?\nNATE: I bought the dip."
    "\nHIS MOTHER (O.S.): Dinner's ready, Nate."
)


def _script(owner):
    made = _make(owner, text=TEXT)
    base = f"/scripts/{made['id']}"
    ids = {}
    for role, description in (("Mom", "Nate's mother"), ("His mother", "Nate's mother, at home")):
        cast = owner.post(f"{base}/cast", json={"role": role, "description": description}).json()
        ids[role] = next(s["id"] for s in cast if s["role"] == role)
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][0]["character_ids"] = [f"slot:{ids['Mom']}"]
    bd["scenes"][0]["shots"][1]["character_ids"] = [f"slot:{ids['His mother']}"]
    bd["scenes"][0]["shots"][1].update(speaker="His mother", line="Dinner's ready, Nate.")
    assert owner.put(f"{base}/drafts/0/breakdown", json=bd).status_code == 200
    return base, ids["Mom"], ids["His mother"]


def _shots(owner, base):
    plan = owner.get(f"{base}/drafts/0/breakdown").json()["breakdown"]
    return [(s["speaker"], s["character_ids"]) for s in plan["scenes"][0]["shots"]]


def _text(owner, base) -> str:
    return owner.get(base).json()["versions"][0]["text"]


def test_merge_moves_shots_and_lines_and_undo_puts_them_back(owner, db):
    base, mom, mother = _script(owner)
    before = (_shots(owner, base), _text(owner, base))

    preview = owner.get(f"{base}/cast/{mother}/merge/preview", params={"into": mom}).json()
    assert preview == {"moved": {"shots": ["1.2"], "lines": [{"version": "A", "line": 4}]},
                       "look_unused": None}  # fmt: skip

    done = owner.post(f"{base}/cast/{mother}/merge", json={"into_slot_id": mom}).json()
    assert [s["role"] for s in done["cast"]] == ["Mom"]
    assert _shots(owner, base) == [("Mom", [f"slot:{mom}"]), ("Mom", [f"slot:{mom}"])]
    assert _text(owner, base).splitlines()[3] == "MOM (O.S.): Dinner's ready, Nate."

    assert owner.post(f"{base}/cast/merge/undo", json={"token": done["token"]}).status_code == 200
    assert (_shots(owner, base), _text(owner, base)) == before
    assert db.get(ScriptCastSlot, mother).role == "His mother"
    gone = owner.post(f"{base}/cast/merge/undo", json={"token": done["token"]})
    assert gone.status_code == 404


def test_a_role_cant_merge_into_itself_or_another_scripts_role(owner):
    base, mom, _ = _script(owner)
    assert owner.post(f"{base}/cast/{mom}/merge", json={"into_slot_id": mom}).status_code == 422
    assert owner.post(f"{base}/cast/{mom}/merge", json={"into_slot_id": 99999}).status_code == 404


def test_maybe_same_is_suggested_and_theyre_different_keeps_them_apart(owner, db):
    base, mom, mother = _script(owner)
    pairs = owner.get(f"{base}/cast/maybe-same").json()
    why = "Both are described as mother, and they're never in the same shot."
    assert pairs == [{"a_slot_id": mom, "b_slot_id": mother, "into_slot_id": mom, "why": why}]
    pair = {"a_slot_id": mom, "b_slot_id": mother}
    assert owner.post(f"{base}/cast/maybe-same/dismiss", json=pair).json() == []
    assert owner.request("DELETE", f"{base}/cast/maybe-same/dismiss", json=pair).json() == pairs


def test_the_cast_reads_doubt_is_a_suggestion_but_never_two_roles_in_one_shot(owner, db):
    base, mom, mother = _script(owner)
    nate = owner.post(f"{base}/cast", json={"role": "Nate"}).json()[-1]["id"]
    db.get(ScriptCastSlot, nate).may_be_same_as = "Mom"
    db.commit()
    pairs = owner.get(f"{base}/cast/maybe-same").json()
    assert {"a_slot_id": nate, "b_slot_id": mom, "into_slot_id": mom,
            "why": "The cast read wasn't sure if they're one person."} in pairs  # fmt: skip
    bd = owner.get(f"{base}/drafts/0/breakdown").json()["breakdown"]
    bd["scenes"][0]["shots"][0]["character_ids"] += [f"slot:{nate}"]
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    assert not [p for p in owner.get(f"{base}/cast/maybe-same").json() if nate in p.values()]


def test_the_scripts_reply_carries_the_pairs(owner):
    base, mom, mother = _script(owner)
    assert [(p["a_slot_id"], p["b_slot_id"]) for p in owner.get(base).json()["maybe_same"]] == [
        (mom, mother)
    ]
