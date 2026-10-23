"""A project's clips: ask Claude for one video prompt per clip of the newest breakdown, list
them, or edit one. Generating the videos is a separate step."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clip_prompts
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.jobs import Job, JobStatus
from app.prompts.schemas import Breakdown, ClipPrompt, Reference
from app.routes.clips import generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.projects import get_project
from app.routes.storyboard import _newest_breakdown
from app.schemas import LongText

router = APIRouter(prefix="/projects/{project_id}/clips", tags=["project clips"])
WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)


class ProjectClipIn(BaseModel):
    prompt: LongText
    references: list[Reference] = Field(max_length=50)


class ProjectClipOut(BaseModel):
    id: int
    clip_id: str
    seconds: int
    prompt: str
    references: list[Reference]
    problems: list[str]
    file_id: int | None
    stale: bool  # made from an older breakdown


def _out(row: ProjectClip, newest: BreakdownVersion | None) -> ProjectClipOut:
    return ProjectClipOut(
        **{f: getattr(row, f) for f in ProjectClipOut.model_fields if f != "stale"},
        stale=not newest or row.breakdown_id != newest.id,
    )


@router.post(
    "/prompts", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)]
)
def write_prompts(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Queue the clip-prompts call (a paid Claude call). New prompts replace the old clips."""
    project = get_project(db, user, project_id)
    bd = _newest_breakdown(db, project)
    if not bd:
        raise HTTPException(409, "Make a breakdown first.")
    pending = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING)))
    if any(j.input.get("step") == "clip_prompts" for j in pending):
        raise HTTPException(409, "Clip prompts are already being written for this project.")
    return enqueue(
        db,
        user,
        "write-claude",
        clip_prompts.job_input(db, project, bd),
        project=project,
        provider="claude",
    )


@router.get("", response_model=list[ProjectClipOut])
def list_clips(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = get_project(db, user, project_id)
    newest = _newest_breakdown(db, project)
    rows = db.scalars(
        select(ProjectClip).where(ProjectClip.project_id == project.id).order_by(ProjectClip.id)
    )
    return [_out(r, newest) for r in rows]


@router.put("/{clip_id}", response_model=ProjectClipOut)
def edit_clip(
    project_id: int,
    clip_id: int,
    body: ProjectClipIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Edit a clip's prompt or references; its problems are checked again."""
    project = get_project(db, user, project_id)
    row = db.get(ProjectClip, clip_id)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "No such clip.")
    row.prompt, row.references = body.prompt, [r.model_dump() for r in body.references]
    bd = Breakdown.model_validate(db.get(BreakdownVersion, row.breakdown_id).data)
    clip = ClipPrompt(clip_id=row.clip_id, seconds=row.seconds, **body.model_dump())
    row.problems = clip_prompts.clip_problems(db, project, bd, clip)
    db.commit()
    return _out(row, _newest_breakdown(db, project))
