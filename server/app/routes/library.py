"""Characters, places and props, filtered by brand. Edits keep a version history."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.library import Kind, LibraryItem, LibraryItemVersion
from app.routes.brands import get_brand
from app.routes.files import get_file
from app.schemas import LongText, Name

router = APIRouter(prefix="/library/{kind}", tags=["library"])


class Outfit(BaseModel):
    name: Name
    file_ids: list[int] = []


class ItemIn(BaseModel):
    name: Name
    notes: LongText = ""
    brand_ids: list[int] = []
    image_file_ids: list[int] = []
    outfits: list[Outfit] = []  # characters only
    voice_file_id: int | None = None  # characters only


class ItemPatch(BaseModel):
    """Send only the fields you want to change."""

    name: Name | None = None
    notes: LongText | None = None
    brand_ids: list[int] | None = None
    image_file_ids: list[int] | None = None
    outfits: list[Outfit] | None = None
    voice_file_id: int | None = None


class ItemOut(ItemIn):
    id: int
    kind: Kind
    version: int


class VersionOut(BaseModel):
    version: int
    snapshot: ItemIn
    saved_by_id: int | None
    created_at: datetime


def _snapshot(item: LibraryItem) -> dict:
    return {
        "name": item.name,
        "notes": item.notes,
        "brand_ids": sorted(b.id for b in item.brands),
        "image_file_ids": item.image_file_ids,
        "outfits": item.outfits,
        "voice_file_id": item.voice_file_id,
    }


def _out(item: LibraryItem) -> ItemOut:
    return ItemOut(id=item.id, kind=item.kind, version=item.version, **_snapshot(item))


def _get_item(db: Session, user: User, kind: Kind, item_id: int) -> LibraryItem:
    item = db.get(LibraryItem, item_id)
    if not item or item.workspace_id != user.workspace_id or item.kind != kind or item.archived:
        raise HTTPException(404, f"No such {kind}.")
    return item


def _apply(db: Session, user: User, item: LibraryItem, values: dict) -> None:
    if values.get("name") is None:
        values.pop("name", None)
    if item.kind != Kind.character and (values.get("outfits") or values.get("voice_file_id")):
        raise HTTPException(422, "Only characters have outfits and a voice.")
    file_ids = list(values.get("image_file_ids") or [])
    file_ids += [f for o in values.get("outfits") or [] for f in o["file_ids"]]
    file_ids += [values["voice_file_id"]] if values.get("voice_file_id") else []
    for file_id in file_ids:
        get_file(db, user, file_id)
    if "brand_ids" in values:
        item.brands = [get_brand(db, user, b) for b in sorted(set(values.pop("brand_ids") or []))]
    for field, value in values.items():
        if value is not None or field == "voice_file_id":
            setattr(item, field, value)


def _save_version(db: Session, user: User, item: LibraryItem) -> None:
    db.add(
        LibraryItemVersion(
            item_id=item.id, version=item.version, snapshot=_snapshot(item), saved_by_id=user.id
        )
    )
    item.version += 1


@router.get("", response_model=list[ItemOut])
def list_items(
    kind: Kind,
    brand_id: int | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    query = select(LibraryItem).where(
        LibraryItem.workspace_id == user.workspace_id,
        LibraryItem.kind == kind,
        LibraryItem.archived.is_(False),
    )
    if brand_id is not None:
        query = query.where(LibraryItem.brands.any(id=brand_id))
    return [_out(i) for i in db.scalars(query.order_by(func.lower(LibraryItem.name)))]


@router.post("", response_model=ItemOut, status_code=201)
def create_item(
    kind: Kind, body: ItemIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    item = LibraryItem(workspace_id=user.workspace_id, kind=kind)
    _apply(db, user, item, body.model_dump())
    db.add(item)
    db.commit()
    return _out(item)


@router.get("/{item_id}", response_model=ItemOut)
def read_item(
    kind: Kind, item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return _out(_get_item(db, user, kind, item_id))


@router.patch("/{item_id}", response_model=ItemOut)
def update_item(
    kind: Kind,
    item_id: int,
    body: ItemPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    item = _get_item(db, user, kind, item_id)
    _save_version(db, user, item)
    _apply(db, user, item, body.model_dump(exclude_unset=True))
    db.commit()
    return _out(item)


@router.delete("/{item_id}", status_code=204)
def archive_item(
    kind: Kind, item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    _get_item(db, user, kind, item_id).archived = True
    db.commit()


@router.get("/{item_id}/versions", response_model=list[VersionOut])
def list_versions(
    kind: Kind, item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    item = _get_item(db, user, kind, item_id)
    return db.scalars(
        select(LibraryItemVersion)
        .where(LibraryItemVersion.item_id == item.id)
        .order_by(LibraryItemVersion.version.desc())
    ).all()


@router.post("/{item_id}/versions/{version}/restore", response_model=ItemOut)
def restore_version(
    kind: Kind,
    item_id: int,
    version: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Bring back an old version. The current state is saved first, so this can be undone too."""
    item = _get_item(db, user, kind, item_id)
    old = db.scalar(
        select(LibraryItemVersion).where(
            LibraryItemVersion.item_id == item.id, LibraryItemVersion.version == version
        )
    )
    if not old:
        raise HTTPException(404, "No such version.")
    _save_version(db, user, item)
    _apply(db, user, item, dict(old.snapshot))
    db.commit()
    return _out(item)
