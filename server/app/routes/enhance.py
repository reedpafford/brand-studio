"""Enhance the working script: ask Claude for marks, accept/reject each, apply the accepted
ones as a new version. Claude never rewrites the script."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_db
from app.enhance import apply, job_input
from app.models.accounts import User
from app.models.jobs import Job, JobStatus
from app.models.scripts import Suggestion
from app.routes.clips import generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.projects import get_project
from app.routes.scripts import ScriptOut, _out, latest, save_version

router = APIRouter(prefix="/projects/{project_id}/script", tags=["scripts"])


class SuggestionOut(BaseModel):
    id: int
    key: str
    kind: str
    line: int
    quote: str
    start: int
    end: int
    placement: str
    text: str
    screen_id: int | None
    reason: str
    status: str


class NoteOut(BaseModel):
    line: int
    text: str


class ApplyOut(BaseModel):
    script: ScriptOut


def _working(db: Session, user: User, project_id: int):
    project = get_project(db, user, project_id)
    version = latest(db, project)
    if not version:
        raise HTTPException(409, "Add a script first.")
    return project, version


@router.post(
    "/enhance", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)]
)
def enhance(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Queue an Enhance call (a paid Claude call, counted against the project budget)."""
    project, version = _working(db, user, project_id)
    waiting = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)
    pending = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(waiting)))
    if any(
        j.input.get("step") == "enhance" and j.input["script_version"] == version.version
        for j in pending
    ):
        raise HTTPException(409, "Enhance is already working on this script.")
    return enqueue(
        db,
        user,
        "write-claude",
        job_input(db, project, version),
        project=project,
        provider="claude",
    )


@router.get("/suggestions", response_model=list[SuggestionOut])
def list_suggestions(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Marks on the working (newest) script version, in script order."""
    project, version = _working(db, user, project_id)
    return db.scalars(
        select(Suggestion)
        .where(Suggestion.project_id == project.id, Suggestion.script_version == version.version)
        .order_by(Suggestion.start, Suggestion.id)
    ).all()


@router.get("/notes", response_model=list[NoteOut])
def list_notes(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Claude's notes on the words of the working version (newest Enhance), for information:
    only the editor changes the words."""
    project, version = _working(db, user, project_id)
    jobs = db.scalars(
        select(Job)
        .where(Job.project_id == project.id, Job.status == JobStatus.succeeded)
        .order_by(Job.id.desc())
    )
    for job in jobs:
        if job.input.get("step") == "enhance" and job.input["script_version"] == version.version:
            return (job.output or {}).get("notes", [])
    return []


def _decide(db: Session, user: User, project_id: int, suggestion_id: int, status: str):
    project, version = _working(db, user, project_id)
    mark = db.get(Suggestion, suggestion_id)
    if not mark or mark.project_id != project.id:
        raise HTTPException(404, "No such suggestion.")
    if mark.script_version != version.version:
        raise HTTPException(409, "The script changed since this suggestion. Enhance again.")
    mark.status = status
    db.commit()
    return mark


@router.post("/suggestions/{suggestion_id}/accept", response_model=SuggestionOut)
def accept(
    project_id: int,
    suggestion_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return _decide(db, user, project_id, suggestion_id, "accepted")


@router.post("/suggestions/{suggestion_id}/reject", response_model=SuggestionOut)
def reject(
    project_id: int,
    suggestion_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return _decide(db, user, project_id, suggestion_id, "rejected")


@router.post("/apply", response_model=ApplyOut)
def apply_accepted(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Apply the accepted marks to the working script, saved as a new version."""
    project, version = _working(db, user, project_id)
    marks = db.scalars(
        select(Suggestion).where(
            Suggestion.project_id == project.id,
            Suggestion.script_version == version.version,
            Suggestion.status == "accepted",
        )
    ).all()
    if not marks:
        raise HTTPException(409, "Accept at least one suggestion first.")
    text = apply(version.text, list(marks))
    return ApplyOut(script=_out(save_version(db, user, project, text, "enhance")))
