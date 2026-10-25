"""A script's cast slots (Reed, 2026-10-25 #197): every named or recurring role, shared by all
its versions. Each is optional. A locked slot uses one library character and the sheet it had
when locked, as-is in every version; unlocked slots are made at the editor's Assets step."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import script_library as lib
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.library import Kind
from app.models.script_library import Script, ScriptCastSlot
from app.routes.library import get_item
from app.schemas import LongText
from app.sheets import require_sheet

router = APIRouter(prefix="/scripts/{script_id}/cast", tags=["script library"])
Role = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class SlotIn(BaseModel):
    role: Role
    description: LongText = ""


class SlotPatch(BaseModel):
    role: Role | None = None
    description: LongText | None = None
    position: int | None = None


class LockIn(BaseModel):
    library_item_id: int


class SlotOut(BaseModel):
    id: int
    role: str
    description: str
    position: int
    library_item_id: int | None  # locked to this character
    sheet_file_id: int | None  # the look used in every version
    locked: bool


def slots(db: Session, script: Script) -> list[SlotOut]:
    rows = db.scalars(
        select(ScriptCastSlot)
        .where(ScriptCastSlot.script_id == script.id)
        .order_by(ScriptCastSlot.position, ScriptCastSlot.id)
    )
    return [
        SlotOut(
            id=s.id,
            role=s.role,
            description=s.description,
            position=s.position,
            library_item_id=s.library_item_id,
            sheet_file_id=s.sheet_file_id,
            locked=s.library_item_id is not None,
        )
        for s in rows
    ]


def _slot(db: Session, user: User, script_id: int, slot_id: int) -> tuple[Script, ScriptCastSlot]:
    script = lib.editable(user, lib.get_script(db, user, script_id))
    slot = db.get(ScriptCastSlot, slot_id)
    if not slot or slot.script_id != script.id:
        raise HTTPException(404, "No such cast slot.")
    return script, slot


def _unique(db: Session, script: Script, role: str, slot_id: int | None = None) -> None:
    taken = db.scalar(
        select(ScriptCastSlot.id).where(
            ScriptCastSlot.script_id == script.id,
            func.lower(ScriptCastSlot.role) == role.lower(),
            ScriptCastSlot.id != (slot_id or 0),
        )
    )
    if taken:
        raise HTTPException(409, f"There's already a slot called {role}.")


@router.get("", response_model=list[SlotOut])
def list_slots(script_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return slots(db, lib.get_script(db, user, script_id))


@router.post("", response_model=list[SlotOut], status_code=201)
def add_slot(
    script_id: int, body: SlotIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    script = lib.editable(user, lib.get_script(db, user, script_id))
    _unique(db, script, body.role)
    last = db.scalar(
        select(func.max(ScriptCastSlot.position)).where(ScriptCastSlot.script_id == script.id)
    )
    db.add(ScriptCastSlot(script_id=script.id, position=(last or 0) + 1, **body.model_dump()))
    db.commit()
    return slots(db, script)


@router.patch("/{slot_id}", response_model=list[SlotOut])
def edit_slot(
    script_id: int,
    slot_id: int,
    body: SlotPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Rename it, describe it, or move it in the list."""
    script, slot = _slot(db, user, script_id, slot_id)
    values = body.model_dump(exclude_none=True)
    if "role" in values:
        _unique(db, script, values["role"], slot.id)
    for field, value in values.items():
        setattr(slot, field, value)
    db.commit()
    return slots(db, script)


@router.delete("/{slot_id}", response_model=list[SlotOut])
def remove_slot(
    script_id: int, slot_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    script, slot = _slot(db, user, script_id, slot_id)
    db.delete(slot)
    db.commit()
    return slots(db, script)


@router.post("/{slot_id}/lock", response_model=list[SlotOut])
def lock(
    script_id: int,
    slot_id: int,
    body: LockIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Lock the role to a character's approved look; it's used as-is in every version."""
    script, slot = _slot(db, user, script_id, slot_id)
    item = get_item(db, user, Kind.character, body.library_item_id)
    require_sheet(item)  # 422 "Approve Maya's sheet first."
    if not item.sheet_file_id:
        raise HTTPException(422, f"Approve {item.name}'s sheet first.")
    slot.library_item_id, slot.sheet_file_id, slot.locked_by_id = (
        item.id,
        item.sheet_file_id,
        user.id,
    )
    db.commit()
    return slots(db, script)


@router.delete("/{slot_id}/lock", response_model=list[SlotOut])
def unlock(
    script_id: int, slot_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Unlock it: the editor makes this character at the Assets step."""
    script, slot = _slot(db, user, script_id, slot_id)
    slot.library_item_id = slot.sheet_file_id = slot.locked_by_id = None
    db.commit()
    return slots(db, script)
