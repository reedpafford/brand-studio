"""A project's clips: ask Claude for one video prompt per clip of the newest breakdown, edit
them, generate takes with the video model, pick and approve one per clip, and stitch the
picked takes into the finished video (free)."""

import hashlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import advice, clip_prompts, clip_takes, cut_in
from app.auth import current_user
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.files import StoredFile
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.prompts.schemas import Breakdown, ClipPrompt, Reference
from app.routes.clips import _check_media_length, generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.projects import get_project
from app.routes.scripts import latest
from app.routes.storyboard import _newest_breakdown
from app.schemas import LongText

router = APIRouter(prefix="/projects/{project_id}", tags=["project clips"])
WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)


class ProjectClipIn(BaseModel):
    prompt: LongText
    references: list[Reference] = Field(max_length=50)


class TakeOut(BaseModel):
    id: int
    number: int
    file_id: int


class VideoOut(BaseModel):
    file_id: int
    take_ids: list[int]  # the picked takes it was made from, in clip order
    out_of_date: bool  # a pick or a "Use the real image" switch changed since


class InsertOut(BaseModel):
    """An insert shot (brand screens, no people): "Use the real image" cuts the real picture
    in over this stretch of the clip when the video is made."""

    shot_id: str
    asset_id: str
    name: str
    start: float  # seconds into the clip, as planned
    end: float
    use_real_image: bool


class InsertIn(BaseModel):
    use_real_image: bool


class ProjectClipOut(BaseModel):
    id: int
    clip_id: str
    seconds: int
    prompt: str
    references: list[Reference]
    problems: list[str]
    kept: list[str]  # advice kept anyway (never blocks)
    file_id: int | None  # the picked take's video
    takes: list[TakeOut]
    picked_take_id: int | None
    approved: bool
    take_credits: float  # what one more take costs (shown on Make clip / Redo)
    stale: bool  # made from an older breakdown
    inserts: list[InsertOut]


def _takes(db: Session, row: ProjectClip) -> list[ClipTake]:
    return list(
        db.scalars(select(ClipTake).where(ClipTake.clip_id == row.id).order_by(ClipTake.number))
    )


def _stale(db: Session, row: ProjectClip, newest: BreakdownVersion | None) -> bool:
    """Made from an older breakdown, or the breakdown is for an older script version."""
    working = latest(db, db.get(Project, row.project_id))
    return (
        not newest
        or row.breakdown_id != newest.id
        or bool(working and newest.script_version != working.version)
    )


def _out(db: Session, row: ProjectClip, newest: BreakdownVersion | None) -> ProjectClipOut:
    computed = ("stale", "takes", "take_credits", "inserts")
    project = db.get(Project, row.project_id)
    inserts = [InsertOut(**vars(i), use_real_image=i.on) for i in cut_in.inserts(db, project, row)]
    return ProjectClipOut(
        inserts=inserts,
        **{f: getattr(row, f) for f in ProjectClipOut.model_fields if f not in computed},
        takes=[TakeOut(id=t.id, number=t.number, file_id=t.file_id) for t in _takes(db, row)],
        take_credits=clip_takes.take_credits(db, project, row),
        stale=_stale(db, row, newest),
    )


def _clip(db: Session, user: User, project_id: int, clip_id: int):
    project = get_project(db, user, project_id)
    row = db.get(ProjectClip, clip_id)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "No such clip.")
    return project, row


def _clips(db: Session, project_id: int) -> list[ProjectClip]:
    query = select(ProjectClip).where(ProjectClip.project_id == project_id).order_by(ProjectClip.id)
    return list(db.scalars(query))


@router.post(
    "/clips/prompts", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)]
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
    steps = {j.input.get("step") for j in pending}
    if "clip_take" in steps:  # new prompts replace the clips; a take on its way would be lost
        raise HTTPException(409, "Wait for the clips being made to finish first.")
    if "clip_prompts" in steps:
        raise HTTPException(409, "Clip prompts are already being written for this project.")
    return enqueue(
        db,
        user,
        "write-claude",
        clip_prompts.job_input(db, project, bd),
        project=project,
        provider="claude",
    )


@router.get("/clips", response_model=list[ProjectClipOut])
def list_clips(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = get_project(db, user, project_id)
    newest = _newest_breakdown(db, project)
    return [_out(db, r, newest) for r in _clips(db, project.id)]


@router.put("/clips/{clip_id}", response_model=ProjectClipOut)
def edit_clip(
    project_id: int,
    clip_id: int,
    body: ProjectClipIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Edit a clip's prompt or references; its problems are checked again."""
    project, row = _clip(db, user, project_id, clip_id)
    row.prompt, row.references = body.prompt, [r.model_dump() for r in body.references]
    bd = Breakdown.model_validate(db.get(BreakdownVersion, row.breakdown_id).data)
    clip = ClipPrompt(clip_id=row.clip_id, seconds=row.seconds, **body.model_dump())
    row.problems = clip_prompts.clip_problems(db, project, bd, clip)
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


class TakeIn(BaseModel):
    note: str = Field("", max_length=500)  # Redo: "What's wrong?" (this take only)


@router.post(
    "/clips/{clip_id}/generate",
    response_model=JobOut,
    status_code=201,
    dependencies=[Depends(generation_on)],
)
def generate(
    project_id: int,
    clip_id: int,
    request: Request,
    body: TakeIn | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Make a new take of this clip (a paid video job, counted against the project budget and
    its per-video cap). A clip with problems must be fixed first."""
    project, row = _clip(db, user, project_id, clip_id)
    if advice.blocking(row.problems):  # "Advice: …" never blocks
        raise HTTPException(409, "Fix this clip's problems first.")
    if _stale(db, row, _newest_breakdown(db, project)):
        raise HTTPException(
            409, "This clip was made for an older breakdown. Write the clip prompts again first."
        )
    pending = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING)))
    if any(j.input.get("project_clip_id") == row.id for j in pending):
        raise HTTPException(409, "A take of this clip is already being made.")
    job_input = clip_takes.take_input(db, project, row, body.note if body else "")
    model = clip_takes.video_model()
    files = {k: job_input["files"].get(k, []) for k in clip_takes.KEYS.values()}
    _check_media_length(db, request.app.state.storage, model, files)
    return enqueue(
        db, user, "video", job_input, units=row.seconds, project=project, provider="replicate"
    )


@router.post("/clips/{clip_id}/takes/{take_id}/pick", response_model=ProjectClipOut)
def pick_take(
    project_id: int,
    clip_id: int,
    take_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Use this take in the video. Picking another take removes the approval."""
    project, row = _clip(db, user, project_id, clip_id)
    take = db.get(ClipTake, take_id)
    if not take or take.clip_id != row.id:
        raise HTTPException(404, "No such take.")
    if row.picked_take_id != take.id:
        clip_takes.pick(row, take)
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


@router.post("/clips/{clip_id}/approve", response_model=ProjectClipOut)
def approve(
    project_id: int,
    clip_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """✓ Looks good: approve the picked take."""
    project, row = _clip(db, user, project_id, clip_id)
    if not row.picked_take_id:
        raise HTTPException(409, "Make a take of this clip first.")
    row.approved = True
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


@router.put("/clips/{clip_id}/inserts/{shot_id}", response_model=ProjectClipOut)
def set_insert(
    project_id: int,
    clip_id: int,
    shot_id: str,
    body: InsertIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Switch "Use the real image" for one insert shot. Free: it applies when the video is
    made, so the take and its approval stay."""
    project, row = _clip(db, user, project_id, clip_id)
    if shot_id not in {i.shot_id for i in cut_in.inserts(db, project, row)}:
        raise HTTPException(404, "That shot isn't an insert in this clip.")
    row.real_images = {**(row.real_images or {}), shot_id: body.use_real_image}
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


def _cut_ins(db: Session, project: Project, clips: list[ProjectClip]) -> list[str]:
    return [
        f"{c.clip_id}/{i.shot_id}" for c in clips for i in cut_in.inserts(db, project, c) if i.on
    ]


@router.post("/clips/{clip_id}/keep", response_model=ProjectClipOut)
def keep_clip_advice(
    project_id: int,
    clip_id: int,
    body: advice.KeepIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Keep anyway: this clip's advice stays as it is."""
    project, row = _clip(db, user, project_id, clip_id)
    advice.keep(row, body.problem)
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


@router.delete("/clips/{clip_id}/approve", response_model=ProjectClipOut)
def unapprove(
    project_id: int,
    clip_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    project, row = _clip(db, user, project_id, clip_id)
    row.approved = False
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


def _video_out(db: Session, video: FinalVideo) -> VideoOut:
    clips = _clips(db, video.project_id)
    current = [c.picked_take_id for c in clips]
    cuts = _cut_ins(db, db.get(Project, video.project_id), clips)
    old = video.take_ids != current or (video.cut_ins or []) != cuts
    return VideoOut(file_id=video.file_id, take_ids=video.take_ids, out_of_date=old)


@router.post("/video", response_model=VideoOut, status_code=201)
def make_video(
    project_id: int,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Stitch the picked takes, in clip order, into one MP4. Free: no credits, no provider."""
    project = get_project(db, user, project_id)
    clips = _clips(db, project.id)
    if not clips:
        raise HTTPException(409, "Write the clip prompts and make the clips first.")
    left = sum(not c.approved for c in clips)
    if left:
        raise HTTPException(409, f"Approve every clip to make the video ({left} left).")
    storage = request.app.state.storage
    try:
        videos = [_with_cut_ins(db, storage, project, c) for c in clips]
        data = clip_takes.stitch(videos, reencode=bool(_cut_ins(db, project, clips)))
    except Exception as exc:  # noqa: BLE001 - a bad clip file: say so plainly
        raise HTTPException(
            422, "The clips couldn't be put together. Redo the odd one out."
        ) from exc
    key = f"{project.workspace_id}/{uuid.uuid4().hex}"
    storage.put(key, data)
    stored = StoredFile(
        workspace_id=project.workspace_id,
        key=key,
        filename=f"{project.name[:200]}.mp4",
        content_type="video/mp4",
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        uploaded_by_id=user.id,
    )
    db.add(stored)
    db.flush()
    video = FinalVideo(
        project_id=project.id,
        file_id=stored.id,
        take_ids=[c.picked_take_id for c in clips],
        cut_ins=_cut_ins(db, project, clips),
        created_by_id=user.id,
    )
    db.add(video)
    project.finished_at = project.finished_at or utcnow()
    db.commit()
    return _video_out(db, video)


def _with_cut_ins(db: Session, storage, project: Project, clip: ProjectClip) -> bytes:
    """The picked take, with the real picture cut in over each insert that's switched on."""
    video = storage.get(db.get(StoredFile, clip.file_id).key)
    cuts = [
        (storage.get(db.get(StoredFile, i.file_id).key), i.start, i.end)
        for i in cut_in.inserts(db, project, clip)
        if i.on
    ]
    return cut_in.apply(video, cuts, clip.seconds) if cuts else video


@router.get("/video", response_model=VideoOut)
def read_video(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = get_project(db, user, project_id)
    video = db.scalar(
        select(FinalVideo)
        .where(FinalVideo.project_id == project.id)
        .order_by(FinalVideo.id.desc())
        .limit(1)
    )
    if not video:
        raise HTTPException(404, "This project has no video yet.")
    return _video_out(db, video)
