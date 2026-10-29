"""The looks (flows ST1, ST3): the cards for the pickers and the owner's Looks page, and the
owner's switch. Rules: app/looks.py."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import looks
from app.auth import current_user, owner_only
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.looks import LookSwitch

router = APIRouter(prefix="/looks", tags=["looks"])
HOUSE_STAYS = "House is the default look, so it stays on."


class LookOut(BaseModel):
    id: str
    name: str
    blurb: str  # one line for the card ("Soft 3D feature-film look")
    on: bool  # editors can pick it
    sample_still_id: int | None = None  # ST3: the approved sample, once made
    sample_clip_id: int | None = None


class LookSwitchIn(BaseModel):
    on: bool


def _out(db: Session, ws: int, look: dict) -> LookOut:
    row = looks.switch(db, ws, look["id"])
    return LookOut(id=look["id"], name=look["name"], blurb=look["blurb"],
                   on=looks.is_on(db, ws, look["id"]),
                   sample_still_id=row.sample_still_id if row else None,
                   sample_clip_id=row.sample_clip_id if row else None)  # fmt: skip


@router.get("", response_model=list[LookOut])
def list_looks(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """House first, then Reed's order. Editors see the Off ones too, greyed (ST1)."""
    return [_out(db, user.workspace_id, x) for x in looks.looks()]


@router.patch("/{look_id}", response_model=LookOut)
def switch_look(
    look_id: str,
    body: LookSwitchIn,
    owner: User = Depends(owner_only),
    db: Session = Depends(get_db),
):
    """Switch on for editors (only with a sample), or off (videos using it keep it); Undo is
    the opposite press."""
    look = looks.get(look_id)
    row = looks.switch(db, owner.workspace_id, look_id)
    if look_id == looks.DEFAULT and not body.on:
        raise HTTPException(409, HOUSE_STAYS)
    if body.on and look_id != looks.DEFAULT and not (row and row.sample_still_id):
        raise HTTPException(409, looks.NO_SAMPLE)
    if row is None:
        row = LookSwitch(workspace_id=owner.workspace_id, look_id=look_id)
        db.add(row)
    row.on, row.switched_by_id, row.switched_at = body.on, owner.id, utcnow()
    db.commit()
    return _out(db, owner.workspace_id, look)
