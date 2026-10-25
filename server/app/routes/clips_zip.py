"""Download every clip at once (Reed, 2026-10-25: downloads, no upload): a zip of each clip's
picked take, or with `all_takes` every take. Built while it is sent, one file at a time, so a
long video's clips are never all in memory. Videos are already compressed, so files are stored
as they are."""

import re
import zipfile
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.clips import ClipTake, ProjectClip
from app.models.files import StoredFile
from app.routes.projects import get_project
from app.storage import Storage

router = APIRouter(prefix="/projects/{project_id}", tags=["project clips"])


class _Chunks:
    """A write-only file the zip writes into; what's written is handed out piece by piece."""

    def __init__(self):
        self.parts: list[bytes] = []
        self.offset = 0

    def write(self, data: bytes) -> int:
        self.parts.append(bytes(data))
        self.offset += len(data)
        return len(data)

    def tell(self) -> int:
        return self.offset

    def flush(self) -> None:
        pass

    def take(self) -> bytes:
        out, self.parts = b"".join(self.parts), []
        return out


def _stream(storage: Storage, files: list[tuple[str, str]]) -> Iterator[bytes]:
    sink = _Chunks()
    with zipfile.ZipFile(sink, "w", zipfile.ZIP_STORED) as archive:
        for name, key in files:
            archive.writestr(name, storage.get(key))
            yield sink.take()
    yield sink.take()


@router.get("/clips.zip", response_class=StreamingResponse)
def clips_zip(
    project_id: int,
    request: Request,
    all_takes: bool = False,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    project = get_project(db, user, project_id)
    clips = db.scalars(
        select(ProjectClip).where(ProjectClip.project_id == project.id).order_by(ProjectClip.id)
    ).all()
    files: list[tuple[str, str]] = []
    for clip in clips:
        takes = db.scalars(
            select(ClipTake).where(ClipTake.clip_id == clip.id).order_by(ClipTake.number)
        ).all()
        for take in takes:
            if all_takes or take.id == clip.picked_take_id:
                name = f"{clip.clip_id}/take{take.number}.mp4" if all_takes else (
                    f"{clip.clip_id}-take{take.number}.mp4"
                )  # fmt: skip
                files.append((name, db.get(StoredFile, take.file_id).key))
    if not files:
        raise HTTPException(409, "There are no takes to download yet.")
    safe = re.sub(r"[^A-Za-z0-9 _-]", "", project.name).strip() or "clips"
    return StreamingResponse(
        _stream(request.app.state.storage, files),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe}.zip"'},
    )
