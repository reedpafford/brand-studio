"""Credit maths: estimates from rates, real cost to credits, budgets and allowances.

Reserving: a job's estimated credits are written on the job when it is queued, in the same
transaction as the check, with the project (or, for quick clips, the editor) row locked.
Failed and cancelled jobs stop counting; on success the real cost replaces the estimate."""

import logging
import math
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.catalogue import get_model
from app.db import utcnow
from app.models.accounts import User
from app.models.credits import (
    BUDGET_MULTIPLIER,
    DEFAULT_PER_VIDEO_MAX_CREDITS,
    DEFAULT_WEEKLY_QUICK_CLIP_CREDITS,
    USD_PER_CREDIT,
    CreditLimits,
    CreditRate,
)
from app.models.jobs import Job, JobStatus
from app.models.projects import Project, ProjectStatus

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
OTHER_RATES = [
    ("write-claude", "call", Decimal(3)),  # Opus script/breakdown call, ~$0.30
    ("check-claude", "call", Decimal("0.2")),  # a low-effort look at one picture, ~$0.01-0.02
    ("music", "call", Decimal(1)),  # a Suno request (2 songs): assumed until Suno prices it
]


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


CLIP_SECONDS_GUESS = 8  # before a breakdown exists: about this many seconds per clip


def plan_cost(db: Session, ws: int, seconds: int, bd, roles: int, breakdown=True,
              video=None) -> Decimal:  # fmt: skip
    """What making a video costs, every step, not just its seconds (QA-Live, video #17:
    "About 55" quoted, 99 charged): the breakdown (`breakdown`), the frame prompts, a still
    per clip, the clip prompts (a Claude call per few clips), a look per role (`roles`) and
    its seconds of video. `bd` is its Breakdown, if it has one; `video` its models (VS1),
    else Auto. Redos aren't counted."""
    from app import clip_prompts
    from app.breakdown import video_model
    from app.sheets import look_usual
    from app.storyboard import image_model, still_credits

    clips = len(bd.clips) if bd else math.ceil(seconds / CLIP_SECONDS_GUESS)
    calls = len(clip_prompts.batches(bd)) if bd else math.ceil(clips / clip_prompts.BATCH_CLIPS)
    claude = estimate(db, ws, "write-claude", Decimal(1)) * (int(breakdown) + 1 + calls)
    clip = {"model": video_model(video).id, "input": {"resolution": "480p"}}
    return (claude + clips * still_credits(db, ws, image_model(video)) + look_usual(db, ws) * roles
            + estimate(db, ws, "video", Decimal(seconds), clip))  # fmt: skip


def budget(db: Session, project: Project) -> Decimal:
    """Twice the video's whole estimate (rule 3): every step at its plan, so the steps before
    its takes never use up the budget (QA-2: a 12 s video's fixed steps came to 12.73 of a
    24-credit budget, and its 12-credit take was refused). A look for each role its script
    doesn't lock, made or not, so the budget never drops as Assets makes them, and never below
    its guess before a breakdown (a plan with fewer clips than guessed). Never above the
    per-video cap, so editors are never shown more than can be spent (QA on #679)."""
    from app import clip_prompts
    from app.cast_roles import all_slots
    from app.prompts.schemas import Breakdown

    row = clip_prompts.newest(db, project)
    bd = Breakdown.model_validate(row.data) if row else None
    roles = sum(s.library_item_id is None for s in all_slots(db, project))
    ws, seconds = project.workspace_id, int(project.estimate_credits)
    cost = max(plan_cost(db, ws, seconds, bd, roles), plan_cost(db, ws, seconds, None, roles))
    return min(cost * BUDGET_MULTIPLIER, Decimal(get_limits(db, ws).per_video_max_credits))


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


def is_quick_clip(kind: str, input: dict, project) -> bool:
    """A Quick clip: a video or picture asked for outside any video, not a step of other work
    (a sheet, a frame). The only thing the weekly allowance counts (Reed, 30 Oct): anything in
    a script or video belongs to a brand and is work."""
    return project is None and kind.startswith(("video", "image")) and "step" not in input


def someone_elses_quick_clip(user: User, job: Job) -> bool:
    """Another editor's Quick clip: theirs alone (Reed's item 4), so to this user it reads as
    not there at all. The owner sees everyone's; a video's or script's steps are the team's."""
    mine = user.is_owner or job.created_by_id == user.id
    return not mine and is_quick_clip(job.kind, job.input, job.project_id)


def week_jobs(user: User) -> tuple:
    """This person's Quick clips this week (Mon-Sun, UTC), as `is_quick_clip` says. The
    allowance and the cost log's week both read through this, so they never drift."""
    return (
        Job.project_id.is_(None),
        or_(Job.kind.startswith("video"), Job.kind.startswith("image")),
        Job.input["step"].as_string().is_(None),
        Job.created_by_id == user.id,
        Job.created_at >= week_start(),
    )


def quick_clip_used(db: Session, user: User) -> Decimal:
    """This week's credits on this person's Quick clips (`week_jobs`)."""
    return _sum_credits(db, *week_jobs(user))


def credits_left(db: Session, user: User) -> Decimal | None:
    """An editor's weekly allowance left (can be below 0); None for the owner (unlimited)."""
    if user.is_owner:
        return None
    return get_limits(db, user.workspace_id).weekly_quick_clip_credits - quick_clip_used(db, user)


def price(total: Decimal) -> int:
    """A price as a button or a refusal says it: rounded up, so it's never below the charge."""
    return max(1, math.ceil(total))


def fits(db: Session, project: Project, user: User, total: Decimal) -> str:
    """Why `total` more credits on this video would go over, or "" when it fits: the
    per-video limit (for everyone), else the video's budget (the owner's too: work made by
    itself stays within it)."""
    cap = get_limits(db, project.workspace_id).per_video_max_credits
    if credits_used(db, project) + total > cap:
        return "would go over this video's limit."
    if credits_used(db, project) + total <= project.budget_credits:
        return ""
    return "would go over this video's budget."


def over_allowance(db: Session, user: User, credits: Decimal) -> str:
    """Plain words if this Quick clip would take an editor past their weekly allowance, else
    "". Past it, it's declined, never sent to the owner. Call with the row locked."""
    if user.is_owner:
        return ""
    allowance = get_limits(db, user.workspace_id).weekly_quick_clip_credits
    used = quick_clip_used(db, user)
    if used + credits <= allowance:
        return ""
    n = f"{allowance:.0f}"
    plural = "" if n == "1" else "s"  # "1 credit", never "1 credits"
    if used >= allowance:  # the screens' words (useScript.ts weekStop)
        return f"You've used this week's {n} credit{plural}. It resets on Monday."
    return (
        f"That's more than this week's {n} credit{plural} ({used:.0f} used). It resets on Monday."
    )


def lock(db: Session, model, row_id: int) -> None:
    """Hold a row until commit (a no-op UPDATE: locks the row on Postgres, the database on
    SQLite), so two jobs can't both pass the check on the last credits."""
    db.execute(update(model).where(model.id == row_id).values(id=model.id))


def needs_approval(db: Session, user: User, project: Project | None, credits: Decimal) -> bool:
    """True if an editor's job on a video would go over its budget (from their own script
    too, since one allowance: Reed, 30 Oct); `enqueue` then declines it with the reason,
    never holds it. A Quick clip goes by `over_allowance` instead. Call with the row locked."""
    if user.is_owner or project is None:
        return False
    if project.status != ProjectStatus.active:
        return True
    return credits_used(db, project) + credits > project.budget_credits


def test_budget_fits(db: Session, provider: str, budget_usd: float, credits: Decimal) -> bool:
    """A real lane on the test site (look samples, language tests; Reed, 2026-10-29): whether
    a press of `credits` still fits its budget. A job counts once sent, whatever happens to
    it after; a finished one at its real cost."""
    jobs = db.scalars(select(Job).where(Job.provider == provider))
    spent = sum(j.credits for j in jobs if j.status != JobStatus.cancelled or j.provider_ref)
    return (spent + credits) * USD_PER_CREDIT <= Decimal(str(budget_usd))
