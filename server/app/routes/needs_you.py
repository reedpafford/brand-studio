"""Needs you (S9-01): the owner's one inbox across brands, an editor's own videos. Questions
from the director, money OKs and stuck videos with their one-click fix (rule 22); a card
answered here is the same answer as in the video's chat (app/routes/asks.py)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import asks, director, hidden, looks, run_progress
from app.auth import current_user, user_name
from app.db import get_db
from app.models.accounts import User
from app.models.asks import Ask
from app.models.brands import Brand
from app.models.freestyles import Freestyle
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft
from app.models.storyboards import StoryboardFrame
from app.routes.asks import AskOut, AskPrice, _price, out
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
    send: bool = False  # an editor's send not yet OK'd (its video hidden): "Gut check (Kel's send)"
    about: str = ""  # "Pasted script, Skeleton style, 45 s"


class NeedsYouRow(BaseModel):
    video: NeedsYouVideo
    brand: NamedBrand
    ask: AskOut


class StuckFix(BaseModel):
    """The one press, as the video's own stuck card has it (run_progress): `again` makes the
    clip's take again, `redraw` its still, `carry_on` starts the run again from where it
    stopped, `split` cuts a clip too long for its model (its breakdown's `problem`); `chat`,
    or any other, opens the video's chat."""

    kind: str
    label: str  # "Try again"
    price: str | None = None  # "up to" in the viewer's money ("$0.42", "4 credits"); "free"
    clip_id: int | None = None  # again: the project clip
    frame_id: int | None = None  # redraw: the storyboard frame
    problem: str | None = None  # split: the breakdown problem it fixes


class StuckVideo(BaseModel):
    video: NeedsYouVideo
    brand: NamedBrand
    at: UtcTime
    what: str  # "Clip 4's take couldn't be made"
    why: str
    fix: StuckFix


class HeldSend(BaseModel):
    """A press held for the owner outside any video: songs, narration or music on a script, or
    an editor's Quick clip past their week (approve or decline through the job routes)."""

    job_id: int
    brand: NamedBrand | None
    what: str  # "Gut check · song", "Quick clip" (usage.what, as Usage names it)
    made_by: str
    up_to: AskPrice
    held: str  # why it waits, in the server's words
    at: UtcTime
    script_id: int | None = None  # Read the script


class BrandCount(NamedBrand):
    count: int


class NeedsYouOut(BaseModel):
    total: int
    brands: list[BrandCount]  # every brand with its count, for the filter (S9-01)
    questions: list[NeedsYouRow]
    money: list[NeedsYouRow]
    sends: list[HeldSend]  # money held outside any video, after `money`
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
    sends = _sends(db, user)
    counts: dict[int, int] = {}
    every = [p.brand_id for _, p in cards] + [s.brand.id for s in stuck]
    for b in every + [s.brand.id for s in sends if s.brand]:
        counts[b] = counts.get(b, 0) + 1
    brands = db.scalars(select(Brand).where(Brand.workspace_id == user.workspace_id,
                                            Brand.archived.is_(False))).all()  # fmt: skip
    shown = [BrandCount(id=b.id, name=b.name, count=counts.get(b.id, 0)) for b in brands
             if not b.hidden or counts.get(b.id)]  # fmt: skip
    keep = [(a, p) for a, p in cards if brand_id in (None, p.brand_id)]
    made = [NeedsYouRow(video=_video(db, p), brand=_brand(db, p), ask=out(db, user, a))
            for a, p in keep]  # fmt: skip
    db.commit()
    return NeedsYouOut(
        total=len(cards) + len(stuck) + len(sends), brands=shown,
        questions=[r for r in made if r.ask.kind in asks.QUESTIONS],
        money=[r for r in made if r.ask.kind in asks.MONEY],
        sends=[s for s in sends if brand_id is None or s.brand and s.brand.id == brand_id],
        stuck=[s for s in stuck if brand_id in (None, s.brand.id)])  # fmt: skip


def _videos(db: Session, user: User, ids: set[int]) -> dict[int, Project]:
    rows = db.scalars(select(Project).where(Project.id.in_(ids or {0}),
                                            Project.archived_at.is_(None))).all()  # fmt: skip
    return {p.id: p for p in rows if user.is_owner or p.created_by_id == user.id}


def _brand(db: Session, p: Project) -> NamedBrand:
    return NamedBrand(id=p.brand_id, name=db.get(Brand, p.brand_id).name)


def _video(db: Session, p: Project) -> NeedsYouVideo:
    fs = db.scalar(select(Freestyle).where(Freestyle.project_id == p.id))
    still = db.scalar(select(StoryboardFrame.file_id).where(
        StoryboardFrame.project_id == p.id, StoryboardFrame.file_id.is_not(None))
        .order_by(StoryboardFrame.id))  # fmt: skip
    return NeedsYouVideo(id=p.id, title=fs.title if fs else p.name, still_file_id=still,
                         made_by=user_name(db, p.created_by_id), send=p.hidden,
                         about=_about(db, p, fs))  # fmt: skip


def _about(db: Session, p: Project, fs: Freestyle | None) -> str:
    """Where its words came from, its style and its length: "Pasted script, Skeleton style,
    45 s" (S9-01)."""
    draft = db.get(ScriptDraft, p.script_draft_id) if p.script_draft_id else None
    script = db.get(Script, draft.script_id) if draft else None
    source = ("" if script is None else "From a reel" if p.reel_script_id
              else "Pasted script" if fs and script.created_at >= fs.created_at
              else "Saved script")  # fmt: skip
    try:
        style = f"{looks.get(p.look)['name']} style"
    except HTTPException:  # a look since taken out of the guides
        style = ""
    seconds = p.planned_seconds or p.breakdown_seconds
    return ", ".join(x for x in (source, style, f"{seconds} s" if seconds else "") if x)


def _stuck(db: Session, user: User) -> list[StuckVideo]:
    """Videos whose newest step failed, or whose run stopped on its own: what and why, and
    the one press that fixes it, the same as the video's own stuck card (S3-11)."""
    from app.needs_you import ADVISORY

    query = select(Project).where(Project.workspace_id == user.workspace_id,
                                  Project.archived_at.is_(None))  # fmt: skip
    if not user.is_owner:
        query = query.where(Project.created_by_id == user.id)
    projects = {p.id: p for p in db.scalars(query)}
    newest = dict(db.execute(select(Job.project_id, func.max(Job.id)).where(
        Job.project_id.in_(projects or {0}), Job.kind != ADVISORY)
        .group_by(Job.project_id)).all())  # fmt: skip
    found = []
    for job in db.scalars(select(Job).where(Job.id.in_(newest.values() or {0}))):
        p = projects[job.project_id]
        stopped = (job.input.get("step") == director.STEP
                   and job.input.get("ended") not in (None, "Stopped.", "Delivered.")
                   and job.input.get("result") != "Delivered.")  # fmt: skip
        if job.status != JobStatus.failed and not stopped:
            continue
        run = run_progress.record(db, p, user) if job.input.get(director.RUN) else None
        if run and run["ended_at"] is None:  # its run goes on: the director deals with it
            continue
        if run and (said := run.get("failed")):  # its run's stuck card: the same fix
            first = (said["fixes"] or [{"kind": "chat", "label": "Open the chat"}])[0]  # none: talk
            fix = StuckFix(kind=first["kind"], label=first["label"], price=first.get("price"),
                           clip_id=said.get("clip"), problem=first.get("problem"))  # fmt: skip
            what, why = said["title"], said["why"]
        elif job.status == JobStatus.failed:
            item = director._item(db, job).removesuffix("'s take")  # "Clip 4", as its card says
            what, why = f"{item} couldn’t be made", job.error or ""
            fix = _fix(db, user, p, job)
        else:
            what, why = "The director stopped", job.input["ended"]
            fix = _fix(db, user, p, job)
        if p.hidden:  # a send not yet the owner's OK'd video: its chat is the way in
            fix = StuckFix(kind="chat", label="Open the chat")
        found.append(StuckVideo(video=_video(db, p), brand=_brand(db, p),
                                at=job.finished_at or job.created_at, what=what, why=why,
                                fix=fix))  # fmt: skip
    return sorted(found, key=lambda s: s.at, reverse=True)


def _fix(db: Session, user: User, p: Project, job: Job) -> StuckFix:
    """A step that failed outside a run: made again at its own price, "up to" (rule 36)."""
    from app.clip_takes import take_credits
    from app.models.clips import ProjectClip

    owner = user.is_owner
    if (clip := db.get(ProjectClip, job.input.get("project_clip_id") or 0)) is not None:
        price = run_progress.money(take_credits(db, p, clip), owner)
        return StuckFix(kind="again", label="Try again", price=price, clip_id=clip.id)
    if frame := job.input.get("frame_id"):
        return StuckFix(kind="redraw", label="Draw it again", frame_id=frame,
                        price=run_progress.money(job.credits, owner))  # fmt: skip
    if job.input.get("step") == director.STEP:
        return StuckFix(kind="carry_on", label="Carry on",
                        price=run_progress.money(run_progress.price_of(db, p), owner))  # fmt: skip
    return StuckFix(kind="chat", label="Open the chat")


def _sends(db: Session, user: User) -> list[HeldSend]:
    """Presses held for the owner outside any video, oldest first (an editor: their own)."""
    from app.routes.jobs import HELD, ON_SCRIPT, _with_check
    from app.usage import what

    query = select(Job).where(Job.workspace_id == user.workspace_id, Job.project_id.is_(None),
                              Job.status == JobStatus.needs_owner_approval)  # fmt: skip
    if not user.is_owner:
        query = query.where(Job.created_by_id == user.id)
    found = []
    for job in db.scalars(query.order_by(Job.id)):
        script_id = job.input.get(ON_SCRIPT) or job.input.get("script_id")
        script = db.get(Script, script_id) if script_id else None
        mark = job.brand_id or (script.brand_id if script else None)  # a script's: its brand
        brand = db.get(Brand, mark) if mark else None
        found.append(HeldSend(
            job_id=job.id, what=what(db, job), made_by=user_name(db, job.created_by_id),
            brand=NamedBrand(id=brand.id, name=brand.name) if brand else None,
            up_to=_price(user, _with_check(db, job)), held=job.input.get(HELD, ""),
            at=job.created_at, script_id=script.id if script else None))  # fmt: skip
    return found
