"""A video's locks and its own outfits (director-chat.md §1): the choices fixed for the
director, and the outfit per character its stills and Keep lines use over the sheet's.
Whoever may change the video sets them."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.routes.projects import get_project, video_writer
from app.storyboard import cast_looks

router = APIRouter(prefix="/projects/{project_id}/locks", tags=["projects"],
                   dependencies=[Depends(video_writer)])  # fmt: skip
Outfit = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class Locks(BaseModel):
    cast: bool = False  # cast and looks
    look: bool = False
    length: bool = False
    song: bool = False
    end_line: bool = False
    screens: list[int] = []  # the brand screens it must use


class LocksIO(BaseModel):
    locks: Locks = Locks()
    outfits: dict[str, Outfit] = {}  # "char:12" -> "mustard trench coat"; none: the sheet's


@router.get("", response_model=LocksIO)
def read(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = get_project(db, user, project_id)
    return LocksIO(locks=Locks(**(project.locks or {})), outfits=project.outfits or {})


@router.put("", response_model=LocksIO)
def save(
    project_id: int,
    body: LocksIO,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Lock or unlock (unlocking hands the choice back), and set each character's outfit for
    this video: one in its cast (422 otherwise); an empty outfit is the sheet's again."""
    project = get_project(db, user, project_id)
    cast = {f"char:{c.id}" for c in cast_looks(db, project)}
    if unknown := sorted(set(body.outfits) - cast):
        raise HTTPException(422, f"Not in this video's cast: {', '.join(unknown)}.")
    project.locks = body.locks.model_dump(exclude_defaults=True)
    project.outfits = {k: v for k, v in body.outfits.items() if v}
    db.commit()
    return read(project_id, user, db)
