"""The site's director on a video (docs/next/director-chat.md, first slice): start a run from a
published script, read what it did (its log), stop it. Whoever may change the video may run
it; every action it takes is checked as that person's own press (app/director_tools)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import director
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.routes.clips import generation_on
from app.routes.projects import get_project, video_writer
from app.schemas import UtcTime

router = APIRouter(
    prefix="/projects/{project_id}/director", tags=["director"],
    dependencies=[Depends(video_writer)],
)  # fmt: skip


class TurnOut(BaseModel):
    turn: int
    tool: str | None  # null while the turn is being decided (or waits for the owner)
    why: str  # its reason; the deliver turn's is the delivery note
    result: str  # what happened: "Making the shots.", "Refused: …" (plain words)
    status: str  # the turn's job: queued, needs_owner_approval, running, succeeded, …
    created_at: UtcTime


class DirectorOut(BaseModel):
    status: str  # none, running, delivered or ended
    ended: str  # why it ended ("" while running)
    turns: list[TurnOut]
    spent_usd: float  # its own Claude time this run (to measure; owner sees Usage too)


def _out(db: Session, project) -> DirectorOut:
    rows = director.turns(db, project)
    last = rows[-1] if rows else None
    ended = (last.input.get("ended") or "") if last else ""
    delivered = bool(last) and last.input.get("result") == "Delivered."
    status = ("none" if not last else "running" if director.active(db, project)
              else "delivered" if delivered else "ended")  # fmt: skip
    turns = [TurnOut(turn=j.input[director.RUN]["turn"], tool=(j.output or {}).get("tool"),
                     why=(j.output or {}).get("why", ""), result=j.input.get("result", ""),
                     status=j.status, created_at=j.created_at) for j in rows]  # fmt: skip
    spent = director.spent(db, last.input[director.RUN]["id"]) if last else 0
    return DirectorOut(status=status, ended=ended, turns=turns, spent_usd=float(spent))


@router.get("", response_model=DirectorOut)
def read(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The newest run: going or not, and each turn (the log on the video)."""
    return _out(db, get_project(db, user, project_id))


@router.post("", response_model=DirectorOut, status_code=201, dependencies=[Depends(generation_on)])
def start(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Build the video from its published script (409 if it isn't, or a run is going). Its
    first turn is paid from the video's budget, held for the owner past it."""
    project = get_project(db, user, project_id)
    director.start(db, user, project)
    return _out(db, project)


@router.post("/stop", response_model=DirectorOut)
def stop(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Stop the run: no more turns. What it already started goes on; nothing is undone."""
    project = get_project(db, user, project_id)
    director.stop(db, project)
    return _out(db, project)
