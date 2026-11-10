"""Spend per video (Reed, 9 Nov: "spend per video/project so I have a general idea"): every
video's whole-life dollars, by provider and by kind, and one video's runs. Owner only; editors
get 404 and keep their credits (rule 4)."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import hidden, spend, usage
from app.db import get_db
from app.models.accounts import User
from app.models.brands import Brand
from app.models.freestyles import Freestyle
from app.models.jobs import Job, Usage
from app.models.projects import Project
from app.routes.usage import Month, Part, PeriodName, _page, _when, owner_or_404, parts
from app.schemas import UtcTime

router = APIRouter(prefix="/usage", tags=["usage"])


class VideoSpend(BaseModel):
    project_id: int
    brand_id: int
    brand: str  # "Freestyle" for a video made with no brand picked
    title: str
    freestyle_id: int | None = None  # a video made from New video's chat opens there
    spend_usd: float  # its whole life
    spend_estimated: bool
    providers: list[Part]
    kinds: list[Part]  # Claude's thinking, Stills, Takes, Voice, … in that order
    last_at: UtcTime  # its newest charge


class VideoSpendsOut(BaseModel):
    total: int
    next_cursor: str | None
    kinds: list[str]  # the kinds any listed video has, for the table's columns
    items: list[VideoSpend]


SORTS = {
    "spend": lambda v: (-v.spend_usd, v.title.lower()),
    "recent": lambda v: -v.last_at.timestamp(),
    "title": lambda v: v.title.lower(),
}


def _freestyles(db: Session, ids) -> dict:
    made = db.scalars(select(Freestyle).where(Freestyle.project_id.in_(ids)))
    return {f.project_id: f for f in made}


def _row(db: Session, p: Project, found: list, names: dict, fs=None) -> VideoSpend:
    split = spend.split(found)
    return VideoSpend(
        project_id=p.id, brand_id=p.brand_id, brand=names.get(p.brand_id, "Freestyle"),
        title=fs.title if fs else usage.video_title(db, p)[0], freestyle_id=fs and fs.id,
        spend_usd=usage.money(split.usd), spend_estimated=bool(split.listed),
        providers=parts(split.providers), kinds=parts(split.kinds, spend.KIND_ORDER),
        last_at=max((c.at for c in found), default=p.created_at),
    )  # fmt: skip


@router.get("/videos", response_model=VideoSpendsOut)
def videos(
    period: PeriodName = "month",
    month: Month = None,
    sort: Literal["spend", "recent", "title"] = "spend",
    cursor: str | None = None,
    limit: int = Query(25, ge=1, le=100),
    owner: User = Depends(owner_or_404),
    db: Session = Depends(get_db),
):
    """Every video with a charge in the period, each with its whole life's spend."""
    hidden.see(db)  # a freestyle's video too
    when, ws = _when(period, month)[1], owner.workspace_id
    active, _ = spend.charges(db, Job.workspace_id == ws, Job.project_id.is_not(None),
                              usage_at=when.has(Usage.created_at),
                              job_at=when.has(Job.created_at))  # fmt: skip
    ids = {c.project_id for c in active}
    every: dict[int, list] = {}
    for c in spend.charges(db, Job.project_id.in_(ids))[0] if ids else []:
        every.setdefault(c.project_id, []).append(c)
    names = {b.id: b.name for b in db.scalars(select(Brand).where(Brand.workspace_id == ws))
             if not b.hidden}  # fmt: skip
    made = _freestyles(db, ids)
    rows = [_row(db, p, every[p.id], names, made.get(p.id))
            for p in db.scalars(select(Project).where(Project.id.in_(ids)))]  # fmt: skip
    rows.sort(key=SORTS[sort])
    page, more = _page(rows, cursor, limit)
    kinds = {k.name for r in rows for k in r.kinds}
    return VideoSpendsOut(total=len(rows), next_cursor=more, items=page,
                          kinds=[k for k in spend.KIND_ORDER if k in kinds])  # fmt: skip


class RunSpend(BaseModel):
    name: str  # "Before the first run", "First run", "Revision 1", …
    started_at: UtcTime | None
    usd: float
    estimated: bool


class VideoSpendOut(VideoSpend):
    unreported: bool  # a job still running: its cost isn't reported yet
    runs: list[RunSpend]  # by the director's runs, oldest first; none before its first


def _runs(db: Session, project_id: int, found: list) -> list[RunSpend]:
    """Each charge with the run going when it was asked for; before the first, apart."""
    from app.director import RUN, STEP

    starts: list[datetime] = sorted(db.scalars(
        select(func.min(Job.created_at)).where(Job.project_id == project_id,
                                               Job.input["step"].as_string() == STEP)
        .group_by(Job.input[RUN]["id"].as_string())))  # fmt: skip
    if not starts:
        return []
    groups: dict[int, list] = {}
    for c in found:
        groups.setdefault(sum(c.at >= s for s in starts), []).append(c)
    out = []
    for n in sorted(groups):
        split = spend.split(groups[n])
        name = "Before the first run" if n == 0 else "First run" if n == 1 else f"Revision {n - 1}"
        out.append(RunSpend(name=name, started_at=starts[n - 1] if n else None,
                            usd=usage.money(split.usd), estimated=bool(split.listed)))  # fmt: skip
    return out


@router.get("/videos/{project_id}", response_model=VideoSpendOut)
def video(project_id: int, owner: User = Depends(owner_or_404), db: Session = Depends(get_db)):
    """One video's whole-life spend: by provider, by kind and by the director's runs."""
    hidden.see(db)
    p = db.get(Project, project_id)
    if not p or p.workspace_id != owner.workspace_id:
        raise HTTPException(404, "No such video.")
    found, pending = spend.charges(db, Job.project_id == p.id)
    brand = db.get(Brand, p.brand_id)
    names = {brand.id: brand.name} if brand and not brand.hidden else {}
    row = _row(db, p, found, names, _freestyles(db, [p.id]).get(p.id))
    return VideoSpendOut(**row.model_dump(), unreported=pending, runs=_runs(db, p.id, found))
