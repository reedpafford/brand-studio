"""Usage, the brand tracker (Reed only; DECISIONS #237): spend, finished videos and cost per
finished video per brand, for this week, this month or all time. Editors get 404."""

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import script_library as lib
from app import usage
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.brands import Brand
from app.models.jobs import ChargeRefund, Job, Usage
from app.models.projects import Project
from app.models.script_library import Script
from app.routes.project_clips import out_of_date
from app.routes.script_library import ScriptRow
from app.routes.script_library import _out as library_row
from app.schemas import UtcTime

router = APIRouter(prefix="/usage", tags=["usage"])
PeriodName = Literal["week", "month", "all"]
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


class UsageBrandsOut(BaseModel):
    total: int
    next_cursor: str | None
    items: list[UsageBrandRow]


class UsageBrandOut(UsageBrandRow):
    previous: UsagePrevious | None
    editors_active: int  # people who made videos for it in the period


def _row(brand: Brand, f: usage.Figures) -> UsageBrandRow:
    b = brand.id
    return UsageBrandRow(
        brand_id=b,
        name=brand.name,
        colour=(brand.colours or [None])[0],
        archived=brand.archived,
        spend_usd=usage.money(f.spend.get(b)),
        spend_estimated=f.estimated.get(b, False),
        finished=f.finished.get(b, 0),
        cost_per_finished_usd=f.cost_per(b),
        in_progress=f.in_progress.get(b, 0),
        scripts=f.scripts.get(b, 0),
        versions_left=f.versions_left.get(b, 0),
        last_activity_at=f.last_activity.get(b),
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
            spend_usd=usage.money(sum(f.spend.values())),
            finished=done,
            cost_per_finished_usd=usage.money(spent / done) if done else None,
        )
    return UsagePrevious(
        spend_usd=usage.money(f.spend.get(brand_id)),
        finished=f.finished.get(brand_id, 0),
        cost_per_finished_usd=f.cost_per(brand_id),
    )


@router.get("/summary", response_model=UsageSummaryOut)
def summary(
    period: PeriodName = "week",
    owner: User = Depends(owner_or_404),
    db: Session = Depends(get_db),
):
    now = usage.period(period)
    f = usage.figures(db, owner.workspace_id, now)
    done, spent = sum(f.finished.values()), sum(f.finished_spend.values())
    return UsageSummaryOut(
        period=period,
        starts_at=now.start,
        previous=_before(db, owner.workspace_id, period, now),
        spend_usd=usage.money(sum(f.spend.values())),
        spend_estimated=any(f.estimated.values()),
        finished=done,
        cost_per_finished_usd=usage.money(spent / done) if done else None,
        in_progress=sum(f.in_progress.values()),
        unassigned_spend_usd=usage.money(f.spend.get(None)),
    )


@router.get("/brands", response_model=UsageBrandsOut)
def brands(
    period: PeriodName = "week",
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
    f = usage.figures(db, owner.workspace_id, usage.period(period))
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
    owner: User = Depends(owner_or_404),
    db: Session = Depends(get_db),
):
    found = db.get(Brand, brand_id)
    if not found or found.workspace_id != owner.workspace_id:
        raise HTTPException(404, "No such brand.")
    now = usage.period(period)
    row = _row(found, usage.figures(db, owner.workspace_id, now))
    return UsageBrandOut(
        **row.model_dump(),
        previous=_before(db, owner.workspace_id, period, now, brand_id),
        editors_active=usage.editors_active(db, brand_id, now),
    )


# --- Lists: a brand's videos and scripts, and every charge (spec items 6-8) ---


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
    cursor: str | None = None,
    limit: int = Query(25, ge=1, le=100),
    owner: User = Depends(owner_or_404),
    db: Session = Depends(get_db),
):
    """The brand's videos with their whole-life spend. The period picks which: done videos
    finished in it, others with activity in it; all time lists everything."""
    _brand(db, owner, brand_id)
    when = usage.period(period)
    projects = list(db.scalars(select(Project).where(Project.brand_id == brand_id)))
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
        for row, job in rows[:limit]
    ]
    more = str(rows[limit - 1][0].id) if len(rows) > limit else None
    return UsageChargesOut(next_cursor=more, items=items)


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
