"""Write a script's words with Claude, one script or many at once ("Write all" after bulk
create). One paid call per script at one price; an editor's run on their own allowance is
declined past it, all or none, before anything is queued."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import reel_read, script_write
from app import script_library as lib
from app.auth import current_user
from app.credits import credits_left, estimate
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
    reading: int = 0  # scripts whose imported reel is read first (watch, write, cast read)
    writing: int = 0  # scripts that are simply written
    waiting: list[int] = []  # reels still being prepared: Write all waits for them
    failed: list[int] = []  # reels that couldn't be fetched: upload the video or untick them


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


def _plan(db: Session, script: Script) -> str:
    """write | read | waiting | failed: what Write all does with this script. A script with
    an unread imported reel reads it first (its own write is part of the read)."""
    if script.reel is None:
        return "write"
    status, failed = reel_read.state(db, script)
    if status == "preparing":
        return "waiting"
    if failed == "prepare" or reel_read.needs_upload(script):
        return "failed"  # Write all says to upload the video (or untick it)
    if status == "reading":
        raise HTTPException(409, f"{script.title}: its reel is being read.")
    return "write" if status == "done" else "read"


def _cost(db: Session, user: User, script: Script, plan: str) -> Decimal:
    if plan == "write":
        return _price(db, user)
    if plan == "failed":  # can't run until the video is uploaded: not in the total
        return Decimal(0)
    return reel_read.price(db, user, reel_read.remaining(script))


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
    scripts = [lib.get_script(db, user, script_id) for script_id in ids]
    plans = [_plan(db, s) for s in scripts]
    left = credits_left(db, user)
    return WriteManyEstimate(
        count=len(ids),
        credits=sum((_cost(db, user, s, p) for s, p in zip(scripts, plans, strict=True)), 0),
        credits_left=None if left is None else max(left, Decimal(0)),
        reading=plans.count("read"),
        writing=plans.count("write"),
        waiting=[s.id for s, p in zip(scripts, plans, strict=True) if p == "waiting"],
        failed=[s.id for s, p in zip(scripts, plans, strict=True) if p == "failed"],
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
    """Write all: one call per script, or the reel read (watch, write, cast read) for a script
    with an unread imported reel. Every script is checked first, and an editor's allowance
    must cover them all; otherwise nothing is queued. Refused while a reel isn't ready."""
    ids = list(dict.fromkeys(body.script_ids))
    scripts = [_writable(db, user, s, f"Row {n}: ") for n, s in enumerate(ids, 1)]
    plans = [_plan(db, s) for s in scripts]
    if waiting := plans.count("waiting"):
        are = "reel is" if waiting == 1 else "reels are"
        raise HTTPException(409, f"{waiting} {are} still being prepared. Try again shortly.")
    if failed := plans.count("failed"):
        it = "reel" if failed == 1 else "reels"
        raise HTTPException(
            409, f"{failed} {it} couldn't be fetched. Upload the video or untick it."
        )
    costs = [_cost(db, user, s, p) for s, p in zip(scripts, plans, strict=True)]
    total, left = sum(costs, Decimal(0)), credits_left(db, user)
    if left is not None and total > left:
        raise HTTPException(
            409,
            f"Writing these takes {total:.0f} credits and you have {max(left, 0):.0f} left "
            "this week. It resets Monday.",
        )
    return [
        reel_read.queue(db, user, s, reel_read.remaining(s)[0])
        if p == "read"
        else _queue(db, user, request, s)
        for s, p in zip(scripts, plans, strict=True)
    ]
