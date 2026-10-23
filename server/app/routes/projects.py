"""Projects and their credit budget. Editors set a planned length; the budget is 2x the 480p
estimate of it. Above the owner's length limit a project waits for the owner.
Editors see credits and % of budget, never dollars."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth import current_user, owner_only
from app.credits import credits_used, get_limits, lock
from app.db import get_db
from app.models.accounts import User
from app.models.jobs import Job, JobStatus
from app.models.library import Kind
from app.models.projects import Project, ProjectStatus
from app.routes.brands import get_brand
from app.routes.files import get_file
from app.routes.library import get_item
from app.schemas import LongText, Name, ShortText

router = APIRouter(prefix="/projects", tags=["credits"])


ASPECTS = Literal["9:16", "1:1", "16:9", "4:3", "3:4", "21:9"]


class BriefPatch(BaseModel):
    """The brief. On PATCH, send only what changes."""

    goal: LongText | None = None
    platform: ShortText | None = None
    aspect_ratio: ASPECTS | None = None
    format: ShortText | None = None
    cast_ids: list[int] | None = None  # library characters
    reference_file_id: int | None = None  # a video


class ProjectIn(BriefPatch):
    brand_id: int
    name: Name
    planned_seconds: int = Field(gt=0, le=3600)


class ProjectPatch(BriefPatch):
    name: Name | None = None
    planned_seconds: int | None = Field(None, gt=0, le=3600)


class ProjectOut(BaseModel):
    id: int
    brand_id: int
    name: str
    planned_seconds: int
    status: ProjectStatus
    goal: str
    platform: str
    aspect_ratio: str
    format: str
    cast_ids: list[int]
    reference_file_id: int | None
    estimate_credits: float
    budget_credits: float
    credits_used: float
    budget_pct: float


def get_project(db: Session, user: User, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project or project.workspace_id != user.workspace_id:
        raise HTTPException(404, "No such project.")
    return project


def _out(db: Session, project: Project) -> ProjectOut:
    used = credits_used(db, project)
    return ProjectOut(
        id=project.id,
        brand_id=project.brand_id,
        name=project.name,
        planned_seconds=project.planned_seconds,
        status=project.status,
        **{f: getattr(project, f) for f in BRIEF_FIELDS},
        estimate_credits=project.estimate_credits,
        budget_credits=project.budget_credits,
        credits_used=used,
        budget_pct=round(float(used / project.budget_credits * 100), 1),
    )


BRIEF_FIELDS = tuple(BriefPatch.model_fields)


def _set_brief(db: Session, user: User, project: Project, values: dict) -> None:
    """Apply sent brief fields. Cast must be the workspace's characters; the reference a video.
    A null `reference_file_id` removes it; any other null means "unchanged"."""
    for field in BRIEF_FIELDS:
        if field not in values or (values[field] is None and field != "reference_file_id"):
            continue
        value = values[field]
        if field == "cast_ids":
            value = sorted(set(value))
            for item_id in value:
                get_item(db, user, Kind.character, item_id)
        elif field == "reference_file_id" and value is not None:
            get_file(db, user, value, "video")
        setattr(project, field, value)


def _set_length(db: Session, user: User, project: Project, seconds: int) -> None:
    project.planned_seconds = seconds
    if user.is_owner:
        project.status, project.approved_by_id = ProjectStatus.active, user.id
    elif seconds > get_limits(db, user.workspace_id).max_planned_seconds:
        project.status = ProjectStatus.needs_owner_approval


@router.get("", response_model=list[ProjectOut])
def list_projects(
    brand_id: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    query = select(Project).where(Project.workspace_id == user.workspace_id)
    if brand_id is not None:
        query = query.where(Project.brand_id == brand_id)
    return [_out(db, p) for p in db.scalars(query.order_by(func.lower(Project.name)))]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    body: ProjectIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    get_brand(db, user, body.brand_id)
    project = Project(workspace_id=user.workspace_id, brand_id=body.brand_id, name=body.name)
    _set_length(db, user, project, body.planned_seconds)
    _set_brief(db, user, project, body.model_dump())
    db.add(project)
    db.commit()
    return _out(db, project)


@router.get("/{project_id}", response_model=ProjectOut)
def read_project(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return _out(db, get_project(db, user, project_id))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    body: ProjectPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    project = get_project(db, user, project_id)
    if body.name is not None:
        project.name = body.name
    if body.planned_seconds is not None:
        _set_length(db, user, project, body.planned_seconds)
    _set_brief(db, user, project, body.model_dump(exclude_unset=True))
    db.commit()
    return _out(db, project)


@router.post("/{project_id}/approve", response_model=ProjectOut)
def approve_project(
    project_id: int, owner: User = Depends(owner_only), db: Session = Depends(get_db)
):
    project = get_project(db, owner, project_id)
    done = db.execute(
        update(Project)
        .where(Project.id == project.id, Project.status == ProjectStatus.needs_owner_approval)
        .values(status=ProjectStatus.active, approved_by_id=owner.id)
    )
    if done.rowcount != 1:
        raise HTTPException(409, "This project isn't waiting for approval.")
    db.refresh(project)
    _release_held_jobs(db, owner, project)
    db.commit()
    return _out(db, project)


def _release_held_jobs(db: Session, owner: User, project: Project) -> None:
    """Approving a project also releases the jobs held in it, oldest first, while they fit
    in its budget. Any that don't fit stay held for a separate decision."""
    lock(db, Project, project.id)
    used = credits_used(db, project)
    held = db.scalars(
        select(Job)
        .where(Job.project_id == project.id, Job.status == JobStatus.needs_owner_approval)
        .order_by(Job.id)
    )
    for job in held:
        if used + job.credits <= project.budget_credits:
            job.status, job.approved_by_id = JobStatus.queued, owner.id
            used += job.credits
