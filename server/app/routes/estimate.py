"""What the rest of a project will cost, stage by stage, in credits: the same estimates
`enqueue` charges (Claude calls from the rates table, stills and clips from the catalogue).
Done stages cost nothing more; the final video is free."""

import math
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import clip_prompts, clip_takes
from app import script_library as lib
from app.auth import current_user
from app.breakdown import video_model
from app.credits import CLIP_SECONDS_GUESS, credits_used, estimate, plan_cost, usd_to_credits
from app.db import get_db
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft
from app.models.storyboards import StoryboardFrame
from app.prompts.schemas import Breakdown
from app.revision import revision
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

    if change := revision(db, video):  # a revision: only what it makes again (F15)
        return _work(db, video, change)
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

    if change := revision(db, video):  # its clips made again, never the whole video's (F15)
        return (_work(db, video, change) + director.own_limit()
                + director.MAX_REDOS * clip_takes.takes_price(db, video, change[0]))  # fmt: skip
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


TYPICAL_TURNS = 14  # a run's usual turns, treatment to deliver: for its expected cost only
WATCH_LOOKS = 12  # a cut watch's usual pictures (its frame strips, the words and the facts)
# A revision's turns, as real ones took them (QA on #1481): its own (the note, its card, the
# cut, its watch, the delivery), and more for each clip (its still, its take, its remake) and
# each look (and its cast OK): Skeleton 261's one clip took 11; Pixar Song 294's three clips
# and a look about 20.
REVISION_TURNS, CLIP_TURNS, LOOK_TURNS = 8, 3, 3


def expected(db: Session, draft: ScriptDraft, video=None, ended: bool = False) -> Decimal:
    """What a run will probably cost (Reed, 6 Nov: the owner's test site, `owner_uncapped`):
    with enough finished videos of its format and style, their credits a second
    (`scorecard.forecast`); else the version's own price (its first takes and their checks),
    its song or narration and the presenter's host made once, and the director's usual turns
    and one watch of the cut, at their own prices. A revision (`revision`; `ended`: the run
    that ended, for its own record): what it makes again, each of its clips once more (real
    ones remake one: 261's clip 7 was made twice), its turns at what a turn really costs, and
    one watch. No allowance, no remakes bound: an estimate, never a limit."""
    from app import director, director_song, host, narration, scorecard, watch_cut

    script = db.get(Script, draft.script_id)
    ws = script.workspace_id
    watch = estimate(db, ws, watch_cut.KIND, Decimal(WATCH_LOOKS), {})
    if change := revision(db, video, ended):
        clips, looks = change
        turns = min(director.MAX_TURNS, REVISION_TURNS + CLIP_TURNS * len(clips)
                    + LOOK_TURNS * looks)  # fmt: skip
        return (_work(db, video, change) + clip_takes.takes_price(db, video, clips)
                + turns * turn_price(db, ws) + watch)  # fmt: skip
    found = scorecard.forecast(db, draft, video)
    if found["basis"] != "estimate":
        return Decimal(str(found["credits"]))
    seconds = quoted_seconds(db, draft, video)
    said = narration.longest(db, draft, video) if script.kind == "narrated" else seconds
    audio = director_song.price(db, draft) / (1 + director_song.REMAKES)  # made once
    talks = host.run_price(db, draft, said, video, 0)
    turns = TYPICAL_TURNS * estimate(db, ws, "write-claude", Decimal(1), {})
    return version_cost(db, draft, video) + audio + talks + turns + watch


MEASURED = 10  # real revision turns before their own mean prices one (else the rate)


def turn_price(db: Session, ws: int) -> Decimal:
    """A revision's director turn at what one really costs (QA on #1481: $0.11-0.14, against
    the $0.31 its charge is capped at; a new video's turns, $0.05-0.08, aren't counted): the
    mean of the workspace's last 40 real revision turns (Usage); with fewer than MEASURED
    (the stand-ins report none), the rate."""
    from app.director import REVISION, RUN, STEP
    from app.models.jobs import Job, Usage

    each = (select(func.sum(Usage.cost_usd).label("usd")).join(Job, Job.id == Usage.job_id)
            .where(Usage.workspace_id == ws, Usage.estimated.is_(False),
                   Job.input["step"].as_string() == STEP,
                   Job.input[RUN][REVISION].as_boolean().is_(True))
            .group_by(Usage.job_id).order_by(Usage.job_id.desc()).limit(40).subquery())  # fmt: skip
    n, usd = db.execute(select(func.count(), func.avg(each.c.usd))).one()
    rate = estimate(db, ws, "write-claude", Decimal(1), {})
    return usd_to_credits(usd) if n >= MEASURED else rate


def _work(db: Session, video: Project, change: tuple[list[ProjectClip], int]) -> Decimal:
    """A revision's own work: its looks, its clips' stills drawn again, a take of each."""
    from app.sheets import look_price

    clips, looks = change
    ws = video.workspace_id
    return (looks * look_price(db, ws) + _shots(db, video, clips) * _still(db, ws, video)
            + clip_takes.takes_price(db, video, clips))  # fmt: skip


def _shots(db: Session, video: Project, clips: list[ProjectClip]) -> int:
    """The stills these clips' shots are drawn from (each drawn again)."""
    bd = clip_prompts.newest(db, video)
    ids = {c.clip_id for c in clips}
    return sum(len(c["shot_ids"]) for c in (bd.data.get("clips", []) if bd else [])
               if c["id"] in ids)  # fmt: skip


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
    # each made clip at its own model with its watch; the planned clips still to write at the
    # video model (a UGC talker who acts is on it too: Omni 1.2, Reed, 6 Nov)
    rest = sum(c["seconds"] for c in fresh) if clips else seconds_left
    from app import talker  # a talker's clips are the host's one take, priced as its own step

    made = sum((take_credits(db, project, c) for c in clips if not c.picked_take_id
                and not talker.says(db, project, c)), Decimal(0))  # fmt: skip
    takes = made + _video(db, ws, rest, project) + take_watch.per_take(db, ws) * len(fresh)
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
                else clip_prompts.priced(n_clips)
            ),
            "half a Claude call a clip",
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
