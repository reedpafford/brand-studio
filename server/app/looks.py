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
OFF = "{} is off for editors. Pick a look that's on, or ask the owner to switch it on."
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


def pick(db: Session, user: User, look_id: str) -> str:
    """A look this person may pick: an editor only one that's on; the owner any (to try)."""
    look = get(look_id)
    if not user.is_owner and not is_on(db, user.workspace_id, look_id):
        raise HTTPException(409, OFF.format(look["name"]))
    return look_id
