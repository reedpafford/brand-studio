"""The project's storyboard: ask Claude for frame prompts from the newest breakdown, list the
frames, or edit one. Rendering the stills is a separate step."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storyboard
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
from app.schemas import LongText

router = APIRouter(prefix="/projects/{project_id}/storyboard", tags=["storyboard"])
WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)


class StoryboardIn(BaseModel):
    per_shot: bool = False  # one still per shot instead of per clip


class FrameIn(BaseModel):
    prompt: LongText
    reference_ids: list[str] = Field(max_length=30)


class FrameOut(BaseModel):
    id: int
    clip_id: str
    shot_id: str
    prompt: str
    reference_ids: list[str]
    problems: list[str]
    file_id: int | None
    stale: bool  # made from an older breakdown


def _newest_breakdown(db: Session, project: Project) -> BreakdownVersion | None:
    return db.scalar(
        select(BreakdownVersion)
        .where(BreakdownVersion.project_id == project.id)
        .order_by(BreakdownVersion.id.desc())
        .limit(1)
    )


def _out(frame: StoryboardFrame, newest: int | None) -> FrameOut:
    return FrameOut(
        **{f: getattr(frame, f) for f in FrameOut.model_fields if f != "stale"},
        stale=frame.breakdown_id != newest,
    )


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
    newest = _newest_breakdown(db, project)
    rows = db.scalars(
        select(StoryboardFrame)
        .where(StoryboardFrame.project_id == project.id)
        .order_by(StoryboardFrame.id)
    )
    return [_out(f, newest.id if newest else None) for f in rows]


@router.put("/frames/{frame_id}", response_model=FrameOut)
def edit_frame(
    project_id: int,
    frame_id: int,
    body: FrameIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Edit a frame's prompt or references; its problems are checked again."""
    project = get_project(db, user, project_id)
    frame = db.get(StoryboardFrame, frame_id)
    if not frame or frame.project_id != project.id:
        raise HTTPException(404, "No such frame.")
    frame.prompt, frame.reference_ids = body.prompt, body.reference_ids
    frame.problems = storyboard.frame_problems(
        db,
        project,
        Frame(clip_id=frame.clip_id, shot_id=frame.shot_id, **body.model_dump()),
    )
    db.commit()
    newest = _newest_breakdown(db, project)
    return _out(frame, newest.id if newest else None)
