"""Jobs as the team sees them (status, output, no money) and usage with dollars (owner only)."""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth import current_user, owner_only
from app.credits import estimate, lock, needs_approval
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.credits import Project
from app.models.jobs import Job, JobStatus, Usage

router = APIRouter(tags=["jobs"])


class JobOut(BaseModel):
    id: int
    kind: str
    project_id: int | None
    credits: float
    status: JobStatus
    output: dict | None
    error: str
    created_at: datetime
    finished_at: datetime | None


class JobDetailOut(JobOut):
    """Owner-only: includes the provider's raw error text."""

    approved_by_id: int | None
    provider: str
    provider_ref: str | None
    error_detail: str


class UsageOut(BaseModel):
    id: int
    job_id: int
    provider: str
    kind: str
    units: Decimal
    unit: str
    cost_usd: Decimal
    created_at: datetime


def enqueue(
    db: Session,
    user: User,
    kind: str,
    input: dict,
    *,
    units: Decimal | int = 1,
    project: Project | None = None,
    provider: str = "fake",
) -> Job:
    """Queue a job for the worker. Feature code calls this; there is no public create route.
    `units` is the expected amount (e.g. seconds of video) used to estimate credits. A job
    that would take its project over budget, sits in a project still waiting for approval,
    or (outside a project) goes past the editor's weekly quick-clip allowance waits as
    `needs_owner_approval`. The check and the reservation are one locked transaction."""
    credits = estimate(db, user.workspace_id, kind, Decimal(units))
    if project is not None:
        lock(db, Project, project.id)
        db.refresh(project)  # read its status after taking the lock
    else:
        lock(db, User, user.id)
    over = needs_approval(db, user, project, credits)
    job = Job(
        workspace_id=user.workspace_id,
        created_by_id=user.id,
        kind=kind,
        provider=provider,
        input=input,
        project_id=project.id if project else None,
        credits=credits,
        status=JobStatus.needs_owner_approval if over else JobStatus.queued,
        approved_by_id=user.id if user.is_owner else None,  # the owner's own jobs need no ask
    )
    db.add(job)
    db.commit()
    return job


def _get_job(db: Session, user: User, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if not job or job.workspace_id != user.workspace_id:
        raise HTTPException(404, "No such job.")
    return job


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    status: JobStatus | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    query = select(Job).where(Job.workspace_id == user.workspace_id)
    if status:
        query = query.where(Job.status == status)
    return db.scalars(query.order_by(Job.id.desc()).limit(200)).all()


@router.get("/jobs/{job_id}", response_model=JobOut)
def read_job(job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _get_job(db, user, job_id)


@router.get("/jobs/{job_id}/detail", response_model=JobDetailOut)
def read_job_detail(job_id: int, owner: User = Depends(owner_only), db: Session = Depends(get_db)):
    return _get_job(db, owner, job_id)


@router.post("/jobs/{job_id}/approve", response_model=JobOut)
def approve_job(job_id: int, owner: User = Depends(owner_only), db: Session = Depends(get_db)):
    """Owner lets a job that goes over its project budget run."""
    job = _get_job(db, owner, job_id)
    done = db.execute(
        update(Job)
        .where(Job.id == job.id, Job.status == JobStatus.needs_owner_approval)
        .values(status=JobStatus.queued, approved_by_id=owner.id)
    )
    if done.rowcount != 1:
        raise HTTPException(409, "This job isn't waiting for approval.")
    db.commit()
    db.refresh(job)
    return job


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Only jobs that haven't started (queued or waiting for approval) can be cancelled."""
    job = _get_job(db, user, job_id)
    done = db.execute(  # conditional, so it can't race the worker picking the job up
        update(Job)
        .where(
            Job.id == job.id,
            Job.status.in_((JobStatus.queued, JobStatus.needs_owner_approval)),
        )
        .values(status=JobStatus.cancelled, finished_at=utcnow())
    )
    if done.rowcount != 1:
        raise HTTPException(409, "This job has already started.")
    db.commit()
    db.refresh(job)
    return job


@router.get("/usage", response_model=list[UsageOut])
def list_usage(owner: User = Depends(owner_only), db: Session = Depends(get_db)):
    return db.scalars(
        select(Usage)
        .where(Usage.workspace_id == owner.workspace_id)
        .order_by(Usage.id.desc())
        .limit(500)
    ).all()
