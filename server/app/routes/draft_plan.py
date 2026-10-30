"""The owner's scene plan on a script version (flows.md S6, 1b P1): made, edited and approved
like a video's, before the version is published. It is each new video's start: Make this
version copies an approved one into the video ("From Reed's plan"). Read only once published
(rule 31). Earlier plans are a video's own; a version keeps just the plan in hand."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import plans
from app import script_library as lib
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.routes.clips import generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.plan import NoteIn, PlanIn, PlanOut, _out, apply_edit
from app.routes.script_library import Slot

router = APIRouter(prefix="/scripts/{script_id}/drafts/{slot}/plan", tags=["plan"])


def _version(db: Session, user: User, script_id: int, slot: int, edit: bool):
    script = lib.get_script(db, user, script_id)
    if edit:
        lib.editable(user, script)  # the author or the owner, before publishing
    draft = lib.get_draft(db, script, slot)
    if edit and not draft.text.strip():
        raise HTTPException(409, "Write the script first.")
    return script, draft, plans.for_version(db, script, draft)


def _done(db: Session, user: User, draft, stand) -> PlanOut:
    plans.keep_version(draft, stand)
    db.commit()
    return _out(db, user, stand)


@router.get("", response_model=PlanOut)
def read(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """The version's plan, or 404 when it has none and none is being made."""
    _, _, stand = _version(db, user, script_id, slot, edit=False)
    out = _out(db, user, stand)
    if out is None:
        raise HTTPException(404, "This version has no plan yet.")
    return out


@router.post("", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)])
def make(
    script_id: int,
    slot: Slot,
    body: NoteIn | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Make the plan for this version: one paid call, from the author's own week."""
    script, draft, stand = _version(db, user, script_id, slot, edit=True)
    job = plans.latest_job(db, stand)
    if job and job.status in plans.WAITING:
        raise HTTPException(409, "A plan is already being made.")
    data = plans.job_input(db, stand, plans.script(db, stand), body.note if body else "")
    data = {**data, "project_id": None, "script_id": script.id, "script_draft_id": draft.id}
    return enqueue(db, user, plans.KIND, data, provider="claude")


@router.post("/stop", status_code=204)
def stop(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    _, _, stand = _version(db, user, script_id, slot, edit=True)
    plans.stop(db, stand)
    db.commit()


@router.post("/by-hand", response_model=PlanOut)
def by_hand(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    _, draft, stand = _version(db, user, script_id, slot, edit=True)
    plans.by_hand(db, stand, plans.script(db, stand))
    return _done(db, user, draft, stand)


@router.put("", response_model=PlanOut)
def edit(
    script_id: int,
    slot: Slot,
    body: PlanIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    _, draft, stand = _version(db, user, script_id, slot, edit=True)
    apply_edit(db, stand, plans.script(db, stand), body)
    return _done(db, user, draft, stand)


@router.post("/approve", response_model=PlanOut)
def approve(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """The owner's plan approved: its breakdown preview follows from it, and each new video
    of this version starts from it. Free (the preview is its own press)."""
    _, draft, stand = _version(db, user, script_id, slot, edit=True)
    plan = plans.current(db, stand)
    if plan is None:
        raise HTTPException(404, "This version has no plan yet.")
    used = [x["line"] for s in plan["scenes"] for x in s["lines"]]
    if used != plans.lines(db, stand, draft.text):
        raise HTTPException(409, "The script changed since this plan: make the plan again.")
    if any(not x["action"].strip() for s in plan["scenes"] for x in s["lines"]):
        raise HTTPException(409, "Give every line an action first.")
    plans.approve(stand, user.id)
    return _done(db, user, draft, stand)
