"""Credit maths: rates per job kind, what a project has used, and the budget check."""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.credits import CreditRate, Project
from app.models.jobs import Job, JobStatus

# 1 credit = 1 s of 480p video. Other kinds' rates are set by the owner (PUT /credits/rates).
LAUNCH_RATES = [("video-480p", "second", Decimal(1))]
# Jobs whose credits count against a budget: done, or on their way.
COUNTED = (JobStatus.queued, JobStatus.running, JobStatus.succeeded)


def seed_rates(db: Session, workspace_id: int) -> None:
    for kind, unit, rate in LAUNCH_RATES:
        if not get_rate(db, workspace_id, kind):
            db.add(
                CreditRate(workspace_id=workspace_id, kind=kind, unit=unit, credits_per_unit=rate)
            )
    db.commit()


def get_rate(db: Session, workspace_id: int, kind: str) -> CreditRate | None:
    return db.scalar(
        select(CreditRate).where(CreditRate.workspace_id == workspace_id, CreditRate.kind == kind)
    )


def credits_for(db: Session, workspace_id: int, kind: str, units: Decimal) -> Decimal:
    """Credits for `units` of a job kind. Unpriced kinds are refused, so nothing runs free."""
    rate = get_rate(db, workspace_id, kind)
    if not rate:
        raise HTTPException(422, f"No credit rate for '{kind}' yet. Ask the owner to set one.")
    return Decimal(units) * rate.credits_per_unit


def credits_used(db: Session, project: Project) -> Decimal:
    used = db.scalar(
        select(func.coalesce(func.sum(Job.credits), 0)).where(
            Job.project_id == project.id, Job.status.in_(COUNTED)
        )
    )
    return Decimal(used)


def fits_budget(db: Session, project: Project, credits: Decimal) -> bool:
    return credits_used(db, project) + credits <= project.budget_credits
