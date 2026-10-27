"""Videos uploaded for Bulk create before their drafts exist (reel-import.md §8). Free: the
file is stored and checked (MP4 or MOV, 100 MB, 90 s, with sound), nothing is read. POST
/scripts/bulk turns each into a draft; unused ones are removed after a day (purge.py)."""

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.advice import SaidText
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.files import StoredFile, VideoUpload
from app.reel import Refused, probe
from app.routes.brands import get_brand
from app.routes.script_import import _store_video

router = APIRouter(prefix="/uploads", tags=["uploads"])


class UploadOut(BaseModel):
    upload_id: int | None  # null when refused: nothing is kept
    file_name: str
    seconds: float | None
    size: int
    problem: SaidText = ""  # the plain sentence for the file's row ("" when fine)
    problem_code: str | None = None  # too_long | bad_file


def get_upload(db: Session, user: User, upload_id: int) -> VideoUpload:
    """One of this person's uploads not yet in a draft, or 404."""
    upload = db.get(VideoUpload, upload_id)
    if upload is None or upload.created_by_id != user.id or upload.used:
        raise HTTPException(404, "That upload was removed. Add the file again.")
    return upload


@router.post("/video", response_model=UploadOut, status_code=201)
async def upload_video(
    request: Request,
    file: UploadFile,
    brand_id: int = Form(),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    get_brand(db, user, brand_id)
    stored = await _store_video(request, user, db, file)
    storage = request.app.state.storage
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "video"
        path.write_bytes(storage.get(stored.key))
        try:
            seconds = probe(path)
        except Refused as refused:  # nothing is kept: the row says why
            db.rollback()
            storage.delete(stored.key)
            return UploadOut(upload_id=None, file_name=stored.filename, seconds=None,
                             size=stored.size, problem=refused.message,
                             problem_code=refused.code)  # fmt: skip
    upload = VideoUpload(workspace_id=user.workspace_id, brand_id=brand_id,
                         created_by_id=user.id, file_id=stored.id, seconds=seconds)  # fmt: skip
    db.add(upload)
    db.commit()
    return UploadOut(upload_id=upload.id, file_name=stored.filename, seconds=seconds,
                     size=stored.size)  # fmt: skip


@router.delete("/{upload_id}", status_code=204)
def remove_upload(
    upload_id: int,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    """Remove: the file goes at once (nothing was charged, so no Undo)."""
    upload = get_upload(db, user, upload_id)
    stored = db.get(StoredFile, upload.file_id)
    db.delete(upload)
    db.delete(stored)
    db.commit()
    request.app.state.storage.delete(stored.key)
