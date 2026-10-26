"""Breakdown preview on a library version (workflow v2): the same breakdown step as a project,
run on the version's words with the script's brand, reel and cast slots, saved on the version.
The editor starts from it when the version is produced.

Locked slots appear as their characters (char:N). Unlocked slots appear as slot:N (no look
yet); the Assets step gives them characters when the version is produced."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import breakdown, prompts
from app.enhance import escape, escape_block, project_context, project_screens
from app.models.brands import Brand
from app.models.projects import Project
from app.models.script_library import Script, ScriptCastSlot, ScriptDraft
from app.prompts import check
from app.prompts.schemas import Breakdown


def stand_in_project(
    db: Session, script: Script, draft: ScriptDraft, reference: dict | None = None
) -> Project:
    """A project that is never saved, so the project-based context and checks work as-is.
    `reference` is the script's reel breakdown (`references.load`), if it has one."""
    slots = db.scalars(select(ScriptCastSlot).where(ScriptCastSlot.script_id == script.id))
    return Project(
        workspace_id=script.workspace_id,
        brand_id=script.brand_id,
        name=script.title,
        goal=script.description,
        planned_seconds=draft.target_seconds,
        aspect_ratio="9:16",
        cast_ids=[s.library_item_id for s in slots if s.library_item_id],
        product_variants={},
        reference_breakdown=reference,
        reference_replace=script.reference_replace,
    )


def with_slots(db: Session, script_id: int, context: str, cast: dict | None = None) -> str:
    """The context with the script's unlocked slots added to <cast> as slot:N lines, leaving
    out any the video already cast (`cast`: the project's slot_cast)."""
    unlocked = db.scalars(
        select(ScriptCastSlot)
        .where(ScriptCastSlot.script_id == script_id, ScriptCastSlot.library_item_id.is_(None))
        .order_by(ScriptCastSlot.position)
    )
    lines = "\n".join(
        f"slot:{s.id} | {s.role} | {s.description} (no look yet)"
        for s in unlocked
        if str(s.id) not in (cast or {})
    )
    return context.replace("\n</cast>", f"\n{escape(lines)}\n</cast>") if lines else context


def job_input(db: Session, script: Script, draft: ScriptDraft, reference: dict | None) -> dict:
    project = stand_in_project(db, script, draft, reference)
    system, context = project_context(db, project, "breakdown")
    context = with_slots(db, script.id, context)
    parts = [context, f"<places>\n{escape(breakdown._places(db, project))}\n</places>"]
    parts.append(breakdown.video_model_block(breakdown.video_model()))
    if project.reference_breakdown:
        ref = prompts.reference_block(project.reference_breakdown, project.reference_replace)
        parts.append(escape_block(ref))
    parts.append(f"<script>\n{escape(prompts.number_lines(draft.text))}\n</script>")
    return {
        "step": "breakdown",
        "script_id": script.id,  # Publish and Write wait for it, as for other script steps
        "script_draft_id": draft.id,
        "script_text": draft.text,
        "system": system,
        "prompt": "\n".join(parts),
        "max_tokens": 32000,
    }


def problems(db: Session, script: Script, draft: ScriptDraft, bd: Breakdown) -> list[str]:
    project = stand_in_project(db, script, draft)
    screens = {f"screen:{s.id}": s.default_for for s in project_screens(db, project)}
    m = breakdown.video_model()
    brand = db.get(Brand, script.brand_id)
    found = check.breakdown(
        draft.text, bd, screens, m.duration.min, m.duration.max, brand.end_line, brand.name,
        approved=draft.status == "approved",
    )  # fmt: skip
    slots = db.scalars(select(ScriptCastSlot).where(ScriptCastSlot.script_id == script.id))
    known_slots = {f"slot:{s.id}" for s in slots}
    unknown = [
        p
        for p in breakdown.unknown_ids(db, project, bd)
        if p.split("unknown ")[-1] not in known_slots
    ]
    return found + unknown


def save(
    db: Session, draft: ScriptDraft, bd: Breakdown, by_id: int | None = None, text=None
) -> None:
    """A new plan for the version, from `text` (the words it was made from; the version's
    own by default). Advice kept on the old plan doesn't carry over."""
    script = db.get(Script, draft.script_id)
    draft.breakdown, draft.breakdown_by_id = bd.model_dump(), by_id
    draft.breakdown_text, draft.breakdown_kept = draft.text if text is None else text, []
    draft.breakdown_problems = problems(db, script, draft, bd)
