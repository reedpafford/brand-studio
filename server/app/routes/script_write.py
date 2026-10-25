"""Write a script's words with Claude, one script or many at once ("Write all" after bulk
create). One paid call per script at one price; an editor's run on their own allowance is
declined past it, all or none, before anything is queued."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import script_library as lib
from app import script_write
from app.auth import current_user
from app.credits import estimate, get_limits, quick_clip_used
from app.db import get_db
from app.models.accounts import User
from app.models.script_library import Script
from app.routes.clips import generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.references import for_script as script_reference
from app.routes.script_preview import EstimateOut

router = APIRouter(prefix="/scripts", tags=["script library"])


class WriteManyIn(BaseModel):
    script_ids: list[int] = Field(min_length=1, max_length=50)


class WriteManyEstimate(BaseModel):
    count: int
    credits: float  # all of them together
    credits_left: float | None  # an editor's weekly allowance left; null for the owner


def _price(db: Session, user: User) -> Decimal:
    return estimate(db, user.workspace_id, "write-claude", Decimal(1), {})


def _writable(db: Session, user: User, script_id: int, row: str = "") -> Script:
    script = lib.editable(user, lib.get_script(db, user, script_id))
    draft = script_write.original(db, script)
    if draft is not None and draft.status == "approved":
        raise HTTPException(409, f"{row}{script.title}: the words are approved.")
    if lib.writing(db, script.id):
        raise HTTPException(409, f"{row}{script.title}: Claude is already writing for it.")
    return script


def credits_left(db: Session, user: User) -> Decimal | None:
    if user.is_owner:
        return None
    return get_limits(db, user.workspace_id).weekly_quick_clip_credits - quick_clip_used(db, user)


def _queue(db: Session, user: User, request: Request, script: Script):
    reference = script_reference(request, script)
    data = script_write.job_input(db, script, reference)
    return enqueue(db, user, "write-claude", data, provider="claude")


@router.get("/{script_id}/write/estimate", response_model=EstimateOut)
def write_estimate(
    script_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    lib.get_script(db, user, script_id)
    return EstimateOut(credits=_price(db, user))


@router.post(
    "/{script_id}/write",
    response_model=JobOut,
    status_code=201,
    dependencies=[Depends(generation_on)],
)
def write_one(
    script_id: int,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Claude writes the original's words from the title, description, cast and reel."""
    return _queue(db, user, request, _writable(db, user, script_id))


@router.post("/write/estimate", response_model=WriteManyEstimate)
def write_many_estimate(
    body: WriteManyIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """What writing these scripts costs, and an editor's allowance left, before pressing."""
    ids = list(dict.fromkeys(body.script_ids))
    for script_id in ids:
        lib.get_script(db, user, script_id)
    left = credits_left(db, user)
    return WriteManyEstimate(
        count=len(ids),
        credits=_price(db, user) * len(ids),
        credits_left=None if left is None else max(left, Decimal(0)),
    )


@router.post(
    "/write", response_model=list[JobOut], status_code=201, dependencies=[Depends(generation_on)]
)
def write_many(
    body: WriteManyIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Write all: one call per script. Every script is checked first, and an editor's
    allowance must cover them all; otherwise nothing is queued."""
    ids = list(dict.fromkeys(body.script_ids))
    scripts = [_writable(db, user, s, f"Row {n}: ") for n, s in enumerate(ids, 1)]
    total, left = _price(db, user) * len(scripts), credits_left(db, user)
    if left is not None and total > left:
        raise HTTPException(
            409,
            f"Writing these takes {total:.0f} credits and you have {max(left, 0):.0f} left "
            "this week. It resets Monday.",
        )
    return [_queue(db, user, request, s) for s in scripts]
