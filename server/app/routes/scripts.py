"""A project's script: paste or upload (txt/docx/pdf), with every change kept as a version."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.credits import lock
from app.db import get_db
from app.docimport import DocumentError, kind_of, to_text
from app.models.accounts import User
from app.models.projects import Project
from app.models.scripts import ScriptVersion
from app.routes.projects import get_project, video_writer
from app.schemas import UtcTime

router = APIRouter(
    prefix="/projects/{project_id}/script", tags=["scripts"], dependencies=[Depends(video_writer)]
)
MAX_DOC_BYTES = 10 * 1024 * 1024
MAX_SCRIPT_CHARS = 50_000
ScriptText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_SCRIPT_CHARS)
]


class ScriptIn(BaseModel):
    text: ScriptText


class VersionOut(BaseModel):
    version: int
    source: str
    words: int
    created_by_id: int | None
    created_at: UtcTime


class ScriptOut(VersionOut):
    text: str


def _out(v: ScriptVersion, with_text: bool = True) -> dict:
    out = {
        "version": v.version,
        "source": v.source,
        "words": len(v.text.split()),
        "created_by_id": v.created_by_id,
        "created_at": v.created_at,
    }
    return {**out, "text": v.text} if with_text else out


def latest(db: Session, project: Project) -> ScriptVersion | None:
    return db.scalar(
        select(ScriptVersion)
        .where(ScriptVersion.project_id == project.id)
        .order_by(ScriptVersion.version.desc())
        .limit(1)
    )


def save_version(db: Session, user: User, project: Project, text: str, source: str):
    """Add a new version (the next number). Used by paste, upload, draft and enhance.
    The project row is locked first, so two saves at once get n+1 and n+2."""
    lock(db, Project, project.id)
    number = db.scalar(
        select(func.coalesce(func.max(ScriptVersion.version), 0)).where(
            ScriptVersion.project_id == project.id
        )
    )
    version = ScriptVersion(
        project_id=project.id, version=number + 1, text=text, source=source, created_by_id=user.id
    )
    db.add(version)
    db.commit()
    return version


@router.get("", response_model=ScriptOut)
def read_script(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    version = latest(db, get_project(db, user, project_id))
    if not version:
        raise HTTPException(404, "This project has no script yet.")
    return _out(version)


@router.put("", response_model=ScriptOut)
def paste_script(
    project_id: int,
    body: ScriptIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    project = get_project(db, user, project_id)
    return _out(save_version(db, user, project, body.text, "paste"))


@router.post("/upload", response_model=ScriptOut, status_code=201)
def upload_script(
    project_id: int,
    upload: UploadFile,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    project = get_project(db, user, project_id)
    data = upload.file.read(MAX_DOC_BYTES + 1)
    if len(data) > MAX_DOC_BYTES:
        raise HTTPException(413, "That document is too big (10 MB max).")
    try:
        text = to_text(data, kind_of(upload.filename or "", upload.content_type), MAX_SCRIPT_CHARS)
    except DocumentError as exc:
        raise HTTPException(422, str(exc)) from None
    return _out(save_version(db, user, project, text, "upload"))


@router.get("/versions", response_model=list[VersionOut])
def list_versions(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    project = get_project(db, user, project_id)
    versions = db.scalars(
        select(ScriptVersion)
        .where(ScriptVersion.project_id == project.id)
        .order_by(ScriptVersion.version.desc())
    )
    return [_out(v, with_text=False) for v in versions]


@router.get("/versions/{version}", response_model=ScriptOut)
def read_version(
    project_id: int,
    version: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    project = get_project(db, user, project_id)
    found = db.scalar(
        select(ScriptVersion).where(
            ScriptVersion.project_id == project.id, ScriptVersion.version == version
        )
    )
    if not found:
        raise HTTPException(404, "No such version.")
    return _out(found)
