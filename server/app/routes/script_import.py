"""Reel import (docs/design/reel-import-server.md): a script made from an uploaded reel or an
Instagram link. Getting and preparing the reel is free (`reel_prepare` on the `local`
provider); the paid read comes later. Status is worked out, never stored."""

import hashlib
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, StringConstraints
from sqlalchemy.orm import Session

from app import reel as media
from app import script_library as lib
from app.auth import current_user
from app.db import get_db
from app.filetypes import matches
from app.models.accounts import User
from app.models.files import StoredFile
from app.models.jobs import Job, JobStatus
from app.models.script_library import Script, ScriptDraft
from app.routes.brands import get_brand
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


class ImportOut(BaseModel):
    script_id: int
    status: Literal["preparing", "ready", "failed"]
    source: str  # upload | link
    url: str | None = None
    seconds: float | None = None
    shots: int | None = None
    transcript: list[dict] = []  # [{start, end, text, speaker}]
    video_file_id: int | None = None
    contact_file_id: int | None = None
    problem: str = ""  # plain words for the editor
    problem_code: str | None = None  # blocked | gone | bad_file | too_long


def _out(db: Session, script: Script) -> ImportOut:
    reel = script.reel or {}
    job = db.get(Job, script.reel_job_id) if script.reel_job_id else None
    problem, code = reel.get("problem", ""), reel.get("problem_code")
    if job and job.status in (JobStatus.queued, JobStatus.running):
        status = "preparing"
    elif problem or not job or job.status != JobStatus.succeeded:
        status, problem = "failed", problem or PREPARE_FAILED
    else:
        status = "ready"
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


def _prepare(db: Session, user: User, script: Script, reel: dict, job_input: dict) -> None:
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
    script = _new_script(db, user, brand_id, (title or "").strip(), new_lines)
    stored = await _store_video(request, user, db, file)
    reel = {"source": "upload", "video_file_id": stored.id}
    _prepare(db, user, script, reel, {"video_key": stored.key})
    return _out(db, script)


@router.post("/import/link", response_model=ImportOut, status_code=201)
def import_link(body: LinkIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """A new script from an Instagram reel link. The worker fetches it; if Instagram refuses,
    the script stays and says to upload the video instead."""
    url = media.reel_link(body.url)
    if not url:
        raise HTTPException(422, "That isn't an Instagram reel link.")
    script = _new_script(db, user, body.brand_id, body.title, body.new_lines)
    _prepare(db, user, script, {"source": "link", "url": url}, {"url": url})
    return _out(db, script)


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
    if _out(db, script).status == "preparing":
        raise HTTPException(409, "This reel is still being prepared.")
    if script.reference_breakdown:
        raise HTTPException(409, "This reel has been read already.")
    stored = await _store_video(request, user, db, file)
    reel = {"source": "upload", "url": script.reel.get("url"), "video_file_id": stored.id}
    _prepare(db, user, script, reel, {"video_key": stored.key})
    return _out(db, script)


@router.get("/{script_id}/import", response_model=ImportOut)
def read_import(script_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    script = lib.get_script(db, user, script_id)
    if script.reel is None:
        raise HTTPException(404, "This script isn't made from a reel.")
    return _out(db, script)


def save_prepared(db: Session, job: Job) -> None:
    """The worker's `reel_prepare` answer onto the script (called once the job succeeds)."""
    script = db.get(Script, job.input["script_id"])
    if not script or script.reel_job_id != job.id:
        return  # a newer upload replaced this one
    output = job.output or {}
    reel = {k: v for k, v in (script.reel or {}).items() if k not in ("problem", "problem_code")}
    if output.get("problem"):
        reel |= {"problem": output["problem"], "problem_code": output.get("problem_code")}
    else:
        files = dict(zip(output.get("files", []), output.get("file_ids", []), strict=False))
        reel |= {k: output[k] for k in ("seconds", "cuts", "stats", "transcript")}
        reel["contact_file_id"] = files.get("contact")
        if "video" in files:
            reel["video_file_id"] = files["video"]
    script.reel = reel
