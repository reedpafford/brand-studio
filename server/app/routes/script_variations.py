"""Write variations of a script's approved original (Reed: one price per run; every
regenerate is paid). Runs on the editor's weekly allowance, as other script steps do."""

from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import script_library as lib
from app import script_variations
from app.auth import current_user
from app.credits import afford, estimate
from app.db import get_db
from app.models.accounts import User
from app.routes.clips import generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.references import for_script as script_reference
from app.routes.script_preview import EstimateOut
from app.schemas import LongText

router = APIRouter(prefix="/scripts/{script_id}/variations", tags=["script library"])


class VariationsIn(BaseModel):
    slots: Annotated[list[Literal[1, 2]], Field(min_length=1, max_length=2)] = [1, 2]
    note: LongText = ""  # what to change, e.g. "make the second one about a car"


@router.get("/estimate", response_model=EstimateOut)
def variations_estimate(
    script_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """What one run costs: one Claude call (one variation or two), then the cast read."""
    lib.get_script(db, user, script_id)
    return EstimateOut(credits=_price(db, user))


def _price(db: Session, user: User) -> Decimal:
    return estimate(db, user.workspace_id, "write-claude", Decimal(2), {})


@router.post("", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)])
def write_variations(
    script_id: int,
    body: VariationsIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Write variations into the given slots (both by default). Pass one slot to regenerate
    it; the other variation is kept apart from the new one."""
    script = lib.editable(user, lib.get_script(db, user, script_id))
    slots = sorted(set(body.slots))
    drafts = {d.slot: d for d in lib.drafts(db, script)}
    original = drafts.get(0)
    if not original or original.status != "approved":
        raise HTTPException(409, "Approve the original first.")
    if any(drafts.get(s) and drafts[s].status == "approved" for s in slots):
        raise HTTPException(409, "That variation is approved and can't change.")
    if lib.writing(db, script.id, "variations"):
        raise HTTPException(409, "Variations are already being written for this script.")
    keep_apart = [d.text for s, d in drafts.items() if s and s not in slots and d.text.strip()]
    reference = script_reference(request, script)
    data = script_variations.job_input(
        db, script, original, slots, keep_apart, body.note, reference
    )
    data |= {"then_cast": True, "then_cast_reference": reference}  # cast read next, prepaid
    afford(db, user, _price(db, user), "Writing variations")
    return enqueue(db, user, "write-claude", data, provider="claude")
