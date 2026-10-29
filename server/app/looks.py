"""Looks (flows ST1–ST3, Reed 2026-10-29): how a video's pictures are drawn, a setting apart
from its format. Each look is a file in app/prompts/styles/ with `kind: look` (the
Director's paragraphs); the formats there are not looks. A look is On for editors only once
the owner switches it on, and that needs its sample first (ST3); with no switch, the file's
own `on:` applies (House alone). The owner may try an Off look on their own drafts."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts
from app.models.accounts import User
from app.models.looks import LookSwitch

DEFAULT = "house"
UNKNOWN = "There's no such look."
OFF = "{} is off for editors. Pick a look that's on."
OTHER = "{} made in another look. Redo them in this video's look, then make the video."
NO_SAMPLE = "Make a sample first: a look is switched on only once its sample is approved."


def looks() -> list[dict]:
    """Every look, House first, then Reed's order."""
    return [s for s in prompts.styles() if s["kind"] == "look"]


def get(look_id: str) -> dict:
    found = next((x for x in looks() if x["id"] == look_id), None)
    if found is None:
        raise HTTPException(422, UNKNOWN)
    return found


def switch(db: Session, workspace_id: int, look_id: str) -> LookSwitch | None:
    return db.scalar(select(LookSwitch).where(LookSwitch.workspace_id == workspace_id,
                                              LookSwitch.look_id == look_id))  # fmt: skip


def is_on(db: Session, workspace_id: int, look_id: str) -> bool:
    row = switch(db, workspace_id, look_id)
    return row.on if row else get(look_id)["on"]


def frame_other(project, frame) -> bool:
    """A still drawn in another look than the video's now (VS1): "Out of date"; changing the
    look back (Undo) makes it current again."""
    return bool(frame.file_id) and frame.look != project.look


def take_other(db: Session, project, clip) -> bool:
    """A clip whose picked take was made in another look than the video's now (VS1)."""
    from app.models.clips import ClipTake

    take = db.get(ClipTake, clip.picked_take_id) if clip.picked_take_id else None
    return bool(take) and take.look != project.look


def redo_credits(db: Session, project) -> float:
    """What redrawing the stills and remaking the clips made in another look costs (VS1)."""
    from app import clip_takes, storyboard
    from app.models.clips import ProjectClip
    from app.models.storyboards import StoryboardFrame

    frames = db.scalars(select(StoryboardFrame).where(StoryboardFrame.project_id == project.id))
    clips = db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id))
    stills = sum(frame_other(project, f) for f in frames) * storyboard.still_price(db, project)
    takes = sum(clip_takes.take_credits(db, project, c) for c in clips
                if take_other(db, project, c))  # fmt: skip
    return float(stills + takes)


def pick(db: Session, user: User, look_id: str) -> str:
    """A look this person may pick: an editor only one that's on; the owner any (to try)."""
    look = get(look_id)
    if not user.is_owner and not is_on(db, user.workspace_id, look_id):
        raise HTTPException(409, OFF.format(look["name"]))
    return look_id
