"""Needs you (S9-01): the owner's one inbox across brands, an editor's own videos. Questions
from the director, money OKs and stuck videos with their one-click fix (rule 22); a card
answered here is the same answer as in the video's chat (app/routes/asks.py)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import asks, director, hidden
from app.auth import current_user, user_name
from app.db import get_db
from app.models.accounts import User
from app.models.asks import Ask
from app.models.brands import Brand
from app.models.freestyles import Freestyle
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.routes.asks import AskOut, out
from app.schemas import UtcTime

router = APIRouter(tags=["needs you"])


class NamedBrand(BaseModel):
    id: int
    name: str


class NeedsYouVideo(BaseModel):
    id: int
    title: str
    still_file_id: int | None
    made_by: str


class NeedsYouRow(BaseModel):
    video: NeedsYouVideo
    brand: NamedBrand
    ask: AskOut


class StuckFix(BaseModel):
    label: str  # "Make it again"
    method: str | None  # null: open the chat (`path` is the video)
    path: str


class StuckVideo(BaseModel):
    video: NeedsYouVideo
    brand: NamedBrand
    at: UtcTime
    what: str  # "Clip 4's take couldn't be made"
    why: str
    fix: StuckFix


class BrandCount(NamedBrand):
    count: int


class NeedsYouOut(BaseModel):
    total: int
    brands: list[BrandCount]  # every brand with its count, for the filter (S9-01)
    questions: list[NeedsYouRow]
    money: list[NeedsYouRow]
    stuck: list[StuckVideo]


@router.get("/needs-you", response_model=NeedsYouOut)
def needs_you(brand_id: int | None = None, user: User = Depends(current_user),
              db: Session = Depends(get_db)):  # fmt: skip
    """One read across brands: questions from the director, money OKs (the start of a run, past
    a budget, the director's own limit) and stuck videos with their one-click fix (rule 22).
    The owner sees every video; an editor their own. `brand_id` filters; the counts don't."""
    hidden.see(db)
    rows = db.scalars(select(Ask).where(Ask.workspace_id == user.workspace_id,
                                        Ask.state.in_(asks.OPEN))
                      .order_by(Ask.id)).all()  # fmt: skip
    videos = _videos(db, user, {a.project_id for a in rows})
    cards = [(a, videos[a.project_id]) for a in rows if a.project_id in videos]
    cards = [(a, p) for a, p in cards if asks.sync(db, a) not in ("answered", "not_needed")]
    stuck = _stuck(db, user)
    counts: dict[int, int] = {}
    for _, p in cards:
        counts[p.brand_id] = counts.get(p.brand_id, 0) + 1
    for s in stuck:
        counts[s.brand.id] = counts.get(s.brand.id, 0) + 1
    brands = db.scalars(select(Brand).where(Brand.workspace_id == user.workspace_id,
                                            Brand.archived.is_(False))).all()  # fmt: skip
    shown = [BrandCount(id=b.id, name=b.name, count=counts.get(b.id, 0)) for b in brands
             if not b.hidden or counts.get(b.id)]  # fmt: skip
    keep = [(a, p) for a, p in cards if brand_id in (None, p.brand_id)]
    made = [NeedsYouRow(video=_video(db, p), brand=_brand(db, p), ask=out(db, user, a))
            for a, p in keep]  # fmt: skip
    db.commit()
    return NeedsYouOut(
        total=len(cards) + len(stuck), brands=shown,
        questions=[r for r in made if r.ask.kind in asks.QUESTIONS],
        money=[r for r in made if r.ask.kind in asks.MONEY],
        stuck=[s for s in stuck if brand_id in (None, s.brand.id)])  # fmt: skip


def _videos(db: Session, user: User, ids: set[int]) -> dict[int, Project]:
    rows = db.scalars(select(Project).where(Project.id.in_(ids or {0}),
                                            Project.archived_at.is_(None))).all()  # fmt: skip
    return {p.id: p for p in rows if user.is_owner or p.created_by_id == user.id}


def _brand(db: Session, p: Project) -> NamedBrand:
    return NamedBrand(id=p.brand_id, name=db.get(Brand, p.brand_id).name)


def _video(db: Session, p: Project) -> NeedsYouVideo:
    fs = db.scalar(select(Freestyle.title).where(Freestyle.project_id == p.id))
    still = db.scalar(select(StoryboardFrame.file_id).where(
        StoryboardFrame.project_id == p.id, StoryboardFrame.file_id.is_not(None))
        .order_by(StoryboardFrame.id))  # fmt: skip
    return NeedsYouVideo(id=p.id, title=fs or p.name, still_file_id=still,
                 made_by=user_name(db, p.created_by_id))  # fmt: skip


def _stuck(db: Session, user: User) -> list[StuckVideo]:
    """Videos whose newest step failed, or whose run stopped on its own: what and why, and
    the one press that fixes it."""
    from app.needs_you import ADVISORY

    query = select(Project).where(Project.workspace_id == user.workspace_id,
                                  Project.archived_at.is_(None))  # fmt: skip
    if not user.is_owner:
        query = query.where(Project.created_by_id == user.id)
    projects = {p.id: p for p in db.scalars(query)}
    newest = dict(db.execute(select(Job.project_id, func.max(Job.id)).where(
        Job.project_id.in_(projects or {0}), Job.kind != ADVISORY)
        .group_by(Job.project_id)).all())  # fmt: skip
    out = []
    for job in db.scalars(select(Job).where(Job.id.in_(newest.values() or {0}))):
        p = projects[job.project_id]
        run = job.input.get(director.RUN) or {}
        if job.status == JobStatus.failed:
            what, why = f"{director._item(db, job)} couldn't be made", job.error or ""
        elif (
            job.input.get("step") == director.STEP
            and job.input.get("ended") not in (None, "Stopped.", "Delivered.")
            and job.input.get("result") != "Delivered."
        ):
            what, why = "The director stopped", job.input["ended"]
        else:
            continue
        out.append(StuckVideo(video=_video(db, p), brand=_brand(db, p),
                         at=job.finished_at or job.created_at, what=what, why=why,
                         fix=_fix(p, job, bool(run))))  # fmt: skip
    return sorted(out, key=lambda s: s.at, reverse=True)


def _fix(p: Project, job: Job, run: bool) -> StuckFix:
    base = f"/projects/{p.id}"
    if p.hidden:  # a send not yet the owner's OK'd video: its chat is the way in
        return StuckFix(label="Open the chat", method=None, path=base)
    if clip := job.input.get("project_clip_id"):
        return StuckFix(label="Make it again", method="POST", path=f"{base}/clips/{clip}/generate")
    if frame := job.input.get("frame_id"):
        return StuckFix(label="Draw it again", method="POST",
                   path=f"{base}/storyboard/frames/{frame}/render")  # fmt: skip
    if run:
        return StuckFix(label="Start it again", method="POST", path=f"{base}/director")
    return StuckFix(label="Open the chat", method=None, path=base)
