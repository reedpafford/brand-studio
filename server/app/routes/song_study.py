"""Study a song ad (flows S3a) on a song script's version: start (a reel link or an uploaded
video), Use as a guide on or off, Remove (with Undo). Free: our own server reads it. The
study shows on the version's GET as `song_study`. Rules: app/song_study.py."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import reel, song_study
from app import script_library as lib
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.script_library import ScriptDraft
from app.routes.jobs import JobOut
from app.routes.script_import import _store_video
from app.routes.script_library import Slot

router = APIRouter(tags=["songs"])
NOT_A_SONG = "This script isn't a song. Start a Song script to study a song ad."
NOT_A_LINK = "That isn't an Instagram reel link. Paste one, or upload the video."
NOTHING = "Paste a reel link or upload the video."


def _version(db: Session, user: User, script_id: int, slot: int) -> ScriptDraft:
    script = lib.editable(user, lib.get_script(db, user, script_id))
    if script.kind != "song":
        raise HTTPException(409, NOT_A_SONG)
    return lib.get_draft(db, script, slot)


@router.post("/scripts/{script_id}/drafts/{slot}/song-study", response_model=JobOut,
             status_code=201)  # fmt: skip
async def study_song_ad(
    script_id: int,
    slot: Slot,
    request: Request,
    url: str | None = Form(None, max_length=500),
    file: UploadFile | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Study a song ad from a reel link or an uploaded video (free). It replaces the version's
    study once it saves (a failed one leaves it); 409 while one is being studied."""
    draft = _version(db, user, script_id, slot)
    if song_study.busy(db, draft):
        raise HTTPException(409, song_study.BUSY)
    link = reel.reel_link(url) if url and url.strip() else None
    if url and url.strip() and not link:
        raise HTTPException(422, NOT_A_LINK)
    if not link and file is None:
        raise HTTPException(422, NOTHING)
    if link:
        job, old = song_study.start(db, user, draft, {"url": link}, "link", link)
    else:
        stored = await _store_video(request, user, db, file)
        job_input = {"video_key": stored.key, "video_file_id": stored.id}
        job, old = song_study.start(db, user, draft, job_input, "upload")
    for key in old:
        request.app.state.storage.delete(key)
    return job


class GuideIn(BaseModel):
    use_as_guide: bool


@router.patch("/scripts/{script_id}/drafts/{slot}/song-study", status_code=204)
def use_as_guide(
    script_id: int,
    slot: Slot,
    body: GuideIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Use as a guide (on by default): the song directions follow its shape, never its words."""
    song_study.set_guide(db, _version(db, user, script_id, slot), body.use_as_guide)
    return Response(status_code=204)


@router.delete("/scripts/{script_id}/drafts/{slot}/song-study", status_code=204)
def remove_study(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Remove the study (Undo: …/song-study/restore)."""
    song_study.remove(db, _version(db, user, script_id, slot))
    return Response(status_code=204)


@router.post("/scripts/{script_id}/drafts/{slot}/song-study/restore", status_code=204)
def restore_study(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    song_study.remove(db, _version(db, user, script_id, slot), back=True)
    return Response(status_code=204)
