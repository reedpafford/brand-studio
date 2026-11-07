"""The looks (flows ST1, ST3): the cards for the pickers and the owner's Looks page, and the
owner's switch. Rules: app/looks.py."""

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import credits, guides, look_samples, looks
from app.auth import current_user, owner_only
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.looks import LookSwitch
from app.routes.brands import get_brand
from app.routes.clips import generation_on

router = APIRouter(prefix="/looks", tags=["looks"])
HOUSE_STAYS = "House is the default style, so it stays on."
# New video's cards: the paid test samples of 3 Nov, until the owner approves the look's own
# sample (Settings → Looks), which then shows instead. A look with no file here has none.
SAMPLES = Path(__file__).parent.parent / "samples"
KINDS = {"mp4": "video/mp4", "jpg": "image/jpeg"}
NO_SAMPLE_FILE = "There's no test sample for that."
SITE_OUTPUT = {"house"}  # its card's still and clip are the site's own output, not test samples
SONG_OFF = "its music provider isn't switched on for this site yet"


class LaneOut(BaseModel):
    id: str
    name: str  # "Paper · Flat Paper"


class LookOut(BaseModel):
    id: str
    name: str
    blurb: str  # one line for the card ("Soft 3D feature-film look")
    on: bool  # editors can pick it
    sample_still_id: int | None = None  # ST3: the approved sample, once made
    sample_clip_id: int | None = None
    video_model: str  # the catalogue id of its default video model (its guide)
    own_sample: bool = False  # its sample shows its own person: no hero, no "Who's in it?"
    lanes: list[LaneOut] = []  # the style's lanes, picked by a video's plan (one look per style)
    card: str = ""  # New video's card: a short line ("Handmade clay"), and its B-roll look
    broll: str = ""
    test_clip: bool = False  # a test sample at /looks/{id}/test-sample.mp4 (and .jpg)
    test_still: bool = False
    test_tag: bool = False  # its card says "Test sample" (not the site's own frame)
    sample_stand_in: bool = False  # its sample is a test-site stand-in: the card shows the test one


class LookSwitchIn(BaseModel):
    on: bool


def _out(db: Session, ws: int, look: dict) -> LookOut:
    row = looks.switch(db, ws, look["id"])
    return LookOut(id=look["id"], name=look["name"], blurb=look["blurb"],
                   on=looks.is_on(db, ws, look["id"]),
                   sample_still_id=row.sample_still_id if row else None,
                   sample_clip_id=row.sample_clip_id if row else None,
                   sample_stand_in=bool(row and row.sample_clip_id)
                   and look_samples.stand_in(db, ws, look["id"]),
                   video_model=look["video_model"], own_sample=look["own_sample"],
                   lanes=[LaneOut(id=x["id"], name=x["name"])
                          for x in looks.lanes(look["id"])],
                   card=look.get("card", ""), broll=look.get("broll", ""),
                   test_clip=_sample_file("looks", look["id"], "mp4") is not None,
                   test_still=_sample_file("looks", look["id"], "jpg") is not None,
                   test_tag=look["id"] not in SITE_OUTPUT)  # fmt: skip


def _sample_file(kind: str, item_id: str, ext: str) -> Path | None:
    path = SAMPLES / kind / f"{item_id}.{ext}"
    return path if ext in KINDS and path.is_file() else None


def _test_sample(kind: str, item_id: str, ext: str) -> FileResponse:
    path = _sample_file(kind, item_id, ext)
    if path is None:
        raise HTTPException(404, NO_SAMPLE_FILE)
    return FileResponse(path, media_type=KINDS[ext],
                        headers={"Cache-Control": "private, max-age=86400"})  # fmt: skip


@router.get("", response_model=list[LookOut])
def list_looks(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """House first, then Reed's order. Editors see the Off ones too, greyed (ST1)."""
    return [_out(db, user.workspace_id, x) for x in looks.looks()]


@router.get("/{look_id}/test-sample.{ext}", response_class=FileResponse)
def look_test_sample(look_id: str, ext: str, user: User = Depends(current_user)):
    """A look's test sample for New video's card: its clip (mp4) or still (jpg)."""
    return _test_sample("looks", looks.get(look_id)["id"], ext)


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
    test_site: str | None = None  # real samples on: real, or a stand-in past their budget


class SampleIn(BaseModel):
    brand_id: int
    character_id: int | None = None  # None: the hero, or else the look's own sample character


def _sample(db: Session, owner: User, look_id: str, brand_id: int, settings) -> SampleOut:
    brand, look = get_brand(db, owner, brand_id), looks.get(look_id)
    status, reason = look_samples.state(db, owner.workspace_id, look_id)
    row = looks.switch(db, owner.workspace_id, look_id)
    own = look["own_sample"]  # its own person: no hero, no pick (ST3)
    hero = None if own else look_samples.hero(db, brand)
    return SampleOut(
        status=status, reason=reason,
        credits=credits.price(look_samples.retry_price(db, owner.workspace_id, look_id)),
        hero=Person(id=hero.id, name=hero.name) if hero else None,
        characters=[] if own else [Person(id=c.id, name=c.name)
                                   for c in look_samples.characters(db, brand)],
        still_id=row.sample_still_id if row else None,
        clip_id=row.sample_clip_id if row else None,
        look=_out(db, owner.workspace_id, look),
        test_site=look_samples.test_site_note(db, settings, owner.workspace_id, look_id),
    )  # fmt: skip


@router.get("/{look_id}/sample", response_model=SampleOut)
def sample(
    look_id: str,
    brand_id: int,
    request: Request,
    owner: User = Depends(owner_only),
    db: Session = Depends(get_db),
):
    return _sample(db, owner, look_id, brand_id, request.app.state.settings)


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
    settings = request.app.state.settings
    look_samples.make(db, owner, look_id, brand, body.character_id, settings)
    return _sample(db, owner, look_id, brand.id, settings)


formats = APIRouter(prefix="/formats", tags=["looks"])  # the format picker, beside the looks


class FormatOut(BaseModel):
    id: str
    name: str
    engine: Literal["story", "song", "narrated"]  # which mechanics make it
    blurb: str
    on: bool
    card: str = ""  # New video's card: a short line ("People talk on camera")
    host: bool = False  # a host over B-roll: its video may have a B-roll look of its own
    off: str | None = None  # why it can't be made on this site now, in plain words
    test_still: bool = False  # a test sample picture at /formats/{id}/test-sample.jpg


def off_reason(f: dict, settings) -> str | None:
    """Off in its guide, or a song while no music provider is on (`kie_suno`)."""
    if not f["on"]:
        return "off"
    if f["engine"] == "song" and not settings.kie_suno:
        return SONG_OFF
    return None


@formats.get("", response_model=list[FormatOut])
def list_formats(request: Request, user: User = Depends(current_user)):
    """Every format in Reed’s order (app/guides/formats), for the format picker."""
    settings = request.app.state.settings
    return [FormatOut(**{k: f[k] for k in ("id", "name", "engine", "blurb", "on")},
                      host=f.get("host", False), card=f.get("card", ""),
                      off=off_reason(f, settings),
                      test_still=_sample_file("formats", f["id"], "jpg") is not None)
            for f in guides.formats()]  # fmt: skip


@formats.get("/{format_id}/test-sample.jpg", response_class=FileResponse)
def format_test_sample(format_id: str, user: User = Depends(current_user)):
    """A format's test sample picture for New video's card."""
    if format_id not in {f["id"] for f in guides.formats()}:
        raise HTTPException(404, NO_SAMPLE_FILE)
    return _test_sample("formats", format_id, "jpg")
