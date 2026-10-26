"""The Assets step (workflow v2): every character and place the breakdown uses, with its look.
Locked cast slots come preloaded with their look; an unlocked slot gets a character from the
editor (picked or new), whose sheet is made and approved with the library's sheet routes.
Storyboard and takes already refuse until every sheet they need is approved."""

import json
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import breakdown, cast_roles, clip_prompts
from app.auth import current_user
from app.credits import COUNTED, fits, get_limits, price
from app.db import get_db
from app.enhance import project_screens, screen_name
from app.models.accounts import User
from app.models.brands import Brand
from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job, JobStatus
from app.models.library import Kind, LibraryItem, LibraryItemVersion
from app.models.projects import Project
from app.models.script_library import ScriptCastSlot, ScriptDraft
from app.prompts.schemas import Breakdown
from app.routes.clips import generation_on
from app.routes.library import LookFitOut, pick_item, sheet_status
from app.routes.projects import get_project
from app.routes.script_cast import RoleFacts, role_facts
from app.routes.scripts import latest
from app.routes.sheets import SheetIn, queue_sheet
from app.schemas import Name
from app.sheets import look_price, look_usual

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
    declined: bool = False  # Not now on the missing-looks note: never made by itself again
    look_credits: int | None = None  # Make a look on a role: "up to" (held at the press)
    look_usual_credits: int | None = None  # "Usually N": its sheet and check, no redo


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
    look = price(look_price(db, project.workspace_id))
    usual_look = price(look_usual(db, project.workspace_id))
    for slot in _slots(db, project):
        item_id = slot.library_item_id or project.slot_cast.get(str(slot.id))
        item = db.get(LibraryItem, item_id) if item_id else None
        out.append(_row("character", f"slot:{slot.id}" if not item_id else f"char:{item_id}",
                        slot.role, item, slot.library_item_id is not None, slot))  # fmt: skip
        own = db.get(LibraryItem, project.slot_looks.get(str(slot.id)) or 0)
        out[-1].own_look_id = own.id if own and not own.archived else None  # removed: gone
        out[-1].declined = project.slot_looks.get(str(slot.id), 0) is None
        out[-1].look_credits, out[-1].look_usual_credits = look, usual_look
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
        cast_roles.carry_clips(db, project, bd, row)
        clip_prompts.follow(db, project, user)


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
    _make_look(db, user, project, slot)
    return list_assets(project_id, user, db)


def _make_look(
    db: Session, user: User, project: Project, slot: ScriptCastSlot, auto: bool = False
) -> None:
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
    queue_sheet(db, user, look, SheetIn(), auto=auto)  # commits; a refusal adds nothing
    _cast(db, user, project, slot, look)
    db.commit()


class MadeOut(BaseModel):
    looks: int  # looks Assets made by itself for this video
    credits_used: int  # what they really cost, whole credits: sheets, checks and any redo
    drawing: bool  # some are still being made or checked: the figure may still grow


class MissingLooksOut(BaseModel):
    slot_ids: list[int]  # roles in this video's shots with no character and no look made yet
    roles: list[str]
    credits: int  # "up to": each look's sheet, check and one redo, held at the press
    usual_credits: int = 0  # "Usually N": the sheets and checks, no redo
    made: MadeOut | None = None  # "Made 3 looks · 7 credits", once Assets has made some
    reason: str | None = None  # why they can't all be made (plain), or null when they fit


def _missing(db: Session, project: Project) -> list[ScriptCastSlot]:
    """The roles Assets makes looks for by itself (Reed, 2026-10-26): every cast slot (a main
    or recurring role; background people are never slots) that the newest breakdown's shots
    show, with no character picked and no look made for it here. A look the editor removed,
    or a role they said Not now to (kept as no look), is never made again by itself."""
    bd = _newest(db, project)
    shown = {
        c for s in (bd.data["scenes"] if bd else []) for x in s["shots"] for c in x["character_ids"]
    }
    return [
        s
        for s in _slots(db, project)
        if s.library_item_id is None
        and str(s.id) not in project.slot_cast
        and str(s.id) not in project.slot_looks
        and f"slot:{s.id}" in shown
    ]


def _missing_out(db: Session, user: User, project: Project) -> MissingLooksOut:
    slots = _missing(db, project)
    total = look_price(db, project.workspace_id) * len(slots)
    why = fits(db, project, user, total) if slots else ""
    n = len(slots)
    said = f"Making {'a look' if n == 1 else f'{n} looks'} (up to {price(total)} credits) {why}"
    return MissingLooksOut(
        slot_ids=[s.id for s in slots],
        roles=[cast_roles.short(s.role) or s.role for s in slots],
        credits=price(total) if slots else 0,
        usual_credits=price(look_usual(db, project.workspace_id) * n) if slots else 0,
        reason=said if why else None,
        made=_made(db, project),
    )


def _made(db: Session, project: Project) -> MadeOut | None:
    """The looks Assets made by itself (make-missing) and their real cost: the jobs it started
    for them (sheet, check, the one redo), stopped ones not counted."""
    own = {v for v in project.slot_looks.values() if v}
    jobs = [
        j
        for j in db.scalars(
            select(Job).where(Job.project_id == project.id, Job.status.in_(COUNTED))
        )
        if j.input.get("auto_made") and j.input.get("library_item_id") in own
    ]
    if not jobs:
        return None
    return MadeOut(
        looks=len({j.input["library_item_id"] for j in jobs}),
        credits_used=price(sum((j.credits for j in jobs), Decimal(0))),
        drawing=any(j.status != JobStatus.succeeded for j in jobs),
    )


@router.get("/missing-looks", response_model=MissingLooksOut)
def missing_looks(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """What opening Assets will make by itself, with its price and, if it doesn't fit, why."""
    return _missing_out(db, user, get_project(db, user, project_id))


@router.post(
    "/make-missing",
    response_model=list[AssetOut],
    dependencies=[Depends(generation_on)],
)
def make_missing_looks(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Make a look for every role that has none (`_missing`), each for this video only, paid
    from its budget or the editor's week. All or none: if they don't all fit, nothing is made
    and the plain reason comes back (409). Each sheet still needs the editor's Approve (or a
    Redo, or a swap) before Storyboard; Storyboard refuses until then."""
    project = get_project(db, user, project_id)
    out = _missing_out(db, user, project)
    if out.reason:
        raise HTTPException(409, out.reason)
    for slot in _missing(db, project):
        _make_look(db, user, project, slot, auto=True)
    return list_assets(project_id, user, db)


@router.post("/missing-looks/decline", response_model=MissingLooksOut)
def decline_missing_looks(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Not now: the roles waiting for a look are left for the editor's own Make a look, and
    opening Assets never makes them by itself again."""
    project = get_project(db, user, project_id)
    waiting = {str(s.id): None for s in _missing(db, project)}
    project.slot_looks = {**project.slot_looks, **waiting}
    db.commit()
    return _missing_out(db, user, project)


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
