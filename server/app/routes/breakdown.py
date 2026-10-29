"""The project's breakdown: ask Claude for one from the working script, read the newest, or
save the editor's edited version. Each comes with the checks' problems in plain words."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from app import advice, breakdown, breakdown_fix, clip_prompts, plans, storyboard
from app.advice import Said, names
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.prompts.schemas import Breakdown
from app.routes.clips import generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.projects import _mine, get_project
from app.routes.scripts import latest

router = APIRouter(prefix="/projects/{project_id}/breakdown", tags=["breakdown"])
shots = APIRouter(prefix="/projects/{project_id}/shots", tags=["breakdown"])
WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)


class SongShotTime(BaseModel):
    start: float
    end: float
    sung: bool
    guessed: bool = False  # its line wasn't heard in the take: "Timing guessed"


class SongPart(BaseModel):
    take_id: int  # the take the times are on (the video's song)
    shots: dict[str, SongShotTime]  # by shot id


class BreakdownOut(BaseModel):
    id: int
    script_version: int
    source: str
    breakdown: Breakdown
    problems: Said
    kept: Said  # advice kept anyway (never blocks)
    stale: bool  # made for an older script version
    changed_shots: list[dict] = []  # fix-cast: [{shot_id, before, after}], for Undo
    cast_redraw: dict | None = None  # fix-cast: redrawn_for_cast or redraw_refused
    fixes: list[dict] = []  # [{problem, kind, label}]: a free one-click fix for that problem
    fixed: list[str] = []  # what a fix just did, in plain words (the toast); Undo is PUT
    unknown_names: dict[str, str] = {}  # a name a shot has that the video doesn't: {ref: name}
    song: SongPart | None = None  # a song video's: each shot's time in the song, and Sung
    older_plan: bool = False  # P2: made from an earlier plan ("Made for an older plan")
    was_id: int | None = None  # OR3 Go back to this: the one it replaced (Undo uses it)


class Maker(BaseModel):
    id: int
    name: str


class BreakdownVersionOut(BaseModel):
    """OR3 Versions: each saved breakdown, newest first; `current` is the one in use."""

    id: int
    made_at: datetime
    made_by: Maker | None
    source: str  # claude | edit | library | earlier (a version gone back to)
    script_version: int
    current: bool


def _song(db: Session, row: BreakdownVersion) -> dict | None:
    """A song video's shot times, each marked when its line wasn't heard in the take."""
    from app import song_breakdown
    from app.models.scripts import ScriptVersion
    from app.models.songs import SongTake

    song = row.data.get("song")
    take = db.get(SongTake, song["take_id"]) if song else None
    if not take:
        return song
    text = db.scalar(select(ScriptVersion.text).where(
        ScriptVersion.project_id == row.project_id, ScriptVersion.version == row.script_version
    )) or ""  # fmt: skip
    unsure = song_breakdown.guessed(
        Breakdown.model_validate(row.data), text, song_breakdown.timing_used(take)
    )
    shots = {sid: {**t, "guessed": sid in unsure} for sid, t in song["shots"].items()}
    return {**song, "shots": shots}


def _out(row: BreakdownVersion, working: int) -> BreakdownOut:
    db = object_session(row)
    project = db.get(Project, row.project_id)
    return BreakdownOut(
        unknown_names=breakdown.unknown_names(db, project, Breakdown.model_validate(row.data)),
        id=row.id,
        script_version=row.script_version,
        source=row.source,
        breakdown=row.data,
        problems=row.problems,
        kept=row.kept or [],
        stale=row.script_version != working,
        song=_song(db, row),
        fixes=breakdown_fix.fixes(row.problems or []),
        older_plan=plans.older(db, project, row),
    )


def _working(db: Session, user: User, project_id: int):
    project = get_project(db, user, project_id)
    version = latest(db, project)
    if not version:
        raise HTTPException(409, "Add a script first.")
    return project, version


@router.post("", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)])
def make(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Queue a breakdown call (a paid Claude call, counted against the project budget). The
    shots of a video made from a script come from an approved plan (flows.md 1b): "Approve
    the plan first" until then. A video made the earlier way makes its breakdown as before."""
    project, version = _working(db, user, project_id)
    if project.script_draft_id:
        plans.require_approved(db, project)
    return queue(db, user, project, version)


def queue(db: Session, user: User, project, version) -> Job:
    pending = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING)))
    if any(
        j.input.get("step") in ("breakdown", "song_breakdown", "narrated_breakdown")
        for j in pending
    ):
        raise HTTPException(409, "A breakdown is already being made for this project.")
    return enqueue(
        db,
        user,
        "write-claude",
        breakdown.job_input(db, project, version),
        project=project,
        provider="claude",
    )


def _newest(db: Session, project) -> BreakdownVersion:
    row = db.scalar(
        select(BreakdownVersion)
        .where(BreakdownVersion.project_id == project.id)
        .order_by(BreakdownVersion.id.desc())
        .limit(1)
    )
    if not row:
        raise HTTPException(404, "This project has no breakdown yet.")
    return row


@router.get("", response_model=BreakdownOut)
def read(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project, version = _working(db, user, project_id)
    return _out(_newest(db, project), version.version)


@router.post("/keep", response_model=BreakdownOut)
def keep_advice(
    project_id: int,
    body: advice.KeepIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Keep anyway: this advice on the newest breakdown stays as it is (never blocks)."""
    project, version = _working(db, user, project_id)
    row = _newest(db, project)
    advice.keep(row, body.problem)
    db.commit()
    return _out(row, version.version)


@router.delete("/keep", response_model=BreakdownOut)
def unkeep_advice(
    project_id: int, problem: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Undo Keep anyway on the newest breakdown's advice (?problem=, the text as shown)."""
    project, version = _working(db, user, project_id)
    row = _newest(db, project)
    advice.unkeep(row, problem)
    db.commit()
    return _out(row, version.version)


VERSIONS = 20  # the newest shown; older rows stay (history only grows)


@router.get("/versions", response_model=list[BreakdownVersionOut])
def versions(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from app.auth import user_name

    project = get_project(db, user, project_id)
    rows = list(db.scalars(select(BreakdownVersion).where(BreakdownVersion.project_id == project.id)
                           .order_by(BreakdownVersion.id.desc()).limit(VERSIONS)))  # fmt: skip
    return [BreakdownVersionOut(id=r.id, made_at=r.created_at, source=r.source,
                                script_version=r.script_version, current=n == 0,
                                made_by=Maker(id=by, name=user_name(db, by)) if (
                                    by := r.created_by_id) else None)
            for n, r in enumerate(rows)]  # fmt: skip


@router.post("/versions/{version_id}/use", response_model=BreakdownOut)
def use_version(
    project_id: int,
    version_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Go back to this (OR3): an earlier breakdown is the newest again, as a new row copied from
    it (history only grows). Free: never refused over budget, and nothing is rewritten for it.
    Frames and clips made for the one gone back to are current again (they move to the copy);
    those made for the one it replaces read "made for an older breakdown", with their usual
    redo. Undo is this press with `was_id`. Whoever made the video, or the owner."""
    _mine(db, user, project_id)
    project, version = _working(db, user, project_id)
    if project.archived_at is not None:
        raise HTTPException(409, "This video is archived. Restore it first.")
    old = db.get(BreakdownVersion, version_id)
    if old is None or old.project_id != project.id:
        raise HTTPException(404, "There's no such breakdown.")
    steps = ("breakdown", "song_breakdown", "narrated_breakdown")
    waiting = list(db.scalars(select(Job).where(Job.project_id == project.id,
                                                Job.status.in_(WAITING))))  # fmt: skip
    if any(j.input.get("step") in steps for j in waiting):
        raise HTTPException(409, "Wait for the breakdown being made.")
    from app.update_after import RUN

    later = ("storyboard", "frame", "clip_prompts", "change")  # made for the one in use now
    if any(j.input.get("step") in later or j.input.get("frame_id") or j.input.get(RUN)
           for j in waiting):  # fmt: skip
        raise HTTPException(409, "Wait for the storyboard, stills and clip prompts being made.")
    was = _newest(db, project)
    if was.id == old.id:
        raise HTTPException(409, "This is the breakdown in use.")
    row = BreakdownVersion(project_id=project.id, script_version=old.script_version,
                           source="earlier", job_id=old.job_id, data=old.data,
                           problems=old.problems, kept=old.kept, created_by_id=user.id)  # fmt: skip
    db.add(row)
    db.flush()
    from sqlalchemy import update

    from app.models.clips import ProjectClip
    from app.models.storyboards import StoryboardFrame

    for made in (StoryboardFrame, ProjectClip):  # made for this one: current again, not redone
        mine = (made.project_id == project.id, made.breakdown_id == old.id)
        db.execute(update(made).where(*mine).values(breakdown_id=row.id))
    breakdown.record_length(project, Breakdown.model_validate(old.data))
    db.commit()
    return _out(row, version.version).model_copy(update={"was_id": was.id})


@router.put("", response_model=BreakdownOut)
def save(
    project_id: int,
    body: Breakdown,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Save the editor's edited breakdown for the working script (a new row)."""
    project, version = _working(db, user, project_id)
    body, landed = breakdown.land(db, project, body)  # never blocks on who's in a shot
    breakdown.record_length(project, body)
    row = BreakdownVersion(
        project_id=project.id,
        script_version=version.version,
        source="edit",
        data=body.model_dump(),
        problems=breakdown.problems(db, project, version.text, body) + landed,
        created_by_id=user.id,
    )
    db.add(row)
    db.commit()
    clip_prompts.follow(db, project, user)  # stale clip prompts are rewritten, within budget
    return _out(row, version.version)


@router.post("/fix-cast", response_model=BreakdownOut)
def fix_cast(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Put the right cast in each shot (free, no model call): a shot whose lines name a role
    but show another role's character gets that role's character instead. Saved as a new
    breakdown version, so stills and clips from the old one are made again."""
    from app.cast_roles import fix

    project, version = _working(db, user, project_id)
    row = _newest(db, project)
    fixed = fix(db, project, version.text, Breakdown.model_validate(row.data))
    if fixed is None:
        raise HTTPException(409, "Every shot already has the right cast.")
    fixed, landed = breakdown.land(db, project, fixed)
    new = BreakdownVersion(
        project_id=project.id,
        script_version=row.script_version,
        source="edit",
        data=fixed.model_dump(),
        problems=breakdown.problems(db, project, version.text, fixed) + landed,
        created_by_id=user.id,
    )
    db.add(new)
    db.flush()
    from app import cast_roles

    redrawn = cast_roles.redraw(db, project, user, cast_roles.carry_frames(db, project, row, new))
    cast_roles.carry_clips(db, project, row, new)
    db.commit()
    clip_prompts.follow(db, project, user)
    out = _out(new, version.version)
    old = Breakdown.model_validate(row.data)
    out.changed_shots, out.cast_redraw = cast_roles.changed_shots(old, fixed), redrawn
    return out


class FixIn(BaseModel):
    problems: list[str] = []  # the problems as shown; empty: every one with a fix


def new_version(db: Session, user: User, project, row: BreakdownVersion, text: str, bd):
    """A fixed breakdown, saved as a new version (stills and clips are carried, as for
    fix-cast); free, no model call."""
    from app import cast_roles

    bd, landed = breakdown.land(db, project, bd)
    new = BreakdownVersion(
        project_id=project.id,
        script_version=row.script_version,
        source="edit",
        data={**bd.model_dump(), **{k: row.data[k] for k in ("plan_version",) if k in row.data}},
        problems=breakdown.problems(db, project, text, bd) + landed,
        created_by_id=user.id,
    )
    db.add(new)
    db.flush()
    cast_roles.carry_frames(db, project, row, new)
    cast_roles.carry_clips(db, project, row, new)
    db.commit()
    clip_prompts.follow(db, project, user)
    return new


@router.post("/fix", response_model=BreakdownOut)
def fix(
    project_id: int,
    body: FixIn | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Fix the breakdown's problems for free (spec one-click-fixes.md §1): a missing line goes
    into the shot around it, a changed line gets the script's words back, the clips are
    fitted to the shots. Undo saves the old breakdown back with PUT."""
    project, version = _working(db, user, project_id)
    row = _newest(db, project)
    every = [f["problem"] for f in breakdown_fix.fixes(row.problems)]
    asked = (body.problems if body else []) or every
    m = breakdown.video_model(project)
    from app.cast_roles import fix as cast

    fixed, done = breakdown_fix.repair(
        version.text, Breakdown.model_validate(row.data), asked, m.duration.min, m.duration.max,
        lambda bd: cast(db, project, version.text, bd),
    )  # fmt: skip
    if not done:
        raise HTTPException(409, "Nothing here can be fixed for you. Edit the shot instead.")
    out = _out(new_version(db, user, project, row, version.text, fixed), version.version)
    out.fixed = done
    return out


class RemoveRefIn(BaseModel):
    kind: Literal["character", "place", "screen"]
    name: str  # as the problem or the shot shows it ("Nate")


PREFIXES = {"character": ("char:", "slot:"), "place": ("place:",), "screen": ("screen:",)}


@shots.post("/{shot_id}/remove-ref", response_model=BreakdownOut)
def remove_ref(
    project_id: int,
    shot_id: str,
    body: RemoveRefIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Take a character, place or screen out of one shot (free; the action stays as written).
    Undo saves the old breakdown back with PUT."""
    project, version = _working(db, user, project_id)
    row = _newest(db, project)
    bd = Breakdown.model_validate(row.data)
    shot = next((s for scene in bd.scenes for s in scene.shots if s.id == shot_id), None)
    if shot is None:
        raise HTTPException(404, "That shot isn't in this breakdown any more.")
    called = names(storyboard.assets(db, project))
    refs = [r for r in [*shot.character_ids, shot.place_id, *shot.screen_ids]
            if r and r.startswith(PREFIXES[body.kind])]  # fmt: skip
    ref = next(
        (
            r
            for r in refs
            if body.name.lower() in (r, called.get(r, advice.KIND[r[: r.index(":")]]).lower())
        ),
        None,
    )
    if ref is None:
        raise HTTPException(409, f"Shot {shot_id} doesn't have {body.name} any more.")
    fixed = breakdown_fix.remove_ref(bd, shot_id, ref)
    out = _out(new_version(db, user, project, row, version.text, fixed), version.version)
    out.fixed = [f"Removed {body.name} from shot {shot_id}."]
    return out
