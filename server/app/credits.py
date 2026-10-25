"""Credit maths: estimates from rates, real cost to credits, budgets and allowances.

Reserving: a job's estimated credits are written on the job when it is queued, in the same
transaction as the check, with the project (or, for quick clips, the editor) row locked.
Failed and cancelled jobs stop counting; on success the real cost replaces the estimate."""

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.catalogue import get_model
from app.db import utcnow
from app.models.accounts import User
from app.models.credits import (
    DEFAULT_PER_VIDEO_MAX_CREDITS,
    DEFAULT_WEEKLY_QUICK_CLIP_CREDITS,
    USD_PER_CREDIT,
    CreditLimits,
    CreditRate,
)
from app.models.jobs import Job, JobStatus
from app.models.projects import Project, ProjectStatus
from app.models.script_library import Script, ScriptDraft

log = logging.getLogger(__name__)
# Estimates only; real cost decides the final credits. Generation rates come from the
# catalogue's default models so the two can't drift; a Claude call is a typical-call guess.
CATALOGUE_RATES = [  # (rate kind, unit, catalogue model, resolution)
    ("video-480p", "second", "seedance-2.5", "480p"),
    ("video-720p", "second", "seedance-2.5", "720p"),
    ("image-nano-banana-2.1", "image", "nano-banana-2.1", "1K"),
    ("image-nano-banana-pro", "image", "nano-banana-pro", "1K"),
    ("watch-gemini", "call", "gemini-3.5-flash", None),
]
OTHER_RATES = [("write-claude", "call", Decimal(3))]  # Opus script/breakdown call, ~$0.30


def launch_rates() -> list[tuple[str, str, Decimal]]:
    from_catalogue = [
        (kind, unit, get_model(model).credits_per_unit(res))
        for kind, unit, model, res in CATALOGUE_RATES
    ]
    return from_catalogue + OTHER_RATES


FALLBACK_RATE = Decimal(1)  # kinds without a rate are still allowed; estimated at 1/unit
COUNTED = (JobStatus.queued, JobStatus.running, JobStatus.succeeded)


def seed_rates(db: Session, workspace_id: int) -> None:
    for kind, unit, rate in launch_rates():
        if not get_rate(db, workspace_id, kind):
            db.add(
                CreditRate(workspace_id=workspace_id, kind=kind, unit=unit, credits_per_unit=rate)
            )
    db.commit()


def get_rate(db: Session, workspace_id: int, kind: str) -> CreditRate | None:
    return db.scalar(
        select(CreditRate).where(CreditRate.workspace_id == workspace_id, CreditRate.kind == kind)
    )


def estimate(
    db: Session, workspace_id: int, kind: str, units: Decimal, input: dict | None = None
) -> Decimal:
    """Catalogue models (input names a "model") are priced from the catalogue; other job
    kinds from the rates table. Nothing to do (0 units, e.g. free reel prep) costs nothing."""
    if not units:
        return Decimal(0)
    model = get_model((input or {}).get("model", ""))
    if model:
        resolution = (input.get("input") or {}).get("resolution")
        try:
            return Decimal(units) * model.credits_per_unit(resolution)
        except ValueError:  # resolution left to the model: assume the dearest
            return Decimal(units) * max(model.credits_per_unit(r) for r in model.price.usd)
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
        weekly_quick_clip_credits=DEFAULT_WEEKLY_QUICK_CLIP_CREDITS,
        per_video_max_credits=DEFAULT_PER_VIDEO_MAX_CREDITS,
    )


def over_cap(user: User, cap: int) -> HTTPException:
    """The per-video hard limit. The owner sees dollars; editors never do."""
    if user.is_owner:
        dollars = (cap * USD_PER_CREDIT).quantize(Decimal(1))
        return HTTPException(409, f"This video would go over its ${dollars} limit.")
    return HTTPException(409, "This video would go over its limit.")


def check_clip_cap(db: Session, user: User, credits: Decimal) -> None:
    """A single job outside a project (a quick clip) is one video too: same hard cap."""
    cap = get_limits(db, user.workspace_id).per_video_max_credits
    if credits > cap:
        raise over_cap(user, cap)


def check_video_cap(db: Session, user: User, project: Project, credits: Decimal) -> None:
    """Refuse (for everyone) a job that would take the project past the per-video maximum.
    Call with the project row locked."""
    cap = get_limits(db, project.workspace_id).per_video_max_credits
    if credits_used(db, project) + credits > cap:
        raise over_cap(user, cap)


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


def own_script(db: Session, project: Project, user: User) -> bool:
    """A video this editor makes from a script they wrote: it runs on their weekly allowance,
    not a budget the owner approves (Reed, 2026-10-25). Someone else's script is not theirs."""
    if user.is_owner or project.script_draft_id is None:
        return False
    author = db.scalar(
        select(Script.created_by_id)
        .join(ScriptDraft)
        .where(ScriptDraft.id == project.script_draft_id)
    )
    return author == user.id


def quick_clip_used(db: Session, user: User) -> Decimal:
    """This week's (Mon-Sun, UTC) credits on this person's own work: jobs outside any
    project (Quick clips, script steps) and on videos from scripts they wrote."""
    own = (
        select(Project.id)
        .join(ScriptDraft, ScriptDraft.id == Project.script_draft_id)
        .join(Script, Script.id == ScriptDraft.script_id)
        .where(Script.created_by_id == user.id)
    )
    return _sum_credits(
        db,
        or_(Job.project_id.is_(None), Job.project_id.in_(own)),
        Job.created_by_id == user.id,
        Job.created_at >= week_start(),
    )


def credits_left(db: Session, user: User) -> Decimal | None:
    """An editor's weekly allowance left (can be below 0); None for the owner (unlimited)."""
    if user.is_owner:
        return None
    return get_limits(db, user.workspace_id).weekly_quick_clip_credits - quick_clip_used(db, user)


def over_allowance(db: Session, user: User, project: Project | None, credits: Decimal) -> str:
    """Plain words if this job would take an editor past their weekly allowance, else "".
    Past it, their own work is declined, never sent to the owner. Call with the row locked."""
    if user.is_owner or (project is not None and not own_script(db, project, user)):
        return ""
    allowance = get_limits(db, user.workspace_id).weekly_quick_clip_credits
    if quick_clip_used(db, user) + credits > allowance:
        return f"You've used this week's {allowance:.0f} credits. It resets Monday."
    return ""


def lock(db: Session, model, row_id: int) -> None:
    """Hold a row until commit (a no-op UPDATE: locks the row on Postgres, the database on
    SQLite), so two jobs can't both pass the check on the last credits."""
    db.execute(update(model).where(model.id == row_id).values(id=model.id))


def needs_approval(db: Session, user: User, project: Project | None, credits: Decimal) -> bool:
    """True if a new job must wait for the owner: an editor's job on a video from the owner's
    scripts (or an older project) that would go over its budget. An editor's own work is
    never held: `over_allowance` declines it instead. Call with the right row locked."""
    if user.is_owner or project is None or own_script(db, project, user):
        return False
    if project.status != ProjectStatus.active:
        return True
    return credits_used(db, project) + credits > project.budget_credits
