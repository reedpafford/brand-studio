"""The Assets step (workflow v2): every character and place the breakdown uses, with its look.
Locked cast slots come preloaded with their look; an unlocked slot gets a character from the
editor (picked or new), whose sheet is made and approved with the library's sheet routes.
Storyboard and takes already refuse until every sheet they need is approved."""

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import breakdown, cast_roles
from app.auth import current_user
from app.credits import get_limits
from app.db import get_db
from app.enhance import project_screens, screen_name
from app.models.accounts import User
from app.models.brands import Brand
from app.models.breakdowns import BreakdownVersion
from app.models.library import Kind, LibraryItem, LibraryItemVersion
from app.models.projects import Project
from app.models.script_library import ScriptCastSlot, ScriptDraft
from app.prompts.schemas import Breakdown
from app.routes.clips import generation_on
from app.routes.library import LookFitOut, pick_item, sheet_status
from app.routes.projects import get_project
from app.routes.script_cast import RoleFacts, role_facts
from app.routes.scripts import latest
from app.routes.sheets import SheetIn, make_sheet
from app.schemas import Name

router = APIRouter(prefix="/projects/{project_id}/assets", tags=["assets"])


class AssetOut(BaseModel):
    kind: str  # character | place | product | screen
    ref: str  # as the breakdown names it: char:5, place:2, or slot:3 until it has a character
    role: str  # the cast slot's role, else the item's name
    library_item_id: int | None
    name: str
    locked: bool  # a locked slot: its look is fixed for every version
    sheet_status: str  # none | drawing | waiting_for_owner | needs_approval | approved | missing
    ready: bool  # nothing left to do for it
    slot_id: int | None = None  # the script's cast slot this row fills; null for other rows
    description: str = ""  # the slot's role, as the script describes it (e.g. "teen, shy")
    shots: int = 0  # how many of the breakdown's shots it is in ("In 3 shots")
    file_id: int | None = None  # a product's or screen's picture (the brand's; nothing to make)
    only_here: Literal["video", "script"] | None = None  # "This video only" / "This script only"
    own_look_id: int | None = None  # the look made for this role here; "Not used" if swapped out
    facts: RoleFacts | None = None  # the role's age range, gender and job (a slot's row only)
    look_fit: LookFitOut | None = None  # its sheet doesn't read as the role: advice, Redo it


class SaveLookIn(BaseModel):
    name: Name


class SavedOut(BaseModel):
    library_item_id: int  # the new Cast & places character; Undo is DELETE on it
    assets: list[AssetOut]


class SlotCastIn(BaseModel):
    library_item_id: int


def _newest(db: Session, project: Project) -> BreakdownVersion | None:
    return db.scalar(
        select(BreakdownVersion)
        .where(BreakdownVersion.project_id == project.id)
        .order_by(BreakdownVersion.id.desc())
        .limit(1)
    )


def _slots(db: Session, project: Project) -> list[ScriptCastSlot]:
    if not project.script_draft_id:
        return []
    draft = db.get(ScriptDraft, project.script_draft_id)
    query = select(ScriptCastSlot).where(ScriptCastSlot.script_id == draft.script_id)
    return list(db.scalars(query.order_by(ScriptCastSlot.position)))


def _row(
    kind: str, ref: str, role: str, item: LibraryItem | None, locked: bool, slot=None
) -> AssetOut:
    status = "missing" if item is None else ("approved" if locked else sheet_status(item))
    only = None
    if item is not None and item.owner_project_id:
        only = "video"
    elif item is not None and item.owner_script_id:
        only = "script"
    return AssetOut(
        only_here=only,
        kind=kind,
        ref=ref,
        role=role or (item.name if item else ""),
        library_item_id=item.id if item else None,
        name=item.name if item else "",
        locked=locked,
        sheet_status=status,
        ready=status == "approved",
        slot_id=slot.id if slot else None,
        description=slot.description if slot else "",
        facts=role_facts(slot.description, slot.guessed or []) if slot else None,
        look_fit=item.look_fit if item else None,
    )


@router.get("", response_model=list[AssetOut])
def list_assets(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Cast slots first (locked, then unlocked), then the breakdown's other characters, its
    places, then the products and screens its shots show, each once."""
    project = get_project(db, user, project_id)
    bd = _newest(db, project)
    data = bd.data if bd else {"scenes": []}
    shots = [s for scene in data["scenes"] for s in scene["shots"]]
    used = list(dict.fromkeys(c for s in shots for c in s["character_ids"]))
    places = list(dict.fromkeys(s["place_id"] for s in shots if s.get("place_id")))
    out, seen = [], set()
    for slot in _slots(db, project):
        item_id = slot.library_item_id or project.slot_cast.get(str(slot.id))
        item = db.get(LibraryItem, item_id) if item_id else None
        out.append(_row("character", f"slot:{slot.id}" if not item_id else f"char:{item_id}",
                        slot.role, item, slot.library_item_id is not None, slot))  # fmt: skip
        own = db.get(LibraryItem, project.slot_looks.get(str(slot.id)) or 0)
        out[-1].own_look_id = own.id if own and not own.archived else None  # removed: gone
        seen.add(f"char:{item_id}")
    for ref in used:
        if ref in seen or not ref.startswith("char:"):
            continue
        out.append(_row("character", ref, "", db.get(LibraryItem, int(ref[5:])), False))
    for ref in places:
        out.append(_row("place", ref, "", db.get(LibraryItem, int(ref.split(":")[1])), False))
    screens = {f"screen:{s.id}": s for s in project_screens(db, project)}
    for ref in dict.fromkeys(r for s in shots for r in s.get("screen_ids", [])):
        if screen := screens.get(ref):
            kind = "product" if "product" in screen.tags else "screen"
            out.append(AssetOut(kind=kind, ref=ref, role="", library_item_id=None,
                                name=screen_name(screen), locked=False, sheet_status="approved",
                                ready=True, file_id=screen.file_id))  # fmt: skip
    for row in out:
        refs = {row.ref, f"slot:{row.slot_id}"}
        row.shots = sum(
            1
            for s in shots
            if refs & {*s["character_ids"], s.get("place_id"), *s.get("screen_ids", [])}
        )
    return out


@router.put("/slots/{slot_id}", response_model=list[AssetOut])
def cast_slot(
    project_id: int,
    slot_id: int,
    body: SlotCastIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Give an unlocked slot its character: it joins the cast, and the newest breakdown's
    slot:N becomes char:M (saved as a new breakdown version)."""
    project = get_project(db, user, project_id)
    slot = _open_slot(db, project, slot_id)
    item = pick_item(db, user, Kind.character, body.library_item_id, project)
    _cast(db, user, project, slot, item)
    db.commit()
    return list_assets(project_id, user, db)


def _open_slot(db: Session, project: Project, slot_id: int) -> ScriptCastSlot:
    slot = next((s for s in _slots(db, project) if s.id == slot_id), None)
    if not slot:
        raise HTTPException(404, "No such cast slot in this video.")
    if slot.library_item_id:
        raise HTTPException(409, f"{slot.role} is locked to one look for every version.")
    return slot


def _cast(
    db: Session, user: User, project: Project, slot, item: LibraryItem, same_look=False
) -> None:
    old = project.slot_cast.get(str(slot.id))
    others = {s.library_item_id for s in _slots(db, project)}
    others |= {v for k, v in project.slot_cast.items() if k != str(slot.id)}
    if old in others:  # another role uses that character too: leave its shots alone
        old = None
    project.slot_cast = {**project.slot_cast, str(slot.id): item.id}
    project.cast_ids = sorted({*(c for c in project.cast_ids if c != old), item.id})
    bd = _newest(db, project)
    if bd:
        text = json.dumps(bd.data)
        for before in (f'"slot:{slot.id}"', f'"char:{old}"' if old else None):
            if before:
                text = text.replace(before, f'"char:{item.id}"')
        new = Breakdown.model_validate(json.loads(text))
        script = latest(db, project)
        row = BreakdownVersion(
            project_id=project.id,
            script_version=bd.script_version,
            source="edit",
            data=new.model_dump(),
            problems=breakdown.problems(db, project, script.text if script else "", new),
            created_by_id=user.id,
        )
        db.add(row)
        db.flush()
        # Frames follow the new look for free; stills of the old one are redrawn if covered.
        outdated = cast_roles.carry_frames(db, project, bd, row, same_look)
        cast_roles.redraw(db, project, user, outdated)


@router.post(
    "/slots/{slot_id}/make-look",
    response_model=list[AssetOut],
    dependencies=[Depends(generation_on)],
)
def make_look(
    project_id: int, slot_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Make a look for this video only, from the role's name and description, cast the role
    to it, and draw its sheet (paid, from this video's budget). Never in Cast & places."""
    project = get_project(db, user, project_id)
    slot = _open_slot(db, project, slot_id)
    mine = db.get(LibraryItem, project.slot_looks.get(str(slot.id)) or 0)
    if mine and not mine.archived:  # a removed one can be made again
        raise HTTPException(409, f"{slot.role} already has a look for this video.")
    look = LibraryItem(
        workspace_id=project.workspace_id,
        kind=Kind.character,
        name=cast_roles.short(slot.role) or slot.role,
        notes=slot.description or slot.role,
        owner_project_id=project.id,
    )
    db.add(look)
    db.flush()
    project.slot_looks = {**project.slot_looks, str(slot.id): look.id}  # the sheet knows its role
    make_sheet(Kind.character, look.id, SheetIn(), user, db)  # commits; a refusal adds nothing
    _cast(db, user, project, slot, look)
    db.commit()
    return list_assets(project_id, user, db)


@router.post("/slots/{slot_id}/save-to-library", response_model=SavedOut, status_code=201)
def save_to_library(
    project_id: int,
    slot_id: int,
    body: SaveLookIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Copy this video's look into Cast & places as a normal character (free: same sheet) and
    use the copy here. Reed always; editors only with the Team setting on."""
    project = get_project(db, user, project_id)
    if not user.is_owner and not get_limits(db, user.workspace_id).editors_can_save_looks:
        raise HTTPException(403, "Only the owner can save looks to Cast & places.")
    slot = _open_slot(db, project, slot_id)
    look = db.get(LibraryItem, project.slot_cast.get(str(slot.id)) or 0)
    if look is None or look.owner_project_id != project.id:
        raise HTTPException(409, f"{slot.role} doesn't have a look made for this video.")
    if sheet_status(look) != "approved":
        raise HTTPException(409, "Approve the sheet first.")
    name = body.name.strip()
    taken = db.scalar(
        select(LibraryItem.id).where(
            LibraryItem.workspace_id == project.workspace_id,
            LibraryItem.kind == Kind.character,
            LibraryItem.archived.is_(False),
            LibraryItem.owner_project_id.is_(None),
            LibraryItem.owner_script_id.is_(None),
            func.lower(LibraryItem.name) == name.lower(),
        )
    )
    if taken:
        raise HTTPException(409, f"{name} is already in Cast & places. Pick another name.")
    copy = LibraryItem(
        workspace_id=look.workspace_id,
        kind=Kind.character,
        name=name,
        notes=look.notes,
        image_file_ids=look.image_file_ids,
        outfits=look.outfits,
        voice_file_id=look.voice_file_id,
        source_photo_file_id=look.source_photo_file_id,
        sheet_file_id=look.sheet_file_id,
        sheet_approved=True,
        copied_from_id=look.id,
        brands=[db.get(Brand, project.brand_id)],
    )
    db.add(copy)
    db.flush()
    _cast(db, user, project, slot, copy, same_look=True)
    db.commit()
    return SavedOut(library_item_id=copy.id, assets=list_assets(project_id, user, db))


def undo_save(db: Session, user: User, copy: LibraryItem) -> bool:
    """Undo of Save to Cast & places (DELETE on the copy): the video goes back on its own look
    and the copy goes for good, unless another video has picked it since (then it's only
    archived, as any DELETE)."""
    look = db.get(LibraryItem, copy.copied_from_id)
    project = db.get(Project, look.owner_project_id) if look and look.owner_project_id else None
    if project is None:
        return False
    for key, item_id in list(project.slot_cast.items()):
        if item_id == copy.id:
            slot = db.get(ScriptCastSlot, int(key))
            look.archived = False  # removed after the save (nobody used it): it's back in use
            _cast(db, user, project, slot, look, same_look=True)
    used = db.scalars(select(Project.cast_ids).where(Project.workspace_id == copy.workspace_id))
    if any(copy.id in ids for ids in used):
        return False
    db.execute(delete(LibraryItemVersion).where(LibraryItemVersion.item_id == copy.id))
    copy.brands = []
    db.delete(copy)
    return True
