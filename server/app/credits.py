"""Credit maths: estimates from rates, real cost to credits, budgets and allowances.

Reserving: a job's estimated credits are written on the job when it is queued, in the same
transaction as the check, with the project (or, for quick clips, the editor) row locked.
Failed and cancelled jobs stop counting; on success the real cost replaces the estimate."""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.catalogue import get_model
from app.db import utcnow
from app.models.accounts import User
from app.models.credits import (
    BUDGET_MULTIPLIER,
    DEFAULT_WEEKLY_QUICK_CLIP_CREDITS,
    USD_PER_CREDIT,
    CreditLimits,
    CreditRate,
)
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.providers import STAND_IN

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
              video=None, look=None, kind=None) -> Decimal:  # fmt: skip
    """What making a video costs, every step, not just its seconds (QA-Live, video #17:
    "About 55" quoted, 99 charged): the breakdown (`breakdown`), the frame prompts, a still
    per clip, the clip prompts (a Claude call per few clips), a look per role (`roles`) and
    its seconds of video. `bd` is its Breakdown, if it has one; `video` its models (VS1),
    else its `look` and script `kind` say which (`breakdown.video_model`). Redos aren't counted."""
    from app import clip_prompts, take_watch
    from app.breakdown import video_model
    from app.sheets import look_usual
    from app.storyboard import image_model, still_credits

    clips = len(bd.clips) if bd else math.ceil(seconds / CLIP_SECONDS_GUESS)
    calls = len(clip_prompts.batches(bd)) if bd else math.ceil(clips / clip_prompts.BATCH_CLIPS)
    claude = estimate(db, ws, "write-claude", Decimal(1)) * (int(breakdown) + 1 + calls)
    m = video_model(video, look, kind)
    clip = {"model": m.id, "input": {"resolution": m.take_resolution}}
    checks = clips * take_watch.per_take(db, ws)  # a watch of a take a clip, while on
    return (claude + clips * still_credits(db, ws, image_model(video)) + look_usual(db, ws) * roles
            + estimate(db, ws, "video", Decimal(seconds), clip) + checks)  # fmt: skip


def approved(db: Session, fs) -> Decimal:
    """What a freestyle's OKs cover: each send's quoted price ("price" on its message), but
    for one declined or withdrawn (nothing ran). A freestyle from before prices were kept on
    its messages: its `up_to`."""
    priced = [m for m in fs.chat if "price" in m]
    if not priced:
        return fs.up_to or Decimal(0)
    jobs = {j.id: j for j in db.scalars(select(Job).where(Job.id.in_([m["job"] for m in priced])))}
    total = Decimal(0)
    for m in priced:
        job = jobs.get(m["job"])
        refused = job is not None and job.status == JobStatus.cancelled and (
            job.input.get("declined") or job.input.get("withdrawn"))  # fmt: skip
        if not refused:
            total += Decimal(str(m["price"]))
    return total


def budget(db: Session, project: Project) -> Decimal:
    """Twice the video's whole estimate (rule 3): every step at its plan, so the steps before
    its takes never use up the budget (QA-2: a 12 s video's fixed steps came to 12.73 of a
    24-credit budget, and its 12-credit take was refused). A look for each role its script
    doesn't lock, made or not, so the budget never drops as Assets makes them, and never below
    its guess before a breakdown (a plan with fewer clips than guessed). There is no cap above
    it (Reed, 2026-11-03)."""
    from app import clip_prompts
    from app.cast_roles import all_slots
    from app.prompts.schemas import Breakdown

    if project.hidden:  # a freestyle's video: the owner's OK covers the price shown, no more
        from app.models.freestyles import Freestyle

        fs = db.scalar(select(Freestyle).where(Freestyle.project_id == project.id))
        if fs is not None and fs.up_to is not None:
            return approved(db, fs)
    row = clip_prompts.newest(db, project)
    bd = Breakdown.model_validate(row.data) if row else None
    roles = sum(s.library_item_id is None for s in all_slots(db, project))
    ws, seconds = project.workspace_id, int(project.estimate_credits)
    cost = max(
        plan_cost(db, ws, seconds, bd, roles, video=project),
        plan_cost(db, ws, seconds, None, roles, video=project),
    )
    return cost * BUDGET_MULTIPLIER


def usd_to_credits(usd: Decimal) -> Decimal:
    return (Decimal(usd) / USD_PER_CREDIT).quantize(Decimal("0.001"))


def get_limits(db: Session, workspace_id: int) -> CreditLimits:
    """The workspace's saved limits, or the defaults (not saved) if the owner hasn't set any."""
    return db.scalar(
        select(CreditLimits).where(CreditLimits.workspace_id == workspace_id)
    ) or CreditLimits(
        workspace_id=workspace_id,
        weekly_quick_clip_credits=DEFAULT_WEEKLY_QUICK_CLIP_CREDITS,
    )


def _sum_credits(db: Session, *where) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(Job.credits), 0)).where(Job.status.in_(COUNTED), *where)
    )
    return Decimal(total)


def credits_used(db: Session, project: Project) -> Decimal:
    return _sum_credits(db, Job.project_id == project.id)


def director_credits(db: Session, project: Project) -> Decimal:
    """The director's own spend on this video: every job of a run (its turns and its watches
    of the cut, as `director.spent` counts them), on its own limit (DECISIONS #1066), so the
    budget, its hold and the owner's release leave it out."""
    return _sum_credits(
        db, Job.project_id == project.id, Job.input["director_run"].as_string().is_not(None)
    )


def budget_used(db: Session, project: Project) -> Decimal:
    """What counts against the video's budget: all of it but the director's own turns. The
    hold and the owner's release both read this, so they always agree. A freestyle's video
    counts everything, its director's turns too: the owner's OK covers its whole price."""
    if project.hidden:  # its plan before Make it is on its own allowance (asks.planned)
        return credits_used(db, project) - _sum_credits(
            db, Job.project_id == project.id, Job.input["before_ok"].as_boolean()
        )
    return credits_used(db, project) - director_credits(db, project)


def week_start() -> datetime:
    now = utcnow()
    return (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


FREESTYLE = "freestyle_id"  # in a freestyle's job's input: its freestyle


def is_quick_clip(kind: str, input: dict, project) -> bool:
    """A Quick clip: a video or picture asked for outside any video, not a step of other work
    (a sheet, a frame). The only thing the weekly allowance counts (Reed, 30 Oct): anything in
    a script or video belongs to a brand and is work."""
    plain = "step" not in input and FREESTYLE not in input  # Reed OKs each freestyle send
    return project is None and kind.startswith(("video", "image")) and plain


def someone_elses_quick_clip(user: User, job: Job) -> bool:
    """Another editor's Quick clip: theirs alone (Reed's item 4), so to this user it reads as
    not there at all. The owner sees everyone's; a video's or script's steps are the team's.
    A freestyle's takes are its maker's too."""
    mine = user.is_owner or job.created_by_id == user.id
    theirs = is_quick_clip(job.kind, job.input, job.project_id) or FREESTYLE in job.input
    return not mine and theirs


def week_jobs(user: User) -> tuple:
    """This person's Quick clips this week (Mon-Sun, UTC), as `is_quick_clip` says. The
    allowance and the cost log's week both read through this, so they never drift."""
    return (
        Job.project_id.is_(None),
        or_(Job.kind.startswith("video"), Job.kind.startswith("image")),
        Job.input["step"].as_string().is_(None),
        Job.input[FREESTYLE].as_integer().is_(None),
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


def uncapped(user: User | None) -> bool:
    """The owner's own work, on a site with BS_OWNER_UNCAPPED (Reed, 6 Nov): no monetary hold
    at all. Never an editor's, and nowhere the setting is off."""
    from app.settings import get_settings

    return bool(user is not None and user.is_owner and get_settings().owner_uncapped)


def never_billed(job: Job) -> bool:
    """A job its provider refused (a content or copyright check, e.g. Replicate's E005), or
    whose request it refused as invalid before running it (a 400 or 422, video 245): nothing was
    charged, so it counts $0 in what was really spent (cost analysis X1). Every other failure
    that was sent still counts: it may have been billed."""
    from app.clip_takes import why_failed

    return job.status == JobStatus.failed and why_failed(job) in ("refused", "invalid")


@dataclass
class Spent:
    """A video's (or a run's) spend at its providers, as the owner's uncapped site shows it."""

    usd: Decimal  # every charge: as the provider reported it, else at its list price
    listed: Decimal  # of it, counted at list price (the provider gave no figure)
    pending: bool  # a job still running: its cost isn't reported yet

    def words(self, where: str) -> str:
        """ "$5.00 spent on this run, $4.00 of it at list price, more not reported yet"."""
        said = f"${self.usd:.2f} spent {where}"
        said += f", ${self.listed:.2f} of it at list price" if self.listed else ""
        return said + (", more not reported yet" if self.pending else "")


def actual_usd(db: Session, project_id: int, since=None, until=None) -> Spent:
    """What this video's jobs from `since` (to `until`) cost at their providers: each job's
    Usage (Claude's planning, directing, reviews and watches, the media and voices, billable
    failures and retries), its estimated rows counted at list price; a job sent with no Usage
    row (a dropped connection, as `real_spent` counts it) at its own price; a job still
    running isn't reported yet."""
    from app.models.jobs import Usage

    window = [Job.project_id == project_id]
    window += [Job.created_at >= since] if since is not None else []
    window += [Job.created_at <= until] if until is not None else []
    from sqlalchemy.orm import defer

    # its rows without their inputs and outputs (a turn's holds its whole prompt: video 240)
    jobs = db.scalars(select(Job).where(*window).options(defer(Job.input), defer(Job.output))).all()
    rows: dict[int, list] = {}
    for u in db.scalars(select(Usage).where(Usage.job_id.in_([j.id for j in jobs] or [0]))):
        rows.setdefault(u.job_id, []).append(u)
    usd = listed = Decimal(0)
    pending = False
    for j in jobs:
        if mine := rows.get(j.id):
            usd += sum((Decimal(u.cost_usd) for u in mine), Decimal(0))
            listed += sum((Decimal(u.cost_usd) for u in mine if u.estimated), Decimal(0))
        elif j.status == JobStatus.running:
            pending = True
        elif (j.provider_ref and not j.provider_ref.startswith(STAND_IN)
              and j.provider not in FREE_LANES and not never_billed(j)):  # fmt: skip
            usd += j.credits * USD_PER_CREDIT
            listed += j.credits * USD_PER_CREDIT
    return Spent(usd.quantize(Decimal("0.01")), listed.quantize(Decimal("0.01")), pending)


def fits(db: Session, project: Project, user: User, total: Decimal) -> str:
    """Why `total` more credits on this video would go over, or "" when it fits its budget
    (the owner's too: work made by itself stays within it, unless `uncapped`)."""
    if uncapped(user):
        return ""
    if budget_used(db, project) + total <= project.budget_credits:  # as the hold counts it
        return ""
    return "would go over this video's budget."


WAIT_OK = "Waiting for the owner's OK: "  # a held press says why it waits, never "ask Reed"
PAST_APPROVED = f"{WAIT_OK}this goes past the price approved."  # a freestyle's next step


def past_approved(db: Session, project: Project, user: User, credits: Decimal) -> str:
    """A run's step its Make it doesn't cover: PAST_APPROVED, and it waits for the owner on a
    card, the owner's own run too (rule 34; Reed, 4 Nov: anything beyond the authorized budget
    needs the owner's OK); a freestyle's past the prices its sends were approved at; else "".
    Never for the owner's own work when `uncapped`, but for a run the owner's priced press
    started (`director.priced`: its "up to" holds there too)."""
    from app.director import priced

    if uncapped(user) and not priced(db, project):
        return ""
    if _over_freestyle(db, project, user, credits):
        return PAST_APPROVED
    return PAST_APPROVED if past_price(db, project, user, credits) else ""


def past_price(db: Session, project: Project, user: User, credits: Decimal) -> bool:
    """Whether a step of `credits` is held because it goes past its run's own approved price
    (rule 34: `asks.past_run`), not a freestyle's whole budget: its card speaks in the run's
    figures."""
    from app import asks
    from app.director import priced

    return ((not uncapped(user) or priced(db, project))
            and not _over_freestyle(db, project, user, credits)
            and asks.past_run(db, project, credits))  # fmt: skip


def _over_freestyle(db: Session, project: Project, user: User, credits: Decimal) -> bool:
    """An editor's step past a hidden freestyle's whole budget."""
    return (project.hidden and not user.is_owner
            and budget_used(db, project) + credits > budget(db, project))  # fmt: skip


def over_allowance(db: Session, user: User, credits: Decimal) -> str:
    """Plain words if this Quick clip would take an editor past their weekly allowance, else
    "". Past it, the clip waits for the owner (`enqueue`). Call with the row locked."""
    if user.is_owner:
        return ""
    allowance = get_limits(db, user.workspace_id).weekly_quick_clip_credits
    used = quick_clip_used(db, user)
    if used + credits <= allowance:
        return ""
    n = f"{allowance:.0f}"
    plural = "" if n == "1" else "s"  # "1 credit", never "1 credits"
    return f"{WAIT_OK}this goes past your week's {n} credit{plural} ({used:.0f} used)."


def lock(db: Session, model, row_id: int) -> None:
    """Hold a row until commit (a no-op UPDATE: locks the row on Postgres, the database on
    SQLite), so two jobs can't both pass the check on the last credits."""
    db.execute(update(model).where(model.id == row_id).values(id=model.id))


def needs_approval(db: Session, user: User, project: Project | None, credits: Decimal) -> bool:
    """True if an editor's job on a video would go over its budget; `enqueue` then holds it
    for the owner (Reed, 30 Oct). A Quick clip goes by `over_allowance` instead. Call with
    the row locked."""
    if user.is_owner or project is None:
        return False
    used = budget_used(db, project)  # the director's turns have their own limit
    return used + credits > project.budget_credits


FREE_LANES = ("fake", "local")  # our own server and the tests' fake: never a paid call
REAL_DONE = "The test site's real-AI budget (${:.2f}) is used up. Nothing was charged."
NO_START = "The test site's real-AI budget: start time not set. Nothing was charged."


def real_capped(settings) -> bool:
    """The test site on real providers (Reed's test): every paid call counts against one
    budget, BS_REAL_BUDGET_USD. Live is never capped here; the stand-ins cost nothing."""
    return settings.env == "next" and not settings.fake_providers


def real_spent(db: Session, settings) -> Decimal:
    """What real calls sent since `real_budget_since` came to, at their credits (the price we
    charge, above the real cost: it errs safe). A job counts once sent, whatever after; a
    stand-in's never does (the dry run counted them)."""
    from app.models.jobs import Usage

    sent = [Job.provider.not_in(FREE_LANES), Job.provider_ref.is_not(None),  # sent
            Job.provider_ref.not_like(f"{STAND_IN}%")]  # to a real provider  # fmt: skip
    if settings.real_budget_since:
        sent.append(Job.started_at >= settings.real_budget_since)
    total = Decimal(db.scalar(select(func.coalesce(func.sum(Job.credits), 0)).where(*sent)))
    # Claude's charge is capped at its shown price, but its real cost can be more (the audit):
    # where the recorded real cost is above it, that's what counts.
    claude = (select(Job.credits, func.coalesce(func.sum(Usage.cost_usd), 0))
              .outerjoin(Usage, Usage.job_id == Job.id).where(*sent, Job.provider == "claude")
              .group_by(Job.id, Job.credits))  # fmt: skip
    over = sum((max(Decimal(0), Decimal(usd) - credits * USD_PER_CREDIT)
                for credits, usd in db.execute(claude)), Decimal(0))  # fmt: skip
    return total * USD_PER_CREDIT + over


def real_budget_refusal(db: Session, settings, provider: str, credits: Decimal,
                        owner: bool = False) -> str:  # fmt: skip
    """The plain refusal when a paid call of `credits` would take the test site's real spend
    past its budget (and on the test site with no budget or start time set, any paid call: the
    test site deploys many times an hour, so the count never restarts by itself); else "".
    The owner's own call with `owner_uncapped` and no budget set (0) is never stopped."""
    if provider in FREE_LANES or not real_capped(settings):
        return ""
    if owner and settings.owner_uncapped and not settings.real_budget_usd > 0:
        return ""
    budget = Decimal(str(settings.real_budget_usd))
    if not settings.real_budget_since:  # not set up: nothing paid runs
        return NO_START
    if not budget > 0:
        return REAL_DONE.format(budget)
    if real_spent(db, settings) + credits * USD_PER_CREDIT <= budget:
        return ""
    return REAL_DONE.format(budget)


def test_budget_fits(db: Session, provider: str, budget_usd: float, credits: Decimal) -> bool:
    """A real lane on the test site (look samples, language tests; Reed, 2026-10-29): whether
    a press of `credits` still fits its budget. A job counts once sent, whatever happens to
    it after; a finished one at its real cost."""
    jobs = db.scalars(select(Job).where(Job.provider == provider))
    spent = sum(j.credits for j in jobs if j.status != JobStatus.cancelled or j.provider_ref)
    return (spent + credits) * USD_PER_CREDIT <= Decimal(str(budget_usd))
