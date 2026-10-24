"""Projects and their credit budget. Editors set a planned length; the budget is 2x the 480p
estimate of it. Above the owner's length limit a project waits for the owner.
Editors see credits and % of budget, never dollars."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import reference
from app.auth import current_user, owner_only, user_name
from app.credits import credits_used, get_limits, lock, over_cap
from app.db import get_db
from app.models.accounts import User
from app.models.brands import BrandScreen
from app.models.credits import BUDGET_MULTIPLIER
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
    product_variants: dict[str, str] | None = None  # product -> the variant this video shows
    reference_breakdown: dict | None = None  # the reel to adapt (docs/references shape)
    reference_replace: LongText | None = None  # which part to rebuild, e.g. "the montage"


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
    product_variants: dict[str, str]
    reference_breakdown: dict | None
    reference_replace: str
    estimate_credits: float
    budget_credits: float
    credits_used: float
    budget_pct: float
    created_by_id: int | None  # who asked (for the owner's Approvals list)
    created_by_name: str


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
        created_by_id=project.created_by_id,
        created_by_name=user_name(db, project.created_by_id),
    )


BRIEF_FIELDS = tuple(BriefPatch.model_fields)


def _set_brief(db: Session, user: User, project: Project, values: dict) -> None:
    """Apply sent brief fields. Cast must be the workspace's characters; the reference a video.
    A null reference file or breakdown removes it; any other null means "unchanged"."""
    removable = ("reference_file_id", "reference_breakdown")
    for field in BRIEF_FIELDS:
        if field not in values or (values[field] is None and field not in removable):
            continue
        value = values[field]
        if field == "cast_ids":
            value = sorted(set(value))
            for item_id in value:
                get_item(db, user, Kind.character, item_id)
        elif field == "reference_file_id" and value is not None:
            get_file(db, user, value, "video")
        elif field == "reference_breakdown" and value is not None:
            value = reference.checked(value)
        elif field == "product_variants":
            value = _check_variants(db, project.brand_id, value)
        setattr(project, field, value)


def _check_variants(db: Session, brand_id: int, chosen: dict[str, str]) -> dict[str, str]:
    """Each chosen variant must be one of the brand's versions of that product."""
    screens = db.scalars(select(BrandScreen).where(BrandScreen.brand_id == brand_id))
    offered: dict[str, set[str]] = {}
    for s in screens:
        if s.product and s.variant:
            offered.setdefault(s.product, set()).add(s.variant)
    for product, variant in chosen.items():
        if variant not in offered.get(product, set()):
            options = ", ".join(sorted(offered.get(product, []))) or "none"
            raise HTTPException(422, f"{product} comes in: {options}.")
    return chosen


def _set_length(db: Session, user: User, project: Project, seconds: int) -> None:
    limits = get_limits(db, user.workspace_id)
    if seconds * BUDGET_MULTIPLIER > limits.per_video_max_credits:  # budget = 2x 480p seconds
        longest = limits.per_video_max_credits // BUDGET_MULTIPLIER
        raise HTTPException(
            422,
            f"{over_cap(user, limits.per_video_max_credits).detail} "
            f"Plan {longest} seconds or less.",
        )
    project.planned_seconds = seconds
    if user.is_owner:
        project.status, project.approved_by_id = ProjectStatus.active, user.id


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
    project = Project(
        workspace_id=user.workspace_id,
        brand_id=body.brand_id,
        name=body.name,
        created_by_id=user.id,
    )
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
    ceiling = min(project.budget_credits, get_limits(db, owner.workspace_id).per_video_max_credits)
    for job in held:
        if used + job.credits <= ceiling:
            job.status, job.approved_by_id = JobStatus.queued, owner.id
            used += job.credits
