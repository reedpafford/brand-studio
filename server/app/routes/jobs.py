"""Jobs as the team sees them (status, output, no money) and usage with dollars (owner only)."""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth import current_user, owner_only
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.jobs import Job, JobStatus, Usage

router = APIRouter(tags=["jobs"])


class JobOut(BaseModel):
    id: int
    kind: str
    status: JobStatus
    output: dict | None
    error: str
    created_at: datetime
    finished_at: datetime | None


class UsageOut(BaseModel):
    id: int
    job_id: int
    provider: str
    kind: str
    units: Decimal
    unit: str
    cost_usd: Decimal
    created_at: datetime


def enqueue(db: Session, user: User, kind: str, input: dict, provider: str = "fake") -> Job:
    """Queue a job for the worker. Feature code calls this; there is no public create route."""
    job = Job(
        workspace_id=user.workspace_id,
        created_by_id=user.id,
        kind=kind,
        provider=provider,
        input=input,
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


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Only jobs that haven't started can be cancelled."""
    job = _get_job(db, user, job_id)
    done = db.execute(  # conditional, so it can't race the worker picking the job up
        update(Job)
        .where(Job.id == job.id, Job.status == JobStatus.queued)
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
