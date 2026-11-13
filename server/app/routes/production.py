"""In production (owner only; docs/design/redesign/workflow-v2/in-production.md): every video
being made from a script version, across all brands, until it's "Video done". Reads existing
tables only, in a fixed handful of queries whatever the number of videos.

Step, from what the video has: no breakdown yet → breakdown; a breakdown but no storyboard
frames → assets; frames but no clips → storyboard; clips not all approved → clips; every clip
approved → downloads. Flags (one per row, in this order): failed (its newest job failed and
nothing started since), stuck (a job queued or running for over 30 min), idle (no job or edit
for 48 h)."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.credits import COUNTED
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.brands import Brand
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.jobs import Job, JobStatus, Usage
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft
from app.models.storyboards import StoryboardFrame
from app.schemas import UtcTime
from app.script_library import letter as letter_of
from app.worker import FAILED

router = APIRouter(prefix="/production", tags=["production"])
STUCK = timedelta(minutes=30)
IDLE = timedelta(hours=48)
WAITING = (JobStatus.queued, JobStatus.running)
# A failed job in plain words, by its step (never model or provider names).
JOB_NAMES = {
    "breakdown": "Planning the shots",
    "sheet": "Making a look",
    "storyboard": "Writing the storyboard",
    "frame": "Drawing a still",
    "clip_prompts": "Writing the clip prompts",
    "clip_take": "Making the takes",
}
Flag = Literal["failed", "stuck", "idle"]
RETRY = "It didn't finish. Open the video to try again."  # the worker's catch-all, on this page


class Named(BaseModel):
    id: int
    name: str


class ScriptRef(BaseModel):
    id: int
    title: str


class ProductionRow(BaseModel):
    project_id: int
    brand: Named
    script: ScriptRef
    letter: str  # A, B or C: the version
    editor: Named | None
    step: Literal["breakdown", "assets", "storyboard", "clips", "downloads"]
    last_activity_at: UtcTime
    credits_used: float
    director_credits: float = 0  # the director's own spend: the budget leaves it out
    budget_credits: float
    spent_usd: float  # owner only, like the whole page
    poster_file_id: int | None
    flag: Flag | None = None
    flag_since: UtcTime | None = None
    flag_job: str | None = None  # e.g. "Making the takes"
    flag_problem: str | None = None  # the failed job's plain sentence
    clips_made: int = 0  # clips with a take: "Making clips: 4 of 6"
    clips_total: int = 0
    finished_at: UtcTime | None = None  # a delivered one (?delivered=today)
    approved_up_to: float | None = None  # a freestyle's video: what the owner's OKs cover


class Summary(BaseModel):
    in_production: int
    needs_attention: int
    changes_waiting: int = 0  # finished videos whose clips changed since (LW2)
    delivered_today: int = 0  # videos done since midnight (UTC): v5's "Delivered today" tab


def _owner(user: User = Depends(current_user)) -> User:
    if not user.is_owner:
        raise HTTPException(404, "Not found.")  # editors never learn the page exists
    return user


def _grouped(db: Session, query, ids: list[int]) -> dict[int, tuple]:
    return {row[0]: row[1:] for row in db.execute(query.where(query.selected_columns[0].in_(ids)))}


def today() -> datetime:
    """Midnight (UTC) today: where "Delivered today" starts. The workspace has no time zone
    setting yet, so it's UTC, like the weekly allowance (6 pm the evening before for Reed)."""
    return utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


def rows(db: Session, user: User, delivered: bool = False) -> list[ProductionRow]:
    """The videos being made; `delivered`: the ones done today instead (no flags: done)."""
    when = and_(
        Project.finished_at >= today() if delivered else Project.finished_at.is_(None),
        Project.archived_at.is_(None),
    )  # an archived one is neither delivered nor being made
    found = db.execute(
        select(Project, ScriptDraft.slot, Script.id, Script.title, Brand.id, Brand.name)
        .join(ScriptDraft, ScriptDraft.id == Project.script_draft_id)
        .join(Script, Script.id == ScriptDraft.script_id)
        .join(Brand, Brand.id == Project.brand_id)
        .where(Project.workspace_id == user.workspace_id, when)
    ).all()
    ids = [r[0].id for r in found]
    if not ids:
        return []
    now = utcnow()
    jobs = _grouped(
        db,
        select(
            Job.project_id,
            func.max(Job.id),
            # counted like the budget gate: failed and cancelled jobs were refunded
            func.coalesce(func.sum(case((Job.status.in_(COUNTED), Job.credits), else_=0)), 0),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                Job.status.in_(COUNTED),  # the director's own
                                Job.input["director_run"].as_string().is_not(None),
                            ),
                            Job.credits,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),  # fmt: skip
            func.max(Job.created_at),
            func.max(Job.finished_at),
        ).group_by(Job.project_id),
        ids,
    )
    newest = {
        j.project_id: j
        for j in db.scalars(select(Job).where(Job.id.in_([v[0] for v in jobs.values()])))
    }
    stuck: dict[int, Job] = {}  # each video's longest-waiting job
    for job in db.scalars(
        select(Job)
        .where(Job.project_id.in_(ids), Job.status.in_(WAITING), Job.created_at < now - STUCK)
        .order_by(Job.created_at.desc())
    ):
        stuck[job.project_id] = job
    spent = _grouped(
        db,
        select(Job.project_id, func.sum(Usage.cost_usd))
        .join(Usage, Usage.job_id == Job.id)
        .group_by(Job.project_id),
        ids,
    )
    planned = _grouped(
        db,
        select(BreakdownVersion.project_id, func.max(BreakdownVersion.created_at)).group_by(
            BreakdownVersion.project_id
        ),
        ids,
    )
    frames, steps = progress(db, ids)
    clips = _grouped(db, select(ProjectClip.project_id, func.count(ProjectClip.id),
                                func.count(ProjectClip.picked_take_id))
                     .group_by(ProjectClip.project_id), ids)  # fmt: skip
    editors = {
        u.id: u.name for u in db.scalars(select(User).where(User.workspace_id == user.workspace_id))
    }
    from app.credits import approved
    from app.models.freestyles import Freestyle

    sent = {fs.project_id: fs for fs in db.scalars(select(Freestyle).where(
        Freestyle.project_id.in_(ids)))}  # fmt: skip
    out = []
    for project, slot, script_id, title, brand_id, brand_name in found:
        pid = project.id
        _, used, director, job_at, done_at = jobs.get(pid, (None, 0, 0, None, None))
        times = [
            project.created_at,
            job_at,
            done_at,
            *(planned.get(pid) or ()),
            (frames.get(pid) or (None,))[0],
        ]
        last = max(t for t in times if t is not None)
        step = steps[pid]
        row = ProductionRow(
            project_id=pid,
            brand=Named(id=brand_id, name=brand_name),
            script=ScriptRef(id=script_id, title=title),
            letter=letter_of(slot),
            editor=Named(id=project.created_by_id, name=editors.get(project.created_by_id, ""))
            if project.created_by_id
            else None,
            step=step,
            last_activity_at=last,
            credits_used=float(used),
            director_credits=float(director),
            budget_credits=float(project.budget_credits),
            spent_usd=round(float((spent.get(pid) or (Decimal(0),))[0] or 0), 4),
            poster_file_id=(frames.get(pid) or (None, None))[1],
            clips_total=(clips.get(pid) or (0, 0))[0],
            clips_made=(clips.get(pid) or (0, 0))[1],
            finished_at=project.finished_at,
            approved_up_to=float(approved(db, sent[pid])) if pid in sent else None,
        )
        job = newest.get(pid)
        if delivered:  # done: nothing to flag
            out.append(row)
            continue
        if job is not None and job.status == JobStatus.failed:
            row.flag, row.flag_since = "failed", job.finished_at or job.created_at
            row.flag_job = JOB_NAMES.get(job.input.get("step", ""), "A step")
            row.flag_problem = RETRY if job.error == FAILED else job.error
        elif pid in stuck:
            row.flag, row.flag_since = "stuck", stuck[pid].created_at
            row.flag_job = JOB_NAMES.get(stuck[pid].input.get("step", ""), "A step")
        elif now - last > IDLE:
            row.flag, row.flag_since = "idle", last
        out.append(row)
    return out


def progress(db: Session, ids: list[int]) -> tuple[dict[int, tuple], dict[int, str]]:
    """Each video's storyboard (newest frame time, newest still) and its step, from what it
    has, in a fixed handful of queries (the Videos list uses the step and still too)."""
    planned = {
        r[0]
        for r in db.execute(
            select(BreakdownVersion.project_id).where(BreakdownVersion.project_id.in_(ids))
        )
    }
    frames = _grouped(
        db,
        select(
            StoryboardFrame.project_id,
            func.max(StoryboardFrame.created_at),
            func.max(StoryboardFrame.file_id),  # the newest still (file ids only grow)
        ).group_by(StoryboardFrame.project_id),
        ids,
    )
    clips = _grouped(
        db,
        select(
            ProjectClip.project_id,
            func.count(ProjectClip.id),
            func.sum(case((ProjectClip.approved, 1), else_=0)),
        ).group_by(ProjectClip.project_id),
        ids,
    )
    steps = {}
    for pid in ids:
        count, approved = clips.get(pid, (0, 0))
        if pid not in planned:
            steps[pid] = "breakdown"
        elif pid not in frames:
            steps[pid] = "assets"
        elif not count:
            steps[pid] = "storyboard"
        elif (approved or 0) < count:
            steps[pid] = "clips"
        else:
            steps[pid] = "downloads"
    return frames, steps


ORDER = {"failed": 0, "stuck": 1, "idle": 2, None: 3}
SORTS = {
    "attention": lambda r: (ORDER[r.flag], -r.last_activity_at.timestamp()),
    "activity": lambda r: -r.last_activity_at.timestamp(),
    "credits": lambda r: -r.credits_used,
    "budget": lambda r: (
        -(  # as the budget counts it: the director's own spend left out
            (r.credits_used - r.director_credits) / r.budget_credits if r.budget_credits else 0
        )
    ),
}


@router.get("", response_model=list[ProductionRow])
def in_production(
    response: Response,
    brand_id: int | None = None,
    editor_id: int | None = None,
    attention: bool = False,
    delivered: Literal["today"] | None = None,  # v5's "Delivered today" tab
    q: str = "",
    sort: Literal["attention", "activity", "credits", "budget"] = "attention",
    limit: int | None = Query(None, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(_owner),
    db: Session = Depends(get_db),
):
    found = rows(db, user, delivered=delivered == "today")
    if brand_id is not None:
        found = [r for r in found if r.brand.id == brand_id]
    if editor_id is not None:
        found = [r for r in found if r.editor and r.editor.id == editor_id]
    if attention:
        found = [r for r in found if r.flag]
    if q.strip():
        found = [r for r in found if q.strip().lower() in r.script.title.lower()]
    found.sort(key=SORTS[sort])
    response.headers["X-Total-Count"] = str(len(found))
    return found[offset : offset + limit] if limit else found[offset:]


@router.get("/summary", response_model=Summary)
def summary(user: User = Depends(_owner), db: Session = Depends(get_db)):
    from app.routes.project_clips import out_of_date

    found = rows(db, user)
    done = db.scalars(select(Project).where(Project.workspace_id == user.workspace_id,
                                            Project.finished_at.is_not(None),
                                            Project.archived_at.is_(None)))  # fmt: skip
    return Summary(in_production=len(found), needs_attention=sum(1 for r in found if r.flag),
                   changes_waiting=len(out_of_date(db, list(done))),
                   delivered_today=len(rows(db, user, delivered=True)))  # fmt: skip
