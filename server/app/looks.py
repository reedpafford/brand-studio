"""Looks (flows ST1–ST3, Reed 2026-10-29): how a video's pictures are drawn, a setting apart
from its format. Each look is a file in app/prompts/styles/ with `kind: look` (the
Director's paragraphs); the formats there are not looks. A look is On for editors only once
the owner switches it on, and that needs its sample first (ST3); with no switch, the file's
own `on:` applies (House alone). The owner may try an Off look on their own drafts."""

import re

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
    """Every look, House first, then Reed's order: one card per style (its lanes aren't)."""
    return [s for s in prompts.styles() if s["kind"] == "look"]


def get(look_id: str) -> dict:
    """A look, or one of a style's lanes (Reed: one look per style; the plan picks the lane):
    a lane is named "Paper · Flat Paper" and carries its look as `parent`."""
    every = {s["id"]: s for s in prompts.styles() if s["kind"] in ("look", "lane")}
    found = every.get(look_id)
    if found is None:
        raise HTTPException(422, UNKNOWN)
    parent = every.get(found.get("parent") or "")
    if found["kind"] == "lane" and parent:
        own = re.sub(rf"\s*\b{re.escape(parent['name'])}\b\s*", " ", found["name"], flags=re.I)
        name = f"{parent['name']} · {own.strip() or found['name']}"  # not "Paper · Flat Paper"
        return {**found, "name": name, "on": parent["on"]}
    return found


def lanes(look_id: str) -> list[dict]:
    """A style's lanes, each as get() gives it ("Paper · Flat Paper")."""
    return [get(s["id"]) for s in prompts.styles()
            if s["kind"] == "lane" and s.get("parent") == look_id]  # fmt: skip


def base(look_id: str) -> str:
    """The look a lane belongs to (its switch and sample are the look's); a look is its own."""
    return get(look_id).get("parent") or look_id


def switch(db: Session, workspace_id: int, look_id: str) -> LookSwitch | None:
    return db.scalar(select(LookSwitch).where(LookSwitch.workspace_id == workspace_id,
                                              LookSwitch.look_id == look_id))  # fmt: skip


def is_on(db: Session, workspace_id: int, look_id: str) -> bool:
    look_id = base(look_id)
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


PICKED = "look_picked"  # in Project.locks: a person chose this video's look themselves


def picked_by_person(project) -> None:
    """A person set the look (the video's settings): a plan's lane never changes it now."""
    project.locks = {**(project.locks or {}), PICKED: True}


def follow_lane(db: Session, project) -> str | None:
    """A saved plan's lane (`structure.lane`, the Director's) becomes the video's look when it
    belongs to it: never once a still, sheet or take is in the look, nor when a person picked
    the look themselves (or locked it), nor while a role's look is being drawn. The look it
    set, or None."""
    from app.models.clips import ClipTake, ProjectClip
    from app.models.storyboards import StoryboardFrame
    from app.sheets import sheet_for
    from app.storyboard import cast_looks

    lane = (((project.plan or {}).get("structure") or {}).get("lane") or "").strip()
    if not lane or project.id is None or lane == project.look:
        return None
    try:
        if get(lane).get("parent") != base(project.look or DEFAULT):
            return None
    except HTTPException:
        return None
    locks = project.locks or {}
    if locks.get(PICKED) or locks.get("look"):
        return None
    look = project.look or DEFAULT
    stills = db.scalar(select(StoryboardFrame.id).where(
        StoryboardFrame.project_id == project.id, StoryboardFrame.file_id.is_not(None),
        StoryboardFrame.look == look).limit(1))  # fmt: skip
    takes = db.scalar(select(ClipTake.id).join(ProjectClip, ClipTake.clip_id == ProjectClip.id)
                      .where(ProjectClip.project_id == project.id, ClipTake.look == look)
                      .limit(1))  # fmt: skip
    sheets = look != DEFAULT and any(sheet_for(db, project, c) for c in cast_looks(db, project))
    from app.models.jobs import Job, JobStatus

    making = db.scalar(select(Job.id).where(  # a role's look still being drawn in this look
        Job.project_id == project.id, Job.input["step"].as_string() == "sheet",
        Job.status.in_((JobStatus.queued, JobStatus.running))).limit(1))  # fmt: skip
    if stills or takes or sheets or making:
        return None
    project.look = lane
    return lane
