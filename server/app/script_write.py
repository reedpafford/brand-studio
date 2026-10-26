"""Write a library script's words with Claude (workflow v2 "Write all"): the script-draft step
on the script's title and description, its locked cast and its reel. Claude returns 2-3
drafts; the first becomes the original (slot 0), the words it replaced are kept in history."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts, rewritten
from app import script_library as lib
from app.enhance import escape, escape_block, project_context
from app.models.brands import Brand
from app.models.jobs import Job
from app.models.script_library import Script, ScriptDraft
from app.prompts import check
from app.prompts.schemas import ScriptDrafts
from app.script_preview import stand_in_project, with_slots


def original(db: Session, script: Script) -> ScriptDraft | None:
    return db.scalar(
        select(ScriptDraft).where(ScriptDraft.script_id == script.id, ScriptDraft.slot == 0)
    )


def edited_since_fill(script: Script, draft: ScriptDraft | None) -> bool:
    """The original's words were changed since the reel last filled them (reel-import §5)."""
    filled = (script.reel or {}).get("filled_text")
    return filled is not None and draft is not None and draft.text != filled


def job_input(db: Session, script: Script, reference: dict | None) -> dict:
    draft = original(db, script) or ScriptDraft(slot=0)
    project = stand_in_project(db, script, draft, reference)
    system, context = project_context(db, project, "script_draft")
    context = context.replace("<brief>\n", f"<brief>\nTitle: {escape(script.title)}\n", 1)
    context = with_slots(db, script.id, context)
    if reference:
        context += f"\n{escape_block(prompts.reference_block(reference, script.reference_replace))}"
        if script.new_lines:
            context += "\n<new_lines>true</new_lines>"
    data = {"step": "script_draft", "script_id": script.id, "system": system, "prompt": context}
    if script.reference_breakdown:  # an imported reel: its kept lines and speakers, to check
        kept = [s for s in script.reference_breakdown["shots"] if not prompts.live_action(s)]
        data["reel_lines"] = [x for s in kept if s.get("line") for x in s["line"].split(" / ")]
        data["reel_speakers"] = [
            x for s in kept if s.get("speaker") for x in s["speaker"].split(" / ")
        ]
    return data


def fill(db: Session, script: Script, draft: ScriptDraft, job: Job, by_id: int | None) -> None:
    """Put a write job's first draft into the version: its words, the lines it rewrote, and
    their "Was:" marks (unless new lines were asked for). Used by the write and by Fill the
    script again, so the marks always match the words."""
    first = ScriptDrafts.model_validate(job.output).drafts[0]
    lib.keep_text(db, draft, first.script, "write", by_id)
    draft.text, draft.job_id, draft.changed_lines = first.script, job.id, first.changed_lines
    draft.rewritten = (
        rewritten.marks(draft.text, draft.changed_lines, job.input["reel_lines"])
        if "reel_lines" in job.input and not script.new_lines
        else []
    )


def save_written(db: Session, job: Job) -> None:
    """The first draft becomes the original's words, unless approved or published meanwhile."""
    if "script_id" not in job.input:
        return  # a project's drafts stay in the job (routes/drafts.py)
    script = db.get(Script, job.input["script_id"])
    if script is None or script.published or script.archived:
        return
    drafts = ScriptDrafts.model_validate(job.output).drafts
    if not drafts:
        return
    draft = original(db, script)
    if draft is None:
        draft = ScriptDraft(script_id=script.id, slot=0)
        db.add(draft)
    if draft.status == "approved":
        return
    if job.input.get("reel_step") and edited_since_fill(script, draft):
        script.reel = {**script.reel, "pending_fill_job_id": job.id}  # "New breakdown ready"
        return
    if job.input.get("reel_step"):
        script.reel = {k: v for k, v in script.reel.items() if k != "pending_fill_job_id"}
        script.reel = {**script.reel, "filled_text": drafts[0].script}
    fill(db, script, draft, job, job.created_by_id)
    if "reel_lines" in job.input:  # advice only: the reel's words kept, no invented speakers
        brand = db.get(Brand, script.brand_id)
        draft.problems = check.reference_lines(
            draft.text, job.input["reel_lines"], script.new_lines
        ) + check.reel_speakers(
            draft.text, job.input["reel_speakers"], end_line=brand.end_line, brand=brand.name
        )
