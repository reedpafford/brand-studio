"""The site's director on a video (docs/next/director-chat.md, first slice): start a run from a
published script, read what it did (its log), stop it. Whoever may change the video may run
it; every action it takes is checked as that person's own press (app/director_tools)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints
from sqlalchemy.orm import Session

from app import director
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.routes.clips import generation_on
from app.routes.projects import _mine, get_project, video_writer
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


class ThreadItem(BaseModel):
    id: str  # stable: "m3" a message, "t41" a move
    kind: Literal["message", "move"]  # what a person said, or one of the director's moves
    at: UtcTime
    who: str  # the person's name, or "Director"
    text: str  # plain words; the deliver move's is the delivery note
    status: Literal["queued", "running", "held", "done", "refused"] | None  # moves only
    why: str = ""  # a move's reason, as the director gave it; "" for messages and deliveries


class MessageIn(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class DirectorOut(BaseModel):
    status: str  # none, running, delivered or ended
    ended: str  # why it ended, in plain words ("" while running)
    turns: list[TurnOut]  # the deliver turn's why is the delivery note
    credits: float  # the run's cost "up to": its turns and every press its tools made
    spent_usd: float | None  # the owner only: its own Claude time this run (to measure)
    start_blocked: str  # "" when this person can press Make it now; else why (the 409's words)
    thread: list[ThreadItem] = []  # the whole chat on the video, every run, oldest first
    unread: int = 0  # notes waiting for the next Make it ("Start again with this note")


def _out(db: Session, user: User, project) -> DirectorOut:
    rows = director.turns(db, project)
    last = rows[-1] if rows else None
    ended = director.ended(db, project)
    delivered = bool(last) and last.input.get("result") == "Delivered."
    status = ("none" if not last else "running" if director.active(db, project)
              else "delivered" if delivered else "ended")  # fmt: skip
    turns = [TurnOut(turn=j.input[director.RUN]["turn"], tool=(j.output or {}).get("tool"),
                     why=director.named((j.output or {}).get("why") or ""),
                     result=director.named(j.input.get("result", "")),
                     status=j.status, created_at=j.created_at) for j in rows]  # fmt: skip
    spent = director.spent(db, last.input[director.RUN]["id"]) if last else 0
    try:
        _mine(db, user, project.id)  # as the start's own check: the maker or the owner
        blocked = director.blocked(db, project)
    except HTTPException as no:
        blocked = no.detail
    return DirectorOut(status=status, ended=ended, turns=turns,
                       credits=float(director.credits(db, project)),
                       spent_usd=float(spent) if user.is_owner else None,
                       start_blocked=blocked, thread=director.thread(db, project),
                       unread=len(director.leftover(db, project)))  # fmt: skip


@router.get("", response_model=DirectorOut)
def read(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The newest run: going or not, and each turn (the log on the video)."""
    return _out(db, user, get_project(db, user, project_id))


@router.post("", response_model=DirectorOut, status_code=201, dependencies=[Depends(generation_on)])
def start(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Build the video from its published script (409 if it isn't, or a run is going). Its
    first turn is paid from the video's budget, held for the owner past it."""
    project = get_project(db, user, project_id)
    director.start(db, user, project)
    return _out(db, user, project)


@router.post("/messages", response_model=DirectorOut, status_code=201,
             dependencies=[Depends(generation_on)])  # fmt: skip
def message(
    project_id: int,
    body: MessageIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Tell the director what to change. While a run goes on, its next turn reads it. It never
    starts a run: after Stop or a delivery it waits (`unread`) for the next Make it, which
    reads every unread note and spends as Make it does. Who may: as Make it. At most one
    note a person every 3 s and 30 a run (429). Nothing is charged for a note."""
    project = get_project(db, user, project_id)
    _mine(db, user, project.id)  # as Make it: the video's maker or the owner
    director.say(db, user, project, body.text)
    return _out(db, user, project)


@router.post("/stop", response_model=DirectorOut)
def stop(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Stop the run: no more turns. What it already started goes on; nothing is undone."""
    project = get_project(db, user, project_id)
    director.stop(db, project)
    return _out(db, user, project)
