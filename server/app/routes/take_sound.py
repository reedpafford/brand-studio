"""Add sound effects to a clip's picked take, and Remove them (app/take_sound.py). Adding is
one MMAudio run at its real cost, priced first; removing is free and the take is as it was."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import take_sound
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.clips import ClipTake
from app.routes.clips import generation_on
from app.routes.project_clips import ProjectClipOut, _clip, _newest_breakdown, _out
from app.routes.projects import video_writer

router = APIRouter(prefix="/projects/{project_id}/clips/{clip_id}/sound",
                   tags=["project clips"], dependencies=[Depends(video_writer)])  # fmt: skip


class SoundIn(BaseModel):
    asked: str = Field("", max_length=take_sound.LONGEST)  # "slight footsteps"; empty: what fits


@router.post("", response_model=ProjectClipOut, status_code=201,
             dependencies=[Depends(generation_on)])  # fmt: skip
def add(project_id: int, clip_id: int, body: SoundIn, user: User = Depends(current_user),
        db: Session = Depends(get_db)):  # fmt: skip
    """Add sound effects under the picked take (Make again after a failed run)."""
    project, row = _clip(db, user, project_id, clip_id)
    take_sound.add(db, user, project, [row], body.asked)
    return _out(db, row, _newest_breakdown(db, project))


@router.delete("", response_model=ProjectClipOut)
def remove(project_id: int, clip_id: int, user: User = Depends(current_user),
           db: Session = Depends(get_db)):  # fmt: skip
    """Undo: the picked take plays as it was made (silent B-roll silent again)."""
    project, row = _clip(db, user, project_id, clip_id)
    take = db.get(ClipTake, row.picked_take_id) if row.picked_take_id else None
    if take is None:
        raise HTTPException(409, take_sound.NO_TAKE)
    take_sound.remove(take)
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))
