"""Merge roles, and "These may be the same person" (merge-roles.md; Reed, 2026-10-27: one
person never becomes two roles). On a script's Cast: a role merged into another moves its
shots (every version's plan) and its spoken lines (only the speaker's name changes, never
the words) onto the other, which keeps its lock and look; the merged role's own look is left
unused, never deleted. Undo puts everything back exactly. Free, no model call.

Possible duplicates come from the cast read (`may_be_same_as`) and a cheap hint in code: two
roles described with the same relationship word, never in the same shot. "They're
different" keeps a pair apart for good."""

import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cast_roles import short
from app.models.library import LibraryItem
from app.models.script_library import CastMerge, Script, ScriptCastSlot, ScriptDraft
from app.prompts import check
from app.prompts.schemas import Breakdown

LETTERS = "ABC"
RELATIONS = {
    "friend", "boss", "brother", "sister", "mom", "mother", "dad", "father", "wife", "husband",
    "girlfriend", "boyfriend", "ex", "neighbor", "neighbour", "coworker", "colleague", "roommate",
    "cousin", "uncle", "aunt", "son", "daughter", "grandma", "grandpa", "coach", "teacher", "rival",
}  # fmt: skip
SLOT_FIELDS = ("id", "script_id", "role", "description", "position", "kind", "appears_in",
               "guessed", "library_item_id", "sheet_file_id", "locked_by_id",
               "may_be_same_as")  # fmt: skip


def _slots(db: Session, script: Script) -> list[ScriptCastSlot]:
    query = select(ScriptCastSlot).where(ScriptCastSlot.script_id == script.id)
    return list(db.scalars(query.order_by(ScriptCastSlot.position, ScriptCastSlot.id)))


def _drafts(db: Session, script: Script) -> list[ScriptDraft]:
    query = select(ScriptDraft).where(ScriptDraft.script_id == script.id)
    return list(db.scalars(query.order_by(ScriptDraft.slot)))


def _refs(slot: ScriptCastSlot) -> set[str]:
    """How a plan names the role: its slot, and its look when it's locked."""
    return {f"slot:{slot.id}", *([f"char:{slot.library_item_id}"] if slot.library_item_id else [])}


def _key(text: str) -> str:
    return (short(text) or text).strip().lower()


def _in(shot, slot: ScriptCastSlot, refs: set[str]) -> bool:
    """The role is in the shot, or speaks in it."""
    spoken = bool(shot.speaker) and _key(shot.speaker) == _key(slot.role)
    return spoken or bool(refs & set(shot.character_ids))


def pair(db: Session, script: Script, slot_id: int, into_id: int):
    """The role to merge and the one it goes into, both this script's, never the same."""
    slots = {s.id: s for s in _slots(db, script)}
    if slot_id not in slots or into_id not in slots:
        raise HTTPException(404, "That role isn't in this script's cast.")
    if slot_id == into_id:
        raise HTTPException(422, "A role can't be merged into itself.")
    return slots[slot_id], slots[into_id]


LABEL = re.compile(r"^(\s*)([^(:]+?)(\s*(?:\([^)]*\))?:)")  # "NATE", " (V.O.):"
DRAFT_FIELDS = ("text", "breakdown", "breakdown_problems", "breakdown_kept", "breakdown_text",
                "breakdown_by_id")  # fmt: skip


def _labels(text: str, role: ScriptCastSlot) -> list[int]:
    """The script's lines (1-based) the role speaks, by its speaker label."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if check.SPEAKER.match(line) and (m := LABEL.match(line)) and _key(m[2]) == _key(role.role):
            out.append(n)
    return out


def preview(db: Session, script: Script, slot: ScriptCastSlot, into: ScriptCastSlot) -> dict:
    """What moves: {moved: {shots, lines: [{version, line}]}, look_unused: {name} | None}."""
    refs, shots, lines = _refs(slot), [], []
    for draft in _drafts(db, script):
        if draft.breakdown:
            bd = Breakdown.model_validate(draft.breakdown)
            shots += [s.id for sc in bd.scenes for s in sc.shots if _in(s, slot, refs)]
        lines += [{"version": LETTERS[draft.slot], "line": n} for n in _labels(draft.text, slot)]
    look = db.get(LibraryItem, slot.library_item_id or 0)
    unused = look is not None and look.id != into.library_item_id
    return {"moved": {"shots": list(dict.fromkeys(shots)), "lines": lines},
            "look_unused": {"name": look.name} if unused else None}  # fmt: skip


def merge(db: Session, script: Script, slot: ScriptCastSlot, into: ScriptCastSlot) -> dict:
    """Merge `slot` into `into` (see the module); returns the preview plus the Undo `token`."""
    from app import script_preview

    out, drafts = preview(db, script, slot, into), _drafts(db, script)
    saved = {
        "slot": {f: getattr(slot, f) for f in SLOT_FIELDS},
        "into_id": into.id,
        "into_appears_in": into.appears_in,
        "apart": script.cast_apart or [],
        "drafts": {str(d.id): {f: getattr(d, f) for f in DRAFT_FIELDS} for d in drafts},
    }
    target = f"char:{into.library_item_id}" if into.library_item_id else f"slot:{into.id}"
    name, refs = (short(into.role) or into.role).upper(), _refs(slot)
    for draft in drafts:
        lines = draft.text.splitlines()
        for n in _labels(draft.text, slot):
            lines[n - 1] = LABEL.sub(lambda m: f"{m[1]}{name}{m[3]}", lines[n - 1], count=1)
        draft.text = "\n".join(lines)
        if draft.breakdown:
            bd = Breakdown.model_validate(draft.breakdown)
            for shot in (s for sc in bd.scenes for s in sc.shots):
                moved = [target if r in refs else r for r in shot.character_ids]
                shot.character_ids = list(dict.fromkeys(moved))
                if shot.speaker and _key(shot.speaker) == _key(slot.role):
                    shot.speaker = into.role
            script_preview.save(db, draft, bd, draft.breakdown_by_id, draft.text)
    into.appears_in = sorted({*(into.appears_in or []), *(slot.appears_in or [])})
    script.cast_apart = [p for p in script.cast_apart or [] if slot.id not in p]
    db.delete(slot)
    record = CastMerge(workspace_id=script.workspace_id, script_id=script.id, data=saved)
    db.add(record)
    db.flush()
    return {**out, "token": record.id}


def undo(db: Session, script: Script, token: int) -> None:
    """Put the merged role back with its shots, lines and look exactly as they were."""
    record = db.get(CastMerge, token)
    if record is None or record.script_id != script.id or record.project_id is not None:
        raise HTTPException(404, "There's nothing to undo here any more.")
    data = record.data
    if db.get(ScriptCastSlot, data["slot"]["id"]) is not None:
        raise HTTPException(409, "That role is already back.")
    db.add(ScriptCastSlot(**data["slot"]))
    for draft in _drafts(db, script):
        for field, value in data["drafts"].get(str(draft.id), {}).items():
            setattr(draft, field, value)
    if (into := db.get(ScriptCastSlot, data["into_id"])) is not None:
        into.appears_in = data["into_appears_in"]
    script.cast_apart = data["apart"]
    db.delete(record)
    db.flush()


def _across_versions(db: Session, script: Script, slots: list[ScriptCastSlot]) -> list[tuple]:
    """Roles (the earlier one first) that are likely one person named differently in different
    versions (QA-Live, Marriage Rejection: GROOM in A, NOAH in C), with the reason: the same
    line of 3+ words said in two versions, or, when two versions share a speaker, each one's
    only other speaker (the one that speaker talks to). Never within one version."""
    from app.cast_roles import labels

    def role(name: str):
        return next((s for s in slots if labels(name, s.role)), None)

    said: dict[str, set] = {}
    speakers: dict[int, set] = {}
    for draft in _drafts(db, script):
        for line in draft.text.splitlines():
            if check.SPEAKER.match(line) and (m := LABEL.match(line)) and (who := role(m[2])):
                speakers.setdefault(draft.slot, set()).add(who)
                words = re.sub(r"[^a-z0-9 ]", "", line[m.end() :].lower()).split()
                if len(words) >= 3:
                    said.setdefault(" ".join(words), set()).add((draft.slot, who))
    out = []
    for heard in said.values():
        out += [(a, b, "They say the same line in different versions of the script.")
                for va, a in heard for vb, b in heard if va < vb and a is not b]  # fmt: skip
    versions = sorted(speakers)
    for i, va in enumerate(versions):
        for vb in versions[i + 1 :]:
            both = speakers[va] & speakers[vb]
            only_a, only_b = speakers[va] - both, speakers[vb] - both
            if both and len(only_a) == len(only_b) == 1:
                (a,), (b,) = only_a, only_b
                lead = min(both, key=lambda s: (s.position, s.id)).role
                out.append((a, b, f"Both are the one {lead} speaks to in different versions."))
    first = sorted(out, key=lambda p: 0 if p[2].startswith("They say") else 1)
    return [(*sorted((a, b), key=lambda s: (s.position, s.id)), why) for a, b, why in first]


def maybe_same(db: Session, script: Script) -> list[dict]:
    """Pairs that may be one person: [{a_slot_id, b_slot_id, into_slot_id, why}], never a pair
    kept apart, nor two roles that share a shot."""
    slots = _slots(db, script)
    apart = {frozenset(p) for p in script.cast_apart or []}
    together: set[frozenset] = set()
    for draft in _drafts(db, script):
        if not draft.breakdown:
            continue
        bd = Breakdown.model_validate(draft.breakdown)
        for shot in (s for sc in bd.scenes for s in sc.shots):
            here = [s for s in slots if _refs(s) & set(shot.character_ids)]
            together |= {frozenset((a.id, b.id)) for a in here for b in here if a.id != b.id}
    by_role = {s.role: s for s in slots}
    out, seen = [], set()

    def add(a: ScriptCastSlot, b: ScriptCastSlot, into: ScriptCastSlot, why: str) -> None:
        key = frozenset((a.id, b.id))
        if a.id != b.id and key not in apart and key not in together and key not in seen:
            seen.add(key)
            out.append({"a_slot_id": a.id, "b_slot_id": b.id, "into_slot_id": into.id, "why": why})

    for s in slots:  # the cast read wasn't sure
        if (other := by_role.get(s.may_be_same_as)) is not None:
            add(s, other, other, "The cast read wasn't sure if they're one person.")
    for a, b, why in _across_versions(db, script, slots):  # versions naming one person apart
        add(a, b, a, why)
    for i, a in enumerate(slots):  # the same relationship, never in one shot
        for b in slots[i + 1 :]:
            words_a = set(re.findall(r"[a-z]+", f"{a.role} {a.description}".lower()))
            words_b = set(re.findall(r"[a-z]+", f"{b.role} {b.description}".lower()))
            if shared := sorted(RELATIONS & words_a & words_b):
                named = [
                    x for x in (a, b) if not re.match(r"(?i)(his|her|their|the|a|an)\b", x.role)
                ]
                add(a, b, (named or [a])[0], f"Both are described as {shared[0]}, and they're "
                    "never in the same shot.")  # fmt: skip
    return out


def dismiss(script: Script, a: int, b: int, undo: bool = False) -> None:
    """They're different (for good), or its Undo."""
    pairs = [p for p in script.cast_apart or [] if set(p) != {a, b}]
    script.cast_apart = pairs if undo else [*pairs, sorted((a, b))]
