"""A presenter video's host (app/host.py): what it is, Make the host, and Make again one piece
(0 is the still: its pieces are made again from it). Each press is priced like a take."""

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import host, narration
from app.advice import SaidText
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.songs import SongTake
from app.routes.clips import generation_on
from app.routes.project_clips import WatchOut
from app.routes.projects import get_project, video_writer

router = APIRouter(prefix="/projects/{project_id}/host", tags=["project clips"],
                   dependencies=[Depends(video_writer)])  # fmt: skip
ways = APIRouter(prefix="/presenter-ways", tags=["project clips"],
                 dependencies=[Depends(current_user)])  # fmt: skip
WAYS = Path(__file__).parent.parent / "samples" / "presenter"
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
    # The Cast tab's Presenter (S5-02): the cast look that says the narration, and the voice
    # the narration in use is read in; before one is made, the voice it will be read in (a
    # person's pick, else the presenter's own saved voice, else the style's).
    presenter_id: int | None = None
    voice: str | None = None


def _out(db: Session, project) -> HostOut:
    if not host.on(db, project):
        return HostOut(on=False, state="none", pieces=[], credits=0)
    who = host.host_look(db, project)
    take = db.get(SongTake, project.song_take_id) if project.song_take_id else None
    from app import director_song

    said = take.voice if take and take.kind == narration.KIND else director_song._voice(db, project)
    return HostOut(on=True, **host.state(db, project), presenter_id=who.id if who else None,
                   voice=said)  # fmt: skip


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


@router.post("/back", response_model=HostOut)
def back(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Use the earlier presenter again (Reed, 4 Nov: "preserve the previous result"): the still
    and each piece go back to the make before, free; the one replaced becomes the earlier one,
    so pressing it again is the Undo. The cut that uses it is out of date (made again free)."""
    project = get_project(db, user, project_id)
    rows = host.rows(db, project)
    if not host.on(db, project) or not any(r.earlier for r in rows):
        raise HTTPException(409, "There's no earlier presenter to go back to.")
    if host.state(db, project)["state"] == "making":
        raise HTTPException(409, host.MAKING)
    for row in rows:
        if row.earlier:
            *rest, last = row.earlier
            row.earlier, row.file_id = [*rest, row.file_id] if row.file_id else rest, last
    db.commit()
    return _out(db, project)


@router.post("/{number}", response_model=HostOut, status_code=201,
             dependencies=[Depends(generation_on)])  # fmt: skip
def again(project_id: int, number: int, request: Request, user: User = Depends(current_user),
          db: Session = Depends(get_db)):  # fmt: skip
    """Make again one piece; the still (0) makes every piece again from the new one."""
    project = get_project(db, user, project_id)
    host.make(db, user, project, request.app.state.storage, number)
    return _out(db, project)


@ways.get("/{way}.jpg", response_class=FileResponse)
def way_picture(way: Literal["talks", "corner", "acts"]):
    """A test sample for each way a presenter can appear (S-gaps-05 L3): talks to camera, in
    a corner over the B-roll, acts in the story. Paid test frames from 3 Nov."""
    path = WAYS / f"{way}.jpg"
    if not path.is_file():
        raise HTTPException(404, "No such picture.")
    return FileResponse(path, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})  # fmt: skip
