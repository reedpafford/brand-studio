"""The project's breakdown: ask Claude for one from the working script, read the newest, or
save the editor's edited version. Each comes with the checks' problems in plain words."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import advice, breakdown
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job, JobStatus
from app.prompts.schemas import Breakdown
from app.routes.clips import generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.projects import get_project
from app.routes.scripts import latest

router = APIRouter(prefix="/projects/{project_id}/breakdown", tags=["breakdown"])
WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)


class BreakdownOut(BaseModel):
    id: int
    script_version: int
    source: str
    breakdown: Breakdown
    problems: list[str]
    kept: list[str]  # advice kept anyway (never blocks)
    stale: bool  # made for an older script version


def _out(row: BreakdownVersion, working: int) -> BreakdownOut:
    return BreakdownOut(
        id=row.id,
        script_version=row.script_version,
        source=row.source,
        breakdown=row.data,
        problems=row.problems,
        kept=row.kept or [],
        stale=row.script_version != working,
    )


def _working(db: Session, user: User, project_id: int):
    project = get_project(db, user, project_id)
    version = latest(db, project)
    if not version:
        raise HTTPException(409, "Add a script first.")
    return project, version


@router.post("", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)])
def make(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Queue a breakdown call (a paid Claude call, counted against the project budget)."""
    project, version = _working(db, user, project_id)
    pending = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING)))
    if any(j.input.get("step") == "breakdown" for j in pending):
        raise HTTPException(409, "A breakdown is already being made for this project.")
    return enqueue(
        db,
        user,
        "write-claude",
        breakdown.job_input(db, project, version),
        project=project,
        provider="claude",
    )


def _newest(db: Session, project) -> BreakdownVersion:
    row = db.scalar(
        select(BreakdownVersion)
        .where(BreakdownVersion.project_id == project.id)
        .order_by(BreakdownVersion.id.desc())
        .limit(1)
    )
    if not row:
        raise HTTPException(404, "This project has no breakdown yet.")
    return row


@router.get("", response_model=BreakdownOut)
def read(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project, version = _working(db, user, project_id)
    return _out(_newest(db, project), version.version)


@router.post("/keep", response_model=BreakdownOut)
def keep_advice(
    project_id: int,
    body: advice.KeepIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Keep anyway: this advice on the newest breakdown stays as it is (never blocks)."""
    project, version = _working(db, user, project_id)
    row = _newest(db, project)
    advice.keep(row, body.problem)
    db.commit()
    return _out(row, version.version)


@router.delete("/keep", response_model=BreakdownOut)
def unkeep_advice(
    project_id: int, problem: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Undo Keep anyway on the newest breakdown's advice (?problem=, the text as shown)."""
    project, version = _working(db, user, project_id)
    row = _newest(db, project)
    advice.unkeep(row, problem)
    db.commit()
    return _out(row, version.version)


@router.put("", response_model=BreakdownOut)
def save(
    project_id: int,
    body: Breakdown,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Save the editor's edited breakdown for the working script (a new row)."""
    project, version = _working(db, user, project_id)
    if unknown := breakdown.unknown_ids(db, project, body):
        raise HTTPException(422, f"{unknown[0]}. Pick from the project's cast, places and screens.")
    breakdown.record_length(project, body)
    row = BreakdownVersion(
        project_id=project.id,
        script_version=version.version,
        source="edit",
        data=body.model_dump(),
        problems=breakdown.problems(db, project, version.text, body),
        created_by_id=user.id,
    )
    db.add(row)
    db.commit()
    return _out(row, version.version)
