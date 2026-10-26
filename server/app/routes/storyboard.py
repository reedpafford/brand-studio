"""The project's storyboard: ask Claude for frame prompts from the newest breakdown, list the
frames, or edit one. Rendering the stills is a separate step."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import advice, storyboard
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.prompts.schemas import Frame
from app.routes.clips import generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.projects import get_project
from app.routes.scripts import latest
from app.schemas import LongText

router = APIRouter(prefix="/projects/{project_id}/storyboard", tags=["storyboard"])
WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)


class StoryboardIn(BaseModel):
    per_shot: bool = False  # one still per shot instead of per clip


class FrameIn(BaseModel):
    prompt: LongText
    reference_ids: list[str] = Field(max_length=30)


class RenderIn(BaseModel):
    note: str = Field("", max_length=500)  # Redo: "What should change?" (this render only)


class FrameOut(BaseModel):
    id: int
    clip_id: str
    shot_id: str
    prompt: str
    reference_ids: list[str]
    problems: list[str]
    kept: list[str]  # advice kept anyway (never blocks)
    file_id: int | None  # the newest still; the old one stays until a new one is ready
    approved: bool  # cleared when the frame is edited, re-rendered or goes stale
    stale: bool  # made from an older breakdown, or the breakdown is for an older script
    still_stale: bool  # the still shows the old cast (its redraw wasn't covered): "Out of date"
    redrawn: bool  # redrawn for a new cast and not approved yet: "Redrawn"
    earlier: list[dict]  # older stills, newest last: [{file_id, prompt}]


def _newest_breakdown(db: Session, project: Project) -> BreakdownVersion | None:
    return db.scalar(
        select(BreakdownVersion)
        .where(BreakdownVersion.project_id == project.id)
        .order_by(BreakdownVersion.id.desc())
        .limit(1)
    )


def _stale(db: Session, project: Project, frame: StoryboardFrame) -> bool:
    newest = _newest_breakdown(db, project)
    working = latest(db, project)
    return (
        not newest
        or frame.breakdown_id != newest.id
        or bool(working and newest.script_version != working.version)
    )


def _out(db: Session, project: Project, frame: StoryboardFrame) -> FrameOut:
    stale = _stale(db, project, frame)
    computed = ("stale", "approved")
    return FrameOut(
        **{f: getattr(frame, f) for f in FrameOut.model_fields if f not in computed},
        approved=frame.approved and not stale,
        stale=stale,
    )


def _frame(db: Session, user: User, project_id: int, frame_id: int):
    project = get_project(db, user, project_id)
    frame = db.get(StoryboardFrame, frame_id)
    if not frame or frame.project_id != project.id:
        raise HTTPException(404, "No such frame.")
    return project, frame


@router.post("", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)])
def make(
    project_id: int,
    body: StoryboardIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Queue a storyboard call (a paid Claude call). New frames replace the old ones."""
    project = get_project(db, user, project_id)
    bd = _newest_breakdown(db, project)
    if not bd:
        raise HTTPException(409, "Make a breakdown first.")
    pending = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING)))
    if any(j.input.get("step") == "storyboard" for j in pending):
        raise HTTPException(409, "A storyboard is already being written for this project.")
    return enqueue(
        db,
        user,
        "write-claude",
        storyboard.job_input(db, project, bd, body.per_shot),
        project=project,
        provider="claude",
    )


@router.get("", response_model=list[FrameOut])
def frames(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = get_project(db, user, project_id)
    rows = db.scalars(
        select(StoryboardFrame)
        .where(StoryboardFrame.project_id == project.id)
        .order_by(StoryboardFrame.id)
    )
    return [_out(db, project, f) for f in rows]


@router.put("/frames/{frame_id}", response_model=FrameOut)
def edit_frame(
    project_id: int,
    frame_id: int,
    body: FrameIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Edit a frame's prompt or references; its problems are checked again."""
    project, frame = _frame(db, user, project_id, frame_id)
    frame.prompt, frame.reference_ids, frame.approved = body.prompt, body.reference_ids, False
    frame.problems = storyboard.frame_problems(
        db,
        project,
        Frame(clip_id=frame.clip_id, shot_id=frame.shot_id, **body.model_dump()),
        frame.breakdown_id,
    )
    db.commit()
    return _out(db, project, frame)


@router.post(
    "/frames/{frame_id}/render",
    response_model=JobOut,
    status_code=201,
    dependencies=[Depends(generation_on)],
)
def render(
    project_id: int,
    frame_id: int,
    body: RenderIn | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Queue the still for one frame (a paid image job, counted against the project budget).
    A frame with problems must be fixed first ("Advice: …" never blocks). An optional Redo
    note goes into this render's prompt only."""
    project, frame = _frame(db, user, project_id, frame_id)
    if advice.blocking(frame.problems):
        raise HTTPException(409, "Fix this frame's problems first.")
    if wrong := advice.open_cast(_newest_breakdown(db, project)):
        detail = wrong[0].removeprefix(advice.CAST)
        raise HTTPException(409, f"Put the right cast in each shot first: {detail}.")
    if _stale(db, project, frame):
        raise HTTPException(
            409, "This frame was made for an older breakdown. Make the storyboard again first."
        )
    pending = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING)))
    if any(j.input.get("frame_id") == frame.id for j in pending):
        raise HTTPException(409, "This frame's still is already being made.")
    return enqueue(
        db,
        user,
        "image",
        storyboard.render_input(db, project, frame, body.note if body else ""),
        project=project,
        provider="replicate",
    )


@router.post("/frames/{frame_id}/approve", response_model=FrameOut)
def approve(
    project_id: int,
    frame_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Approve the frame's still (Next: Clips needs every frame approved)."""
    project, frame = _frame(db, user, project_id, frame_id)
    if not frame.file_id:
        raise HTTPException(409, "Draw this frame first.")
    if _stale(db, project, frame):
        raise HTTPException(409, "This frame was made for an older breakdown.")
    frame.approved, frame.redrawn = True, False  # the "Redrawn" badge goes once approved
    db.commit()
    return _out(db, project, frame)


@router.delete("/frames/{frame_id}/approve", response_model=FrameOut)
def unapprove(
    project_id: int,
    frame_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    project, frame = _frame(db, user, project_id, frame_id)
    frame.approved = False
    db.commit()
    return _out(db, project, frame)


@router.post("/frames/{frame_id}/keep", response_model=FrameOut)
def keep_frame_advice(
    project_id: int,
    frame_id: int,
    body: advice.KeepIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Keep anyway: this frame's advice stays as it is."""
    project, frame = _frame(db, user, project_id, frame_id)
    advice.keep(frame, body.problem)
    db.commit()
    return _out(db, project, frame)


@router.delete("/frames/{frame_id}/keep", response_model=FrameOut)
def unkeep_frame_advice(
    project_id: int,
    frame_id: int,
    problem: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Undo Keep anyway on this frame's advice (?problem=, the text as shown)."""
    project, frame = _frame(db, user, project_id, frame_id)
    advice.unkeep(frame, problem)
    db.commit()
    return _out(db, project, frame)
