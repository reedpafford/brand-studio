"""Credit maths: estimates from rates, real cost to credits, budgets and allowances.

Reserving: a job's estimated credits are written on the job when it is queued, in the same
transaction as the check, with the project (or, for quick clips, the editor) row locked.
Failed and cancelled jobs stop counting; on success the real cost replaces the estimate."""

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models.accounts import User
from app.models.credits import (
    DEFAULT_MAX_PLANNED_SECONDS,
    DEFAULT_WEEKLY_QUICK_CLIP_CREDITS,
    USD_PER_CREDIT,
    CreditLimits,
    CreditRate,
    Project,
    ProjectStatus,
)
from app.models.jobs import Job, JobStatus

log = logging.getLogger(__name__)
# Estimates only; real cost decides the final credits. Claude/Gemini are typical-call guesses.
LAUNCH_RATES = [
    ("video-480p", "second", Decimal(1)),
    ("video-720p", "second", Decimal("2.25")),
    ("image-nano-banana-2.1", "image", Decimal("0.3333")),
    ("image-nano-banana-pro", "image", Decimal("1.5")),
    ("write-claude", "call", Decimal(3)),  # Opus script/breakdown call, ~$0.30
    ("watch-gemini", "call", Decimal(1)),  # one watch pass, ~$0.10
]
FALLBACK_RATE = Decimal(1)  # kinds without a rate are still allowed; estimated at 1/unit
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


def estimate(db: Session, workspace_id: int, kind: str, units: Decimal) -> Decimal:
    rate = get_rate(db, workspace_id, kind)
    if not rate:
        log.warning("No credit rate for %s; estimating %s credit per unit.", kind, FALLBACK_RATE)
    return Decimal(units) * (rate.credits_per_unit if rate else FALLBACK_RATE)


def usd_to_credits(usd: Decimal) -> Decimal:
    return (Decimal(usd) / USD_PER_CREDIT).quantize(Decimal("0.001"))


def get_limits(db: Session, workspace_id: int) -> CreditLimits:
    """The workspace's saved limits, or the defaults (not saved) if the owner hasn't set any."""
    return db.scalar(
        select(CreditLimits).where(CreditLimits.workspace_id == workspace_id)
    ) or CreditLimits(
        workspace_id=workspace_id,
        max_planned_seconds=DEFAULT_MAX_PLANNED_SECONDS,
        weekly_quick_clip_credits=DEFAULT_WEEKLY_QUICK_CLIP_CREDITS,
    )


def _sum_credits(db: Session, *where) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(Job.credits), 0)).where(Job.status.in_(COUNTED), *where)
    )
    return Decimal(total)


def credits_used(db: Session, project: Project) -> Decimal:
    return _sum_credits(db, Job.project_id == project.id)


def week_start() -> datetime:
    now = utcnow()
    return (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def quick_clip_used(db: Session, user: User) -> Decimal:
    """This week's (Mon-Sun, UTC) credits on jobs outside any project, by this person."""
    return _sum_credits(
        db, Job.project_id.is_(None), Job.created_by_id == user.id, Job.created_at >= week_start()
    )


def lock(db: Session, model, row_id: int) -> None:
    """Hold a row until commit (a no-op UPDATE: locks the row on Postgres, the database on
    SQLite), so two jobs can't both pass the check on the last credits."""
    db.execute(update(model).where(model.id == row_id).values(id=model.id))


def needs_approval(db: Session, user: User, project: Project | None, credits: Decimal) -> bool:
    """True if a new job must wait for the owner. Call with the right row locked."""
    if user.is_owner:
        return False
    if project is not None:
        if project.status != ProjectStatus.active:
            return True
        return credits_used(db, project) + credits > project.budget_credits
    allowance = get_limits(db, user.workspace_id).weekly_quick_clip_credits
    return quick_clip_used(db, user) + credits > allowance
