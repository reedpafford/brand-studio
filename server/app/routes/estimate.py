"""What the rest of a project will cost, stage by stage, in credits: the same estimates
`enqueue` charges (Claude calls from the rates table, stills and clips from the catalogue).
Done stages cost nothing more; the final video is free."""

import math
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.breakdown import video_model
from app.credits import credits_used, estimate
from app.db import get_db
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.routes.projects import get_project
from app.routes.scripts import latest
from app.storyboard import image_model

router = APIRouter(prefix="/projects/{project_id}/estimate", tags=["credits"])
CLIP_SECONDS_GUESS = 8  # before a breakdown exists: about this many seconds per clip


class StageOut(BaseModel):
    stage: str  # script, breakdown, storyboard, clip_prompts, clips, video
    done: bool
    credits: float  # still to spend on this stage (0 when done)
    note: str  # how it was worked out, in plain words


class ProjectEstimateOut(BaseModel):
    stages: list[StageOut]
    remaining_credits: float
    used_credits: float
    budget_credits: float


def _claude(db: Session, project: Project) -> Decimal:
    return estimate(db, project.workspace_id, "write-claude", Decimal(1))


def _still(db: Session, project: Project) -> Decimal:
    job = {"model": image_model().id, "input": {"resolution": "1K"}}
    return estimate(db, project.workspace_id, "image", Decimal(1), job)


def _video(db: Session, project: Project, seconds: int) -> Decimal:
    job = {"model": video_model().id, "input": {"resolution": "480p"}}
    return estimate(db, project.workspace_id, "video", Decimal(seconds), job)


def _stages(db: Session, project: Project) -> list[StageOut]:
    script = latest(db, project)
    bd = db.scalar(
        select(BreakdownVersion)
        .where(BreakdownVersion.project_id == project.id)
        .order_by(BreakdownVersion.id.desc())
        .limit(1)
    )
    bd_ok = bool(bd and script and bd.script_version == script.version)
    frames = list(
        db.scalars(select(StoryboardFrame).where(StoryboardFrame.project_id == project.id))
    )
    frames = [f for f in frames if bd and f.breakdown_id == bd.id]
    clips = list(db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)))
    clips = [c for c in clips if bd and c.breakdown_id == bd.id]
    planned = bd.data["clips"] if bd_ok else []
    n_clips = len(planned) or math.ceil(project.estimate_credits / CLIP_SECONDS_GUESS)
    claude, still = _claude(db, project), _still(db, project)

    stills_left = (len([f for f in frames if not f.file_id]) if frames else n_clips) * still
    storyboard_done = bool(frames) and all(f.file_id for f in frames)
    if clips:
        seconds_left = sum(c.seconds for c in clips if not c.picked_take_id)
    else:
        seconds_left = sum(c["seconds"] for c in planned) or int(project.estimate_credits)
    clips_done = bool(clips) and all(c.picked_take_id for c in clips)
    rows = [
        ("script", script is not None, claude, "one Claude call to draft it"),
        ("breakdown", bd_ok, claude, "one Claude call"),
        (
            "storyboard",
            storyboard_done,
            (0 if frames else claude) + stills_left,
            f"frame prompts (one Claude call) and {n_clips} stills",
        ),
        ("clip_prompts", bool(clips), claude, "one Claude call"),
        (
            "clips",
            clips_done,
            _video(db, project, seconds_left),
            f"{seconds_left} s of video at 480p, one take each",
        ),
        ("video", False, Decimal(0), "putting the clips together is free"),
    ]
    return [
        StageOut(stage=s, done=done, credits=0 if done else float(cost), note=note)
        for s, done, cost, note in rows
    ]


@router.get("", response_model=ProjectEstimateOut)
def project_estimate(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    project = get_project(db, user, project_id)
    stages = _stages(db, project)
    return ProjectEstimateOut(
        stages=stages,
        remaining_credits=round(sum(s.credits for s in stages), 2),
        used_credits=float(credits_used(db, project)),
        budget_credits=float(project.budget_credits),
    )
