"""A video's locks and its own outfits (director-chat.md §1): the choices fixed for the
director, and the outfit per character its stills and Keep lines use over the sheet's.
Whoever may change the video sets them."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints
from sqlalchemy.orm import Session

from app import looks
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
    screens: list[int] = []  # the brand screens it must use
    roles: list[str] = []  # "slot:3": that role's look is fixed in this video (the Cast tab)


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
    body.locks.roles = _check_roles(db, user, project, body.locks.roles)
    picked = {looks.PICKED: True} if (project.locks or {}).get(looks.PICKED) else {}
    project.locks = {**body.locks.model_dump(exclude_defaults=True), **picked}
    project.outfits = {k: v for k, v in body.outfits.items() if v}
    db.commit()
    return read(project_id, user, db)


def _check_roles(db: Session, user: User, project, roles: list[str]) -> list[str]:
    """The roles locked in this video, as kept: a newly locked one must be one of its roles,
    with an approved look (422 otherwise); one locked before that is no longer a role (merged
    into another) just drops off, so it never stops another lock being saved."""
    from app.routes.project_assets import list_assets

    if not roles:
        return []
    rows = {f"slot:{r.slot_id}": r for r in list_assets(project.id, user, db) if r.slot_id}
    before = set((project.locks or {}).get("roles") or [])
    new = [r for r in dict.fromkeys(roles) if r not in before]
    if unknown := sorted(set(new) - set(rows)):
        raise HTTPException(422, f"Not a role in this video: {', '.join(unknown)}.")
    for ref in new:
        if rows[ref].sheet_status != "approved":
            raise HTTPException(422, f"Approve {rows[ref].role}'s look first, then lock it.")
    return [r for r in dict.fromkeys(roles) if r in rows]
