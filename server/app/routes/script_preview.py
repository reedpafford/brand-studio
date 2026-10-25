"""Breakdown preview on a library version (optional): run it, see length, scenes and shots,
edit them (timing, shots, splits and joins are all the Breakdown JSON), and save it on the
version. The editor starts from it when the version is produced."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import script_library as lib
from app import script_preview
from app.auth import current_user
from app.credits import estimate
from app.db import get_db
from app.models.accounts import User
from app.models.jobs import Job, JobStatus
from app.prompts.schemas import Breakdown
from app.routes.clips import generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.references import load as load_reference
from app.routes.script_library import Slot

router = APIRouter(prefix="/scripts/{script_id}/drafts/{slot}/breakdown", tags=["script library"])
WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)


class PreviewOut(BaseModel):
    breakdown: Breakdown | None
    problems: list[str]
    seconds: int  # the clips added up (0 before any breakdown)
    running: bool  # a breakdown is being made


class EstimateOut(BaseModel):
    credits: float


def _version(db: Session, user: User, script_id: int, slot: int, edit: bool):
    script = lib.get_script(db, user, script_id)
    if edit:
        lib.editable(user, script)
    return script, lib.get_draft(db, script, slot)


def _running(db: Session, draft_id: int) -> bool:
    jobs = db.scalars(select(Job).where(Job.status.in_(WAITING), Job.kind == "write-claude"))
    return any(j.input.get("script_draft_id") == draft_id for j in jobs)


def _out(db: Session, draft) -> PreviewOut:
    bd = Breakdown.model_validate(draft.breakdown) if draft.breakdown else None
    return PreviewOut(
        breakdown=bd,
        problems=draft.breakdown_problems,
        seconds=sum(c.seconds for c in bd.clips) if bd else 0,
        running=_running(db, draft.id),
    )


@router.get("", response_model=PreviewOut)
def read_preview(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    _, draft = _version(db, user, script_id, slot, edit=False)
    return _out(db, draft)


@router.get("/estimate", response_model=EstimateOut)
def preview_estimate(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """What running the breakdown costs (one Claude call), before pressing it."""
    _version(db, user, script_id, slot, edit=False)
    return EstimateOut(credits=estimate(db, user.workspace_id, "write-claude", Decimal(1), {}))


@router.post("", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)])
def run_preview(
    script_id: int,
    slot: Slot,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Run the breakdown on this version's words (a paid Claude call; an editor's own work
    comes from their weekly allowance). It replaces any saved breakdown when it finishes."""
    script, draft = _version(db, user, script_id, slot, edit=True)
    if not draft.text.strip():
        raise HTTPException(422, "Write the script first.")
    if _running(db, draft.id):
        raise HTTPException(409, "A breakdown is already being made for this version.")
    ref = load_reference(request, script.reference_id) if script.reference_id else None
    job_input = script_preview.job_input(db, script, draft, ref)
    return enqueue(db, user, "write-claude", job_input, provider="claude")


@router.put("", response_model=PreviewOut)
def save_preview(
    script_id: int,
    slot: Slot,
    body: Breakdown,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Save an edited breakdown on the version. Its problems are shown, never blocking."""
    _, draft = _version(db, user, script_id, slot, edit=True)
    script_preview.save(db, draft, body)
    db.commit()
    return _out(db, draft)
