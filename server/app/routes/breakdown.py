"""The project's breakdown: ask Claude for one from the working script, read the newest, or
save the editor's edited version. Each comes with the checks' problems in plain words."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from app import advice, breakdown, breakdown_fix, clip_prompts, storyboard
from app.advice import Said, names, plain
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.prompts.schemas import Breakdown
from app.routes.clips import generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.projects import get_project
from app.routes.scripts import latest

router = APIRouter(prefix="/projects/{project_id}/breakdown", tags=["breakdown"])
shots = APIRouter(prefix="/projects/{project_id}/shots", tags=["breakdown"])
WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)


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
        fixes=breakdown_fix.fixes(row.problems or []),
    )


def _working(db: Session, user: User, project_id: int):
    project = get_project(db, user, project_id)
    version = latest(db, project)
    if not version:
        raise HTTPException(409, "Add a script first.")
    return project, version


@router.post("", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)])
def make(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Queue a breakdown call (a paid Claude call, counted against the project budget)."""
    project, version = _working(db, user, project_id)
    pending = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING)))
    if any(j.input.get("step") == "breakdown" for j in pending):
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


@router.put("", response_model=BreakdownOut)
def save(
    project_id: int,
    body: Breakdown,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Save the editor's edited breakdown for the working script (a new row)."""
    project, version = _working(db, user, project_id)
    body = breakdown.as_roles(db, project, body)  # speakers are roles, never looks
    if unknown := breakdown.unknown_ids(db, project, body):
        called = {
            **breakdown.unknown_names(db, project, body),
            **names(storyboard.assets(db, project)),
        }
        said = plain(unknown, called)[0]
        raise HTTPException(422, f"{said}. Pick from the video's cast, places and screens.")
    breakdown.record_length(project, body)
    row = BreakdownVersion(
        project_id=project.id,
        script_version=version.version,
        source="edit",
        data=body.model_dump(),
        problems=breakdown.problems(db, project, version.text, body),
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
    new = BreakdownVersion(
        project_id=project.id,
        script_version=row.script_version,
        source="edit",
        data=fixed.model_dump(),
        problems=breakdown.problems(db, project, version.text, fixed),
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

    new = BreakdownVersion(
        project_id=project.id,
        script_version=row.script_version,
        source="edit",
        data=bd.model_dump(),
        problems=breakdown.problems(db, project, text, bd),
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
    m = breakdown.video_model()
    fixed, done = breakdown_fix.repair(
        version.text, Breakdown.model_validate(row.data), asked, m.duration.min, m.duration.max
    )
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
