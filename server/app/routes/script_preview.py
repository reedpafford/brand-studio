"""Breakdown preview on a library version (optional): run it, see length, scenes and shots,
edit them (timing, shots, splits and joins are all the Breakdown JSON), and save it on the
version. The editor starts from it when the version is produced."""

from decimal import Decimal
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import advice, breakdown_fix, script_preview
from app import script_library as lib
from app.advice import Said
from app.auth import current_user
from app.credits import estimate
from app.db import get_db
from app.models.accounts import User
from app.models.jobs import Job, JobStatus
from app.prompts.schemas import Breakdown
from app.routes.clips import generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.references import for_script as script_reference
from app.routes.script_library import Slot

router = APIRouter(prefix="/scripts/{script_id}/drafts/{slot}/breakdown", tags=["script library"])
WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)


class PreviewOut(BaseModel):
    breakdown: Breakdown | None
    problems: Said
    seconds: int  # the clips added up (0 before any breakdown)
    running: bool  # a breakdown is being made
    kept: Said = []  # advice kept anyway (never blocks)
    stale: bool = False  # the words changed since it was planned: plan again or keep it
    changed_shots: list[dict] = []  # fix-cast: [{shot_id, before, after}], for Undo
    fixes: list[dict] = []  # [{problem, kind, label}]: a free one-click fix for that problem
    fixed: list[str] = []  # what a fix just did, in plain words (the toast); Undo is PUT


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
        kept=draft.breakdown_kept,
        stale=bool(bd and draft.breakdown_text is not None and draft.breakdown_text != draft.text),
        fixes=breakdown_fix.fixes(draft.breakdown_problems or []),
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
    ref = script_reference(request, script)
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
    script_preview.save(db, draft, body, user.id)
    db.commit()
    return _out(db, draft)


@router.delete("", response_model=PreviewOut)
def remove_preview(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Remove the version's saved plan (the screen's Undo saves it back with PUT). Its video
    then plans its own shots when it is made."""
    _, draft = _version(db, user, script_id, slot, edit=True)
    draft.breakdown, draft.breakdown_problems, draft.breakdown_by_id = None, [], None
    draft.breakdown_text, draft.breakdown_kept = None, []
    db.commit()
    return _out(db, draft)


def _advice(draft):
    """advice.keep/unkeep work on a row's problems and kept: the version's plan's."""
    return SimpleNamespace(problems=draft.breakdown_problems, kept=draft.breakdown_kept)


@router.post("/keep", response_model=PreviewOut)
def keep_advice(
    script_id: int,
    slot: Slot,
    body: advice.KeepIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Keep anyway: this advice on the version's plan stays as it is (never blocks)."""
    _, draft = _version(db, user, script_id, slot, edit=True)
    row = _advice(draft)
    advice.keep(row, body.problem)
    draft.breakdown_kept = row.kept
    db.commit()
    return _out(db, draft)


@router.delete("/keep", response_model=PreviewOut)
def unkeep_advice(
    script_id: int,
    slot: Slot,
    problem: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Undo Keep anyway (?problem=, the text as shown)."""
    _, draft = _version(db, user, script_id, slot, edit=True)
    row = _advice(draft)
    advice.unkeep(row, problem)
    draft.breakdown_kept = row.kept
    db.commit()
    return _out(db, draft)


@router.post("/fix-cast", response_model=PreviewOut)
def fix_plan_cast(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Put the right cast in each shot of the version's plan (free, no model call). Undo
    saves the old plan back with PUT."""
    from app import cast_roles

    script, draft = _version(db, user, script_id, slot, edit=True)
    if not draft.breakdown:
        raise HTTPException(404, "This version has no plan yet.")
    old = Breakdown.model_validate(draft.breakdown)
    project = script_preview.stand_in_project(db, script, draft)
    fixed = cast_roles.fix(db, project, draft.text, old)
    if fixed is None:
        raise HTTPException(409, "Every shot already has the right cast.")
    kept_text = draft.breakdown_text
    script_preview.save(db, draft, fixed, user.id, kept_text)  # still the words it was planned from
    db.commit()
    out = _out(db, draft)
    out.changed_shots = cast_roles.changed_shots(old, fixed)
    return out


class FixIn(BaseModel):
    problems: list[str] = []  # the problems as shown; empty: every one with a fix


@router.post("/fix", response_model=PreviewOut)
def fix_plan(
    script_id: int,
    slot: Slot,
    body: FixIn | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Fix the version's plan for free (spec one-click-fixes.md §1), as for a video's
    breakdown. Undo saves the old plan back with PUT."""
    from app import breakdown

    _, draft = _version(db, user, script_id, slot, edit=True)
    if not draft.breakdown:
        raise HTTPException(404, "This version has no plan yet.")
    text = draft.breakdown_text if draft.breakdown_text is not None else draft.text
    every = [f["problem"] for f in breakdown_fix.fixes(draft.breakdown_problems or [])]
    m = breakdown.video_model()
    fixed, done = breakdown_fix.repair(
        text, Breakdown.model_validate(draft.breakdown), (body.problems if body else []) or every,
        m.duration.min, m.duration.max,
    )  # fmt: skip
    if not done:
        raise HTTPException(409, "Nothing here can be fixed for you. Edit the shot instead.")
    script_preview.save(db, draft, fixed, user.id, draft.breakdown_text)
    db.commit()
    out = _out(db, draft)
    out.fixed = done
    return out
