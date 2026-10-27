"""A script's cast slots (Reed, 2026-10-25 #197): every named or recurring role, shared by all
its versions. Each is optional. A locked slot uses one library character and the sheet it had
when locked, as-is in every version; unlocked slots are made at the editor's Assets step."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import merge_roles
from app import script_library as lib
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.library import Kind
from app.models.script_library import Script, ScriptCastSlot
from app.routes.library import pick_item
from app.schemas import LongText
from app.sheets import require_sheet

router = APIRouter(prefix="/scripts/{script_id}/cast", tags=["script library"])
Role = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
SlotKind = Literal["Main", "Helper", "Rival", "Family"]


class SlotIn(BaseModel):
    role: Role
    kind: SlotKind | None = None  # Main when not given; reading the cast sets it
    description: LongText = ""


class SlotPatch(BaseModel):
    role: Role | None = None
    kind: SlotKind | None = None
    description: LongText | None = None
    position: int | None = None


class LockIn(BaseModel):
    library_item_id: int


class Fact(BaseModel):
    value: str
    inferred: bool  # a guess from the story: shown as "(a guess)"


class RoleFacts(BaseModel):
    """Who the role is, from its description's lead ("Mid-40s woman, a teacher; …")."""

    age_range: Fact | None = None
    gender: Fact | None = None
    occupation: Fact | None = None


def role_facts(description: str, guessed: list[str]) -> RoleFacts:
    from app.prompts.check import AGE, GENDER

    who, _, job = description.split(";", 1)[0].partition(",")
    found = GENDER.search(who)
    age = who[: found.start()].strip() if found else who.strip()

    def fact(value: str, name: str) -> Fact | None:
        return Fact(value=value, inferred=name in guessed) if value else None

    return RoleFacts(
        age_range=fact(age if AGE.search(age) else "", "age"),
        gender=fact(found[0].lower() if found else "", "gender"),
        occupation=fact(  # only in the lead's shape ("17-year-old boy, a student")
            job.strip().removeprefix("a ").removeprefix("an ") if found else "", "occupation"
        ),
    )


class SlotOut(BaseModel):
    id: int
    role: str
    kind: str  # Main, Helper, Rival or Family
    description: str
    position: int
    appears_in: list[int]  # version slots the last cast read found it in; [] = not any more
    library_item_id: int | None  # locked to this character
    sheet_file_id: int | None  # the look used in every version
    locked: bool
    facts: RoleFacts = RoleFacts()  # age range, gender and job, each marked when a guess


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
            kind=s.kind,
            description=s.description,
            position=s.position,
            appears_in=s.appears_in or [],
            library_item_id=s.library_item_id,
            sheet_file_id=s.sheet_file_id,
            locked=s.library_item_id is not None,
            facts=role_facts(s.description, s.guessed or []),
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


class Line(BaseModel):
    version: str  # A, B or C
    line: int  # 1-based, in that version's script


class Moved(BaseModel):
    shots: list[str]
    lines: list[Line]


class LookName(BaseModel):
    name: str


class MergePreview(BaseModel):
    """What a merge moves; the merged role's look (if any) is left unused, never deleted."""

    moved: Moved
    look_unused: LookName | None


class MergeIn(BaseModel):
    into_slot_id: int


class Merged(MergePreview):
    token: int  # for Undo
    cast: list[SlotOut]


class UndoIn(BaseModel):
    token: int


class SamePair(BaseModel):
    a_slot_id: int
    b_slot_id: int
    into_slot_id: int  # the suggested role to keep
    why: str


class PairIn(BaseModel):
    a_slot_id: int
    b_slot_id: int


@router.get("/maybe-same", response_model=list[SamePair])
def maybe_same(script_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Roles that may be one person, never two kept apart or seen in one shot."""
    return merge_roles.maybe_same(db, lib.get_script(db, user, script_id))


@router.post("/maybe-same/dismiss", response_model=list[SamePair])
def dismiss(
    script_id: int, body: PairIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """They're different: the pair isn't suggested again."""
    script = lib.editable(user, lib.get_script(db, user, script_id))
    merge_roles.dismiss(script, body.a_slot_id, body.b_slot_id)
    db.commit()
    return merge_roles.maybe_same(db, script)


@router.delete("/maybe-same/dismiss", response_model=list[SamePair])
def undo_dismiss(
    script_id: int, body: PairIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Undo "They're different"."""
    script = lib.editable(user, lib.get_script(db, user, script_id))
    merge_roles.dismiss(script, body.a_slot_id, body.b_slot_id, undo=True)
    db.commit()
    return merge_roles.maybe_same(db, script)


@router.post("/merge/undo", response_model=list[SlotOut])
def undo_merge(
    script_id: int, body: UndoIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Put a merged role back, with its shots, lines and look as they were."""
    script = lib.editable(user, lib.get_script(db, user, script_id))
    merge_roles.undo(db, script, body.token)
    db.commit()
    return slots(db, script)


@router.get("/{slot_id}/merge/preview", response_model=MergePreview)
def merge_preview(
    script_id: int,
    slot_id: int,
    into: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """What merging this role into `into` would move, before it's done."""
    script = lib.editable(user, lib.get_script(db, user, script_id))
    return merge_roles.preview(db, script, *merge_roles.pair(db, script, slot_id, into))


@router.post("/{slot_id}/merge", response_model=Merged)
def merge(
    script_id: int,
    slot_id: int,
    body: MergeIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Merge this role into another: its shots and lines move there (see app/merge_roles.py)."""
    script = lib.editable(user, lib.get_script(db, user, script_id))
    pair = merge_roles.pair(db, script, slot_id, body.into_slot_id)
    out = merge_roles.merge(db, script, *pair)
    db.commit()
    return {**out, "cast": slots(db, script)}


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
    values = {**body.model_dump(), "kind": body.kind or "Main"}
    db.add(ScriptCastSlot(script_id=script.id, position=(last or 0) + 1, **values))
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
    if "description" in values:
        slot.guessed = []  # a person wrote it: nothing in it is a guess any more
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
    item = pick_item(db, user, Kind.character, body.library_item_id, script_id=script.id)
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
