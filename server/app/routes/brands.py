"""Brands and their kit (v6 S8-05, S-gaps-05 L1): a name, a logo, colours, and tone and rules.
Everyone reads a brand and edits its kit; only the owner adds or archives one. The script and
the director carry the rest (Reed, 4 Nov); a brand's products, apps included, are its library's
Products."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.brands import Brand
from app.routes.files import get_file
from app.schemas import Colour, LongText, Name, slugify

router = APIRouter(prefix="/brands", tags=["brands"])

OWNER_ONLY = "Only the owner adds or archives a brand."


def brand_owner(user: User = Depends(current_user)) -> User:
    if not user.is_owner:
        raise HTTPException(403, OWNER_ONLY)
    return user


class KitFields(BaseModel):
    logo_file_id: int | None = None
    colours: list[Colour] = []
    tone_notes: LongText = ""  # "Tone and rules" on the Brand kit


class BrandIn(KitFields):
    name: Name


class BrandPatch(BaseModel):
    """Send only the fields you want to change."""

    name: Name | None = None
    logo_file_id: int | None = None
    colours: list[Colour] | None = None
    tone_notes: LongText | None = None


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
    """A logo sent as null removes it; anything else left out or null stays as it is."""
    values = {k: v for k, v in values.items() if v is not None or k == "logo_file_id"}
    if values.get("logo_file_id") is not None:
        get_file(db, user, values["logo_file_id"], "image")
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
    found = db.scalars(
        select(Brand)
        .where(Brand.workspace_id == user.workspace_id, Brand.archived.is_(False))
        .order_by(func.lower(Brand.name))
    ).all()
    return found


@router.post("", response_model=BrandOut, status_code=201)
def create_brand(body: BrandIn, user: User = Depends(brand_owner), db: Session = Depends(get_db)):
    """Add a brand (owner only, like archiving one)."""
    brand = Brand(workspace_id=user.workspace_id)
    _apply(db, user, brand, body.model_dump(exclude_unset=True))
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
    """Change the kit (Reed, 30 Oct: editors fill in the brand too). Nothing already made
    changes."""
    brand = get_brand(db, user, brand_id)
    _apply(db, user, brand, body.model_dump(exclude_unset=True))
    db.commit()
    return brand


@router.delete("/{brand_id}", status_code=204)
def archive_brand(
    brand_id: int, owner: User = Depends(brand_owner), db: Session = Depends(get_db)
) -> None:
    get_brand(db, owner, brand_id).archived = True
    db.commit()


@router.post("/{brand_id}/restore", response_model=BrandOut)
def restore_brand(brand_id: int, owner: User = Depends(brand_owner), db: Session = Depends(get_db)):
    """Undo an archive: the brand and everything in it come back."""
    brand = db.get(Brand, brand_id)
    if not brand or brand.workspace_id != owner.workspace_id or not brand.archived:
        raise HTTPException(404, "No such archived brand.")
    brand.archived = False
    db.commit()
    return brand
