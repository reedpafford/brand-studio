"""Brand screens: named images of the brand's real UI, tagged, some attached to moments
by default (e.g. fomo's trading screens appear whenever a scene is about trading)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.brands import BrandScreen
from app.routes.brands import get_brand
from app.routes.files import get_file
from app.schemas import Name, ShortText, Slug

router = APIRouter(prefix="/brands/{brand_id}/screens", tags=["brands"])

# Suggested tags; others are allowed.
COMMON_TAGS = ["trading", "chart-up", "chart-down", "desktop", "mobile"]


class ScreenIn(BaseModel):
    name: Name
    file_id: int
    tags: list[Slug] = []
    default_for: list[Slug] = []
    product: ShortText = ""  # e.g. "bag": screens sharing it are versions of one product
    variant: ShortText = ""  # e.g. "Chicken"; each project picks one variant per product


Box = Annotated[list[Annotated[int, Field(ge=0, le=10000)]], Field(min_length=4, max_length=4)]


class FigureSpot(BaseModel):
    """Where a shot's figure is written on this screen (screen_figures.py), in pixels."""

    box: Box  # cleared to the screen's background: x0, y0, x1, y1
    at: list[Annotated[int, Field(ge=0, le=10000)]] = Field(min_length=2, max_length=2)  # number
    size: int = Field(ge=8, le=400)  # the number's height; the gain line is under it, smaller
    chart: Box | None = None  # a fresh chart is drawn here, when set


class ScreenPatch(BaseModel):
    name: Name | None = None
    file_id: int | None = None
    tags: list[Slug] | None = None
    default_for: list[Slug] | None = None
    product: ShortText | None = None
    variant: ShortText | None = None
    balance: str | None = Field(None, max_length=40)
    figure_spot: FigureSpot | None = None  # no spot: shots get the plain screen


class ScreenOut(ScreenIn):
    id: int
    brand_id: int
    balance: str  # the money the picture shows, e.g. "$348,920.15" (set with PATCH or seed)
    figure_spot: FigureSpot | None


def _get_screen(
    db: Session, user: User, brand_id: int, screen_id: int, deleted: bool = False
) -> BrandScreen:
    get_brand(db, user, brand_id)
    screen = db.get(BrandScreen, screen_id)
    if not screen or screen.brand_id != brand_id or (screen.deleted_at is not None) != deleted:
        raise HTTPException(404, "No such screen.")
    return screen


def _apply(db: Session, user: User, screen: BrandScreen, values: dict) -> None:
    values = {k: v for k, v in values.items() if v is not None}
    if "file_id" in values:
        get_file(db, user, values["file_id"], "image")
    if "name" in values:
        clash = db.scalar(
            select(BrandScreen).where(
                BrandScreen.brand_id == screen.brand_id, BrandScreen.name == values["name"]
            )
        )
        if clash and clash is not screen:
            if clash.deleted_at is not None:  # names stay unique, deleted screens included
                raise HTTPException(
                    409, "A deleted screen has that name. Restore it, or pick another name."
                )
            raise HTTPException(409, "This brand already has a screen with that name.")
    for field, value in values.items():
        setattr(screen, field, sorted(set(value)) if isinstance(value, list) else value)


@router.get("", response_model=list[ScreenOut])
def list_screens(
    brand_id: int,
    tag: str | None = None,
    moment: str | None = None,
    deleted: bool = False,  # true: the deleted screens instead, to bring back
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Filter by `tag`, or by `moment` to get the screens attached to it by default."""
    get_brand(db, user, brand_id)
    gone = BrandScreen.deleted_at.is_not(None)
    screens = db.scalars(
        select(BrandScreen)
        .where(BrandScreen.brand_id == brand_id, gone if deleted else ~gone)
        .order_by(BrandScreen.name)
    ).all()
    return [
        s
        for s in screens
        if (tag is None or tag in s.tags) and (moment is None or moment in s.default_for)
    ]


@router.post("", response_model=ScreenOut, status_code=201)
def add_screen(
    brand_id: int, body: ScreenIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    get_brand(db, user, brand_id)
    screen = BrandScreen(brand_id=brand_id)
    _apply(db, user, screen, body.model_dump())
    db.add(screen)
    db.commit()
    return screen


@router.patch("/{screen_id}", response_model=ScreenOut)
def update_screen(
    brand_id: int,
    screen_id: int,
    body: ScreenPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    screen = _get_screen(db, user, brand_id, screen_id)
    _apply(db, user, screen, body.model_dump(exclude_unset=True))
    db.commit()
    return screen


@router.delete("/{screen_id}", status_code=204)
def delete_screen(
    brand_id: int, screen_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    """Delete it, undoably: it leaves every list and is never used again until restored."""
    _get_screen(db, user, brand_id, screen_id).deleted_at = utcnow()
    db.commit()


@router.post("/{screen_id}/restore", response_model=ScreenOut)
def restore_screen(
    brand_id: int, screen_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Undo a delete: the screen comes back as it was."""
    screen = _get_screen(db, user, brand_id, screen_id, deleted=True)
    screen.deleted_at = None
    db.commit()
    return screen
