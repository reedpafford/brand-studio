"""The Assets step (workflow v2): every character and place the breakdown uses, with its look.
Locked cast slots come preloaded with their look; an unlocked slot gets a character from the
editor (picked or new), whose sheet is made and approved with the library's sheet routes.
Storyboard and takes already refuse until every sheet they need is approved."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import breakdown
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.library import Kind, LibraryItem
from app.models.projects import Project
from app.models.script_library import ScriptCastSlot, ScriptDraft
from app.prompts.schemas import Breakdown
from app.routes.library import get_item, sheet_status
from app.routes.projects import get_project
from app.routes.scripts import latest

router = APIRouter(prefix="/projects/{project_id}/assets", tags=["assets"])


class AssetOut(BaseModel):
    kind: str  # character | place
    ref: str  # as the breakdown names it: char:5, place:2, or slot:3 until it has a character
    role: str  # the cast slot's role, else the item's name
    library_item_id: int | None
    name: str
    locked: bool  # a locked slot: its look is fixed for every version
    sheet_status: str  # none | drawing | waiting_for_owner | needs_approval | approved | missing
    ready: bool  # nothing left to do for it


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


def _row(kind: str, ref: str, role: str, item: LibraryItem | None, locked: bool) -> AssetOut:
    status = "missing" if item is None else ("approved" if locked else sheet_status(item))
    return AssetOut(
        kind=kind,
        ref=ref,
        role=role or (item.name if item else ""),
        library_item_id=item.id if item else None,
        name=item.name if item else "",
        locked=locked,
        sheet_status=status,
        ready=status == "approved",
    )


@router.get("", response_model=list[AssetOut])
def list_assets(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Cast slots first (locked, then unlocked), then the breakdown's other characters and
    its places, each once."""
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
                        slot.role, item, slot.library_item_id is not None))  # fmt: skip
        seen.add(f"char:{item_id}")
    for ref in used:
        if ref in seen or not ref.startswith("char:"):
            continue
        out.append(_row("character", ref, "", db.get(LibraryItem, int(ref[5:])), False))
    for ref in places:
        out.append(_row("place", ref, "", db.get(LibraryItem, int(ref.split(":")[1])), False))
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
    slot = next((s for s in _slots(db, project) if s.id == slot_id), None)
    if not slot:
        raise HTTPException(404, "No such cast slot in this video.")
    if slot.library_item_id:
        raise HTTPException(409, f"{slot.role} is locked to one look for every version.")
    item = get_item(db, user, Kind.character, body.library_item_id)
    old = project.slot_cast.get(str(slot.id))
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
        db.add(
            BreakdownVersion(
                project_id=project.id,
                script_version=bd.script_version,
                source="edit",
                data=new.model_dump(),
                problems=breakdown.problems(db, project, script.text if script else "", new),
                created_by_id=user.id,
            )
        )
    db.commit()
    return list_assets(project_id, user, db)
