"""What the rest of a project will cost, stage by stage, in credits: the same estimates
`enqueue` charges (Claude calls from the rates table, stills and clips from the catalogue).
Done stages cost nothing more; the final video is free."""

import math
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clip_prompts
from app import script_library as lib
from app.auth import current_user
from app.breakdown import video_model
from app.credits import CLIP_SECONDS_GUESS, credits_used, estimate, plan_cost
from app.db import get_db
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft
from app.models.storyboards import StoryboardFrame
from app.prompts.schemas import Breakdown
from app.routes.projects import get_project
from app.routes.scripts import latest
from app.storyboard import image_model, still_credits

router = APIRouter(prefix="/projects/{project_id}/estimate", tags=["credits"])


class StageOut(BaseModel):
    stage: str  # script, breakdown, looks, storyboard, clip_prompts, clips, video
    done: bool
    credits: float  # still to spend on this stage (0 when done)
    note: str  # how it was worked out, in plain words


class ProjectEstimateOut(BaseModel):
    stages: list[StageOut]
    remaining_credits: float
    used_credits: float
    budget_credits: float


def _claude(db: Session, ws: int) -> Decimal:
    return estimate(db, ws, "write-claude", Decimal(1))


def _still(db: Session, ws: int, project: Project | None = None) -> Decimal:
    return still_credits(db, ws, image_model(project))  # the job's own model and size


def _video(db: Session, ws: int, seconds: int, project: Project | None = None) -> Decimal:
    job = {"model": video_model(project).id, "input": {"resolution": "480p"}}
    return estimate(db, ws, "video", Decimal(seconds), job)


def version_cost(db: Session, draft: ScriptDraft, video=None) -> Decimal:
    """A version's whole price before it's started, by the rules its video will cost by
        (QA-3: 14.73 quoted, its video's to-finish 28.06): `credits.plan_cost` with no breakdown
        call when one is saved; with neither a saved breakdown nor a target, at least the length
        the video plans for until its plan exists (PRE_BREAKDOWN_SECONDS); a look for every role
        that will need one: each not cast yet, each speaker the cast hasn't got yet (it becomes a
        role), and each cast one with no look in the video's look: `sheets.roles_without_a_look`
    and `roles_needing_look`, the rules VS1's to-finish uses too. A Song
        version's video is its Preferred take's (the song decides the length). `video`: the
        video it would make, for its models and look (Make this version's settings, VS1)."""
    from app import song_takes
    from app.models.projects import PRE_BREAKDOWN_SECONDS
    from app.sheets import look_price, roles_needing_look, roles_without_a_look

    script, seconds = db.get(Script, draft.script_id), lib.seconds(draft)
    each = look_price(db, script.workspace_id)  # as the look press shows and holds
    looks_cost = len(roles_needing_look(db, script, video.look if video else None)) * each
    if script.kind == "song" and (take := song_takes.preferred(db, draft)):  # its take card's
        return song_takes.video_credits(db, take, video=video) + looks_cost
    looks_cost += len(roles_without_a_look(db, script, draft)) * each  # their first look
    bd = Breakdown.model_validate(draft.breakdown) if draft.breakdown else None
    if not bd and not draft.target_seconds:
        seconds = max(seconds, PRE_BREAKDOWN_SECONDS)
    return looks_cost + plan_cost(db, script.workspace_id, seconds, bd, 0,
                                  breakdown=not bd, video=video)  # fmt: skip


def _looks(db: Session, project: Project) -> tuple:
    """The looks still to make (rule 32: up to what Make a look can charge): each role's
    first look and each one with none in the video's look, by the quote's own rules."""
    from app.sheets import look_price, roles_needing_look, roles_without_a_look

    n = len(roles_without_a_look(db, project)) + len(roles_needing_look(db, project))
    note = f"up to {n} look{'' if n == 1 else 's'} to make" if n else "every role has a look"
    return ("looks", not n, n * look_price(db, project.workspace_id), note)


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
    claude, still = _claude(db, project.workspace_id), _still(db, project.workspace_id, project)

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
        _looks(db, project),
        (
            "storyboard",
            storyboard_done,
            (0 if frames else claude) + stills_left,
            f"frame prompts (one Claude call) and {n_clips} stills",
        ),
        (
            "clip_prompts",
            bool(clips),
            claude * clip_prompts.calls(db, project),
            "a Claude call per few clips",
        ),
        (
            "clips",
            clips_done,
            _video(db, project.workspace_id, seconds_left, project),
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
