"""Rules for the Script Library: who sees and changes what, and each version's status.

- The owner sees and changes everything. An editor sees published scripts and their own, and
  changes only their own (Reed, 2026-10-25).
- A version's words change only while it is a draft; once approved they never change.
- A published script is final: its versions can't change (duplicate it to change it)."""

import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accounts import User
from app.models.clips import FinalVideo, ProjectClip
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft

MAX_SLOT = 2  # the original (0) plus up to two variations
WORDS_PER_SECOND = 4.8


def visible(user: User, script: Script) -> bool:
    return script.workspace_id == user.workspace_id and (
        user.is_owner or script.published or script.created_by_id == user.id
    )


def get_script(db: Session, user: User, script_id: int) -> Script:
    script = db.get(Script, script_id)
    if not script or not visible(user, script):
        raise HTTPException(404, "No such script.")
    return script


def editable(user: User, script: Script) -> Script:
    """Change it: the author or the owner, and only before it is published."""
    if not (user.is_owner or script.created_by_id == user.id):
        raise HTTPException(403, "Only its author or the owner can change this script.")
    if script.published:
        raise HTTPException(
            409, "This script is published, so it's final. Duplicate it to change it."
        )
    return script


def drafts(db: Session, script: Script) -> list[ScriptDraft]:
    query = select(ScriptDraft).where(ScriptDraft.script_id == script.id)
    return list(db.scalars(query.order_by(ScriptDraft.slot)))


def get_draft(db: Session, script: Script, slot: int) -> ScriptDraft:
    found = db.scalar(
        select(ScriptDraft).where(ScriptDraft.script_id == script.id, ScriptDraft.slot == slot)
    )
    if not found:
        raise HTTPException(404, "No such version.")
    return found


def spoken_seconds(text: str) -> int:
    """A rough length before any breakdown: spoken words at 4.8 a second."""
    said = [ln.split(":", 1)[1] for ln in text.splitlines() if re.match(r"^[A-Z][A-Z .'()-]*:", ln)]
    words = sum(len(s.split()) for s in said) or len(text.split())
    return round(words / WORDS_PER_SECOND)


def seconds(draft: ScriptDraft) -> int:
    if draft.breakdown:
        return sum(c["seconds"] for c in draft.breakdown.get("clips", []))
    return draft.target_seconds or spoken_seconds(draft.text)


def version_status(db: Session, draft: ScriptDraft) -> tuple[str, int | None]:
    """draft | approved | in_production | clips_ready | done, and the project if produced."""
    project = db.scalar(select(Project).where(Project.script_draft_id == draft.id))
    if not project:
        return draft.status, None
    if db.scalar(select(FinalVideo.id).where(FinalVideo.project_id == project.id).limit(1)):
        return "done", project.id
    clips = db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)).all()
    ready = bool(clips) and all(c.approved for c in clips)
    return ("clips_ready" if ready else "in_production"), project.id


def script_status(script: Script, statuses: list[str]) -> str:
    """draft (not published) | published | in_production | done (every approved version)."""
    if not script.published:
        return "draft"
    made = [s for s in statuses if s in ("in_production", "clips_ready", "done")]
    approved = [s for s in statuses if s != "draft"]
    if approved and all(s == "done" for s in approved):
        return "done"
    return "in_production" if made else "published"
