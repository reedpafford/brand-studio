"""A presenter video's host (app/host.py): what it is, Make the host, and Make again one piece
(0 is the still: its pieces are made again from it). Each press is priced like a take."""

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import host
from app.advice import SaidText
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.routes.clips import generation_on
from app.routes.project_clips import WatchOut
from app.routes.projects import get_project, video_writer

router = APIRouter(prefix="/projects/{project_id}/host", tags=["project clips"],
                   dependencies=[Depends(video_writer)])  # fmt: skip
State = Literal["none", "making", "ready", "failed"]


class HostPieceOut(BaseModel):
    number: int  # 0: the host's still on green; 1, 2, …: the pieces, in order
    start: float  # seconds into the narration it says
    end: float
    state: State
    file_id: int | None  # the still or the piece's video, once made
    earlier: list[int]  # the makes before, oldest first
    error: SaidText = ""  # its newest make failed: why, in plain words
    credits: float  # Make again (the still: and every piece from it)
    watch: WatchOut | None = None  # a piece's: the director's watch of it (app/host_watch)


class HostOut(BaseModel):
    on: bool  # the video's format has a host (Presenter)
    state: State
    pieces: list[HostPieceOut]
    credits: float  # Make the host: what isn't made yet


def _out(db: Session, project) -> HostOut:
    if not host.on(db, project):
        return HostOut(on=False, state="none", pieces=[], credits=0)
    return HostOut(on=True, **host.state(db, project))


@router.get("", response_model=HostOut)
def read(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _out(db, get_project(db, user, project_id))


@router.post("", response_model=HostOut, status_code=201, dependencies=[Depends(generation_on)])
def make(project_id: int, request: Request, user: User = Depends(current_user),
         db: Session = Depends(get_db)):  # fmt: skip
    """Make what isn't made yet: the still first, then each piece from it."""
    project = get_project(db, user, project_id)
    host.make(db, user, project, request.app.state.storage)
    return _out(db, project)


@router.post("/{number}", response_model=HostOut, status_code=201,
             dependencies=[Depends(generation_on)])  # fmt: skip
def again(project_id: int, number: int, request: Request, user: User = Depends(current_user),
          db: Session = Depends(get_db)):  # fmt: skip
    """Make again one piece; the still (0) makes every piece again from the new one."""
    project = get_project(db, user, project_id)
    host.make(db, user, project, request.app.state.storage, number)
    return _out(db, project)
