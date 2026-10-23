"""Make a character's turnaround sheet or a place's establishing still with Nano Banana, in the
house style (the Director's `prompts.sheet_prompt`). The result becomes the item's first
picture, as a new version, so editors can make a video without uploading drawings."""

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
from app.routes.library import _save_version, get_item

router = APIRouter(prefix="/library/{kind}/{item_id}/sheet", tags=["library"])
ASPECT, RESOLUTION = "16:9", "2K"  # a wide turnaround / establishing still


class SheetIn(BaseModel):
    model_id: Literal["nano-banana-pro", "nano-banana-2.1"] = "nano-banana-pro"
    from_photo: bool = False  # character: draw it from the item's first picture (a photo)
    change: str = Field("", max_length=500)  # Redo: what should change from the last sheet


@router.post("", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)])
def make_sheet(
    kind: Kind,
    item_id: int,
    body: SheetIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Queue the picture (a paid image job). Only the editor's own pictures of this item are
    attached: the photo to draw from, and the last sheet when redoing."""
    if kind == Kind.prop:
        raise HTTPException(422, "Sheets are for characters and places.")
    item = get_item(db, user, kind, item_id)
    if not item.notes.strip() and not body.from_photo:
        raise HTTPException(422, "Describe it first (the notes), or draw it from a photo.")
    if (body.from_photo or body.change) and not item.image_file_ids:
        raise HTTPException(422, "Add a picture first.")
    from_photo = body.from_photo and kind == Kind.character
    refs = [item.image_file_ids[0]] if from_photo or body.change else []
    prompt = prompts.sheet_prompt(str(kind), item.notes, from_photo=from_photo, change=body.change)
    job = image_job_input(
        get_model(body.model_id), prompt, ASPECT, objects=refs, resolution=RESOLUTION
    )
    job_input = {**job, "step": "sheet", "item_id": item.id}
    return enqueue(db, user, "image", job_input, provider="replicate")


def save_sheet(db: Session, job: Job) -> None:
    """The new picture goes first (it's what every step uses); the old ones stay after it."""
    item = db.get(LibraryItem, job.input["item_id"])
    file_ids = (job.output or {}).get("file_ids") or []
    if not item or not file_ids:
        return
    _save_version(db, db.get(User, job.created_by_id), item)
    item.image_file_ids = [file_ids[0], *[f for f in item.image_file_ids if f != file_ids[0]]]
