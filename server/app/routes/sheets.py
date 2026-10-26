"""House-style sheets for characters and places (Reed, 2026-10-23). Nano Banana draws one from
the item's notes, or from its source photo, with the Director's `prompts.sheet_prompt`. An
editor approves it; only an approved sheet is ever used in a video (`app/sheets.py`), and the
source photo never is."""

import logging
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
from app.models.projects import Project
from app.prompts.schemas import LookFit
from app.routes.clips import generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.library import ItemOut, _out, _save_version, get_item, sheet_status

log = logging.getLogger(__name__)
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
    status = sheet_status(item)
    if status == "drawing":
        raise HTTPException(409, "A sheet is being made.")
    if status == "waiting_for_owner":
        raise HTTPException(409, "A sheet is waiting for the owner's OK.")
    return queue_sheet(db, user, item, body)


def queue_sheet(db: Session, user: User, item: LibraryItem, body: SheetIn, fit_redo=False) -> Job:
    """The sheet's paid image job. A redo with a note (a person's "Change this…", or the
    one automatic fit redo) is checked after it lands but never redone by itself again."""
    kind = item.kind
    from_photo = bool(item.source_photo_file_id)
    redo = bool(body.change.strip()) and item.sheet_file_id is not None
    refs = [item.source_photo_file_id] if from_photo else []
    refs += [item.sheet_file_id] if redo else []
    prompt = prompts.sheet_prompt(
        str(kind), item.notes, from_photo=from_photo, change=body.change if redo else "",
        role=role_for(db, item),
    )  # fmt: skip
    job = image_job_input(
        get_model(body.model_id), prompt, ASPECT[kind], objects=refs, resolution=RESOLUTION
    )
    project = db.get(Project, item.owner_project_id) if item.owner_project_id else None
    return enqueue(  # a video's own look is paid from that video's budget (gaps #19)
        db,
        user,
        "image",
        {**job, "step": "sheet", "library_item_id": item.id, "changed": redo or fit_redo},
        project=project,
        provider="replicate",
    )


def role_for(db: Session, item: LibraryItem) -> str:
    """The script's role a look was made for ("Omar, the boyfriend"), so every sheet of it,
    a redo too, knows the part; "" for a Cast & places look."""
    from sqlalchemy import select

    from app.models.script_library import ScriptCastSlot

    slot_id = None
    if item.owner_project_id:
        project = db.get(Project, item.owner_project_id)
        mine = [k for k, v in (project.slot_looks if project else {}).items() if v == item.id]
        slot_id = int(mine[0]) if mine else None
    elif item.owner_script_id:
        slot_id = db.scalar(
            select(ScriptCastSlot.id).where(
                ScriptCastSlot.script_id == item.owner_script_id,
                ScriptCastSlot.library_item_id == item.id,
            )
        )
    slot = db.get(ScriptCastSlot, slot_id) if slot_id else None
    return slot.role if slot else ""


def save_sheet(db: Session, job: Job) -> None:
    """A new sheet waits for an editor's approval (a new version of the item)."""
    item = db.get(LibraryItem, job.input["library_item_id"])
    file_ids = (job.output or {}).get("file_ids") or []
    if not item or not file_ids:
        return
    user = db.get(User, job.created_by_id)
    _save_version(db, user, item)
    item.sheet_file_id, item.sheet_approved, item.look_fit = file_ids[0], False, None
    if item.kind == Kind.character and not item.source_photo_file_id:
        check_fit(db, user, item, redo=not job.input.get("changed"))


def check_fit(db: Session, user: User, item: LibraryItem, redo: bool) -> None:
    """Does the new sheet read as its description (age, gender, job)? One cheap Claude look
    (prompts/look_fit.md, effort low), paid like the sheet; the sheet shows as still being
    drawn until it answers. A sheet from an uploaded photo is never checked: the photo is the
    truth. Past the budget or the week the check is skipped, never held."""
    data = {
        "step": "look_fit",
        "library_item_id": item.id,
        "redo": redo,  # one automatic redo; never after a person's own change
        "system": [prompts.system("look_fit")],
        "prompt": prompts.look_fit_input(item.notes, role_for(db, item)),
        "effort": "low",
        "max_tokens": 2000,
        "files": {"reference_images": [item.sheet_file_id]},
        "fit_images_to": 1024,
    }
    project = db.get(Project, item.owner_project_id) if item.owner_project_id else None
    db.commit()  # a refusal rolls back: never take the landed sheet with it
    try:
        enqueue(db, user, "write-claude", data, project=project, provider="claude")
    except HTTPException:
        log.info("look %s: the fit check doesn't fit the budget; shown unchecked", item.id)


def save_fit(db: Session, job: Job) -> None:
    """It fits: nothing to say. It doesn't: redo the sheet once with the check's note, within
    the budget; after that (or past the budget, or after a person's change), the look shows
    advice: who it reads as, with Redo it and the note prefilled."""
    item = db.get(LibraryItem, job.input["library_item_id"])
    if not item or item.archived:
        return
    fit = LookFit.model_validate(job.output)
    if fit.fits:
        item.look_fit = None
        return
    advice = {"seen": fit.seen, "problem": fit.problem}
    if job.input.get("redo") and item.sheet_file_id:
        note = prompts.look_fit_redo(item.notes, fit)[:500]
        db.commit()  # the check's answer stays even if the redo is refused (that rolls back)
        try:
            queue_sheet(db, db.get(User, job.created_by_id), item, SheetIn(change=note), True)
            return
        except HTTPException:
            pass  # past the budget: the look shows as it is, with the advice
    item.look_fit = advice


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
