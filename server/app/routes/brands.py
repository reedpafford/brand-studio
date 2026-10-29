"""Brands and their kit (flows BR1). Everyone reads a brand. Only the owner adds or archives
one, and changes BR1's new sections (voice, CTA lines, defaults: app/brand_setup.py; "Only the
owner changes the brand."); editors still edit what they could before BR1 (Next-Lead)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import brand_setup, languages, looks
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.brands import Brand
from app.routes.files import get_file
from app.schemas import Colour, LongText, Name, ShortText, slugify

router = APIRouter(prefix="/brands", tags=["brands"])

FILE_FIELDS = ("logo_file_id", "style_board_file_id", "end_card_file_id")
OWNER_ONLY = "Only the owner changes the brand."
Language = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=10)]


def brand_owner(user: User = Depends(current_user)) -> User:
    if not user.is_owner:
        raise HTTPException(403, OWNER_ONLY)
    return user


class KitFields(BaseModel):
    logo_file_id: int | None = None
    style_board_file_id: int | None = None
    end_card_file_id: int | None = None
    colours: list[Colour] = []
    fonts: list[ShortText] = []
    tone_notes: LongText = ""  # "How the brand talks" on the page
    never_say: list[ShortText] = []  # main's field: the Don't list (kept in step with it)
    legal_line: LongText = ""
    end_line: LongText = ""  # main's field: the default CTA line's text (Current rules 18)


class SetupIn(BaseModel):
    """Brand setup (BR1); left out or null: as it is."""

    audience: LongText | None = None
    do_list: list[ShortText] | None = None
    dont_list: list[ShortText] | None = None
    music_style: ShortText | None = None  # prefills Music style on new song versions (S2)
    default_language: Language | None = None
    default_look: ShortText | None = None  # new scripts start on it (Off: House for editors)
    default_cast: list[int] | None = None  # library character ids


class BrandIn(KitFields, SetupIn):
    name: Name


class BrandPatch(KitFields, SetupIn):
    """Send only the fields you want to change."""

    name: Name | None = None


class CtaLine(BaseModel):
    id: str
    text: str
    default: bool


class CastPick(BaseModel):
    id: int
    name: str
    deleted: bool  # deleted or archived since: "Deleted: pick another"


class BrandOut(KitFields):
    id: int
    name: str
    slug: str
    audience: str = ""
    do_list: list[str] = []
    dont_list: list[str] = []
    music_style: str = ""
    default_language: str = "en"
    default_look: str = "house"
    default_cast: list[int] = []
    cta_lines: list[CtaLine] = []  # live lines, one Default
    cast: list[CastPick] = []  # default_cast, named
    advice: list[str] = []  # e.g. no CTA line: never a block


def get_brand(db: Session, user: User, brand_id: int) -> Brand:
    """Fetch a live brand in the caller's workspace, or 404. Other routes use this too."""
    brand = db.get(Brand, brand_id)
    if not brand or brand.workspace_id != user.workspace_id or brand.archived:
        raise HTTPException(404, "No such brand.")
    return brand


def _apply(db: Session, user: User, brand: Brand, values: dict) -> None:
    for field in ("name", *SetupIn.model_fields):
        if values.get(field) is None:
            values.pop(field, None)
    if "default_look" in values:
        looks.get(values["default_look"])
    if "default_language" in values:
        languages.check(values["default_language"])
    if "default_cast" in values:
        values["default_cast"] = brand_setup.check_cast(db, brand, values["default_cast"])
    legacy = {k: values.pop(k) for k in ("never_say", "end_line") if k in values}
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
    brand_setup.from_legacy(brand, legacy)
    brand_setup.sync(brand)


def brand_out(db: Session, brand: Brand) -> BrandOut:
    return BrandOut.model_validate(brand, from_attributes=True).model_copy(update={
        "cta_lines": [CtaLine(**{k: x[k] for k in ("id", "text", "default")})
                      for x in brand_setup.live(brand)],
        "cast": [CastPick(**x) for x in brand_setup.cast_out(db, brand)],
        "advice": brand_setup.advice(brand),
    })  # fmt: skip


@router.get("", response_model=list[BrandOut])
def list_brands(user: User = Depends(current_user), db: Session = Depends(get_db)):
    found = db.scalars(
        select(Brand)
        .where(Brand.workspace_id == user.workspace_id, Brand.archived.is_(False))
        .order_by(func.lower(Brand.name))
    ).all()
    return [brand_out(db, b) for b in found]


@router.post("", response_model=BrandOut, status_code=201)
def create_brand(body: BrandIn, user: User = Depends(brand_owner), db: Session = Depends(get_db)):
    """Add a brand (owner only, like archiving one)."""
    brand = Brand(workspace_id=user.workspace_id, cta_lines=[], dont_list=[], do_list=[])
    _apply(db, user, brand, body.model_dump(exclude_unset=True))
    db.add(brand)
    db.commit()
    return brand_out(db, brand)


@router.get("/{brand_id}", response_model=BrandOut)
def read_brand(brand_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return brand_out(db, get_brand(db, user, brand_id))


@router.patch("/{brand_id}", response_model=BrandOut)
def update_brand(
    brand_id: int,
    body: BrandPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Change the brand. BR1's new sections are the owner's; what editors changed before BR1
    (name, logo, colours, fonts, notes, never_say, legal and end line) they still may, until
    Reed decides. Nothing already made or published changes (BR1)."""
    brand = get_brand(db, user, brand_id)
    values = body.model_dump(exclude_unset=True)
    if not user.is_owner and any(values.get(k) is not None for k in SetupIn.model_fields):
        raise HTTPException(403, OWNER_ONLY)
    _apply(db, user, brand, values)
    db.commit()
    return brand_out(db, brand)


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
    return brand_out(db, brand)


class CtaIn(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    default: bool = False


class CtaPatch(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1,
                                           max_length=500)] | None = None  # fmt: skip
    default: bool | None = None  # true: this line becomes the Default


class CtaDeleted(BaseModel):
    promoted_id: str | None  # the line that became the Default (toast, Undo: restore)
    brand: BrandOut


@router.post("/{brand_id}/cta-lines", response_model=BrandOut, status_code=201)
def add_cta_line(
    brand_id: int, body: CtaIn, user: User = Depends(brand_owner), db: Session = Depends(get_db)
):
    """Add a call to action line (the first one is the Default)."""
    brand = get_brand(db, user, brand_id)
    brand_setup.add_line(brand, body.text, body.default)
    db.commit()
    return brand_out(db, brand)


@router.patch("/{brand_id}/cta-lines/{line_id}", response_model=BrandOut)
def edit_cta_line(
    brand_id: int,
    line_id: str,
    body: CtaPatch,
    user: User = Depends(brand_owner),
    db: Session = Depends(get_db),
):
    brand = get_brand(db, user, brand_id)
    brand_setup.edit_line(brand, line_id, body.text, body.default)
    db.commit()
    return brand_out(db, brand)


@router.delete("/{brand_id}/cta-lines/{line_id}", response_model=CtaDeleted)
def delete_cta_line(
    brand_id: int, line_id: str, user: User = Depends(brand_owner), db: Session = Depends(get_db)
):
    """Delete a line; deleting the Default makes the next line the Default (Undo: restore)."""
    brand = get_brand(db, user, brand_id)
    promoted = brand_setup.delete_line(brand, line_id)
    db.commit()
    return CtaDeleted(promoted_id=promoted, brand=brand_out(db, brand))


@router.post("/{brand_id}/cta-lines/{line_id}/restore", response_model=BrandOut)
def restore_cta_line(
    brand_id: int, line_id: str, user: User = Depends(brand_owner), db: Session = Depends(get_db)
):
    """Undo a delete: the line comes back, and the Default again if it was."""
    brand = get_brand(db, user, brand_id)
    brand_setup.restore_line(brand, line_id)
    db.commit()
    return brand_out(db, brand)
