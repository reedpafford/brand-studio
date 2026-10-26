"""Characters, places and props, filtered by brand. Edits keep a version history."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, object_session

from app.auth import current_user, owner_only
from app.db import get_db
from app.models.accounts import User
from app.models.brands import Brand
from app.models.jobs import Job, JobStatus
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
    # Characters and places: a photo kept as source material only, never used in videos.
    source_photo_file_id: int | None = None


class NewItemIn(ItemIn):
    # A look for one video or one script only (gaps #19): never listed here, never offered
    # elsewhere. Set once, on create.
    owner_project_id: int | None = None
    owner_script_id: int | None = None


class ItemPatch(BaseModel):
    """Send only the fields you want to change."""

    name: Name | None = None
    notes: LongText | None = None
    brand_ids: list[int] | None = None
    image_file_ids: list[int] | None = None
    outfits: list[Outfit] | None = None
    voice_file_id: int | None = None
    source_photo_file_id: int | None = None


class ItemOut(ItemIn):
    id: int
    kind: Kind
    version: int
    sheet_file_id: int | None  # the house-style sheet; only an approved one is used in videos
    sheet_status: Literal["none", "drawing", "waiting_for_owner", "needs_approval", "approved"]
    owner_project_id: int | None = None  # "This video only"
    owner_script_id: int | None = None  # "This script only"


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
        "source_photo_file_id": item.source_photo_file_id,
        "sheet_file_id": item.sheet_file_id,
        "sheet_approved": item.sheet_approved,
    }


def sheet_status(item: LibraryItem) -> str:
    """Worked out, not stored, so a failed sheet job never leaves it stuck at "drawing"."""
    db = object_session(item)
    waiting = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)
    jobs = (
        db.scalars(
            select(Job).where(Job.workspace_id == item.workspace_id, Job.status.in_(waiting))
        )
        if db
        else []
    )
    mine = [j for j in jobs if j.input.get("library_item_id") == item.id]
    if any(j.status == JobStatus.needs_owner_approval for j in mine):
        return "waiting_for_owner"  # over the editor's allowance: held until the owner says yes
    if mine:
        return "drawing"
    if not item.sheet_file_id:
        return "none"
    return "approved" if item.sheet_approved else "needs_approval"


def _out(item: LibraryItem) -> ItemOut:
    data = {k: v for k, v in _snapshot(item).items() if k != "sheet_approved"}
    return ItemOut(
        id=item.id,
        kind=item.kind,
        version=item.version,
        sheet_status=sheet_status(item),
        owner_project_id=item.owner_project_id,
        owner_script_id=item.owner_script_id,
        **data,
    )


def get_item(
    db: Session, user: User, kind: Kind, item_id: int, archived: bool = False
) -> LibraryItem:
    """A live item (or, with archived=True, an archived one) in the caller's workspace."""
    item = db.get(LibraryItem, item_id)
    if (
        not item
        or item.workspace_id != user.workspace_id
        or item.kind != kind
        or item.archived != archived
    ):
        raise HTTPException(404, f"No such {kind}.")
    return item


def owned(item: LibraryItem) -> bool:
    return item.owner_project_id is not None or item.owner_script_id is not None


def pick_item(
    db: Session, user: User, kind: Kind, item_id: int, project=None, script_id: int | None = None
) -> LibraryItem:
    """An item picked for a video (`project`) or a script: a look made for another video or
    script isn't offered here, so it's not found (gaps #19)."""
    item = get_item(db, user, kind, item_id)
    if project is not None and script_id is None and project.script_draft_id:
        from app.models.script_library import ScriptDraft

        script_id = db.get(ScriptDraft, project.script_draft_id).script_id
    mine = (project is not None and item.owner_project_id == project.id) or (
        script_id is not None and item.owner_script_id == script_id
    )
    if owned(item) and not mine:
        raise HTTPException(404, f"No such {kind}.")
    return item


def _apply(db: Session, user: User, item: LibraryItem, values: dict) -> None:
    """Null means "leave as is" for every field except `voice_file_id` (null removes it)."""
    for field in ("name", "brand_ids"):
        if values.get(field) is None:
            values.pop(field, None)
    if item.kind != Kind.character and (values.get("outfits") or values.get("voice_file_id")):
        raise HTTPException(422, "Only characters have outfits and a voice.")
    images = list(values.get("image_file_ids") or [])
    images += [f for o in values.get("outfits") or [] for f in o["file_ids"]]
    for file_id in images:
        get_file(db, user, file_id, "image")
    if values.get("voice_file_id"):
        get_file(db, user, values["voice_file_id"], "audio")
    if values.get("source_photo_file_id"):
        if item.kind == Kind.prop:
            raise HTTPException(422, "Only characters and places have a source photo.")
        get_file(db, user, values["source_photo_file_id"], "image")
    if "brand_ids" in values:
        item.brands = [get_brand(db, user, b) for b in sorted(set(values.pop("brand_ids")))]
    for field, value in values.items():
        if value is not None or field in ("voice_file_id", "source_photo_file_id"):
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
    archived: bool = False,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """`archived=true` lists the archive instead, so items can be brought back."""
    query = select(LibraryItem).where(
        LibraryItem.workspace_id == user.workspace_id,
        LibraryItem.kind == kind,
        LibraryItem.archived.is_(archived),
        LibraryItem.owner_project_id.is_(None),  # a video's or script's own look stays there
        LibraryItem.owner_script_id.is_(None),
    )
    if brand_id is not None:
        query = query.where(LibraryItem.brands.any(id=brand_id))
    return [_out(i) for i in db.scalars(query.order_by(func.lower(LibraryItem.name)))]


@router.post("", response_model=ItemOut, status_code=201)
def create_item(
    kind: Kind, body: NewItemIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    from app import script_library as lib
    from app.routes.projects import get_project

    values = body.model_dump()
    project_id, script_id = values.pop("owner_project_id"), values.pop("owner_script_id")
    if project_id and script_id:
        raise HTTPException(422, "A look belongs to one video or one script, not both.")
    item = LibraryItem(workspace_id=user.workspace_id, kind=kind)
    if project_id:
        item.owner_project_id = get_project(db, user, project_id).id
    if script_id:
        item.owner_script_id = lib.editable(user, lib.get_script(db, user, script_id)).id
    _apply(db, user, item, values)
    db.add(item)
    db.commit()
    return _out(item)


@router.get("/{item_id}", response_model=ItemOut)
def read_item(
    kind: Kind, item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return _out(get_item(db, user, kind, item_id))


@router.patch("/{item_id}", response_model=ItemOut)
def update_item(
    kind: Kind,
    item_id: int,
    body: ItemPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    item = get_item(db, user, kind, item_id)
    _save_version(db, user, item)
    _apply(db, user, item, body.model_dump(exclude_unset=True))
    item.sheet_approved = False  # any edit (a new photo included) needs the sheet approved again
    db.commit()
    return _out(item)


@router.delete("/{item_id}", status_code=204)
def archive_item(
    kind: Kind, item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    """Archive (reversible: see unarchive). Anyone on the team can do this. On a look just
    saved to Cast & places, it's the Undo: the video goes back on its own look."""
    item = get_item(db, user, kind, item_id)
    if item.copied_from_id:
        from app.routes.project_assets import undo_save

        if undo_save(db, user, item):
            db.commit()
            return
    item.archived = True
    db.commit()


@router.post("/{item_id}/unarchive", response_model=ItemOut)
def unarchive_item(
    kind: Kind, item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    item = get_item(db, user, kind, item_id, archived=True)
    item.archived = False
    db.commit()
    return _out(item)


@router.delete("/{item_id}/permanent", status_code=204)
def delete_item_forever(
    kind: Kind, item_id: int, owner: User = Depends(owner_only), db: Session = Depends(get_db)
) -> None:
    """Owner only, and only from the archive: removes the item and its history for good."""
    item = get_item(db, owner, kind, item_id, archived=True)
    db.execute(delete(LibraryItemVersion).where(LibraryItemVersion.item_id == item.id))
    item.brands = []
    db.delete(item)
    db.commit()


@router.get("/{item_id}/versions", response_model=list[VersionOut])
def list_versions(
    kind: Kind, item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    item = get_item(db, user, kind, item_id)
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
    item = get_item(db, user, kind, item_id)
    old = db.scalar(
        select(LibraryItemVersion).where(
            LibraryItemVersion.item_id == item.id, LibraryItemVersion.version == version
        )
    )
    if not old:
        raise HTTPException(404, "No such version.")
    snapshot = dict(old.snapshot)
    # Brands archived since that version are left out, so old versions stay restorable.
    live = {
        b.id
        for b in db.scalars(select(Brand).where(Brand.id.in_(snapshot["brand_ids"])))
        if b.workspace_id == user.workspace_id and not b.archived
    }
    snapshot["brand_ids"] = [b for b in snapshot["brand_ids"] if b in live]
    _save_version(db, user, item)
    _apply(db, user, item, snapshot)
    db.commit()
    return _out(item)
