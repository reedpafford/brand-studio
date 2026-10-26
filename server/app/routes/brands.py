"""Brands and their kit. Anyone on the team can create and edit; only the owner archives."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import current_user, owner_only
from app.db import get_db
from app.models.accounts import User
from app.models.brands import Brand
from app.routes.files import get_file
from app.schemas import Colour, LongText, Name, ShortText, slugify

router = APIRouter(prefix="/brands", tags=["brands"])

FILE_FIELDS = ("logo_file_id", "style_board_file_id", "end_card_file_id")


class KitFields(BaseModel):
    logo_file_id: int | None = None
    style_board_file_id: int | None = None
    end_card_file_id: int | None = None
    colours: list[Colour] = []
    fonts: list[ShortText] = []
    tone_notes: LongText = ""
    never_say: list[ShortText] = []
    legal_line: LongText = ""
    end_line: LongText = ""  # the call to action every video ends on, word for word


class BrandIn(KitFields):
    name: Name


class BrandPatch(KitFields):
    """Send only the fields you want to change."""

    name: Name | None = None


class BrandOut(KitFields):
    id: int
    name: str
    slug: str


def get_brand(db: Session, user: User, brand_id: int) -> Brand:
    """Fetch a live brand in the caller's workspace, or 404. Other routes use this too."""
    brand = db.get(Brand, brand_id)
    if not brand or brand.workspace_id != user.workspace_id or brand.archived:
        raise HTTPException(404, "No such brand.")
    return brand


def _apply(db: Session, user: User, brand: Brand, values: dict) -> None:
    if values.get("name") is None:
        values.pop("name", None)
    for field in FILE_FIELDS:
        if values.get(field) is not None:
            get_file(db, user, values[field], "image")
    if "name" in values:
        slug = slugify(values["name"])
        clash = db.scalar(
            select(Brand).where(Brand.workspace_id == user.workspace_id, Brand.slug == slug)
        )
        if not slug or (clash and clash is not brand):
            raise HTTPException(409, "A brand with that name already exists.")
        brand.slug = slug
    for field, value in values.items():
        setattr(brand, field, value)


@router.get("", response_model=list[BrandOut])
def list_brands(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Brand)
        .where(Brand.workspace_id == user.workspace_id, Brand.archived.is_(False))
        .order_by(func.lower(Brand.name))
    ).all()


@router.post("", response_model=BrandOut, status_code=201)
def create_brand(body: BrandIn, user: User = Depends(owner_only), db: Session = Depends(get_db)):
    """Add a brand (owner only, like archiving one)."""
    brand = Brand(workspace_id=user.workspace_id)
    _apply(db, user, brand, body.model_dump())
    db.add(brand)
    db.commit()
    return brand


@router.get("/{brand_id}", response_model=BrandOut)
def read_brand(brand_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return get_brand(db, user, brand_id)


@router.patch("/{brand_id}", response_model=BrandOut)
def update_brand(
    brand_id: int,
    body: BrandPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    brand = get_brand(db, user, brand_id)
    _apply(db, user, brand, body.model_dump(exclude_unset=True))
    db.commit()
    return brand


@router.delete("/{brand_id}", status_code=204)
def archive_brand(
    brand_id: int, owner: User = Depends(owner_only), db: Session = Depends(get_db)
) -> None:
    get_brand(db, owner, brand_id).archived = True
    db.commit()


@router.post("/{brand_id}/restore", response_model=BrandOut)
def restore_brand(brand_id: int, owner: User = Depends(owner_only), db: Session = Depends(get_db)):
    """Undo an archive: the brand and everything in it come back."""
    brand = db.get(Brand, brand_id)
    if not brand or brand.workspace_id != owner.workspace_id or not brand.archived:
        raise HTTPException(404, "No such archived brand.")
    brand.archived = False
    db.commit()
    return brand
