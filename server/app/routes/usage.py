"""Usage, the brand tracker (Reed only; DECISIONS #237): spend, finished videos and cost per
finished video per brand, for this week, this month or all time. Editors get 404."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import usage
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.brands import Brand

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


class Before(BaseModel):
    spend_usd: float
    finished: int
    cost_per_finished_usd: float | None


class SummaryOut(BaseModel):
    period: PeriodName
    starts_at: datetime | None  # null for all time
    previous: Before | None  # last week or last month; null for all time
    spend_usd: float  # every charge in the period, brands and not
    spend_estimated: bool  # some of it is an estimate (the provider didn't say)
    finished: int
    cost_per_finished_usd: float | None
    in_progress: int
    unassigned_spend_usd: float  # "Not tied to one brand"


class BrandRow(BaseModel):
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
    last_activity_at: datetime | None


class BrandsOut(BaseModel):
    total: int
    next_cursor: str | None
    items: list[BrandRow]


class BrandOut(BrandRow):
    previous: Before | None
    editors_active: int  # people who made videos for it in the period


def _row(brand: Brand, f: usage.Figures) -> BrandRow:
    b = brand.id
    return BrandRow(
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
        return Before(
            spend_usd=usage.money(sum(f.spend.values())),
            finished=done,
            cost_per_finished_usd=usage.money(spent / done) if done else None,
        )
    return Before(
        spend_usd=usage.money(f.spend.get(brand_id)),
        finished=f.finished.get(brand_id, 0),
        cost_per_finished_usd=f.cost_per(brand_id),
    )


@router.get("/summary", response_model=SummaryOut)
def summary(
    period: PeriodName = "week",
    owner: User = Depends(owner_or_404),
    db: Session = Depends(get_db),
):
    now = usage.period(period)
    f = usage.figures(db, owner.workspace_id, now)
    done, spent = sum(f.finished.values()), sum(f.finished_spend.values())
    return SummaryOut(
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


@router.get("/brands", response_model=BrandsOut)
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
    start = int(cursor) if cursor and cursor.isdigit() else 0
    page = rows[start : start + limit]
    more = start + limit < len(rows)
    return BrandsOut(total=len(rows), next_cursor=str(start + limit) if more else None, items=page)


@router.get("/brands/{brand_id}", response_model=BrandOut)
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
    return BrandOut(
        **row.model_dump(),
        previous=_before(db, owner.workspace_id, period, now, brand_id),
        editors_active=usage.editors_active(db, brand_id, now),
    )
