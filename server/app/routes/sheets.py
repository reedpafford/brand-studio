"""House-style sheets for characters and places (Reed, 2026-10-23). Nano Banana draws one from
the item's notes, or from its source photo, with the Director's `prompts.sheet_prompt`. An
editor approves it; only an approved sheet is ever used in a video (`app/sheets.py`), and the
source photo never is."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import prompts
from app.auth import current_user
from app.catalogue import get_model
from app.db import get_db
from app.images import image_job_input
from app.models.accounts import User
from app.models.jobs import Job
from app.models.library import Kind, LibraryItem
from app.routes.clips import generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.library import ItemOut, _out, _save_version, get_item, sheet_status

router = APIRouter(prefix="/library/{kind}/{item_id}/sheet", tags=["library"])
ASPECT = {Kind.character: "9:16", Kind.place: "16:9"}  # a tall turnaround / a wide view
RESOLUTION = "2K"


class SheetIn(BaseModel):
    model_id: Literal["nano-banana-pro", "nano-banana-2.1"] = "nano-banana-pro"
    change: str = Field("", max_length=500)  # Redo: "What should change?" (optional)


def _item(db: Session, user: User, kind: Kind, item_id: int) -> LibraryItem:
    if kind == Kind.prop:
        raise HTTPException(422, "Sheets are for characters and places.")
    return get_item(db, user, kind, item_id)


@router.post("", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)])
def make_sheet(
    kind: Kind,
    item_id: int,
    body: SheetIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Queue a sheet (a paid image job). It is drawn from the source photo when there is one
    (attached as image 1), else from the notes; a redo also attaches the last sheet."""
    item = _item(db, user, kind, item_id)
    if not item.notes.strip() and not item.source_photo_file_id:
        raise HTTPException(422, "Describe it first (the notes), or add a photo.")
    if sheet_status(item) == "drawing":
        raise HTTPException(409, "A sheet is being made.")
    from_photo = bool(item.source_photo_file_id)
    redo = bool(body.change.strip()) and item.sheet_file_id is not None
    refs = [item.source_photo_file_id] if from_photo else []
    refs += [item.sheet_file_id] if redo else []
    prompt = prompts.sheet_prompt(
        str(kind), item.notes, from_photo=from_photo, change=body.change if redo else ""
    )
    job = image_job_input(
        get_model(body.model_id), prompt, ASPECT[kind], objects=refs, resolution=RESOLUTION
    )
    return enqueue(
        db,
        user,
        "image",
        {**job, "step": "sheet", "library_item_id": item.id},
        provider="replicate",
    )


def save_sheet(db: Session, job: Job) -> None:
    """A new sheet waits for an editor's approval (a new version of the item)."""
    item = db.get(LibraryItem, job.input["library_item_id"])
    file_ids = (job.output or {}).get("file_ids") or []
    if not item or not file_ids:
        return
    _save_version(db, db.get(User, job.created_by_id), item)
    item.sheet_file_id, item.sheet_approved = file_ids[0], False


@router.post("/approve", response_model=ItemOut)
def approve(
    kind: Kind, item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """✓ Approve the sheet: from now on it is what storyboards and clips use."""
    item = _item(db, user, kind, item_id)
    if sheet_status(item) != "needs_approval":
        raise HTTPException(409, "There's no new sheet to approve.")
    _save_version(db, user, item)
    item.sheet_approved = True
    db.commit()
    return _out(item)


@router.delete("/approve", response_model=ItemOut)
def unapprove(
    kind: Kind, item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    item = _item(db, user, kind, item_id)
    _save_version(db, user, item)
    item.sheet_approved = False
    db.commit()
    return _out(item)
