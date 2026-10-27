"""Upload and fetch files (images, audio, video). Files belong to a workspace."""

import hashlib
import re
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_db
from app.filetypes import ALLOWED_TYPES, matches
from app.models.accounts import User
from app.models.files import StoredFile
from app.references import too_many_pixels
from app.schemas import UtcTime

router = APIRouter(prefix="/files", tags=["files"])
CHUNK = 1024 * 1024


class FileOut(BaseModel):
    id: int
    filename: str
    content_type: str
    size: int
    created_at: UtcTime


def get_file(
    db: Session, user: User, file_id: int, kind: Literal["image", "audio", "video"] | None = None
) -> StoredFile:
    """Fetch a file in the caller's workspace, or 404. With `kind`, it must also be that kind
    of file (422 otherwise). Every route that stores a file id checks it through here."""
    stored = db.get(StoredFile, file_id)
    if not stored or stored.workspace_id != user.workspace_id:
        raise HTTPException(404, f"No such file: {file_id}.")
    if kind and not stored.content_type.startswith(f"{kind}/"):
        raise HTTPException(
            422, f"File {file_id} must be {'an' if kind == 'image' else 'a'} {kind}."
        )
    return stored


@router.post("", response_model=FileOut, status_code=201)
async def upload(
    upload: UploadFile,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if upload.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "That file type isn't supported.")
    limit = request.app.state.settings.max_upload_mb * 1024 * 1024
    chunks, size = [], 0
    while chunk := await upload.read(CHUNK):
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, "That file is too big.")
        chunks.append(chunk)
    data = b"".join(chunks)
    if not matches(upload.content_type, data[:16]):
        raise HTTPException(415, "The file's contents don't match its type.")
    if upload.content_type.startswith("image/") and (problem := too_many_pixels(data)):
        raise HTTPException(422, problem)
    key = f"{user.workspace_id}/{uuid.uuid4().hex}"
    request.app.state.storage.put(key, data)
    stored = StoredFile(
        workspace_id=user.workspace_id,
        key=key,
        filename=(upload.filename or "file")[:255],
        content_type=upload.content_type,
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        uploaded_by_id=user.id,
    )
    db.add(stored)
    db.commit()
    return stored


@router.get("/{file_id}", responses={200: {"content": {"application/octet-stream": {}}}})
def download(
    file_id: int,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    stored = get_file(db, user, file_id)
    try:
        data = request.app.state.storage.get(stored.key)
    except FileNotFoundError:
        raise HTTPException(404, "This file is missing from storage.") from None
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, max-age=3600",
        "Accept-Ranges": "bytes",
    }
    part = _range(request.headers.get("range", ""), len(data))
    if part is None:
        return Response(data, media_type=stored.content_type, headers=headers)
    if part == ():
        headers["Content-Range"] = f"bytes */{len(data)}"
        return Response(status_code=416, headers=headers)
    start, end = part
    headers["Content-Range"] = f"bytes {start}-{end}/{len(data)}"
    return Response(
        data[start : end + 1], status_code=206, media_type=stored.content_type, headers=headers
    )


def _range(header: str, size: int) -> tuple[int, int] | tuple[()] | None:
    """One byte range ("bytes=0-", "bytes=100-199", "bytes=-500"): iPhone Safari only plays a
    video when the server answers these. None = send the whole file; () = can't be met."""
    found = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
    if not found or found.groups() == ("", ""):
        return None
    first, last = found.groups()
    if not first:  # the last N bytes
        start, end = max(0, size - int(last)), size - 1
    else:
        start, end = int(first), min(int(last), size - 1) if last else size - 1
    return (start, end) if start <= end and start < size else ()
