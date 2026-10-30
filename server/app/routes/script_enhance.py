"""Directions (gaps #4): today's Enhance on a library script version. Claude suggests camera,
movement, reaction and brand-screen lines; the words never change. Priced first, paid like
other script steps (an editor's own script runs on their weekly allowance)."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import enhance
from app import script_library as lib
from app.auth import current_user
from app.credits import estimate
from app.db import get_db
from app.models.accounts import User
from app.models.jobs import WAITING, Job, JobStatus
from app.models.script_library import Script, ScriptDraft
from app.models.scripts import Suggestion
from app.routes.clips import generation_on
from app.routes.enhance import NoteOut, SuggestionOut
from app.routes.jobs import JobOut, enqueue
from app.routes.script_library import ScriptOut, Slot, _out
from app.routes.script_preview import EstimateOut

router = APIRouter(prefix="/scripts/{script_id}/drafts/{slot}", tags=["script library"])


def _version(db: Session, user: User, script_id: int, slot: int) -> tuple[Script, ScriptDraft]:
    script = lib.editable(user, lib.get_script(db, user, script_id))
    draft = lib.get_draft(db, script, slot)
    if not draft.text.strip():
        raise HTTPException(409, "Write the script first.")
    return script, draft


def _jobs(db: Session, draft: ScriptDraft, *statuses: JobStatus) -> list[Job]:
    """This version's Enhance jobs, newest first."""
    found = db.scalars(
        select(Job)
        .where(Job.kind == "write-claude", Job.status.in_(statuses))
        .order_by(Job.id.desc())
    )
    return [j for j in found if j.input.get("draft_id") == draft.id]


def _current(db: Session, draft: ScriptDraft) -> Job | None:
    """The newest finished Enhance, if it was on the version's words as they are now."""
    done = _jobs(db, draft, JobStatus.succeeded)
    return done[0] if done and done[0].input["script_text"] == draft.text else None


@router.get("/enhance/estimate", response_model=EstimateOut)
def enhance_estimate(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    _version(db, user, script_id, slot)
    return EstimateOut(credits=estimate(db, user.workspace_id, "write-claude", Decimal(1), {}))


@router.post(
    "/enhance", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)]
)
def enhance_version(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Suggest directions for this version (one paid Claude call)."""
    script, draft = _version(db, user, script_id, slot)
    if _jobs(db, draft, *WAITING):
        raise HTTPException(409, "Claude is already suggesting directions for this version.")
    data = enhance.draft_job_input(db, script, draft)
    return enqueue(db, user, "write-claude", data, provider="claude")


@router.get("/suggestions", response_model=list[SuggestionOut])
def list_suggestions(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """The marks on the version's words as they are now, in script order (none once the
    words change: suggest again)."""
    _, draft = _version(db, user, script_id, slot)
    job = _current(db, draft)
    if job is None:
        return []
    return db.scalars(
        select(Suggestion)
        .where(Suggestion.script_draft_id == draft.id, Suggestion.job_id == job.id)
        .order_by(Suggestion.start, Suggestion.id)
    ).all()


@router.get("/notes", response_model=list[NoteOut])
def list_notes(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Claude's notes on the words, for information: only people change the words."""
    _, draft = _version(db, user, script_id, slot)
    job = _current(db, draft)
    return (job.output or {}).get("notes", []) if job else []


def _decide(db: Session, user: User, script_id: int, slot: int, suggestion_id: int, status: str):
    _, draft = _version(db, user, script_id, slot)
    mark = db.get(Suggestion, suggestion_id)
    if not mark or mark.script_draft_id != draft.id:
        raise HTTPException(404, "No such suggestion.")
    job = _current(db, draft)
    if job is None or mark.job_id != job.id:
        raise HTTPException(409, "The script changed since this suggestion. Suggest again.")
    mark.status = status
    db.commit()
    return mark


@router.post("/suggestions/{suggestion_id}/accept", response_model=SuggestionOut)
def accept(
    script_id: int,
    slot: Slot,
    suggestion_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return _decide(db, user, script_id, slot, suggestion_id, "accepted")


@router.post("/suggestions/{suggestion_id}/reject", response_model=SuggestionOut)
def reject(
    script_id: int,
    slot: Slot,
    suggestion_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return _decide(db, user, script_id, slot, suggestion_id, "rejected")


@router.post("/apply", response_model=ScriptOut)
def apply_accepted(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Add the accepted directions as lines. Allowed on approved words too: only direction
    lines are added, never a spoken word changed. The words before are kept for Undo."""
    script, draft = _version(db, user, script_id, slot)
    job = _current(db, draft)
    marks = (
        db.scalars(
            select(Suggestion).where(
                Suggestion.script_draft_id == draft.id,
                Suggestion.job_id == job.id,
                Suggestion.status == "accepted",
            )
        ).all()
        if job
        else []
    )
    if not marks:
        raise HTTPException(409, "Accept at least one suggestion first.")
    text = enhance.apply(draft.text, list(marks))
    lib.keep_text(db, draft, text, "enhance", user.id)
    draft.text = text
    db.commit()
    return _out(db, script)
