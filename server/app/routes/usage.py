"""Usage, the brand tracker (Reed only; DECISIONS #237): spend, finished videos and cost per
finished video per brand, for this week, this month or all time. Editors get 404, except
/usage/mine: their own videos in credits (OR4)."""

import csv
import io
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import folders, spend, usage
from app import script_library as lib
from app.auth import current_user
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.brands import Brand
from app.models.folders import Folder
from app.models.jobs import ChargeRefund, Job, Usage
from app.models.projects import Project
from app.models.script_library import Script
from app.routes.brands import get_brand
from app.routes.project_clips import out_of_date
from app.routes.script_library import ScriptRow
from app.routes.script_library import _out as library_row
from app.schemas import UtcTime

router = APIRouter(prefix="/usage", tags=["usage"])
PeriodName = Literal["week", "month", "all"]
# A calendar month picked ("2026-11", UTC): it wins over `period` (v5 month picker)
MONTH = r"^2\d{3}-(0[1-9]|1[0-2])$"  # 2000-2999: datetime never overflows
Month = Annotated[str | None, Query(pattern=MONTH)]


def _when(period: PeriodName, month: str | None) -> tuple[PeriodName, usage.Period]:
    if not month:
        return period, usage.period(period)
    try:
        return "month", usage.month(month)
    except ValueError:  # QA-10: never a 500 for a month out of range
        raise HTTPException(422, "Pick a month as YYYY-MM.") from None


SORTS = {
    "spend": lambda r: (-r.spend_usd, r.name.lower()),
    "finished": lambda r: (-r.finished, r.name.lower()),
    "cost": lambda r: (-(r.cost_per_finished_usd or -1), r.name.lower()),
    "activity": lambda r: (
        r.last_activity_at is None,
        -r.last_activity_at.timestamp() if r.last_activity_at else 0,
        r.name.lower(),
    ),
    "name": lambda r: (r.name.lower(), r.brand_id),
}


def owner_or_404(user: User = Depends(current_user)) -> User:
    if not user.is_owner:
        raise HTTPException(404, "Not found.")
    return user


class UsagePrevious(BaseModel):
    spend_usd: float
    finished: int
    cost_per_finished_usd: float | None


class Part(BaseModel):
    """One provider's (or one kind's) share of a figure, most first."""

    name: str  # "Replicate", "Claude", "MiniMax", …; "Takes", "Stills", "Claude's thinking", …
    usd: float
    estimated: bool  # some of it at list price: the provider didn't say


def parts(split: dict, order: list[str] | None = None) -> list[Part]:
    """A Split's providers or kinds as rows: most first, else in `order`."""
    rows = [Part(name=k, usd=usage.money(usd), estimated=bool(listed))
            for k, (usd, listed) in split.items()]  # fmt: skip
    if order:
        return sorted(rows, key=lambda p: order.index(p.name))
    return sorted(rows, key=lambda p: (-p.usd, p.name))


class FreestyleUsage(BaseModel):
    credits: float
    spend_usd: float
    videos: int  # finished in the period, plus being made now
    providers: list[Part] = []
    spend_estimated: bool = False  # some of it at list price


class UsageSummaryOut(BaseModel):
    period: PeriodName
    starts_at: UtcTime | None  # null for all time
    previous: UsagePrevious | None  # last week or last month; null for all time
    spend_usd: float  # every charge in the period, brands and not
    spend_estimated: bool  # some of it is an estimate (the provider didn't say)
    finished: int
    cost_per_finished_usd: float | None
    in_progress: int
    unassigned_spend_usd: float  # "Not tied to one brand"
    freestyle_spend_usd: float = 0  # Freestyle sends with no brand (its hidden brand)
    director_spend_usd: float = 0  # the director's own time: its turns, watches and looks
    spend_credits: float = 0  # every charge in the period, in credits
    unassigned_credits: float = 0  # "Other (no brand or video)", as unassigned_spend_usd
    freestyle: FreestyleUsage  # "Freestyle (no brand picked)": its own row
    providers: list[Part] = []  # every charge in the period, by provider (Reed, 9 Nov)
    unassigned_providers: list[Part] = []  # "Other (no brand or video)", by provider
    unassigned_estimated: bool = False  # some of "Other" at list price


class UsageBrandRow(BaseModel):
    brand_id: int
    name: str
    colour: str | None
    archived: bool
    spend_usd: float
    spend_estimated: bool
    finished: int
    cost_per_finished_usd: float | None
    in_progress: int
    scripts: int
    versions_left: int
    last_activity_at: UtcTime | None
    credits: float = 0  # charged in the period, in credits
    videos: int = 0  # finished in the period, plus being made now
    providers: list[Part] = []  # spend_usd by provider


class UsageBrandsOut(BaseModel):
    total: int
    next_cursor: str | None
    items: list[UsageBrandRow]


class UsageBrandOut(UsageBrandRow):
    previous: UsagePrevious | None
    editors_active: int  # people who made videos for it in the period


def _row(brand: Brand, f: usage.Figures) -> UsageBrandRow:
    b = brand.id
    spent = f.spent([b])
    return UsageBrandRow(
        brand_id=b,
        name=brand.name,
        colour=(brand.colours or [None])[0],
        archived=brand.archived,
        spend_usd=usage.money(spent.usd),
        spend_estimated=bool(spent.listed),
        providers=parts(spent.providers),
        finished=f.finished.get(b, 0),
        cost_per_finished_usd=f.cost_per(b),
        in_progress=f.in_progress.get(b, 0),
        scripts=f.scripts.get(b, 0),
        versions_left=f.versions_left.get(b, 0),
        last_activity_at=f.last_activity.get(b),
        credits=float(f.credits.get(b) or 0),
        videos=f.finished.get(b, 0) + f.in_progress.get(b, 0),
    )


def _before(db: Session, workspace_id: int, name: str, now: usage.Period, brand_id=...):
    """The same three figures for the period before (one brand, or everything)."""
    then = usage.previous(name, now)
    if then is None:
        return None
    f = usage.figures(db, workspace_id, then)
    if brand_id is ...:
        done = sum(f.finished.values())
        spent = sum(f.finished_spend.values())
        return UsagePrevious(
            spend_usd=usage.money(f.spent().usd),
            finished=done,
            cost_per_finished_usd=usage.money(spent / done) if done else None,
        )
    return UsagePrevious(
        spend_usd=usage.money(f.spent([brand_id]).usd),
        finished=f.finished.get(brand_id, 0),
        cost_per_finished_usd=f.cost_per(brand_id),
    )


@router.get("/summary", response_model=UsageSummaryOut)
def summary(
    period: PeriodName = "week",
    month: Month = None,
    owner: User = Depends(owner_or_404),
    db: Session = Depends(get_db),
):
    period, now = _when(period, month)
    f = usage.figures(db, owner.workspace_id, now)
    done, spent = sum(f.finished.values()), sum(f.finished_spend.values())
    free = _freestyle_brands(db, owner)
    every, freestyle, other = f.spent(), f.spent(free), f.spent([None])
    return UsageSummaryOut(
        spend_credits=float(sum(f.credits.values(), Decimal(0))),
        unassigned_credits=float(f.credits.get(None) or 0),
        freestyle=FreestyleUsage(
            credits=float(sum((f.credits.get(b) or 0 for b in free), Decimal(0))),
            spend_usd=usage.money(freestyle.usd),
            videos=_freestyle_videos(db, free, now),
            providers=parts(freestyle.providers),
            spend_estimated=bool(freestyle.listed),
        ),
        period=period,
        starts_at=now.start,
        previous=_before(db, owner.workspace_id, period, now),
        spend_usd=usage.money(every.usd),
        spend_estimated=bool(every.listed),
        finished=done,
        cost_per_finished_usd=usage.money(spent / done) if done else None,
        in_progress=sum(f.in_progress.values()),
        unassigned_spend_usd=usage.money(other.usd),
        freestyle_spend_usd=usage.money(freestyle.usd),
        director_spend_usd=usage.money(usage.director_spend(db, owner.workspace_id, now)),
        providers=parts(every.providers),
        unassigned_providers=parts(other.providers),
        unassigned_estimated=bool(other.listed),
    )


def _freestyle_videos(db: Session, brands: list[int], when: usage.Period) -> int:
    """Freestyle's videos, hidden from the brand figures: finished in the period, or not yet."""
    from app import hidden

    done = Project.finished_at.is_(None) | and_(true(), *when.has(Project.finished_at))
    found = select(func.count(Project.id)).where(Project.brand_id.in_(brands), done)
    return db.scalar(found.execution_options(**{hidden.SEE: True})) or 0


def _freestyle_brands(db: Session, owner: User) -> list[int]:
    """The workspace's hidden "Freestyle" brand (app/hidden.py), whose spend Usage shows apart."""
    from app import hidden

    query = select(Brand.id).where(Brand.workspace_id == owner.workspace_id, Brand.hidden)
    return list(db.scalars(query.execution_options(**{hidden.SEE: True})))


@router.get("/brands", response_model=UsageBrandsOut)
def brands(
    period: PeriodName = "week",
    month: Month = None,
    q: str = "",
    archived: bool = False,
    sort: Literal["spend", "finished", "cost", "activity", "name"] = "spend",
    cursor: str | None = None,
    limit: int = Query(25, ge=1, le=100),
    owner: User = Depends(owner_or_404),
    db: Session = Depends(get_db),
):
    """Every brand in the workspace, including new ones with nothing yet. Paged over brands;
    the figures are per brand, so the client never adds anything up."""
    query = select(Brand).where(Brand.workspace_id == owner.workspace_id)
    if not archived:
        query = query.where(Brand.archived.is_(False))
    if q.strip():
        query = query.where(Brand.name.ilike(f"%{q.strip()}%"))
    f = usage.figures(db, owner.workspace_id, _when(period, month)[1])
    rows = sorted((_row(b, f) for b in db.scalars(query)), key=SORTS[sort])
    # Archived first, so one just archived is never behind "Show more"; the sort holds in each.
    if archived:
        rows.sort(key=lambda r: not r.archived)
    start = int(cursor) if cursor and cursor.isdigit() else 0
    page = rows[start : start + limit]
    more = start + limit < len(rows)
    return UsageBrandsOut(
        total=len(rows), next_cursor=str(start + limit) if more else None, items=page
    )


@router.get("/brands/{brand_id}", response_model=UsageBrandOut)
def brand(
    brand_id: int,
    period: PeriodName = "week",
    month: Month = None,
    owner: User = Depends(owner_or_404),
    db: Session = Depends(get_db),
):
    found = db.get(Brand, brand_id)
    if not found or found.workspace_id != owner.workspace_id:
        raise HTTPException(404, "No such brand.")
    period, now = _when(period, month)
    row = _row(found, usage.figures(db, owner.workspace_id, now))
    return UsageBrandOut(
        **row.model_dump(),
        previous=_before(db, owner.workspace_id, period, now, brand_id),
        editors_active=usage.editors_active(db, brand_id, now),
    )


# --- Lists: a brand's videos and scripts, and every charge (spec items 6-8) ---


class PersonRow(BaseModel):
    user_id: int
    name: str
    role: Literal["owner", "editor"]
    credits: float  # charged in the period, every brand
    spend_usd: float  # the same in dollars (this page is the owner's only)
    videos: int  # videos of theirs finished in the period
    week_used: float  # this week, as the allowance counts it (My credits' week)
    week_allowance: float | None  # null for the owner (no weekly limit)


@router.get("/people", response_model=list[PersonRow])
def people(period: PeriodName = "week", month: Month = None,
           owner: User = Depends(owner_or_404), db: Session = Depends(get_db)):  # fmt: skip
    """v5 Usage › By person: what each person in the team spent in the period, most first.
    Everyone is listed, someone who spent nothing too."""
    from app.credits import COUNTED, get_limits, quick_clip_used

    when, ws = _when(period, month)[1], owner.workspace_id
    jobs = (Job.workspace_id == ws, Job.status.in_(COUNTED), *when.has(Job.created_at))
    credits = dict(db.execute(select(Job.created_by_id, func.sum(Job.credits)).where(*jobs)
                              .group_by(Job.created_by_id)).all())  # fmt: skip
    dollars: dict = {}  # as every other figure reads them (`spend.charges`)
    for c in spend.charges(db, Job.workspace_id == ws, usage_at=when.has(Usage.created_at),
                           job_at=when.has(Job.created_at))[0]:  # fmt: skip
        dollars[c.by] = dollars.get(c.by, Decimal(0)) + c.usd
    videos = dict(db.execute(select(Project.created_by_id, func.count()).where(
        Project.workspace_id == ws, Project.finished_at.is_not(None),
        *when.has(Project.finished_at)).group_by(Project.created_by_id)).all())  # fmt: skip
    allowance = float(get_limits(db, ws).weekly_quick_clip_credits)
    rows = []
    for person in db.scalars(select(User).where(User.workspace_id == ws)):
        if not person.active and person.id not in credits:
            continue  # someone removed who spent nothing in the period
        rows.append(PersonRow(
            user_id=person.id, name=person.name, role="owner" if person.is_owner else "editor",
            credits=float(credits.get(person.id) or 0),
            spend_usd=usage.money(dollars.get(person.id)), videos=videos.get(person.id, 0),
            week_used=float(quick_clip_used(db, person)),
            week_allowance=None if person.is_owner else allowance))  # fmt: skip
    return sorted(rows, key=lambda r: (-r.credits, r.name.lower()))


class Who(BaseModel):
    id: int
    name: str


def _who(db: Session, user_id: int | None) -> Who | None:
    found = db.get(User, user_id) if user_id else None  # the session caches each person
    return Who(id=found.id, name=found.name) if found else None


def _page(rows: list, cursor: str | None, limit: int) -> tuple[list, str | None]:
    start = int(cursor) if cursor and cursor.isdigit() else 0
    more = start + limit < len(rows)
    return rows[start : start + limit], str(start + limit) if more else None


def _brand(db: Session, owner: User, brand_id: int) -> Brand:
    found = db.get(Brand, brand_id)
    if not found or found.workspace_id != owner.workspace_id:
        raise HTTPException(404, "No such brand.")
    return found


class UsageVideo(BaseModel):
    project_id: int
    title: str  # "Bo tries salmon · B", or the video's own name
    script_id: int | None
    version_letter: str | None
    legacy: bool  # made before scripts
    person: Who | None
    status: Literal["in_production", "done", "failed"]
    spend_usd: float  # its whole life
    spend_estimated: bool
    credits: float
    finished_at: UtcTime | None
    last_activity_at: UtcTime
    final_out_of_date: bool = False  # done, but its clips changed since: "changes waiting"
    folder_id: int | None = None  # its project (OR1); null: No project


class UsageVideosOut(BaseModel):
    total: int
    next_cursor: str | None
    people: list[Who]  # for the Who filter
    items: list[UsageVideo]


VIDEO_SORTS = {
    "activity": lambda v: -v.last_activity_at.timestamp(),
    "spend": lambda v: -v.spend_usd,
    "finished": lambda v: -(v.finished_at.timestamp() if v.finished_at else 0),
    "title": lambda v: v.title.lower(),
}


@router.get("/brands/{brand_id}/videos", response_model=UsageVideosOut)
def brand_videos(
    brand_id: int,
    period: PeriodName = "week",
    status: Literal["any", "in_production", "done", "failed"] = "any",
    person_id: int | None = None,
    q: str = "",
    sort: Literal["activity", "spend", "finished", "title"] = "activity",
    folder: str | None = None,  # a project's id, or none: No project (OR4)
    cursor: str | None = None,
    limit: int = Query(25, ge=1, le=100),
    owner: User = Depends(owner_or_404),
    db: Session = Depends(get_db),
):
    """The brand's videos with their whole-life spend. The period picks which: done videos
    finished in it, others with activity in it; all time lists everything."""
    _brand(db, owner, brand_id)
    when = usage.period(period)
    query = select(Project).where(Project.brand_id == brand_id)
    if (filed := folders.where(Project.folder_id, folder)) is not None:
        query = query.where(filed)
    projects = list(db.scalars(query))
    spend, guessed, credits, last = usage.project_totals(db, [p.id for p in projects])
    states = usage.video_statuses(db, projects)
    old = out_of_date(db, projects)  # LW2, read once for the whole list
    videos, people = [], {}
    for p in projects:
        title, script_id, letter = usage.video_title(db, p)
        state = states[p.id]
        active = max(filter(None, [last.get(p.id), p.created_at]))
        moment = p.finished_at if state == "done" else active
        if when.start is not None and moment < when.start:
            continue
        person = _who(db, p.created_by_id)
        if person:
            people[person.id] = person
        videos.append(
            UsageVideo(
                project_id=p.id,
                title=title,
                script_id=script_id,
                version_letter=letter,
                legacy=script_id is None,
                person=person,
                status=state,
                spend_usd=usage.money(spend.get(p.id)),
                spend_estimated=guessed.get(p.id, False),
                credits=float(credits.get(p.id, 0)),
                finished_at=p.finished_at,
                last_activity_at=active,
                final_out_of_date=state == "done" and p.id in old,
                folder_id=p.live_folder_id,
            )
        )
    shown = [
        v
        for v in videos
        if (status == "any" or v.status == status)
        and (person_id is None or (v.person and v.person.id == person_id))
        and q.strip().lower() in v.title.lower()
    ]
    shown.sort(key=VIDEO_SORTS[sort])
    page, more = _page(shown, cursor, limit)
    return UsageVideosOut(
        total=len(shown),
        next_cursor=more,
        people=sorted(people.values(), key=lambda w: w.name.lower()),
        items=page,
    )


class ProjectCost(BaseModel):
    folder_id: int | None  # null: No project
    name: str
    videos: int  # filed in it now, not put away
    finished: int  # in the period
    spend_usd: float
    spend_estimated: bool
    credits: float
    cost_per_finished_usd: float | None  # those finished videos' whole life, each


class ProjectCostsOut(BaseModel):
    items: list[ProjectCost]


def _names(db: Session, brand_id: int) -> dict:
    live = select(Folder).where(Folder.brand_id == brand_id, Folder.deleted_at.is_(None))
    return {f.id: f.name for f in db.scalars(live)}


@router.get("/brands/{brand_id}/projects", response_model=ProjectCostsOut)
def brand_projects(
    brand_id: int,
    period: PeriodName = "week",
    owner: User = Depends(owner_or_404),
    db: Session = Depends(get_db),
):
    """OR4: what each project cost in the period, by spend, No project last. Spend follows
    where each video, script and quick clip is filed now (not a history): its videos' jobs,
    its scripts' own writing calls and its quick clips, each counted once."""
    _brand(db, owner, brand_id)
    when, names = usage.period(period), _names(db, brand_id)
    costs = usage.filed(db, brand_id, when)
    projects = list(db.scalars(select(Project).where(Project.brand_id == brand_id)))
    lifetime, _, _, _ = usage.project_totals(db, [p.id for p in projects])
    rows = []
    for folder_id in [*names, None]:
        mine = [p for p in projects if p.live_folder_id == folder_id]
        start = when.start
        done = [p for p in mine if p.finished_at and (start is None or p.finished_at >= start)]
        cost = costs.get(folder_id, {})
        spent = sum((lifetime.get(p.id, Decimal(0)) for p in done), Decimal(0))
        rows.append(ProjectCost(
            folder_id=folder_id, name=names.get(folder_id, "No project"),
            videos=sum(1 for p in mine if p.archived_at is None), finished=len(done),
            spend_usd=usage.money(cost.get("spend")),
            spend_estimated=cost.get("estimated", False),
            credits=float(cost.get("credits", 0)),
            cost_per_finished_usd=usage.money(spent / len(done)) if done else None))  # fmt: skip
    rows.sort(key=lambda r: (r.folder_id is None, -r.spend_usd, r.name.lower()))
    return ProjectCostsOut(items=rows)


class MyVideo(BaseModel):
    project_id: int
    title: str
    status: Literal["in_production", "done", "failed"]
    credits: float  # its whole life
    budget_credits: float
    director_credits: float = 0  # of `credits`, the director's own time (its own limit)
    approved_up_to: float | None = None  # a freestyle's video: what the owner's OKs cover
    folder_id: int | None
    finished_at: UtcTime | None
    last_activity_at: UtcTime
    # v5 My credits' words: a freestyle's own status, else the video's (failed: its last step)
    state: Literal["delivered", "making", "waiting", "declined", "stopped", "failed"]
    brand_id: int  # the hidden Freestyle brand's for a freestyle


class MyProject(BaseModel):
    folder_id: int | None  # null: No project
    name: str
    videos: int
    credits: float


class MyScript(BaseModel):
    script_id: int
    title: str
    credits: float  # the caller's own calls writing it, in the period
    brand_id: int  # for its link (/b/<brand>/scripts/<id>) once My credits covers every brand


class WeekLine(BaseModel):
    label: str  # "Videos", "Quick clips", "Scripts", "A look", "Checking a look", …
    credits: float


class MyWeek(BaseModel):
    """Every charge that counts toward the caller's week, every brand: it adds up to used."""

    used: float
    allowance: float | None  # null for the owner (no weekly limit)
    lines: list[WeekLine]


class MySend(BaseModel):
    """One of the caller's own sends waiting for the owner's OK (any kind: a freestyle send, a
    Quick clip past the allowance, a script's song or narration, a step past the budget), or
    a freestyle whose last send the owner declined."""

    job_id: int | None = None  # the held job (Withdraw cancels it); null for a declined one
    freestyle_id: int | None = None  # a freestyle's send
    title: str  # the freestyle's title, or what was asked ("Quick clip", "Song · Bo tries salmon")
    brand: str  # its brand's name, "" with none picked
    status: Literal["waiting", "declined"]
    up_to_credits: float  # what it asks for ("up to"); nothing is spent until it's approved
    reason: str = ""  # declined: the owner's words
    created_at: UtcTime


class MineOut(BaseModel):
    credits: float  # the videos listed, plus quick clips and writing scripts
    quick_clip_credits: float  # in the period
    script_credits: float  # writing scripts, in the period: their own calls only
    videos: list[MyVideo]
    projects: list[MyProject]
    scripts: list[MyScript] = []
    week: MyWeek | None = None  # this week, as the allowance counts it
    sends: list[MySend] = []  # every brand: each held send of any kind, and declined ones
    waiting_credits: float = 0  # up to, over the waiting sends (as Needs you): none spent yet
    videos_and_freestyles: int = 0  # the videos listed (a freestyle's video among them)


@router.get("/mine", response_model=MineOut)
def mine(
    brand_id: int | None = None,  # none: every brand, freestyles too (v5 My credits)
    period: PeriodName = "week",
    month: Month = None,
    folder: str | None = None,  # a project's id, or none: No project
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """OR4 for anyone: the caller's own videos in the brand, in credits only (never dollars,
    never someone else's video), and their quick clips' and script writing's credits in the
    period (both come out of an editor's week). Videos are
    picked by the period as on the owner's list: done ones finished in it, others active."""
    from app import hidden

    when = _when(period, month)[1]
    if brand_id is not None:
        get_brand(db, user, brand_id)
        brand_ids, names = [brand_id], _names(db, brand_id)
    else:  # every brand, the hidden Freestyle one too (its video, script and brand)
        hidden.see(db)
        ours = select(Brand.id).where(Brand.workspace_id == user.workspace_id)
        brand_ids = list(db.scalars(ours))
        names = {k: v for b in brand_ids for k, v in _names(db, b).items()}
    query = select(Project).where(Project.brand_id.in_(brand_ids),
                                  Project.created_by_id == user.id)  # fmt: skip
    if (filed := folders.where(Project.folder_id, folder)) is not None:
        query = query.where(filed)
    projects = list(db.scalars(query))
    _, _, credits, last = usage.project_totals(db, [p.id for p in projects])
    states, videos = usage.video_statuses(db, projects), []
    from app.credits import approved, director_credits
    from app.models.freestyles import Freestyle

    sent = {fs.project_id: fs for fs in db.scalars(select(Freestyle).where(
        Freestyle.project_id.in_([p.id for p in projects])))}  # fmt: skip
    for p in projects:
        active = max(filter(None, [last.get(p.id), p.created_at]))
        moment = p.finished_at if states[p.id] == "done" else active
        if (when.start is not None and moment < when.start) or (when.end and moment >= when.end):
            continue
        videos.append(MyVideo(
            project_id=p.id, title=usage.video_title(db, p)[0], status=states[p.id],
            credits=float(credits.get(p.id, 0)), budget_credits=float(p.budget_credits),
            director_credits=float(director_credits(db, p)),
            approved_up_to=float(approved(db, sent[p.id])) if p.id in sent else None,
            folder_id=p.live_folder_id, finished_at=p.finished_at, brand_id=p.brand_id,
            state=_state(db, states[p.id], sent.get(p.id)), last_activity_at=active))  # fmt: skip
    quick = [
        c["credits"]
        for b in brand_ids
        for c in usage.filed(db, b, when, made_by=user.id, quick_only=True).values()
    ]
    quick_credits = float(sum(quick, Decimal(0)))
    written = {k: v for b in brand_ids
               for k, v in usage.script_credits(db, b, when, user.id).items()}  # fmt: skip
    scripts = [MyScript(script_id=s.id, title=s.title, credits=float(written[s.id]),
                        brand_id=s.brand_id)
               for s in db.scalars(select(Script).where(Script.id.in_(written)))]  # fmt: skip
    script_total = sum(s.credits for s in scripts)
    groups: dict = {}
    for v in videos:
        group = groups.setdefault(v.folder_id, [0, 0.0])
        group[0], group[1] = group[0] + 1, group[1] + v.credits
    sends = _sends(db, user)  # last: it reads Freestyle's hidden rows (hidden.see)
    return MineOut(
        sends=sends, waiting_credits=sum(s.up_to_credits for s in sends if s.status == "waiting"),
        videos_and_freestyles=len(videos),
        credits=sum(v.credits for v in videos) + quick_credits + script_total,
        quick_clip_credits=quick_credits, script_credits=script_total,
        scripts=sorted(scripts, key=lambda s: -s.credits), week=_week(db, user),
        videos=sorted(videos, key=lambda v: -v.last_activity_at.timestamp()),
        projects=[MyProject(folder_id=f, name=names.get(f, "No project"), videos=n, credits=c)
                  for f, (n, c) in sorted(groups.items(), key=lambda g: g[0] is None)])  # fmt: skip


FREESTYLE_STATES = {"working": "making", "withdrawn": "stopped"}  # else its own word


def _state(db: Session, status: str, fs) -> str:
    """A row's v5 words: a freestyle's own status, else delivered, making or failed."""
    if fs is not None:
        from app.routes import freestyles

        said = freestyles._out(db, fs).status
        return FREESTYLE_STATES.get(said, said)
    return {"done": "delivered", "in_production": "making"}.get(status, status)


def _sends(db: Session, user: User) -> list[MySend]:
    """Every send of the caller's waiting for the owner's OK, of any kind, each at the price
    Needs you shows the owner (a freestyle's "up to", else the held job's price with what
    rides along), and the freestyles whose last send was declined (v5 My credits), newest
    first. A freestyle's video and script are hidden until the OK, so this sees hidden rows."""
    from app import hidden
    from app.models.freestyles import Freestyle
    from app.models.jobs import JobStatus
    from app.routes import freestyles
    from app.routes.jobs import _freestyle, _with_check

    hidden.see(db)

    def name(brand_id: int | None) -> str:
        brand = db.get(Brand, brand_id) if brand_id else None
        return brand.name if brand and not brand.hidden else ""

    out = []
    held = select(Job).where(Job.created_by_id == user.id,
                             Job.status == JobStatus.needs_owner_approval)  # fmt: skip
    for job in db.scalars(held):
        ref = _freestyle(db, job)
        fs = db.get(Freestyle, ref.id) if ref else None
        price = ref.up_to if ref and ref.up_to is not None else _with_check(db, job)
        out.append(MySend(job_id=job.id, freestyle_id=fs and fs.id, status="waiting",
                          title=fs.title if fs else usage.what(db, job),
                          brand=name(fs.brand_id if fs else job.brand_id),
                          up_to_credits=float(price), created_at=job.created_at))  # fmt: skip
    for fs in db.scalars(select(Freestyle).where(Freestyle.created_by_id == user.id)
                         .order_by(Freestyle.id.desc()).limit(200)):  # fmt: skip
        seen = freestyles._out(db, fs)
        if seen.status == "declined":
            said = next((m.text for m in reversed(seen.thread)
                         if m.text.startswith("The owner declined: ")), "")  # fmt: skip
            out.append(MySend(freestyle_id=fs.id, title=fs.title, status="declined",
                              brand=name(fs.brand_id), created_at=fs.created_at,
                              up_to_credits=float(seen.up_to or _asked(db, fs)),
                              reason=said.removeprefix("The owner declined: ")))  # fmt: skip
    return sorted(out, key=lambda s: s.created_at, reverse=True)


def _asked(db: Session, fs) -> Decimal:
    """A one-clip freestyle's newest send's price (a declined one's too)."""
    from app.routes.freestyles import _jobs

    jobs, sent = _jobs(db, fs), [m["job"] for m in fs.chat if m.get("job")]
    return Decimal(jobs[sent[-1]].credits or 0) if sent and sent[-1] in jobs else Decimal(0)


def _week(db: Session, user: User) -> MyWeek:
    from app.credits import get_limits

    used, lines = usage.week_lines(db, user)
    allowance = None if user.is_owner else get_limits(db, user.workspace_id)
    return MyWeek(used=float(used), lines=[WeekLine(label=k, credits=float(v)) for k, v in lines],
                  allowance=allowance and float(allowance.weekly_quick_clip_credits))  # fmt: skip


class UsageScript(ScriptRow):
    spend_usd: float  # writing it plus every video made from it, whole life
    spend_estimated: bool
    changed_at: UtcTime


class UsageScriptsOut(BaseModel):
    total: int
    next_cursor: str | None
    authors: list[Who]  # for the Author filter
    items: list[UsageScript]


SCRIPT_STATUS = {"writing": "draft", "ready": "published", "in_production": "in_production"}


@router.get("/brands/{brand_id}/scripts", response_model=UsageScriptsOut)
def brand_scripts(
    brand_id: int,
    status: Literal["any", "writing", "ready", "in_production", "done"] = "any",
    author_id: int | None = None,
    q: str = "",
    sort: Literal["changed", "spend", "title"] = "changed",
    cursor: str | None = None,
    limit: int = Query(25, ge=1, le=100),
    owner: User = Depends(owner_or_404),
    db: Session = Depends(get_db),
):
    """The brand's scripts (drafts included, as the owner sees them), with what each cost."""
    _brand(db, owner, brand_id)
    scripts = db.scalars(
        select(Script).where(Script.brand_id == brand_id, Script.archived.is_(False))
    )
    spends = usage.script_spends(db, brand_id)
    rows, authors = [], {}
    for script in scripts:
        row = library_row(db, script, full=False)
        total, guessed = spends.get(script.id, (Decimal(0), False))
        changed = max(
            filter(None, [script.created_at, *(d.approved_at for d in lib.drafts(db, script))])
        )
        if who := _who(db, script.created_by_id):
            authors[who.id] = who
        rows.append(
            UsageScript(
                **row.model_dump(),
                spend_usd=usage.money(total),
                spend_estimated=guessed,
                changed_at=changed,
            )
        )
    wanted = SCRIPT_STATUS.get(status, status)
    shown = [
        r
        for r in rows
        if (status == "any" or r.status == wanted)
        and (author_id is None or r.created_by_id == author_id)
        and q.strip().lower() in r.title.lower()
    ]
    keys = {
        "changed": lambda r: -r.changed_at.timestamp(),
        "spend": lambda r: -r.spend_usd,
        "title": lambda r: r.title.lower(),
    }
    shown.sort(key=keys[sort])
    page, more = _page(shown, cursor, limit)
    return UsageScriptsOut(
        total=len(shown),
        next_cursor=more,
        authors=sorted(authors.values(), key=lambda w: w.name.lower()),
        items=page,
    )


class UsageBrandRef(BaseModel):
    id: int
    name: str


class UsageCharge(BaseModel):
    id: int  # for POST /usage/charges/{id}/refund
    at: UtcTime
    person: Who | None
    brand: UsageBrandRef | None  # null: not tied to one brand
    what: str  # "Clip 3 take · Bo tries salmon · B", "Quick clip"
    credits: float
    cost_usd: float
    estimated: bool
    status: str
    # Its credits were given back (the dollars stay spent): what it cost before, why and when,
    # so the struck credits and the reason survive a reload. Null if not refunded.
    refunded: "RefundedOut | None" = None


class RefundedOut(BaseModel):
    credits: float  # what it was charged before the refund (`credits` above is now 0)
    reason: str
    at: UtcTime


class UsageChargesOut(BaseModel):
    next_cursor: str | None
    items: list[UsageCharge]


@router.get("/charges", response_model=UsageChargesOut)
def charges(
    brand_id: int | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    owner: User = Depends(owner_or_404),
    db: Session = Depends(get_db),
):
    """Every charge, newest first, for checking one (the old "By job" list). The cursor is
    the last row's id, so new charges never shift a page."""
    query = (
        select(Usage, Job)
        .join(Job, Job.id == Usage.job_id)
        .where(Usage.workspace_id == owner.workspace_id)
        .order_by(Usage.id.desc())
    )
    if brand_id is not None:
        query = query.where(Job.brand_id == brand_id)
    if cursor and cursor.isdigit():
        query = query.where(Usage.id < int(cursor))
    rows = db.execute(query.limit(limit + 1)).all()
    items = _charges(db, owner, rows[:limit])
    more = str(rows[limit - 1][0].id) if len(rows) > limit else None
    return UsageChargesOut(next_cursor=more, items=items)


def _charges(db: Session, owner: User, rows: list) -> list[UsageCharge]:
    names = {
        b.id: b.name
        for b in db.scalars(select(Brand).where(Brand.workspace_id == owner.workspace_id))
    }
    refunded = {
        r.job_id: RefundedOut(credits=float(r.credits), reason=r.reason, at=r.created_at)
        for r in db.scalars(
            select(ChargeRefund).where(ChargeRefund.job_id.in_([j.id for _, j in rows]))
        )
    }
    items = [
        UsageCharge(
            id=row.id,
            refunded=refunded.get(job.id),
            at=row.created_at,
            person=_who(db, job.created_by_id),
            brand=UsageBrandRef(id=job.brand_id, name=names[job.brand_id])
            if job.brand_id
            else None,
            what=usage.what(db, job),
            credits=float(job.credits),
            cost_usd=float(round(row.cost_usd, 4)),
            estimated=row.estimated,
            status=str(job.status),
        )
        for row, job in rows
    ]
    return items


CSV_HEAD = ["When (UTC)", "Who", "Brand", "What", "Credits", "Dollars", "Estimated", "Status",
            "Credits given back", "Why given back"]  # fmt: skip


def _cell(value) -> str:
    """A spreadsheet never runs a title as a formula ("=SUM(…)" typed as a script's title)."""
    text = str(value)
    return f"'{text}" if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.get("/charges.csv", response_class=Response,
            responses={200: {"content": {"text/csv": {}}}})  # fmt: skip
def charges_csv(
    month: str | None = Query(None, pattern=r"^2\d{3}-(0[1-9]|1[0-2])$"),  # "2026-11"; now's
    owner: User = Depends(owner_or_404),
    db: Session = Depends(get_db),
):
    """The month's charges (UTC), oldest first, as a CSV file to download (owner only)."""
    now = utcnow()
    year, number = map(int, month.split("-")) if month else (now.year, now.month)
    start = datetime(year, number, 1)
    end = datetime(year + number // 12, number % 12 + 1, 1)
    rows = db.execute(select(Usage, Job).join(Job, Job.id == Usage.job_id)
                      .where(Usage.workspace_id == owner.workspace_id,
                             Usage.created_at >= start, Usage.created_at < end)
                      .order_by(Usage.id)).all()  # fmt: skip
    out = io.StringIO()
    sheet = csv.writer(out)
    sheet.writerow(CSV_HEAD)
    for c in _charges(db, owner, rows):
        back = c.refunded
        sheet.writerow([c.at.strftime("%Y-%m-%d %H:%M"), *map(_cell, (
            c.person.name if c.person else "", c.brand.name if c.brand else "", c.what)),
            c.credits, c.cost_usd, "yes" if c.estimated else "", c.status,
            back.credits if back else "", _cell(back.reason) if back else ""])  # fmt: skip
    name = f"brand-studio-charges-{year}-{number:02d}.csv"
    return Response(out.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})  # fmt: skip


ALREADY = "Those credits were already given back."


class RefundIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)  # e.g. "a still with the wrong person"


class RefundOut(BaseModel):
    job_id: int
    credits: float  # given back
    reason: str
    by: Who | None
    at: UtcTime


@router.post("/charges/{charge_id}/refund", response_model=RefundOut)
def refund_charge(
    charge_id: int,
    body: RefundIn,
    owner: User = Depends(owner_or_404),
    db: Session = Depends(get_db),
):
    """Give one charge's credits back (owner only; editors never see it). The job's credits
    go to 0, so the editor's week and the video's budget get them back; the dollars the
    service charged stay on the bill. Once per charge: asking again is refused (409)."""
    charge = db.get(Usage, charge_id)
    if not charge or charge.workspace_id != owner.workspace_id:
        raise HTTPException(404, "No such charge.")
    if db.scalar(select(ChargeRefund.id).where(ChargeRefund.job_id == charge.job_id)):
        raise HTTPException(409, ALREADY)
    job = db.get(Job, charge.job_id)
    done = ChargeRefund(job_id=job.id, credits=job.credits, by_id=owner.id, reason=body.reason)
    job.credits = Decimal(0)
    db.add(done)
    try:
        db.commit()
    except IntegrityError:  # two presses at once: the unique job_id lets only one through
        db.rollback()
        raise HTTPException(409, ALREADY) from None
    return RefundOut(
        job_id=done.job_id, credits=float(done.credits), reason=done.reason,
        by=_who(db, done.by_id), at=done.created_at,
    )  # fmt: skip
