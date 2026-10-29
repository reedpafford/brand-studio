"""Characters, places and props, filtered by brand. Edits keep a version history."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, object_session

from app.advice import SaidText
from app.auth import current_user, owner_only
from app.db import get_db
from app.models.accounts import User
from app.models.brands import Brand
from app.models.jobs import Job, JobStatus
from app.models.library import Kind, LibraryItem, LibraryItemVersion
from app.routes.brands import get_brand
from app.routes.files import get_file
from app.schemas import LongText, Name, UtcTime


def look_writer(
    request: Request,
    item_id: int | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    """A video's own look is changed only by whoever made the video, or the owner; a script's
    own look by its author or the owner. Cast & places items keep their own rules."""
    from app.routes.projects import WRITES, _mine

    item = db.get(LibraryItem, item_id) if item_id is not None else None
    if request.method not in WRITES or item is None or user.is_owner:
        return
    if item.workspace_id != user.workspace_id:
        return  # not found, said by the route itself
    if item.owner_project_id:
        _mine(db, user, item.owner_project_id)
    elif item.owner_script_id:
        from app.models.script_library import Script

        script = db.get(Script, item.owner_script_id)
        if script is not None and script.created_by_id != user.id:
            raise HTTPException(403, "Only the script's author, or the owner, changes its looks.")


router = APIRouter(prefix="/library/{kind}", tags=["library"],
                   dependencies=[Depends(look_writer)])  # fmt: skip


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
    # Products (flows BR1; owner only): what it is in a line, and the claim scripts may make
    short_description: LongText | None = None  # left out: as it is
    main_claim: LongText | None = None


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
    short_description: LongText | None = None  # products, owner only
    main_claim: LongText | None = None  # products, owner only


class LookFitOut(BaseModel):
    seen: SaidText  # "This look reads as: girl of about 10"
    problem: SaidText  # Redo it's note, prefilled


class LookSheetOut(BaseModel):
    file_id: int | None
    status: Literal["none", "drawing", "waiting_for_owner", "needs_approval", "approved"]


class ItemOut(ItemIn):
    id: int
    kind: Kind
    version: int
    sheet_file_id: int | None  # the house-style sheet; only an approved one is used in videos
    sheet_status: Literal["none", "drawing", "waiting_for_owner", "needs_approval", "approved"]
    owner_project_id: int | None = None  # "This video only"
    owner_script_id: int | None = None  # "This script only"
    look_fit: LookFitOut | None = None  # the sheet doesn't read as its role: advice, Redo it
    sheet_credits: int = 0  # Make sheet / Redo: "up to" (its check and one redo, held)
    sheet_usual_credits: int = 0  # "Usually N": the sheet and its check
    change_credits: int = 0  # Change this…: the sheet and its check (never redone by itself)
    advice: list[str] = []  # a product with no main claim: "Scripts won't mention…" (BR1)
    look_sheets: dict[str, LookSheetOut] = {}  # ST2: the owner's sheets in other looks


class VersionOut(BaseModel):
    version: int
    snapshot: ItemIn
    saved_by_id: int | None
    created_at: UtcTime


PRODUCT_WORDS = ("short_description", "main_claim")
NO_CLAIM = "Scripts won't mention a claim for this product."


def _snapshot(item: LibraryItem) -> dict:
    return {
        "name": item.name,
        "notes": item.notes,
        "brand_ids": sorted(b.id for b in item.brands),
        "image_file_ids": item.image_file_ids,
        "outfits": item.outfits,
        "voice_file_id": item.voice_file_id,
        "source_photo_file_id": item.source_photo_file_id,
        "short_description": item.short_description,
        "main_claim": item.main_claim,
        "sheet_file_id": item.sheet_file_id,
        "sheet_approved": item.sheet_approved,
        "look_sheets": item.look_sheets or {},
    }


def _waiting_sheets(item: LibraryItem) -> list[Job]:
    """This item's sheet jobs not finished yet (queued, running or held for the owner)."""
    db = object_session(item)
    waiting = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)
    jobs = (
        db.scalars(
            select(Job).where(Job.workspace_id == item.workspace_id, Job.status.in_(waiting))
        )
        if db
        else []
    )
    return [j for j in jobs if j.input.get("library_item_id") == item.id]


def _sheet_looks_drawing(item: LibraryItem) -> list[str]:
    """The other looks (ST2) a sheet is being drawn in, so one whose first sheet isn't back
    yet is listed as drawing (Flow-QA on #944: "Make a {look} sheet" would offer it again)."""
    return [look for j in _waiting_sheets(item) if (look := j.input.get("sheet_look_id"))]


def sheet_status(item: LibraryItem, look: str | None = None) -> str:
    """Worked out, not stored, so a failed sheet job never leaves it stuck at "drawing".
    `look`: the owner's sheet in another look (ST2), else the House one."""
    mine = [j for j in _waiting_sheets(item) if j.input.get("sheet_look_id") == look]
    if any(j.status == JobStatus.needs_owner_approval for j in mine):
        return "waiting_for_owner"  # over the editor's allowance: held until the owner says yes
    if mine:
        return "drawing"
    sheet = (item.look_sheets or {}).get(look) or {} if look else {
        "file_id": item.sheet_file_id, "approved": item.sheet_approved}  # fmt: skip
    if not sheet.get("file_id"):
        return "none"
    return "approved" if sheet.get("approved") else "needs_approval"


def _prices(item: LibraryItem) -> dict:
    from app.credits import price
    from app.sheets import SHEET_KINDS, press_price, press_usual

    db = object_session(item)
    if db is None or item.kind not in SHEET_KINDS:
        return {}
    return {
        "sheet_credits": price(press_price(db, item)),
        "sheet_usual_credits": price(press_usual(db, item)),
        "change_credits": price(press_price(db, item, change=True)),
    }


def _out(item: LibraryItem) -> ItemOut:
    data = {k: v for k, v in _snapshot(item).items() if k not in ("sheet_approved", "look_sheets")}
    drawing = _sheet_looks_drawing(item)  # a look's first sheet: listed while it's drawn
    looks = {k: LookSheetOut(file_id=(item.look_sheets or {}).get(k, {}).get("file_id"),
                             status=sheet_status(item, k))
             for k in dict.fromkeys([*(item.look_sheets or {}), *drawing])}  # fmt: skip
    return ItemOut(
        id=item.id,
        kind=item.kind,
        version=item.version,
        sheet_status=sheet_status(item),
        owner_project_id=item.owner_project_id,
        owner_script_id=item.owner_script_id,
        look_fit=item.look_fit,
        advice=[NO_CLAIM] if item.kind == Kind.prop and not item.main_claim.strip() else [],
        look_sheets=looks,
        **_prices(item),
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
    words = {k for k in PRODUCT_WORDS  # changed, not just sent again (a version, a create)
             if values.get(k) is not None and values[k] != (getattr(item, k) or "")}  # fmt: skip
    if words and item.kind != Kind.prop:
        raise HTTPException(422, "Only products have a description and a main claim.")
    if words and not user.is_owner:
        raise HTTPException(403, "Only the owner changes the brand.")
    for field in PRODUCT_WORDS:
        if values.get(field) is None:
            values.pop(field, None)
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
    values = body.model_dump(exclude_unset=True)
    words_only = set(values) <= set(PRODUCT_WORDS)  # a product's words don't change its picture
    if not words_only:
        _save_version(db, user, item)
    _apply(db, user, item, values)
    if not words_only:
        item.sheet_approved = False  # any other edit needs the sheet approved again
    db.commit()
    return _out(item)


@router.delete("/{item_id}", status_code=204)
def archive_item(
    kind: Kind, item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    """Archive (reversible: see unarchive). Anyone on the team can do this."""
    item = get_item(db, user, kind, item_id)
    if owned(item):
        _may_remove_look(db, user, item)
    item.archived = True
    db.commit()


def _may_remove_look(db: Session, user: User, look: LibraryItem) -> None:
    """A video's or script's own look (QA on #423): Reed, or whoever made that video or script,
    and never while a role still uses it. It's archived, so Undo (unarchive) brings it back."""
    from app import script_library as lib
    from app.models.projects import Project
    from app.models.script_library import ScriptCastSlot, ScriptDraft

    if look.owner_project_id:
        project = db.get(Project, look.owner_project_id)
        if not (user.is_owner or project.created_by_id == user.id):
            raise HTTPException(
                403, "Only the owner or whoever made this video can remove its looks."
            )
        in_use = look.id in project.cast_ids or look.id in project.slot_cast.values()
    else:
        script = lib.editable(user, lib.get_script(db, user, look.owner_script_id))
        drafts = select(ScriptDraft.id).where(ScriptDraft.script_id == script.id)
        locked = select(ScriptCastSlot.id).where(
            ScriptCastSlot.script_id == script.id, ScriptCastSlot.library_item_id == look.id
        )
        videos = db.scalars(select(Project.cast_ids).where(Project.script_draft_id.in_(drafts)))
        in_use = db.scalar(locked.limit(1)) is not None or any(look.id in c for c in videos)
    if in_use:
        raise HTTPException(409, "Swap the role to another look first.")


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
