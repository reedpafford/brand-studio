"""Spend you can forecast: the owner's "By format and style" table, and a finished video's
scorecard (forecast against actual, the auto checks, Reed's 1-5 score). Credits only."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import scorecard
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.routes.projects import get_project
from app.routes.usage import owner_or_404

router = APIRouter(tags=["usage"])


class PairRow(BaseModel):
    format: str
    look: str
    videos: int
    seconds: int
    credits: float
    director_credits: float  # part of credits: the director's own turns
    credits_per_second: float
    redo_rate: float | None  # takes made per clip (1 is no redo)
    scored: int
    average_score: float | None


class CardOut(BaseModel):
    forecast_credits: float | None
    forecast_basis: str | None  # "estimate" or "N finished videos"
    actual_credits: float
    director_credits: float
    within_forecast: bool | None
    words_exact: bool | None  # null: no words check ran
    must_show_ok: bool | None
    score: int | None  # the owner's: an editor gets null
    note: str | None


class ScoreIn(BaseModel):
    score: Annotated[int, Field(ge=1, le=5)] | None  # null clears it
    note: str | None = Field(default=None, max_length=1000)


@router.get("/usage/by-format-and-style", response_model=list[PairRow])
def by_format_and_style(owner: User = Depends(owner_or_404), db: Session = Depends(get_db)):
    return scorecard.table(db, owner.workspace_id)


@router.get("/projects/{project_id}/scorecard", response_model=CardOut)
def get_card(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = get_project(db, user, project_id)
    out = scorecard.card(db, project)
    if not user.is_owner:
        out["score"] = out["note"] = None
    return out


@router.put("/projects/{project_id}/score", response_model=CardOut)
def set_score(project_id: int, body: ScoreIn, owner: User = Depends(owner_or_404),
              db: Session = Depends(get_db)):  # fmt: skip
    project = get_project(db, owner, project_id)
    if not project.finished_at:
        raise HTTPException(409, "Score a video once it is finished.")
    project.score, project.score_note = body.score, (body.note or "").strip() or None
    db.commit()
    return scorecard.card(db, project)
