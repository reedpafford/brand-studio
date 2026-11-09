"""Make variations on a finished video (Runway #2, app/video_variations): 2 or 3, of its hook
or its ending, with an optional note. Who may: as Make it, the video's maker or the owner."""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import video_variations
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.routes.clips import generation_on
from app.routes.projects import _mine, get_project, video_writer
from app.schemas import NoteText

router = APIRouter(prefix="/projects/{project_id}/variations", tags=["director"],
                   dependencies=[Depends(video_writer)])  # fmt: skip


class VideoVariationsIn(BaseModel):
    count: Literal[2, 3] = 3
    part: Literal["hook", "ending"] = "hook"
    note: NoteText = ""  # "Open on the empty bowl", or new words in quotes (the owner's only)


class VariationVideoOut(BaseModel):
    id: int
    title: str  # "<title> · variation A"


class VideoVariationsOut(BaseModel):
    state: Literal["none", "writing", "done", "failed"]
    videos: list[VariationVideoOut] = Field(default_factory=list)
    blocked: str = ""  # why Make variations can't be pressed now, or ""


def _out(db: Session, project) -> VideoVariationsOut:
    return VideoVariationsOut(**video_variations.made(db, project),
                         blocked=video_variations.refusal(db, project))  # fmt: skip


@router.get("", response_model=VideoVariationsOut)
def read(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The newest variations asked for on this video, and whether more can be asked now."""
    return _out(db, get_project(db, user, project_id))


@router.post("", response_model=VideoVariationsOut, status_code=201,
             dependencies=[Depends(generation_on)])  # fmt: skip
def make(project_id: int, body: VideoVariationsIn, user: User = Depends(current_user),
         db: Session = Depends(get_db)):  # fmt: skip
    """One director call proposes them; each becomes a video in this one's folder, its run
    waiting on its own direction card, priced as only the clips it changes (409 while a run
    goes on, before a delivery, or while some are being written)."""
    project = get_project(db, user, project_id)
    _mine(db, user, project.id)
    video_variations.ask(db, user, project, body.count, body.part, body.note)
    return _out(db, project)
