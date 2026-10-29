"""The looks (flows ST1, ST3): the cards for the pickers and the owner's Looks page, and the
owner's switch. Rules: app/looks.py."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import credits, look_samples, looks
from app.auth import current_user, owner_only
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.looks import LookSwitch
from app.routes.brands import get_brand
from app.routes.clips import generation_on

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
    if body.on and look_id != looks.DEFAULT and not (row and row.sample_clip_id):
        raise HTTPException(409, looks.NO_SAMPLE)
    if row is None:
        row = LookSwitch(workspace_id=owner.workspace_id, look_id=look_id)
        db.add(row)
    row.on, row.switched_by_id, row.switched_at = body.on, owner.id, utcnow()
    db.commit()
    return _out(db, owner.workspace_id, look)


class Person(BaseModel):
    id: int
    name: str


class SampleOut(BaseModel):
    """ST3: Make a sample · credits; "Who's in the sample?" when the brand has no hero."""

    status: Literal["none", "making", "ready", "failed"]
    reason: str | None  # why it failed, in plain words
    credits: int  # Make a sample · N credits (the still and the 5 s clip)
    hero: Person | None  # the brand's default cast's first character
    characters: list[Person]  # the brand's characters, to pick from with no hero
    still_id: int | None
    clip_id: int | None
    look: LookOut


class SampleIn(BaseModel):
    brand_id: int
    character_id: int | None = None  # None: the hero, or else the look's own sample character


def _sample(db: Session, owner: User, look_id: str, brand_id: int) -> SampleOut:
    brand, look = get_brand(db, owner, brand_id), looks.get(look_id)
    status, reason = look_samples.state(db, owner.workspace_id, look_id)
    row = looks.switch(db, owner.workspace_id, look_id)
    hero = look_samples.hero(db, brand)
    return SampleOut(
        status=status, reason=reason,
        credits=credits.price(look_samples.retry_price(db, owner.workspace_id, look_id)),
        hero=Person(id=hero.id, name=hero.name) if hero else None,
        characters=[Person(id=c.id, name=c.name) for c in look_samples.characters(db, brand)],
        still_id=row.sample_still_id if row else None,
        clip_id=row.sample_clip_id if row else None,
        look=_out(db, owner.workspace_id, look),
    )  # fmt: skip


@router.get("/{look_id}/sample", response_model=SampleOut)
def sample(
    look_id: str, brand_id: int, owner: User = Depends(owner_only), db: Session = Depends(get_db)
):
    return _sample(db, owner, look_id, brand_id)


@router.post("/{look_id}/sample", response_model=SampleOut, status_code=201,
             dependencies=[Depends(generation_on)])  # fmt: skip
def make_sample(
    look_id: str,
    body: SampleIn,
    request: Request,
    owner: User = Depends(owner_only),
    db: Session = Depends(get_db),
):
    """Make a sample (paid: one still, then a 5 s clip from it); again replaces it."""
    looks.get(look_id)
    brand = get_brand(db, owner, body.brand_id)
    look_samples.make(db, owner, look_id, brand, body.character_id, request.app.state.settings)
    return _sample(db, owner, look_id, brand.id)
