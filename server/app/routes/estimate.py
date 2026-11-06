"""What the rest of a project will cost, stage by stage, in credits: the same estimates
`enqueue` charges (Claude calls from the rates table, stills and clips from the catalogue).
Done stages cost nothing more; the final video is free."""

import math
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clip_prompts, model_map
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
    m = video_model(project)
    job = {"model": m.id, "input": {"resolution": m.take_resolution}}
    return estimate(db, ws, "video", Decimal(seconds), job)


def quoted_seconds(db: Session, draft: ScriptDraft, video=None) -> int:
    """The length a version's price is for: its own (`lib.seconds`), at least the length a
    video plans for before any plan or target, and a narrated version's at least its B-roll's
    (`broll_seconds`, rule 36)."""
    from app.models.projects import PRE_BREAKDOWN_SECONDS

    seconds = lib.seconds(draft)
    if not draft.breakdown and not draft.target_seconds:
        seconds = max(seconds, PRE_BREAKDOWN_SECONDS)
    script = db.get(Script, draft.script_id)
    if script.kind == "narrated":
        seconds = max(seconds, broll_seconds(db, script, draft, video))
    return seconds


def broll_seconds(db: Session, script: Script, draft: ScriptDraft, video=None) -> int:
    """A narrated version's B-roll at most (rule 36): a shot shorter than the clip model's
    shortest clip is made at that length (F7). With a plan, each of its shots at least that
    long; before one, the narration's length (`narration.longest`) times max(1, shortest / 2),
    the references' median shot being about 2 s (Seedance x2, P-Video x1). The model is the
    one the video's takes will use (`video_model`)."""
    from app import narration

    low = video_model(video, script.look, script.kind).duration.min
    row = clip_prompts.newest(db, video) if video is not None else None
    plan = (row.data if row else draft.breakdown) or {}
    shots = [sh.get("seconds") or 0 for sc in plan.get("scenes", []) for sh in sc.get("shots", [])]
    if shots:
        return math.ceil(sum(max(s, low) for s in shots))
    return math.ceil(narration.longest(db, draft, video) * max(1, low / 2))


def version_cost(db: Session, draft: ScriptDraft, video=None) -> Decimal:
    """A version's whole price before it's started, by the rules its video will cost by
    (QA-3: 14.73 quoted, its video's to-finish 28.06): `credits.plan_cost` with no breakdown
    call when one is saved; with neither a saved breakdown nor a target, at least the length
    the video plans for until its plan exists (PRE_BREAKDOWN_SECONDS); and up to a look
    (`look_price`, rule 36) for every role that will need one: each not cast yet, each speaker
    the cast hasn't got yet (it becomes a role) and each cast one with no look in the video's
    look (`sheets.roles_without_a_look`, `roles_needing_look`, as the video's cost bar); and
    the plan call the press charges first (`plans.plan_first`, QA-3: 31.06 against 28.06). A Song
    version's is its Preferred take's card (the song decides the length; the same looks).
    `video`: the video it would make, for its models and look (Make this version's settings)."""
    from app import plans, song_takes
    from app.sheets import look_price, roles_needing_look, roles_without_a_look

    script, seconds = db.get(Script, draft.script_id), quoted_seconds(db, draft, video)
    if script.kind == "song" and (take := song_takes.preferred(db, draft)):
        return song_takes.video_credits(db, take, video=video)  # its plan call included
    plan = plans.plan_first(db, draft)  # charged at the press, before the rest
    looks = len(roles_needing_look(db, script, video.look if video else None))
    looks += len(roles_without_a_look(db, script, draft))
    looks_cost = looks * look_price(db, script.workspace_id)  # as the look press shows and holds
    bd = Breakdown.model_validate(draft.breakdown) if draft.breakdown else None
    return plan + looks_cost + plan_cost(db, script.workspace_id, seconds, bd, 0,
                                  breakdown=not bd, video=video, look=script.look,
                                  kind=script.kind)  # fmt: skip


def run_price(db: Session, draft: ScriptDraft, video=None) -> Decimal:
    """A director run's "up to" (Freestyle, rule 36): the version's whole price and all a run
    may add under its own limits (QA on #1176: 80.898 shown, 82.03 charged): every clip made
    again MAX_REDOS times with its watch, and the director's own limit (its turns and
    watches, `director.own_limit`; past it, it waits for an OK); and for a song or narrated
    version with no song yet, its making and one remake (`director_song.price`); a presenter's
    host, its still and every second in one HeyGen take, made once and MAX_REDOS times again
    by its watch (`host.run_price`). The cut, mutes and splices are free."""
    from app import director, narration, take_watch

    script = db.get(Script, draft.script_id)
    ws = script.workspace_id
    bd = Breakdown.model_validate(draft.breakdown) if draft.breakdown else None
    seconds = quoted_seconds(db, draft, video)  # as `version_cost` guesses it
    said = narration.longest(db, draft, video) if script.kind == "narrated" else seconds
    clips = len(bd.clips) if bd else math.ceil(seconds / CLIP_SECONDS_GUESS)
    m = video_model(video, script.look, script.kind)
    model = {"model": m.id, "input": {"resolution": m.take_resolution}}
    takes = (estimate(db, ws, "video", Decimal(seconds), model)
             + clips * take_watch.per_take(db, ws))  # fmt: skip
    from app import director_song, host

    audio = director_song.price(db, draft)  # a song or narration still to make, and one remake
    talks = host.run_price(db, draft, said, video, director.MAX_REDOS)  # on HeyGen, and remakes
    return (version_cost(db, draft, video) + audio + talks + director.MAX_REDOS * takes
            + director.own_limit())  # fmt: skip


def _looks(db: Session, project: Project) -> tuple:
    """The looks still to make (rule 36: up to what Make a look can charge): each role's
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
    if clips:  # and a planned clip with no prompt yet (QA-3 #1013: c2 after a split)
        have = {c.clip_id for c in clips}
        seconds_left = sum(c.seconds for c in clips if not c.picked_take_id) + sum(
            c["seconds"] for c in planned if c["id"] not in have
        )
    else:
        seconds_left = sum(c["seconds"] for c in planned) or int(project.estimate_credits)
    clips_done = bool(clips) and not seconds_left
    from app import take_watch  # each take's watch rides along while watches are on

    ws = project.workspace_id
    from app.clip_takes import take_credits

    fresh = [c for c in planned if c["id"] not in {r.clip_id for r in clips}]
    # each made clip at its own model (Omni's fixed length) with its check; new ones as planned,
    # a talker's shot on Omni when the presenter acts (QA on #1327: before its row exists)
    omni = model_map.on_omni(db, project, bd.data) if bd_ok else set()
    acting = [c for c in fresh if c["id"] in omni]
    rest = (sum(c["seconds"] for c in fresh) if clips else seconds_left) - sum(
        c["seconds"] for c in acting
    )
    takes = (sum((take_credits(db, project, c) for c in clips if not c.picked_take_id),
                 Decimal(0)) + _video(db, ws, max(rest, 0), project)
             + sum((model_map.omni_take(db, project, c["seconds"]) for c in acting), Decimal(0))
             + take_watch.per_take(db, ws) * len(fresh))  # fmt: skip
    rewrite = clip_prompts.to_rewrite(db, project) if clips else []
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
            bool(clips) and not rewrite,
            claude
            * (
                clip_prompts.calls(db, project, rewrite or None)
                if bd_ok  # before a plan: as the quote
                else math.ceil(n_clips / clip_prompts.BATCH_CLIPS)
            ),
            "a Claude call per few clips",
        ),
        (
            "clips",
            clips_done,
            takes,
            f"{seconds_left} s of video at {video_model(project).take_resolution}, one take each",
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
