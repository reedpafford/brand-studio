"""Variations (workflow v2): Claude writes one or two alternates of a script's approved
original into version slots 1 and 2. Each run is one paid call at one price; a regenerate is
another run, kept apart from the variation it doesn't replace. Slots stay drafts until
someone approves them; an approved slot is never overwritten."""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts
from app.enhance import escape, project_context, project_screens
from app.models.brands import Brand
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.script_library import Script, ScriptCastSlot, ScriptDraft
from app.prompts import check
from app.prompts.schemas import Variations
from app.script_preview import stand_in_project


def _locked(db: Session, script: Script) -> list[tuple[LibraryItem, ScriptCastSlot]]:
    slots = db.scalars(
        select(ScriptCastSlot)
        .where(ScriptCastSlot.script_id == script.id, ScriptCastSlot.library_item_id.is_not(None))
        .order_by(ScriptCastSlot.position)
    )
    return [(db.get(LibraryItem, s.library_item_id), s) for s in slots]


def job_input(
    db: Session,
    script: Script,
    original: ScriptDraft,
    slots: list[int],
    keep_apart: list[str],
    note: str,
    reference: dict | None,
) -> dict:
    project = stand_in_project(db, script, original, reference)
    system, _ = project_context(db, project, "variations")
    cast = [f"char:{item.id} {item.name} ({slot.role})" for item, slot in _locked(db, script)]
    ref = prompts.reference_block(reference, script.reference_replace) if reference else ""
    message = prompts.variations_input(
        escape(original.text),
        [escape(c) for c in cast],
        len(slots),
        reference=escape(ref),
        keep_apart=escape("\n\n".join(keep_apart)),
        note=escape(note),
    )
    return {
        "step": "variations",
        "script_id": script.id,
        "slots": slots,
        "system": system,
        "prompt": message,
    }


def _mine(problems: list[str], n: int) -> list[str]:
    """Variation n's problems, plus those about the set (a wrong count, two close ones)."""
    return [p for p in problems if f"variation {n}" in p or not re.search(r"variation \d", p)]


def save_variations(db: Session, job: Job) -> None:
    script = db.get(Script, job.input["script_id"])
    if script is None:
        return
    result = Variations.model_validate(job.output)
    original = db.scalar(
        select(ScriptDraft).where(ScriptDraft.script_id == script.id, ScriptDraft.slot == 0)
    )
    brand = db.get(Brand, script.brand_id)
    screens = {
        f"screen:{s.id}": s.default_for
        for s in project_screens(db, stand_in_project(db, script, original))
    }
    names = [item.name for item, _ in _locked(db, script)]
    slots = job.input["slots"]
    found = check.variations(
        original.text, result, screens, brand.end_line, brand.never_say, len(slots), cast=names
    )
    for n, (slot, made) in enumerate(zip(slots, result.variations, strict=False), 1):
        draft = db.scalar(
            select(ScriptDraft).where(ScriptDraft.script_id == script.id, ScriptDraft.slot == slot)
        )
        if draft and draft.status == "approved":
            continue  # approved while it was being written: keep the approved words
        if not draft:
            draft = ScriptDraft(script_id=script.id, slot=slot)
            db.add(draft)
        draft.text, draft.title, draft.premise = made.script, made.title, made.premise
        draft.changes, draft.problems, draft.job_id = made.changes, _mine(found, n), job.id
        draft.breakdown, draft.breakdown_problems = None, []  # made for the old words
