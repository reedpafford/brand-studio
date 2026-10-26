"""Reel import (docs/design/reel-import-server.md): a script made from an uploaded reel or an
Instagram link. Getting and preparing the reel is free (`reel_prepare` on the `local`
provider); the paid read comes later. Status is worked out, never stored."""

import hashlib
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import reel as media
from app import reel_read as read
from app import script_library as lib
from app import script_write
from app.auth import current_user
from app.credits import credits_left
from app.db import get_db
from app.filetypes import matches
from app.models.accounts import User
from app.models.files import StoredFile
from app.models.jobs import Job, JobStatus
from app.models.script_library import Script, ScriptDraft
from app.routes.brands import get_brand
from app.routes.clips import generation_on
from app.routes.jobs import enqueue

router = APIRouter(prefix="/scripts", tags=["reel import"])
UNTITLED = "Untitled reel"
VIDEO_TYPES = ("video/mp4", "video/quicktime")  # both start with an ftyp box
CHUNK = 1024 * 1024
MAX_BYTES = media.MAX_MB * 1024 * 1024
UPLOAD_PATHS = r"/scripts(/\d+)?/import/upload"
PREPARE_FAILED = "We couldn't prepare this reel. Upload it again."
Title = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class LinkIn(BaseModel):
    brand_id: int
    url: Annotated[str, StringConstraints(max_length=500)]
    title: Title | None = None
    new_lines: bool | None = None


class Estimate(BaseModel):
    credits: float  # every step still to run, together
    credits_left: float | None  # an editor's weekly allowance left; null for the owner
    # How often the step it starts from has been tried already: a retry is charged again, so
    # after 2 failed tries the screen says so before the next press.
    tries: int = 0


class ImportOut(BaseModel):
    script_id: int
    status: Literal["preparing", "ready", "reading", "done", "failed"]
    source: str  # upload | link
    url: str | None = None
    seconds: float | None = None
    shots: int | None = None
    transcript: list[dict] = []  # [{start, end, text, speaker}]
    video_file_id: int | None = None
    contact_file_id: int | None = None
    problem: str = ""  # plain words for the editor
    problem_code: str | None = None  # blocked | gone | bad_file | too_long
    steps_done: list[str] = []  # of watch, write, cast
    watched_from: str | None = None  # video | frames (Gemini couldn't take the video)
    failed_step: str | None = None  # prepare | watch | write | cast
    estimate: Estimate | None = None  # once ready: what "Read this reel" costs now


def _out(db: Session, script: Script, user: User) -> ImportOut:
    reel = script.reel or {}
    status, failed = read.state(db, script)
    problem, code = reel.get("problem", ""), reel.get("problem_code")
    if failed == "prepare":
        problem = problem or PREPARE_FAILED
    elif failed:
        problem = f"{read.NAMES[failed]} didn't finish. Nothing more was charged; try again."
    estimate = None
    if status in ("ready", "failed") and failed != "prepare":
        left = credits_left(db, user)
        estimate = Estimate(
            credits=read.price(db, user, read.remaining(script)),
            credits_left=None if left is None else max(left, 0),
            tries=(reel.get("tries") or {}).get(failed or "", 0),
        )
    return ImportOut(
        script_id=script.id,
        status=status,
        source=reel.get("source", "upload"),
        url=reel.get("url"),
        seconds=reel.get("seconds"),
        shots=(reel.get("stats") or {}).get("shots"),
        transcript=reel.get("transcript", []),
        video_file_id=reel.get("video_file_id"),
        contact_file_id=reel.get("contact_file_id"),
        problem=problem,
        problem_code=code,
        steps_done=reel.get("done", []),
        watched_from=reel.get("watched_from"),
        failed_step=failed,
        estimate=estimate,
    )


async def _store_video(request: Request, user: User, db: Session, file: UploadFile) -> StoredFile:
    if file.content_type not in VIDEO_TYPES:
        raise HTTPException(415, "That file isn't a video we can read. Use an MP4 or MOV.")
    chunks, size = [], 0
    while chunk := await file.read(CHUNK):
        size += len(chunk)
        if size > MAX_BYTES:
            raise HTTPException(
                413, f"This video is over {media.MAX_MB} MB. Upload a smaller copy."
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    if not matches("video/mp4", data[:16]):
        raise HTTPException(415, "That file isn't a video we can read. Use an MP4 or MOV.")
    key = f"{user.workspace_id}/{uuid.uuid4().hex}"
    request.app.state.storage.put(key, data)
    stored = StoredFile(
        workspace_id=user.workspace_id,
        key=key,
        filename=(file.filename or "reel.mp4")[:255],
        content_type=file.content_type,
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        uploaded_by_id=user.id,
    )
    db.add(stored)
    db.flush()
    return stored


def _new_script(db: Session, user: User, brand_id: int, title: str | None, new_lines) -> Script:
    get_brand(db, user, brand_id)
    script = Script(
        workspace_id=user.workspace_id,
        brand_id=brand_id,
        title=title or UNTITLED,
        created_by_id=user.id,
        new_lines=bool(new_lines),
    )
    db.add(script)
    db.flush()
    db.add(ScriptDraft(script_id=script.id, slot=0, text=""))
    return script


def one_at_a_time(
    db: Session, user: User, busy: str = "You have a reel being prepared. Try again when it's done."
) -> None:
    """One reel (or one bulk batch) being prepared per person, so one editor can't fill the
    prep queue."""
    waiting = select(Job.id).where(
        Job.kind == "reel_prepare",
        Job.created_by_id == user.id,
        Job.status.in_((JobStatus.queued, JobStatus.running)),
    )
    if db.scalar(waiting.limit(1)):
        raise HTTPException(409, busy)


def drop_files(db: Session, reel: dict | None) -> list[str]:
    """Delete a reel's own file rows (its video and contact sheet), e.g. when it's replaced.
    Returns their storage keys: delete those bytes only once the deletion is committed, so a
    refused request never leaves a row whose bytes are gone."""
    keys = []
    ids = [(reel or {}).get(k) for k in ("video_file_id", "contact_file_id", "watch_file_id")]
    for file_id in [*ids, *(reel or {}).get("grid_file_ids", [])]:
        if (stored := db.get(StoredFile, file_id or 0)) is not None:
            keys.append(stored.key)
            db.delete(stored)
    return keys


def delete_bytes(request: Request, keys: list[str]) -> None:
    for key in keys:
        request.app.state.storage.delete(key)


def prepare(db: Session, user: User, script: Script, reel: dict, job_input: dict) -> None:
    """Queue the free `reel_prepare` job and point the script at it."""
    script.reel = reel
    db.flush()
    job = enqueue(
        db,
        user,
        "reel_prepare",
        {"step": "reel_prepare", "script_id": script.id, **job_input},
        units=0,
        provider="local",
    )
    script.reel_job_id = job.id
    db.commit()


@router.post("/import/upload", response_model=ImportOut, status_code=201)
async def import_upload(
    request: Request,
    file: UploadFile,
    brand_id: int = Form(),
    title: str | None = Form(None, max_length=200),
    new_lines: bool | None = Form(None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """A new script from an uploaded reel (mp4 or mov, up to 100 MB and 90 seconds)."""
    one_at_a_time(db, user)
    script = _new_script(db, user, brand_id, (title or "").strip(), new_lines)
    stored = await _store_video(request, user, db, file)
    reel = {"source": "upload", "video_file_id": stored.id}
    prepare(db, user, script, reel, {"video_key": stored.key})
    return _out(db, script, user)


@router.post("/import/link", response_model=ImportOut, status_code=201)
def import_link(body: LinkIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """A new script from an Instagram reel link. The worker fetches it; if Instagram refuses,
    the script stays and says to upload the video instead."""
    url = media.reel_link(body.url)
    if not url:
        raise HTTPException(422, "That isn't an Instagram reel link.")
    one_at_a_time(db, user)
    script = _new_script(db, user, body.brand_id, body.title, body.new_lines)
    prepare(db, user, script, {"source": "link", "url": url}, {"url": url})
    return _out(db, script, user)


@router.post("/{script_id}/import/upload", response_model=ImportOut)
async def replace_with_upload(
    script_id: int,
    request: Request,
    file: UploadFile,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Upload the video to a script whose reel couldn't be fetched (or to try another one)."""
    script = lib.editable(user, lib.get_script(db, user, script_id))
    if script.reel is None:
        raise HTTPException(409, "This script isn't made from a reel.")
    if read.state(db, script)[0] in ("preparing", "reading"):
        raise HTTPException(409, "This reel is still being prepared or read.")
    if script.reference_breakdown:
        raise HTTPException(409, "This reel has been read already.")
    one_at_a_time(db, user)
    stored = await _store_video(request, user, db, file)  # checked before anything goes
    old = drop_files(db, script.reel)  # the old video and sheet aren't needed any more
    reel = {"source": "upload", "url": script.reel.get("url"), "video_file_id": stored.id}
    prepare(db, user, script, reel, {"video_key": stored.key})  # commits
    delete_bytes(request, old)
    return _out(db, script, user)


@router.get("/{script_id}/import", response_model=ImportOut)
def read_import(script_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    script = lib.get_script(db, user, script_id)
    if script.reel is None:
        raise HTTPException(404, "This script isn't made from a reel.")
    return _out(db, script, user)


@router.post(
    "/{script_id}/import/read",
    response_model=ImportOut,
    status_code=201,
    dependencies=[Depends(generation_on)],
)
def read_reel(script_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Read this reel: watch, write and cast read, priced together and paid for once. An
    editor's allowance must cover every step left, or nothing runs. After a failed step,
    pressing again retries from it at the price of what's left."""
    script = lib.editable(user, lib.get_script(db, user, script_id))
    status, failed = read.state(db, script)
    if status in ("preparing", "reading"):
        raise HTTPException(409, "This reel is still being prepared or read.")
    if status == "done" or failed == "prepare":
        raise HTTPException(409, "There's nothing to read: the reel is done or wasn't prepared.")
    if (original := script_write.original(db, script)) and original.status == "approved":
        raise HTTPException(409, "Version A is approved, so the reel can't rewrite it.")
    if read.needs_upload(script):
        raise HTTPException(409, "Upload the video again so this reel can be read.")
    steps = read.remaining(script)
    total, left = read.price(db, user, steps), credits_left(db, user)
    if left is not None and total > left:
        raise HTTPException(
            409,
            f"This reel needs {total:.0f} credits; you have {max(left, 0):.0f} left this week.",
        )
    read.queue(db, user, script, steps[0])
    return _out(db, script, user)


def save_prepared(db: Session, job: Job) -> None:
    """The worker's `reel_prepare` answer onto the script (called once the job succeeds)."""
    script = read.latest(db, job)
    if not script or script.reel_job_id != job.id:
        return  # a newer upload replaced this one
    output = job.output or {}
    reel = {k: v for k, v in (script.reel or {}).items() if k not in ("problem", "problem_code")}
    if output.get("problem"):
        reel |= {"problem": output["problem"], "problem_code": output.get("problem_code")}
        if (video := db.get(StoredFile, reel.pop("video_file_id", None) or 0)) is not None:
            db.delete(video)  # an upload we can't read; the local provider removed its bytes
    else:
        named = list(zip(output.get("files", []), output.get("file_ids", []), strict=False))
        files = dict(named)
        reel["grid_file_ids"] = [i for name, i in named if name == "grid"]
        reel |= {k: output[k] for k in ("seconds", "cuts", "stats", "transcript")}
        reel["contact_file_id"] = files.get("contact")
        reel["watch_file_id"] = files.get("watch")
        if "video" in files:
            reel["video_file_id"] = files["video"]
        if script.title == UNTITLED:  # named from its caption, else its first line
            script.title = media.name_for(output.get("caption", ""), reel["transcript"]) or (
                UNTITLED
            )
    script.reel = reel
