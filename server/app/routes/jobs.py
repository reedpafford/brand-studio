"""Jobs as the team sees them (status, output, no money) and usage with dollars (owner only)."""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, object_session

from app.auth import current_user, owner_only, user_name
from app.credits import (
    USD_PER_CREDIT,
    check_clip_cap,
    check_video_cap,
    estimate,
    lock,
    needs_approval,
    over_allowance,
    own_script,
)
from app.db import get_db, utcnow
from app.job_brand import brand_for
from app.models.accounts import User
from app.models.jobs import Job, JobStatus, Usage
from app.models.projects import Project, ProjectStatus

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
    # Safe summary of what was asked, for history lists (from the job's input).
    prompt_summary: str = ""
    step: str | None = None  # script-flow step: enhance, script_draft, breakdown, …
    frame_id: int | None = None  # storyboard frame a still render is for
    project_clip_id: int | None = None  # project clip a take is for
    library_item_id: int | None = None  # character or place a sheet is for
    script_id: int | None = None  # library script a writing, variations or cast step is for
    script_draft_id: int | None = None  # library version a breakdown preview is for
    model_id: str | None = None
    brand_id: int | None = None
    duration: int | None = None
    aspect_ratio: str | None = None
    resolution: str | None = None
    created_by_id: int | None = None  # who asked (for the owner's Approvals list)
    created_by_name: str = ""

    @model_validator(mode="before")
    @classmethod
    def _summary(cls, job):
        if not isinstance(job, Job):
            return job
        data = {
            f: getattr(job, f)
            for f in (
                "id",
                "kind",
                "project_id",
                "credits",
                "status",
                "output",
                "error",
                "created_at",
                "finished_at",
            )
        }
        extra = {
            f: getattr(job, f)
            for f in ("provider", "provider_ref", "error_detail", "approved_by_id")
            if hasattr(job, f)
        }
        db = object_session(job)
        given = job.input.get("input") or {}
        prompt = _prompt(job)
        return {
            **data,
            **extra,
            "prompt_summary": prompt if len(prompt) <= 140 else prompt[:139] + "…",
            "step": job.input.get("step"),
            "frame_id": job.input.get("frame_id"),
            "project_clip_id": job.input.get("project_clip_id"),
            "library_item_id": job.input.get("library_item_id"),
            "script_id": job.input.get("script_id"),
            "script_draft_id": job.input.get("script_draft_id"),
            "model_id": job.input.get("model"),
            "brand_id": job.input.get("brand_id"),
            **{k: given.get(k) for k in ("duration", "aspect_ratio", "resolution")},
            "created_by_id": job.created_by_id,
            "created_by_name": user_name(db, job.created_by_id) if db else "",
            **({"cost_usd": _usd(db, job)} if "cost_usd" in cls.model_fields and db else {}),
        }


def _usd(db: Session, job: Job) -> float:
    spent = db.scalar(select(func.sum(Usage.cost_usd)).where(Usage.job_id == job.id))
    return round(float(spent if spent is not None else job.credits * USD_PER_CREDIT), 4)


class JobDetailOut(JobOut):
    """Owner-only: includes the provider's raw error text and the cost in dollars (what was
    spent once it ran; until then, what its credits are worth)."""

    approved_by_id: int | None
    provider: str
    provider_ref: str | None
    error_detail: str
    cost_usd: float = 0.0


class UsageOut(BaseModel):
    id: int
    job_id: int
    provider: str
    kind: str
    units: Decimal
    unit: str
    cost_usd: Decimal
    estimated: bool
    created_at: datetime


OVER_BUDGET = "That's more than this video's budget."


def enqueue(
    db: Session,
    user: User,
    kind: str,
    input: dict,
    *,
    units: Decimal | int = 1,
    project: Project | None = None,
    provider: str = "fake",
    prepaid: bool = False,
) -> Job:
    """Queue a job for the worker. Feature code calls this; there is no public create route.
    `units` is the expected amount (e.g. seconds of video) used to estimate credits. An
    editor's own work (outside a project, or on a video from their own script) past their
    weekly allowance is declined (409), and so is an editor's job that would take a library
    version over its budget (409, no Ask Reed). Jobs in a project still waiting for approval
    wait as `needs_owner_approval`. The
    check and the reservation are one locked transaction. `prepaid`: a later step of work the
    editor already pressed for at its full price (the reel read chain), so the allowance isn't
    checked again; caps, brand, credits and Usage stay as for any job."""
    credits = estimate(db, user.workspace_id, kind, Decimal(units), input)
    if project is not None:
        lock(db, Project, project.id)
        db.refresh(project)  # read its status after taking the lock
        if project.archived_at is not None:
            raise HTTPException(409, "This video is archived. Bring it back to work on it.")
        check_video_cap(db, user, project, credits)
        if own_script(db, project, user):
            lock(db, User, user.id)  # it spends their weekly allowance, like a Quick clip
    else:
        lock(db, User, user.id)
        check_clip_cap(db, user, credits)
    # Free work (e.g. getting a reel) never takes anyone past their allowance.
    if credits and not prepaid and (declined := over_allowance(db, user, project, credits)):
        db.rollback()
        raise HTTPException(409, declined)
    over = needs_approval(db, user, project, credits)
    if over and project.status == ProjectStatus.active:  # Reed, 2026-10-26: no Ask Reed
        db.rollback()
        raise HTTPException(409, OVER_BUDGET)
    job = Job(
        workspace_id=user.workspace_id,
        created_by_id=user.id,
        kind=kind,
        provider=provider,
        input=input,
        project_id=project.id if project else None,
        brand_id=brand_for(db, project, input),
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
    q: str = "",  # in what was asked (the prompt)
    removed: bool = False,  # true: the Quick clips taken off the history, to bring back
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    gone = Job.removed_at.is_not(None)
    query = select(Job).where(Job.workspace_id == user.workspace_id, gone if removed else ~gone)
    if status:
        query = query.where(Job.status == status)
    if not q.strip():
        return db.scalars(query.order_by(Job.id.desc()).limit(200)).all()
    words = q.strip().lower()
    found = db.scalars(query.order_by(Job.id.desc()).limit(SEARCHED)).all()
    return [j for j in found if words in _prompt(j).lower()][:200]


SEARCHED = 2000  # the newest jobs a search looks through
FINISHED = (JobStatus.succeeded, JobStatus.failed, JobStatus.cancelled)


def _prompt(job: Job) -> str:
    """What was asked: the person's own words, not the [ImageN] lines added for the model."""
    given = job.input.get("input") or {}
    return str((job.input.get("request") or given).get("prompt", ""))


def _quick_clip(db: Session, user: User, job_id: int, removed: bool) -> Job:
    """A finished Quick clip of the caller's (the owner: anyone's). Video steps and paid work
    still going can't be taken off the history."""
    job = _get_job(db, user, job_id)
    if (job.removed_at is not None) != removed:
        raise HTTPException(404, "No such clip in the history.")
    if not (user.is_owner or job.created_by_id == user.id):
        raise HTTPException(403, "Only whoever made it, or the owner, can do that.")
    if job.project_id is not None or not job.kind.startswith(("video", "image")):
        raise HTTPException(409, "Only Quick clips can be removed from the history.")
    if job.status not in FINISHED:
        raise HTTPException(409, "Wait for it to finish first.")
    return job


@router.delete("/jobs/{job_id}", status_code=204)
def remove_from_history(
    job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    """Take a Quick clip off the history, undoably. Its credits still count."""
    _quick_clip(db, user, job_id, removed=False).removed_at = utcnow()
    db.commit()


@router.post("/jobs/{job_id}/restore", response_model=JobOut)
def restore_to_history(
    job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Undo a remove: the clip is back in the history."""
    job = _quick_clip(db, user, job_id, removed=True)
    job.removed_at = None
    db.commit()
    return job


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
    if job.project_id is not None and job.status == JobStatus.needs_owner_approval:
        project = db.get(Project, job.project_id)
        lock(db, Project, project.id)
        check_video_cap(db, owner, project, job.credits)  # not even the owner goes past it
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
