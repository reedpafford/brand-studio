"""Projects and their credit budget. Editors set a planned length; the budget is 2x the 480p
estimate of it. Above the owner's length limit a project waits for the owner.
Editors see credits and % of budget, never dollars."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import looks, narration, needs_you, plans, reference
from app.auth import current_user, owner_only, user_name
from app.credits import credits_used, get_limits, lock, over_cap, own_script, price
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.brands import BrandScreen
from app.models.credits import BUDGET_MULTIPLIER
from app.models.jobs import Job, JobStatus
from app.models.library import Kind
from app.models.projects import Project, ProjectStatus
from app.models.script_library import ScriptDraft
from app.routes import references
from app.routes.brands import get_brand
from app.routes.files import get_file
from app.routes.jobs import stop_jobs
from app.routes.library import pick_item
from app.routes.production import progress
from app.schemas import LongText, Name, ShortText, UtcTime

router = APIRouter(prefix="/projects", tags=["credits"])


ASPECTS = Literal["9:16", "1:1", "16:9", "4:3", "3:4", "21:9"]


class BriefPatch(BaseModel):
    """The brief. On PATCH, send only what changes."""

    goal: LongText | None = None
    platform: ShortText | None = None
    aspect_ratio: ASPECTS | None = None
    format: ShortText | None = None
    cast_ids: list[int] | None = None  # library characters
    reference_file_id: int | None = None  # a video
    product_variants: dict[str, str] | None = None  # product -> the variant this video shows
    reference_breakdown: dict | None = None  # the reel to adapt (docs/references shape)
    reference_replace: LongText | None = None  # which part to rebuild, e.g. "the montage"


class ProjectIn(BriefPatch):
    reference_id: str | None = None  # a reel from GET /references: its breakdown is copied in
    brand_id: int
    name: Name
    planned_seconds: int | None = Field(None, gt=0, le=3600)  # null: the breakdown decides


class ProjectPatch(BriefPatch):
    reference_id: str | None = None  # a reel from GET /references: its breakdown is copied in
    name: Name | None = None
    look: str | None = None  # VS1: the video's own look (its stills and clips go out of date)
    planned_seconds: int | None = Field(None, gt=0, le=3600)


class ProjectOut(BaseModel):
    id: int
    plan_status: str = (
        "none"  # 1b: none, ready or approved (the Plan step, "Approve the plan first")
    )
    plan_credits: int = 0  # Make the plan's price, before there's a plan to carry it
    brand_id: int
    name: str
    song: bool = False  # made from a Song script: timed to its song (song_take_id)
    song_take_id: int | None = None
    look: str = "house"  # how its pictures are drawn (VS1)
    look_redo_credits: float = 0  # redrawing and remaking what was made in another look (VS1)
    planned_seconds: int | None  # a set length; null: the breakdown decides
    breakdown_seconds: int | None  # the newest breakdown's length
    status: ProjectStatus
    goal: str
    platform: str
    aspect_ratio: str
    format: str
    cast_ids: list[int]
    reference_file_id: int | None
    product_variants: dict[str, str]
    reference_breakdown: dict | None
    reference_replace: str
    estimate_credits: float
    budget_credits: float
    credits_used: float
    budget_pct: float
    created_by_id: int | None  # who asked (for the owner's Approvals list)
    created_by_name: str
    script_draft_id: int | None = None  # made from a library version; null: an earlier-style video
    own_script: bool = False  # from a script the viewer wrote: it runs on their weekly allowance
    archived_at: UtcTime | None = None  # put away; POST .../unarchive brings it back
    finished_at: UtcTime | None = None  # "Video done": the whole video was downloaded
    # The last still redraw after a cast change, for the Storyboard note: {"redrawn_for_cast":
    # {count, credits}} or {"redraw_refused": {count, credits, reason}}.
    cast_redraw: dict | None = None
    # On the Videos list: its newest still (null before any), and its step as In production
    # names it, or "done" once finished.
    poster_file_id: int | None = None
    step: Literal["breakdown", "assets", "storyboard", "clips", "downloads", "done"] | None = None
    final_out_of_date: bool = False  # finished, but its clips changed since: "changes waiting"
    # On the Videos list (audit M6): it waits on its editor, and for what ("3 stills ready to
    # check"); null when nothing is theirs to do (app/needs_you.py)
    needs_you: bool = False
    waiting_on: str | None = None


def archive(db: Session, project: Project) -> None:
    """Put a video away (or release its version): hidden from lists, and every job of it that
    hasn't finished stops (`stop_jobs`; live test: a released video's breakdown went on and
    charged 3.92). Cancelled jobs aren't counted, so its credits come back."""
    project.archived_at = utcnow()
    stop_jobs(db, Job.project_id == project.id)


def _mine(db: Session, user: User, project_id: int) -> Project:
    project = get_project(db, user, project_id)
    if not (user.is_owner or project.created_by_id == user.id):
        raise HTTPException(403, "Only whoever made this video, or the owner, can do that.")
    return project


def get_project(db: Session, user: User, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project or project.workspace_id != user.workspace_id:
        raise HTTPException(404, "No such project.")
    return project


def _is_song(db: Session, project: Project) -> bool:
    from app.models.script_library import Script, ScriptDraft

    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    return bool(draft) and db.get(Script, draft.script_id).kind in narration.TIMED


def _out(db: Session, project: Project, user: User, old: set[int] | None = None) -> ProjectOut:
    """`old`: the finished videos out of date (`out_of_date`), read once for a whole list."""
    from app.routes.project_clips import out_of_date

    used = credits_used(db, project)
    return ProjectOut(
        final_out_of_date=project.id in (out_of_date(db, [project]) if old is None else old),
        id=project.id,
        brand_id=project.brand_id,
        name=project.name,
        song=_is_song(db, project),
        song_take_id=project.song_take_id,
        look=project.look,
        look_redo_credits=looks.redo_credits(db, project),
        planned_seconds=project.planned_seconds,
        breakdown_seconds=project.breakdown_seconds,
        status=project.status,
        **{f: getattr(project, f) for f in BRIEF_FIELDS},
        estimate_credits=project.estimate_credits,
        budget_credits=project.budget_credits,
        credits_used=used,
        budget_pct=round(float(used / project.budget_credits * 100), 1),
        created_by_id=project.created_by_id,
        created_by_name=user_name(db, project.created_by_id),
        script_draft_id=project.script_draft_id,
        own_script=own_script(db, project, user),
        archived_at=project.archived_at,
        finished_at=project.finished_at,
        cast_redraw=project.cast_redraw,
        plan_status=plans.status(db, project),
        plan_credits=price(plans.price(db, project)),
    )


BRIEF_FIELDS = tuple(BriefPatch.model_fields)


def _set_brief(db: Session, user: User, project: Project, values: dict) -> None:
    """Apply sent brief fields. Cast must be the workspace's characters; the reference a video.
    A null reference file or breakdown removes it; any other null means "unchanged"."""
    removable = ("reference_file_id", "reference_breakdown")
    for field in BRIEF_FIELDS:
        if field not in values or (values[field] is None and field not in removable):
            continue
        value = values[field]
        if field == "cast_ids":
            value = sorted(set(value))
            for item_id in value:
                pick_item(db, user, Kind.character, item_id, project)
        elif field == "reference_file_id" and value is not None:
            get_file(db, user, value, "video")
        elif field == "reference_breakdown" and value is not None:
            value = reference.checked(value)
        elif field == "product_variants":
            value = _check_variants(db, project.brand_id, value)
        setattr(project, field, value)


def _check_variants(db: Session, brand_id: int, chosen: dict[str, str]) -> dict[str, str]:
    """Each chosen variant must be one of the brand's versions of that product."""
    screens = db.scalars(
        select(BrandScreen).where(
            BrandScreen.brand_id == brand_id, BrandScreen.deleted_at.is_(None)
        )
    )
    offered: dict[str, set[str]] = {}
    for s in screens:
        if s.product and s.variant:
            offered.setdefault(s.product, set()).add(s.variant)
    for product, variant in chosen.items():
        if variant not in offered.get(product, set()):
            options = ", ".join(sorted(offered.get(product, []))) or "none"
            raise HTTPException(422, f"{product} comes in: {options}.")
    return chosen


def _set_length(db: Session, user: User, project: Project, seconds: int | None) -> None:
    limits = get_limits(db, user.workspace_id)
    if (
        seconds is not None and seconds * BUDGET_MULTIPLIER > limits.per_video_max_credits
    ):  # budget = 2x 480p seconds
        longest = limits.per_video_max_credits // BUDGET_MULTIPLIER
        raise HTTPException(
            422,
            f"{over_cap(user, limits.per_video_max_credits).detail} "
            f"Plan {longest} seconds or less.",
        )
    project.planned_seconds = seconds
    if user.is_owner:
        project.status, project.approved_by_id = ProjectStatus.active, user.id


@router.get("", response_model=list[ProjectOut])
def list_projects(
    brand_id: int | None = None,
    archived: bool = False,  # true: the archived videos instead, so they can be brought back
    q: str = "",  # in the video's name (a script's title, and its version's)
    mine: bool = False,  # only the videos the caller started
    status: Literal["making", "done", "needs_you"] | None = None,  # done: "Video done"
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    query = select(Project).where(
        Project.workspace_id == user.workspace_id,
        Project.archived_at.is_not(None) if archived else Project.archived_at.is_(None),
    )
    if brand_id is not None:
        query = query.where(Project.brand_id == brand_id)
    if q.strip():
        query = query.where(Project.name.ilike(f"%{q.strip()}%"))
    if mine:
        query = query.where(Project.created_by_id == user.id)
    if status in ("making", "done"):
        done = Project.finished_at.is_not(None)
        query = query.where(done if status == "done" else ~done)
    found = db.scalars(query.order_by(func.lower(Project.name))).all()
    frames, steps = progress(db, [p.id for p in found])
    from app.routes.project_clips import out_of_date

    old = out_of_date(db, list(found))
    waits = needs_you.waiting_on(db, list(found), old)
    out = [_out(db, p, user, old) for p in found]
    for row, project in zip(out, found, strict=True):
        row.poster_file_id = (frames.get(project.id) or (None, None))[1]
        row.step = "done" if project.finished_at else steps[project.id]
        row.waiting_on = waits.get(project.id)
        row.needs_you = row.waiting_on is not None
    return [r for r in out if r.needs_you] if status == "needs_you" else out


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    body: ProjectIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    get_brand(db, user, body.brand_id)
    project = Project(
        workspace_id=user.workspace_id,
        brand_id=body.brand_id,
        name=body.name,
        created_by_id=user.id,
    )
    _set_length(db, user, project, body.planned_seconds)
    _set_brief(db, user, project, body.model_dump())
    if body.reference_id:
        project.reference_breakdown = references.load(request, body.reference_id)
    db.add(project)
    db.commit()
    return _out(db, project, user)


@router.post("/{project_id}/archive", response_model=ProjectOut)
def archive_project(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    project = _mine(db, user, project_id)
    if project.archived_at is None:
        archive(db, project)
        db.commit()
    return _out(db, project, user)


@router.post("/{project_id}/release", response_model=ProjectOut)
def release_project(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Put a started version back to "Ready to make": the owner, or the editor making it.
    Produce-once holds because the video goes too: it is archived (kept, not deleted; jobs
    that haven't started are cancelled, so their credits come back, and credits already used
    stay used) and unlinked from the version, which anyone may then make afresh. Restore
    undoes it while nobody has. A finished video can't be released."""
    project = get_project(db, user, project_id)
    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    if draft is None:
        raise HTTPException(409, "This video isn't made from a library version.")
    if not (user.is_owner or draft.reserved_by_id == user.id):
        raise HTTPException(403, "Only whoever is making it, or the owner, can release it.")
    if project.finished_at:
        raise HTTPException(409, "This video is done, so its version can't be released.")
    archive(db, project)
    project.script_draft_id, project.released_draft_id = None, draft.id
    draft.reserved_by_id = None
    db.commit()
    return _out(db, project, user)


@router.post("/{project_id}/restore", response_model=ProjectOut)
def restore_project(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Undo archive or release: the video comes back as it was (cancelled jobs stay
    cancelled; run them again). A released video gets its version back; once someone has
    started that version again it can't come back (one video per version)."""
    project = _mine(db, user, project_id)
    draft = db.get(ScriptDraft, project.released_draft_id) if project.released_draft_id else None
    again = draft and db.scalar(select(Project).where(Project.script_draft_id == draft.id))
    if again:
        who, letter = user_name(db, again.created_by_id) or "Someone", "ABC"[draft.slot]
        raise HTTPException(
            409, f"{who} started version {letter} again, so this video can't come back."
        )
    project.archived_at = None
    if draft is not None:
        project.script_draft_id, project.released_draft_id = draft.id, None
        draft.reserved_by_id = project.created_by_id
    db.commit()
    return _out(db, project, user)


@router.get("/{project_id}", response_model=ProjectOut)
def read_project(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return _out(db, get_project(db, user, project_id), user)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    body: ProjectPatch,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    project = get_project(db, user, project_id)
    if body.name is not None:
        project.name = body.name
    if body.look is not None:
        project.look = looks.pick(db, user, body.look)
    if "planned_seconds" in body.model_fields_set:  # null clears it: the breakdown decides
        _set_length(db, user, project, body.planned_seconds)
    _set_brief(db, user, project, body.model_dump(exclude_unset=True))
    if body.reference_id:
        project.reference_breakdown = references.load(request, body.reference_id)
    db.commit()
    return _out(db, project, user)


@router.post("/{project_id}/approve", response_model=ProjectOut)
def approve_project(
    project_id: int, owner: User = Depends(owner_only), db: Session = Depends(get_db)
):
    project = get_project(db, owner, project_id)
    done = db.execute(
        update(Project)
        .where(Project.id == project.id, Project.status == ProjectStatus.needs_owner_approval)
        .values(status=ProjectStatus.active, approved_by_id=owner.id)
    )
    if done.rowcount != 1:
        raise HTTPException(409, "This project isn't waiting for approval.")
    db.refresh(project)
    _release_held_jobs(db, owner, project)
    db.commit()
    return _out(db, project, owner)


def _release_held_jobs(db: Session, owner: User, project: Project) -> None:
    """Approving a project also releases the jobs held in it, oldest first, while they fit
    in its budget. Any that don't fit stay held for a separate decision."""
    lock(db, Project, project.id)
    used = credits_used(db, project)
    held = db.scalars(
        select(Job)
        .where(Job.project_id == project.id, Job.status == JobStatus.needs_owner_approval)
        .order_by(Job.id)
    )
    ceiling = project.budget_credits  # never above the per-video cap
    for job in held:
        if used + job.credits <= ceiling:
            job.status, job.approved_by_id = JobStatus.queued, owner.id
            used += job.credits
