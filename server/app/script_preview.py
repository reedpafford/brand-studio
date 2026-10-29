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
from app.models.library import Kind, LibraryItem
from app.models.projects import Project
from app.models.script_library import Script, ScriptCastSlot, ScriptDraft
from app.prompts import check
from app.prompts.schemas import Breakdown


def stand_in_project(
    db: Session, script: Script, draft: ScriptDraft, reference: dict | None = None
) -> Project:
    """A project that is never saved, so the project-based context and checks work as-is.
    `reference` is the script's reel breakdown (`references.load`), if it has one."""
    slots = list(db.scalars(select(ScriptCastSlot).where(ScriptCastSlot.script_id == script.id)))
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
        script_draft_id=draft.id,  # never saved; lets the cast lines name each role
        slot_cast={},
    )


def with_slots(db: Session, script_id: int, context: str, project: Project | None = None) -> str:
    """The context with the script's roles that have no usable look added to <cast> as slot:N
    lines: not locked and not cast in the video (`project`), or their look was deleted (Kel's
    empty chair: "Her friend" was left out of the prompt altogether)."""
    from app.cast_roles import pick

    slots = db.scalars(
        select(ScriptCastSlot)
        .where(ScriptCastSlot.script_id == script_id)
        .order_by(ScriptCastSlot.position)
    )
    lines = "\n".join(
        f"slot:{s.id} | {s.role} | {s.description} (no look yet)"
        for s in slots
        if (pick(db, project, s) if project else s.library_item_id) is None
    )
    return context.replace("\n</cast>", f"\n{escape(lines)}\n</cast>") if lines else context


def job_input(db: Session, script: Script, draft: ScriptDraft, reference: dict | None) -> dict:
    project = stand_in_project(db, script, draft, reference)
    system, context = project_context(db, project, "breakdown")
    context = with_slots(db, script.id, context, project)
    parts = [context, f"<places>\n{escape(breakdown._places(db, project))}\n</places>"]
    from app import plans

    project.plan = draft.plan  # S6: the preview films the owner's approved plan
    planned = plans.block(db, project, plans.script(db, project))
    if planned:
        parts.append(planned[0])
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
        **(
            {
                "plan_version": planned[1],
                "plan": {k: draft.plan[k] for k in ("structure", "cast", "scenes")},
            }
            if planned
            else {}
        ),
        "system": system,
        "prompt": "\n".join(parts),
        "max_tokens": 32000,
    }


def live_looks(db: Session, script: Script) -> set[str]:
    """A plan may name any live look in the workspace (it joins the video's cast), not a
    deleted one or another workspace's."""
    looks = db.scalars(
        select(LibraryItem.id).where(
            LibraryItem.workspace_id == script.workspace_id,
            LibraryItem.kind == Kind.character,
            LibraryItem.archived.is_(False),
        )
    )
    return {f"char:{i}" for i in looks}


def problems(db: Session, script: Script, draft: ScriptDraft, bd: Breakdown) -> list[str]:
    project = stand_in_project(db, script, draft)
    shown = project_screens(db, project)
    screens = {f"screen:{s.id}": s.default_for for s in shown}
    m = breakdown.video_model()
    brand = db.get(Brand, script.brand_id)
    found = check.breakdown(
        draft.text, bd, screens, m.duration.min, m.duration.max, brand.end_line, brand.name,
        kinds=check.kinds_of(shown),
    )  # fmt: skip
    slots = db.scalars(select(ScriptCastSlot).where(ScriptCastSlot.script_id == script.id))
    known_slots = {f"slot:{s.id}" for s in slots} | live_looks(db, script)
    unknown = [
        p
        for p in breakdown.unknown_ids(db, project, bd)
        if p.split("unknown ")[-1] not in known_slots
    ]
    from app.advice import names, plain
    from app.cast_roles import short
    from app.storyboard import assets

    found += unknown + breakdown.cast_problems(db, project, draft.text, bd)
    called = {f"slot:{s.id}": short(s.role) or s.role for s in slots}
    unknown_called = breakdown.unknown_names(db, project, bd)  # even a deleted look's name
    return plain(found, {**unknown_called, **called, **names(assets(db, project))})


def save(
    db: Session,
    draft: ScriptDraft,
    bd: Breakdown,
    by_id: int | None = None,
    text=None,
    plan_version: int | None | str = "keep",
) -> None:
    """A new plan for the version, from `text` (the words it was made from; the version's
    own by default). Advice kept on the old plan doesn't carry over. A name the version doesn't
    have is taken out first, said as advice (it has no Remove button here). `plan_version`:
    the owner's plan it was made from (S6); an edit or fix keeps the one before."""
    script = db.get(Script, draft.script_id)
    bd, removed = breakdown.land(
        db, stand_in_project(db, script, draft), bd, live_looks(db, script)
    )
    if plan_version == "keep":
        plan_version = (draft.breakdown or {}).get("plan_version")
    made = {"plan_version": plan_version} if plan_version else {}
    draft.breakdown, draft.breakdown_by_id = {**bd.model_dump(), **made}, by_id
    draft.breakdown_text, draft.breakdown_kept = draft.text if text is None else text, []
    draft.breakdown_problems = problems(db, script, draft, bd) + removed
