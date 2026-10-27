"""Reading the cast (Reed, #197): Claude reads every approved version and lists the roles
that need a look. A role the script already has keeps its slot (a locked one stays
locked); new roles join as unlocked slots. The list's order sets the slots' order. Each slot
records the versions it's in; one the read no longer finds is kept with none."""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts
from app.enhance import escape, escape_block, project_context
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.script_library import Script, ScriptCastSlot, ScriptDraft
from app.prompts import check
from app.prompts.schemas import CastSlots
from app.script_preview import stand_in_project


def _slots(db: Session, script: Script) -> list[ScriptCastSlot]:
    query = select(ScriptCastSlot).where(ScriptCastSlot.script_id == script.id)
    return list(db.scalars(query.order_by(ScriptCastSlot.position, ScriptCastSlot.id)))


def _versions(db: Session, script: Script) -> dict[int, str]:
    rows = db.scalars(
        select(ScriptDraft).where(
            ScriptDraft.script_id == script.id, ScriptDraft.status == "approved"
        )
    )
    return {d.slot: d.text for d in rows}


def _cast(db: Session, script: Script) -> list[tuple[str, str]]:
    """The locked cast as (prompt line, name): ('char:1 Bruno (Bruno, the pitbull)', 'Bruno')."""
    out = []
    for slot in _slots(db, script):
        if slot.library_item_id and (item := db.get(LibraryItem, slot.library_item_id)):
            out.append((f"char:{item.id} {item.name} ({slot.role})", item.name))
    return out


def ready(db: Session, script: Script) -> bool:
    return 0 in _versions(db, script)


def job_input(
    db: Session, script: Script, reference: dict | None, versions: dict[int, str] | None = None
) -> dict:
    """`versions`: the texts to read (default: the approved ones; a reel import reads its
    fresh draft A before anyone approves it)."""
    original = db.scalar(
        select(ScriptDraft).where(ScriptDraft.script_id == script.id, ScriptDraft.slot == 0)
    )
    system, _ = project_context(db, stand_in_project(db, script, original), "cast_slots")
    ref = prompts.reference_block(reference, script.reference_replace) if reference else ""
    brief = f"{script.title}: {script.description}" if script.description else script.title
    message = prompts.cast_slots_input(
        {slot: escape(text) for slot, text in (versions or _versions(db, script)).items()},
        reference=escape_block(ref),
        cast=[escape(line) for line, _ in _cast(db, script)],
        brief=escape(brief),
    )
    return {"step": "cast_slots", "script_id": script.id, "system": system, "prompt": message}


def after(db: Session, job: Job) -> None:
    """Writing a script's words or its variations reads its cast next (Designer #322),
    already paid for with them: every version written so far, the locked cast as <cast> so
    locked slots aren't added twice. Version A needn't be approved yet."""
    from app.models.accounts import User
    from app.routes.jobs import enqueue

    script = db.get(Script, job.input["script_id"], populate_existing=True)
    if script is None or script.published or script.archived:
        return
    drafts = db.scalars(select(ScriptDraft).where(ScriptDraft.script_id == script.id))
    versions = {d.slot: d.text for d in drafts if d.text.strip()}
    if not versions:
        return
    data = job_input(db, script, job.input.get("then_cast_reference"), versions)
    enqueue(
        db, db.get(User, job.created_by_id), "write-claude", data, provider="claude", prepaid=True
    )


def problems(db: Session, script: Script, job: Job) -> list[str]:
    result = CastSlots.model_validate(job.output)
    names = [name for _, name in _cast(db, script)]
    return check.cast_slots(_versions(db, script), result, cast=names)


# Script cues that look like "NAME:" but are nobody (QA on #565): each would auto-make a look.
NOT_A_ROLE = {
    "vo",
    "v.o",
    "v.o.",
    "narrator",
    "voiceover",
    "voice over",
    "text",
    "caption",
    "super",
    "cut",
    "cut to",
    "smash cut",
    "match cut",
    "fade in",
    "fade out",
    "fade to black",
    "dissolve to",
    "music",
    "sfx",
    "sound",
    "montage",
    "title",
    "note",
    "on screen",
    "text on screen",
    "insert",
    "beat",
    "b-roll",
    "int",
    "ext",
    "int.",
    "ext.",
    "scene",
}


def _speakers(db: Session, script: Script) -> dict[str, list[int]]:
    """Everyone who speaks in the script's versions, as the script labels them ("FRIEND:" is
    Friend), with the versions they speak in."""
    out: dict[str, list[int]] = {}
    for draft in db.scalars(select(ScriptDraft).where(ScriptDraft.script_id == script.id)):
        for line in draft.text.splitlines():
            if m := check.SPEAKER.match(line):
                name = re.sub(r"\(.*?\)", "", m[0]).strip(" :").strip()  # "NATE (V.O.)"
                said = re.search(r"[A-Za-z]", line[m.end() :])  # only someone who speaks
                cue = name.lower() in NOT_A_ROLE or name.lower().endswith(" to")  # "CUT TO:"
                if name and said and not cue and not name.lower().startswith(("int.", "ext.")):
                    out.setdefault(name.title(), [])
                    if draft.slot not in out[name.title()]:
                        out[name.title()].append(draft.slot)
    return out


def _key(role: str) -> str:
    """One role however it's written: "Nate, the teen groom" and "NATE" are both Nate."""
    from app.cast_roles import short

    return (short(role) or role).strip().lower()


def speaker_slots(db: Session, script: Script, slots: list[ScriptCastSlot]) -> list[ScriptCastSlot]:
    """A role for each speaker the cast read missed (Reed: FRIEND), added to the script. A
    speaker whose label is a role already there (`cast_roles.labels`) is that role, never a
    second one (Reed: one person is never two roles)."""
    from app.cast_roles import labels

    out = []
    for name, versions in _speakers(db, script).items():
        if not any(labels(name, s.role) for s in [*slots, *out]):
            out.append(ScriptCastSlot(script_id=script.id, role=name, kind="Helper",
                                      appears_in=versions))  # fmt: skip
            db.add(out[-1])
    return out


def save_cast_slots(db: Session, job: Job) -> None:
    script = db.get(Script, job.input["script_id"])
    if script is None or script.published or script.archived:
        return  # published scripts are final
    result = CastSlots.model_validate(job.output)
    have = {_key(s.role): s for s in _slots(db, script)}
    order, done = [], {}
    for made in result.slots:
        key = _key(made.role)
        if key in done:  # one role listed twice ("Nate", "Nate, the groom"): one slot
            done[key].appears_in = sorted({*done[key].appears_in, *made.appears_in})
            continue
        slot = have.pop(key, None)
        if slot is None:
            slot = ScriptCastSlot(script_id=script.id, role=made.role[:120], kind=made.kind)
            db.add(slot)
        if not slot.description:
            slot.description, slot.guessed = made.description, list(made.guessed)
        slot.appears_in = sorted(set(made.appears_in))
        slot.may_be_same_as = made.may_be_same_as.strip()[:120]  # the editor decides
        order.append(slot)
        done[key] = slot
    for slot in have.values():
        slot.appears_in = []  # the script doesn't name it any more
    order += speaker_slots(db, script, [*order, *have.values()])
    for position, slot in enumerate([*order, *have.values()], 1):  # others keep their order
        slot.position = position
