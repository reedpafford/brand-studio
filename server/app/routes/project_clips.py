"""A project's clips: ask Claude for one video prompt per clip of the newest breakdown, edit
them, generate takes with the video model, pick and approve one per clip, and stitch the
picked takes into the finished video (free)."""

import hashlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import advice, breakdown, change, clip_prompts, clip_takes, credits, cut_in
from app.advice import Said
from app.auth import current_user
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.files import StoredFile
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.prompts import check
from app.prompts.schemas import Breakdown, ClipPrompt, Reference
from app.routes.clips import _check_media_length, generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.projects import get_project
from app.routes.storyboard import ChangeIn, PriceOut, _newest_breakdown
from app.schemas import LongText, UtcTime
from app.sheets import require_looks
from app.storyboard import assets as picture_assets

router = APIRouter(prefix="/projects/{project_id}", tags=["project clips"])
WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)


class ProjectClipIn(BaseModel):
    prompt: LongText
    references: list[Reference] = Field(max_length=50)


class TakeOut(BaseModel):
    id: int
    number: int
    file_id: int
    created_at: UtcTime  # "made 10:42"


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
    problems: Said
    kept: Said  # advice kept anyway (never blocks)
    file_id: int | None  # the picked take's video
    takes: list[TakeOut]
    picked_take_id: int | None
    approved: bool
    prompt_ok: bool  # Looks good on the prompt; Make the takes waits for every clip's
    take_credits: float  # what one more take costs (shown on Make clip / Redo)
    stale: bool  # made from an older breakdown
    inserts: list[InsertOut]
    change: dict | None  # the last Change it note, as on a frame (app/change.py)
    free_fix_used: bool = False  # Fix this clip's prompt's free rewrite used for this prompt


def _takes(db: Session, row: ProjectClip) -> list[ClipTake]:
    return list(
        db.scalars(select(ClipTake).where(ClipTake.clip_id == row.id).order_by(ClipTake.number))
    )


_stale = clip_prompts.is_stale


def _out(db: Session, row: ProjectClip, newest: BreakdownVersion | None) -> ProjectClipOut:
    computed = ("stale", "takes", "take_credits", "inserts")
    project = db.get(Project, row.project_id)
    inserts = [InsertOut(**vars(i), use_real_image=i.on) for i in cut_in.inserts(db, project, row)]
    return ProjectClipOut(
        inserts=inserts,
        **{f: getattr(row, f) for f in ProjectClipOut.model_fields if f not in computed},
        takes=[
            TakeOut(id=t.id, number=t.number, file_id=t.file_id, created_at=t.created_at)
            for t in _takes(db, row)
        ],
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


class RewriteIn(BaseModel):
    clip_id: str | None = None  # one clip ("c2"); else every stale clip (and any new one)


class RewriteOut(BaseModel):
    clip_ids: list[str]  # the clips it would rewrite; [] when none is stale
    credits: int  # "up to": one Claude call, never charged above it


def _rewrite_ids(db: Session, project: Project, clip_id: str | None) -> list[str] | None:
    """None: every clip (no clips yet); else the clips to rewrite."""
    if not _clips(db, project.id):
        return None
    return clip_prompts.to_rewrite(db, project, clip_id)


@router.get("/clips/prompts/price", response_model=RewriteOut)
def rewrite_price(
    project_id: int,
    clip_id: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Rewrite clip prompts · N credits: for every stale clip, or one clip (?clip_id=c2)."""
    project = get_project(db, user, project_id)
    ids = _rewrite_ids(db, project, clip_id)
    bd = _newest_breakdown(db, project)
    every = [c["id"] for c in bd.data["clips"]] if bd else []
    return RewriteOut(
        clip_ids=every if ids is None else ids,
        credits=credits.price(clip_prompts.rewrite_price(db, project, ids)),
    )


@router.post(
    "/clips/prompts", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)]
)
def write_prompts(
    project_id: int,
    body: RewriteIn | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Write the clip prompts (a paid Claude call): all of them at first, then every stale
    clip, or one clip (Reed, 2026-10-26: Clips never dead-ends). Existing takes are kept as
    earlier takes (clip_prompts.save_clip_prompts)."""
    project = get_project(db, user, project_id)
    if not (bd := _newest_breakdown(db, project)):
        raise HTTPException(409, "Make a breakdown first.")
    require_looks(breakdown.would_show(db, project, bd.data), picture_assets(db, project), 409)
    ids = _rewrite_ids(db, project, body.clip_id if body else None)
    if ids == []:
        raise HTTPException(409, "No clip needs new prompts.")
    return clip_prompts.queue_rewrite(db, user, project, ids)


class FixOut(BaseModel):
    fixed: bool | None  # True: fixed now; None: Claude is fixing it (job); False: can't be
    before: str = ""
    after: str = ""
    reason: str = ""  # why it can't be fixed, in plain words
    job: JobOut | None = None  # the free rewrite of this clip, when the code couldn't fix it
    clip: ProjectClipOut


@router.post("/clips/{clip_id}/fix", response_model=FixOut)
def fix_clip(
    project_id: int, clip_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Fix this clip's prompt (spec one-click-fixes.md §5), free and never refused for money:
    its shape is put right in code (seconds, [Image1], audio, Summary and Keep lines); what
    the code can't fix, Claude rewrites for this clip only, charged to no budget or week.
    Looks good is cleared. Undo is PUT of the earlier prompt."""
    project, row = _clip(db, user, project_id, clip_id)
    newest = _newest_breakdown(db, project)
    bd = Breakdown.model_validate(db.get(BreakdownVersion, row.breakdown_id).data)
    was = ClipPrompt(clip_id=row.clip_id, seconds=row.seconds, prompt=row.prompt,
                     references=[Reference(**r) for r in row.references])  # fmt: skip
    if not advice.stops(row):
        raise HTTPException(409, "This clip has nothing to fix.")
    if running := clip_prompts.fixing(db, row):  # one in flight per clip: never a second call
        return FixOut(fixed=None, before=was.prompt, job=running, clip=_out(db, row, newest))
    now = clip_prompts.repair_shape(was, bd) if row.prompt else was  # unwritten: Claude
    problems = clip_prompts.clip_problems(db, project, bd, now)
    if now != was:
        row.same_fix = True  # the free fix's own change: its free rewrite stays counted
        row.prompt, row.seconds, row.problems = now.prompt, now.seconds, problems
        row.prompt_ok, row.approved = False, False
        row.change = {"note": "Fix this clip's prompt", "status": "done", "before": was.prompt,
                      "after": now.prompt, "unchanged": False}  # fmt: skip
        db.commit()
    if not advice.stops(row):
        return FixOut(fixed=True, before=was.prompt, after=now.prompt,
                      clip=_out(db, row, newest))  # fmt: skip
    if _stale(db, row, newest):
        return FixOut(fixed=False, clip=_out(db, row, newest), reason="This clip was made for an "
                      "older breakdown. Rewrite this clip's prompt first.")  # fmt: skip
    looks = [p for p in advice.stops(row) if "approved look" in p]
    if looks and len(looks) == len(advice.stops(row)):
        return FixOut(fixed=False, clip=_out(db, row, newest), reason=looks[0])
    if row.free_fix_used:  # once per clip per prompt version (Reed, 2026-10-27)
        raise HTTPException(409, "We couldn't fix this one automatically.")
    job = clip_prompts.queue_fix(db, user, project, row, advice.stops(row))
    return FixOut(fixed=None, before=was.prompt, job=job, clip=_out(db, row, newest))


@router.get("/clips", response_model=list[ProjectClipOut])
def list_clips(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = get_project(db, user, project_id)
    if clip_prompts.repair(db, project):  # free: a look approved or swapped since, never stuck
        db.commit()
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
    """Edit a clip's prompt or references; the cast's sheets are added if missing and its
    problems are checked again. Saving an edit counts as reading it (Looks good)."""
    project, row = _clip(db, user, project_id, clip_id)
    fix = (row.change or {}).get("note") == "Fix this clip's prompt"
    row.same_fix = fix and body.prompt == row.change.get("before")  # its Undo: still counted
    bd = Breakdown.model_validate(db.get(BreakdownVersion, row.breakdown_id).data)
    clip = ClipPrompt(clip_id=row.clip_id, seconds=row.seconds, **body.model_dump())
    clip = clip_prompts.with_cast(db, project, clip, bd, trim=False)
    row.prompt, row.references = clip.prompt, [r.model_dump() for r in clip.references]
    row.prompt_ok = True
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
    if advice.stops(row):  # advice and problems kept anyway never block
        raise HTTPException(409, "Fix this clip's problems first.")
    if _stale(db, row, _newest_breakdown(db, project)):
        raise HTTPException(
            409, "This clip was made for an older breakdown. Rewrite its prompt first."
        )
    pending = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING)))
    if any(j.input.get("project_clip_id") == row.id for j in pending):
        raise HTTPException(409, "A take of this clip is already being made.")
    note = body.note.strip() if body else ""
    if note:  # a Redo note never changes the dialogue
        bd = Breakdown.model_validate(db.get(BreakdownVersion, row.breakdown_id).data)
        if wrong := check.redo_note(note, bd, row.clip_id):
            raise HTTPException(422, " ".join(wrong))
    job_input = clip_takes.take_input(db, project, row, note)
    model = clip_takes.video_model()
    files = {k: job_input["files"].get(k, []) for k in clip_takes.KEYS.values()}
    _check_media_length(db, request.app.state.storage, model, files)
    return enqueue(
        db, user, "video", job_input, units=row.seconds, project=project, provider="replicate"
    )


@router.get("/clips/{clip_id}/change", response_model=PriceOut)
def change_price(
    project_id: int, clip_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    project, row = _clip(db, user, project_id, clip_id)
    return PriceOut(credits=credits.price(change.credits(db, project, row)))


@router.post(
    "/clips/{clip_id}/change",
    response_model=JobOut,
    status_code=201,
    dependencies=[Depends(generation_on)],
)
def change_clip(
    project_id: int,
    clip_id: int,
    body: ChangeIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Change it: the note rewrites this clip's prompt; once there's a take, a new take is
    made from it (one price). A note that changes what's said is refused before any charge."""
    project, row = _clip(db, user, project_id, clip_id)
    if _stale(db, row, _newest_breakdown(db, project)):
        raise HTTPException(
            409, "This clip was made for an older breakdown. Rewrite its prompt first."
        )
    return change.start(db, user, project, row, body.note)


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
    row.approved, row.change = True, None
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


@router.post("/clips/approve-all", response_model=advice.ApproveAllOut)
def approve_all(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Approve all (Reed, 2026-10-26): every clip with a picked take, made for the newest
    breakdown and with nothing to fix; the others are listed with why. Undo takes back
    exactly these."""
    project = get_project(db, user, project_id)
    newest = _newest_breakdown(db, project)
    approved, skipped = [], []
    for row in _clips(db, project.id):
        if row.approved:
            continue
        why = (
            "no take picked yet" if not row.picked_take_id
            else "made for an older breakdown" if _stale(db, row, newest)
            else "has a problem to fix" if advice.stops(row)
            else ""
        )  # fmt: skip
        if why:
            skipped.append({"id": row.id, "reason": why})
            continue
        row.approved, row.change = True, None
        approved.append(row.id)
    db.commit()
    return advice.ApproveAllOut(approved=approved, skipped=skipped)


@router.post("/clips/approve-all/undo", response_model=list[ProjectClipOut])
def undo_approve_all(
    project_id: int,
    body: advice.UndoIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Undo Approve all: exactly the clips it approved go back to not approved."""
    project = get_project(db, user, project_id)
    for row in _clips(db, project.id):
        if row.id in body.ids:
            row.approved = False
    db.commit()
    return list_clips(project_id, user, db)


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


@router.post("/clips/{clip_id}/prompt-ok", response_model=ProjectClipOut)
def prompt_looks_good(
    project_id: int, clip_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Looks good: the editor read this clip's prompt (and what a note changed in it)."""
    project, row = _clip(db, user, project_id, clip_id)
    row.prompt_ok = True
    if not row.picked_take_id:
        row.change = None
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


@router.delete("/clips/{clip_id}/prompt-ok", response_model=ProjectClipOut)
def undo_prompt_looks_good(
    project_id: int, clip_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    project, row = _clip(db, user, project_id, clip_id)
    row.prompt_ok = False
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


@router.post("/clips/{clip_id}/keep", response_model=ProjectClipOut)
def keep_clip_advice(
    project_id: int,
    clip_id: int,
    body: advice.KeepIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Keep anyway: this clip's advice stays as it is. A blocking problem can be kept too once
    the free fix was tried (one-click-fixes.md §5); it then stops blocking the takes."""
    project, row = _clip(db, user, project_id, clip_id)
    tried = row.free_fix_used and bool(row.prompt)  # an unwritten clip has nothing to keep
    advice.keep(
        row, body.problem, None if tried else "Try Fix this clip's prompt first. It's free."
    )
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


@router.delete("/clips/{clip_id}/keep", response_model=ProjectClipOut)
def unkeep_clip_advice(
    project_id: int,
    clip_id: int,
    problem: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Undo Keep anyway on this clip's advice or kept problem (?problem=, the text as shown)."""
    project, row = _clip(db, user, project_id, clip_id)
    advice.unkeep(row, problem)
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
