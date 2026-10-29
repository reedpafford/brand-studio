"""Update everything after this (audit M14 part 2): what it would run and its price, and the
press itself (app/update_after.py)."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import credits, update_after
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.routes.clips import generation_on
from app.routes.projects import get_project

router = APIRouter(prefix="/projects/{project_id}", tags=["update after"])
From = Literal["plan", "storyboard", "clips"]


class UpdateStep(BaseModel):
    step: Literal["storyboard", "stills", "clip_prompts"]
    what: str  # "Make the storyboard again (6 frames, 6 stills)"
    credits: int  # rounded up
    status: Literal["started", "waiting"] | None = None  # after the press


class UpdateOut(BaseModel):
    credits: int  # "Update everything after this · N credits" (0: nothing to update)
    steps: list[UpdateStep]
    running: bool  # the newest run still has work on its way
    stopped_at: Literal["storyboard", "stills", "clip_prompts"] | None  # where it stopped
    reason: str | None  # why, in plain words; that step's own press is the way on


def _out(db: Session, project, steps: list[dict]) -> UpdateOut:
    total = sum(s["credits"] for s in steps)
    shown = [UpdateStep(**{**s, "credits": credits.price(s["credits"])}) for s in steps]
    return UpdateOut(credits=credits.price(total) if steps else 0, steps=shown,
                     **update_after.last_run(db, project))  # fmt: skip


@router.get("/update-after", response_model=UpdateOut)
def update_price(
    project_id: int,
    start: From = Query("plan", alias="from"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    project = get_project(db, user, project_id)
    return _out(db, project, update_after.plan(db, project, start))


@router.post("/update-after", response_model=UpdateOut, status_code=202,
             dependencies=[Depends(generation_on)])  # fmt: skip
def update_now(
    project_id: int,
    start: From = Query("plan", alias="from"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Paid: the whole price is checked first (409 with why, and nothing starts)."""
    project = get_project(db, user, project_id)
    steps = update_after.start(db, user, project, start)
    return _out(db, project, steps)
