"""Write a library script's words with Claude (workflow v2 "Write all"): the script-draft step
on the script's title and description, its locked cast and its reel. Claude returns 2-3
drafts; the first becomes the original (slot 0), the words it replaced are kept in history."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts
from app import script_library as lib
from app.enhance import escape, escape_block, project_context
from app.models.jobs import Job
from app.models.script_library import Script, ScriptDraft
from app.prompts.schemas import ScriptDrafts
from app.script_preview import stand_in_project, with_slots


def original(db: Session, script: Script) -> ScriptDraft | None:
    return db.scalar(
        select(ScriptDraft).where(ScriptDraft.script_id == script.id, ScriptDraft.slot == 0)
    )


def job_input(db: Session, script: Script, reference: dict | None) -> dict:
    draft = original(db, script) or ScriptDraft(slot=0)
    project = stand_in_project(db, script, draft, reference)
    system, context = project_context(db, project, "script_draft")
    context = context.replace("<brief>\n", f"<brief>\nTitle: {escape(script.title)}\n", 1)
    context = with_slots(db, script.id, context)
    if reference:
        context += f"\n{escape_block(prompts.reference_block(reference, script.reference_replace))}"
    return {"step": "script_draft", "script_id": script.id, "system": system, "prompt": context}


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
    lib.keep_text(db, draft, drafts[0].script, "write", job.created_by_id)
    draft.text, draft.job_id = drafts[0].script, job.id
