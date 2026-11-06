"""Video ideas (v6 S0-01, S1, S-gaps-01): a brand's videos as the folder tree and an open
folder show them. Each has a status as a dot plus words and a short reason, its still,
style, length, maker, last activity and cost. Read-only and free: statuses take a fixed
handful of queries for any number of ideas; a page of cards adds its working ideas' budgets
and its not-started ideas' run prices (one page, at most 200). Everyone sees every idea in
the brand (S1-08); moving or archiving one is for whoever made it, or the owner."""

import math
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app import asks, director, guides, looks, needs_you
from app.credits import COUNTED
from app.models.accounts import User
from app.models.clips import ProjectClip
from app.models.credits import USD_PER_CREDIT
from app.models.freestyles import Freestyle
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.schemas import UtcTime

Kind = Literal["working", "needs_you", "waiting", "needs_fix", "delivered", "stopped", "archived"]
# The one place the status words live (S0-01's six, S-gaps-01's reasons, Reed 3 Nov: "yes to
# all"). The owner reads "waiting" as "Waiting for your OK" (S1-04).
WORDS = {"working": "Working", "needs_you": "Needs you", "waiting": "Waiting for the owner",
         "needs_fix": "Needs a fix", "delivered": "Delivered", "stopped": "Stopped",
         "archived": "Archived"}  # fmt: skip
YOUR_OK = "Waiting for your OK"
START = "Start it"  # nothing has run, or the treatment waits for Make it
CAST_OK = "Approve the cast and places"  # its run waits on that OK only (S7: never "Working")
AT = "Stopped at {}"  # a run that stopped on its own: an error or a limit
STEPS = {"breakdown": "the plan", "assets": "the cast", "storyboard": "the stills",
         "clips": "the clips", "downloads": "the cut"}  # fmt: skip
TABS = {"needs_you": ("needs_you", "needs_fix"), "working": ("working", "waiting"),
        "delivered": ("delivered",)}  # fmt: skip
Tab = Literal["all", "needs_you", "working", "delivered"]
Sort = Literal["newest", "oldest", "name"]  # Newest is the latest activity (S-gaps-01)


class Status(BaseModel):
    kind: Kind
    words: str  # "Needs you"
    reason: str | None = None  # "Check the scene plan", "14 of 24", "by Reed"
    at: UtcTime | None = None  # stopped or archived: when ("by Reed at 10:14", "Archived 28 Oct")
    made: int = 0  # working: clips with a take, of `total` (the card's bar)
    total: int = 0


class Cost(BaseModel):
    kind: Literal["up_to", "so_far", "total"]  # "up to $16.86" · "$0.42 so far" · "$7.20"
    credits: float
    usd: float | None = None  # the owner only: editors see credits (rule 4)


class Named(BaseModel):
    id: int
    name: str


class Idea(BaseModel):
    id: int
    title: str
    folder_id: int | None  # null: Unsorted
    status: Status
    still_file_id: int | None
    look: str
    style: str  # "Dr. Pickle"
    seconds: int | None  # null before a plan sets it
    made_by: Named | None
    created_at: UtcTime
    updated_at: UtcTime  # the latest activity
    cost: Cost | None  # None: nothing used and no price yet
    can_manage: bool  # move and archive: whoever made it, or the owner
    from_script: bool  # made from a script version; false: an earlier-style video (its own page)


@dataclass
class Facts:
    """What the statuses and cards read, for many videos at once."""

    last: dict[int, datetime] = field(default_factory=dict)
    used: dict[int, Decimal] = field(default_factory=dict)
    own: dict[int, Decimal] = field(default_factory=dict)  # the director's own (rule 34)
    held: dict[int, Decimal] = field(default_factory=dict)  # credits waiting for an OK
    busy: set[int] = field(default_factory=set)
    clips: dict[int, tuple[int, int]] = field(default_factory=dict)  # (made, total)


def facts(db: Session, projects: list[Project]) -> Facts:
    ids = [p.id for p in projects]
    out = Facts(last={p.id: p.created_at for p in projects})
    if not ids:
        return out
    hold, waiting = JobStatus.needs_owner_approval, (JobStatus.queued, JobStatus.running)
    rows = db.execute(select(
        Job.project_id, func.max(Job.created_at), func.max(Job.finished_at),
        func.coalesce(func.sum(case((Job.status.in_(COUNTED), Job.credits), else_=0)), 0),
        func.coalesce(func.sum(case((Job.status.in_(COUNTED) & Job.input[director.RUN]
                                     .as_string().is_not(None), Job.credits), else_=0)), 0),
        func.coalesce(func.sum(case((Job.status == hold, Job.credits), else_=0)), 0),
        func.sum(case((Job.status.in_(waiting), 1), else_=0)),
        func.sum(case((Job.status == hold, 1), else_=0)),
    ).where(Job.project_id.in_(ids)).group_by(Job.project_id))  # fmt: skip
    for pid, made, done, used, own, held, busy, holds in rows:
        out.last[pid] = max(t for t in (out.last[pid], made, done) if t is not None)
        out.used[pid], out.own[pid] = Decimal(used), Decimal(own)
        if holds:
            out.held[pid] = Decimal(held)
        if busy:
            out.busy.add(pid)
    for pid, total, made in db.execute(select(ProjectClip.project_id, func.count(),
                                              func.count(ProjectClip.picked_take_id))
                                       .where(ProjectClip.project_id.in_(ids))
                                       .group_by(ProjectClip.project_id)):  # fmt: skip
        out.clips[pid] = (made, total)
    return out


def _runs(db: Session, ids: list[int]) -> dict[int, dict]:
    """Each video's newest director run, by what its turns say: how it ended, who stopped it."""
    out: dict[int, dict] = {}
    rows = db.execute(select(Job.project_id, Job.input).where(
        Job.project_id.in_(ids), Job.input["step"].as_string() == director.STEP)
        .order_by(Job.id))  # fmt: skip
    for pid, data in rows:
        run = data[director.RUN]["id"]
        if out.get(pid, {}).get("run") != run:
            out[pid] = {"run": run}
        for key in ("ended", "result", "stopped_by", "stopped_at"):
            if data.get(key):
                out[pid][key] = data[key]
        out[pid]["last"] = data.get("result")  # its newest turn's (None while it's asked)
    return out


def _where(db: Session, job: Job | None, step: str, made: int, total: int) -> str:
    """Where a run stopped on its own, as "clip 4" or "the plan"."""
    if job is not None and job.input.get("step") == "clip_take":
        clip = db.get(ProjectClip, job.input.get("project_clip_id") or 0)
        if clip is not None:
            return director.named(clip.clip_id)
    if job is not None and (name := needs_you.NAMES.get(job.input.get("step", ""))):
        return name[0].lower() + name[1:]
    if 0 < total and made < total:
        return f"clip {made + 1}"
    return STEPS.get(step, "the plan")


def statuses(db: Session, user: User, projects: list[Project], known: Facts) -> dict[int, Status]:
    """Each video's status, first match wins: archived; a step held for an OK; a failed step;
    working; something waiting on a person; stopped by a person; a run that stopped on its own;
    delivered; else not started. An editor's own start card reads "Needs you · Start it" and
    a question from the director "Needs you" with the question (piece B), above working."""
    from app.auth import user_name
    from app.routes.production import progress
    from app.routes.project_clips import out_of_date

    ids = [p.id for p in projects]
    failed = needs_you.failures(db, ids)
    waits = needs_you.waiting_on(db, projects, out_of_date(db, projects))
    runs = _runs(db, ids)
    _, steps = progress(db, ids)
    asked, starts = asks.needing(db, ids), asks.starting(db, ids)
    out = {}
    for p in projects:
        made, total = known.clips.get(p.id, (0, 0))
        run = runs.get(p.id, {})
        if p.archived_at:
            s = Status(kind="archived", words=WORDS["archived"], at=p.archived_at)
        elif p.id in starts and not user.is_owner and asks.may_start(db, user, p):
            s = Status(kind="needs_you", words=WORDS["needs_you"], reason=START)
        elif p.id in known.held:
            s = Status(kind="waiting", words=YOUR_OK if user.is_owner else WORDS["waiting"])
        elif run.get("ended") == director.STOPPED:
            who = user_name(db, run.get("stopped_by"))
            s = Status(kind="stopped", words=WORDS["stopped"], reason=who and f"by {who}",
                       at=run.get("stopped_at"))  # fmt: skip
        elif p.id in failed:
            s = Status(
                kind="needs_fix",
                words=WORDS["needs_fix"],
                reason=AT.format(_where(db, failed[p.id], steps[p.id], made, total)),
            )
        elif run.get("last") == director.CAST_WAIT and not run.get("ended"):  # its run waits
            s = Status(kind="needs_you", words=WORDS["needs_you"], reason=CAST_OK)  # on the OK
        elif p.id in asked:  # the director's question waits (S-gaps-01 option 4)
            s = Status(kind="needs_you", words=WORDS["needs_you"], reason=asked[p.id])
        elif p.id in known.busy:
            s = Status(kind="working", words=WORDS["working"], made=made, total=total,
                       reason=f"{made} of {total}" if total else None)  # fmt: skip
        elif p.id in waits:
            s = Status(kind="needs_you", words=WORDS["needs_you"], reason=waits[p.id])
        elif run.get("ended") and run.get("result") != "Delivered.":  # its newest run, even
            # after an earlier one delivered (S7: never "Delivered" while the chat says stopped)
            s = Status(
                kind="needs_fix",
                words=WORDS["needs_fix"],
                reason=AT.format(_where(db, None, steps[p.id], made, total)),
            )
        elif p.finished_at:
            s = Status(kind="delivered", words=WORDS["delivered"])
        else:
            s = Status(kind="needs_you", words=WORDS["needs_you"], reason=START)
        out[p.id] = s
    return out


def _cost(db: Session, user: User, p: Project, status: Status, known: Facts) -> Cost | None:
    """Delivered: what it cost. Working: the most it can charge before another OK (its budget
    and the director's own limit, never below what it has used). Held: what it has spent (the
    held step says its own price where it's asked). Not started: its run's price. Else what it
    has used so far; None for an idea with nothing used and no price yet. Every figure before a
    charge is "up to" and rounded up (rule 36)."""
    from app.models.script_library import ScriptDraft
    from app.routes.estimate import run_price

    used = known.used.get(p.id, Decimal(0))
    kind, credits = "so_far", used
    if status.kind == "delivered":
        kind = "total"
    elif status.kind == "working":
        kind, credits = "up_to", _most(p, known)
    elif status.kind == "waiting":  # S1-04, S9-01: what it has spent
        kind = "total"
    elif status.reason == START and not used:
        if not p.script_draft_id:
            return None
        kind, credits = "up_to", run_price(db, db.get(ScriptDraft, p.script_draft_id), p)
    money = _money(user, credits, math.ceil if kind == "up_to" else round)
    return Cost(kind=kind, credits=money.credits, usd=money.usd)


def _most(p: Project, known: Facts) -> Decimal:
    """The most a working run may charge before another OK: its budget with the director's own
    limit beside it (rule 34), as budget_used reads it; never below what it has used."""
    used, own = known.used.get(p.id, Decimal(0)), known.own.get(p.id, Decimal(0))
    top = max(p.budget_credits, used if p.hidden else used - own)
    if not p.hidden:
        top += max(own, director.OWN_CREDITS)
    return max(used, top)


def _style(look: str) -> str:
    try:
        return looks.get(look)["name"]
    except HTTPException:  # a look since taken out of the guides
        return look


def titles(db: Session, ids: list[int]) -> dict[int, str]:
    """A freestyle's video by its freestyle's title (its own name carries " · freestyle N")."""
    rows = db.execute(select(Freestyle.project_id, Freestyle.title)
                      .where(Freestyle.project_id.in_(ids)))  # fmt: skip
    return dict(rows.all())


def cards(db: Session, user: User, projects: list[Project], known: Facts,
          shown: dict[int, Status]) -> list[Idea]:  # fmt: skip
    """The ideas as cards (and list rows), in the order given."""
    from app.auth import user_name
    from app.routes.production import progress

    ids = [p.id for p in projects]
    frames, _ = progress(db, ids)
    named = titles(db, ids)
    out = []
    for p in projects:
        status = shown[p.id]
        who = user_name(db, p.created_by_id)
        out.append(Idea(
            id=p.id, title=named.get(p.id, p.name), folder_id=p.live_folder_id, status=status,
            still_file_id=(frames.get(p.id) or (None, None))[1], look=p.look,
            style=_style(p.look), seconds=p.planned_seconds or p.breakdown_seconds,
            made_by=Named(id=p.created_by_id, name=who) if p.created_by_id and who else None,
            created_at=p.created_at, updated_at=known.last[p.id],
            cost=_cost(db, user, p, status, known),
            can_manage=user.is_owner or p.created_by_id == user.id,
            from_script=p.script_draft_id is not None))  # fmt: skip
    return out


class Money(BaseModel):
    credits: float
    usd: float | None = None  # the owner only: editors see credits (rule 4)


class Head(BaseModel):
    """One idea's header on its video page (S3, P-04, P-05): its status with the reason, what
    it has used, the most its run may charge, its budget, where it's filed and what it is."""

    title: str
    status: Status
    spent: Money  # every charge on the video so far, the director's own included
    up_to: Money | None  # the most the run the owner approved may charge; None: not known yet
    budget: Money  # the video's budget (a step past it waits for the owner's OK)
    folder: Named | None  # None: Unsorted
    format: str  # "Presenter"; "" for a video with no script
    style: str  # "Dr. Pickle"
    seconds: int | None  # null before a plan sets it
    song: bool  # the video has a song (the Song lock means something)
    # The owner's presses in the preview panel say dollars, as the boards draw them (rule 4:
    # editors see credits, so it's null for them). A press's dollars are rounded up.
    usd_per_credit: float | None = None


def _money(user: User, credits: Decimal, up=round) -> Money:
    usd = up(credits * USD_PER_CREDIT * 100) / 100 if user.is_owner else None
    return Money(credits=up(credits * 1000) / 1000, usd=usd)


def _up(credits: Decimal) -> Decimal:
    """An "up to" in credits, rounded up to the thousandth, as the run card and note keep it."""
    return Decimal(math.ceil(credits * 1000)) / 1000


def head(db: Session, user: User, p: Project) -> Head:
    """The header's facts for one video. The "up to" of a director video once approved (its
    freestyle's OKs or a Make it) is the run card's and the note's (`run_progress.spent`);
    else the budget with the director's own limit beside it, as a working card reads
    it (rule 34); before any run, its run's price. Never below what it has used, and rounded
    up (rule 36)."""
    from app import narration, run_progress
    from app.models.folders import Folder
    from app.script_library import format_id

    known = facts(db, [p])
    status = statuses(db, user, [p], known)[p.id]
    used = known.used.get(p.id, Decimal(0))
    fs = db.scalar(select(Freestyle).where(Freestyle.project_id == p.id))
    top: Decimal | None
    if (fs is not None and fs.up_to) or asks.approved_total(db, p) or status.reason == START:
        top = run_progress.spent(db, p)[1]  # one figure with the start, run card and note
    else:
        top = _most(p, known)
    script = narration.video_script(db, p)
    try:
        kind = guides.format_(format_id(script))["name"] if script else ""
    except ValueError:  # a format since taken out of the guides
        kind = ""
    folder = db.get(Folder, p.live_folder_id) if p.live_folder_id else None
    return Head(
        title=fs.title if fs is not None else p.name, status=status,
        spent=_money(user, used), budget=_money(user, Decimal(p.budget_credits)),
        up_to=None if top is None else _money(user, _up(max(top, used)), math.ceil),
        folder=Named(id=folder.id, name=folder.name) if folder else None,
        format=kind, style=_style(p.look), seconds=p.planned_seconds or p.breakdown_seconds,
        song=narration.video_kind(db, p) == "song",
        usd_per_credit=float(USD_PER_CREDIT) if user.is_owner else None,
    )  # fmt: skip
