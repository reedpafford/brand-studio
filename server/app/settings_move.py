"""The director changes a video's settings from the chat (S-gaps-05 V1: "the director also
changes them when asked in the chat"): style, video model, picture model or shape, through the
Plan tab's own switch (app/video_settings.py), so every check and price is the same. It says
the new "up to" first, and its switch can be undone as a person's can. Every switch is logged
on the video (`settings_log`); a setting a person chose themselves is theirs: the director
changes it only when a person asks for it in the chat (its why names their note; Lead, 4 Nov:
"A person's own setting wins over the director's choice")."""

import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import host, looks, plans
from app import video_settings as vs
from app.catalogue import get_model
from app.db import utcnow
from app.models.accounts import User
from app.models.projects import Project

FIELDS = {"look": "style", "video_model": "video model", "image_model": "picture model",
          "aspect_ratio": "shape", "presenter": "way the presenter appears"}  # fmt: skip
HOW = {"talks": "talking to camera", "corner": "in a corner over the B-roll",
       "acts": "acting in the story"}  # fmt: skip
KEPT = 20  # the log keeps this many switches
ONE_OF = ("Refused: the director changes the style, video model, picture model, shape or how "
          "the presenter appears.")  # fmt: skip
THEIRS = ("Refused: {who} chose the {what} themselves; their choice stays unless they ask for "
          "the change in the chat (name their note).")  # fmt: skip
LANGUAGE = ("Refused: a video's language is its script's; it changes on the script, before "
            "it's published.")  # fmt: skip
NOT_YET = ("Refused: a setting changes only for a person's request (name their note) or as the "
           "approved plan has it; this plan isn't approved yet.")  # fmt: skip
ASKED = re.compile(r"\bnote \d+\b", re.I)  # the director's why names the note it answers


def named(field: str, value) -> str:
    """A setting's value as people read it ("Seedance 1 Lite", "UGC", "Auto")."""
    if value is None:
        return "Auto"
    if field in ("video_model", "image_model"):
        return m.name if (m := get_model(value)) else value
    return looks.get(value)["name"] if field == "look" else str(value)


def back(field: str, was) -> str:
    """What Undo puts back, in words."""
    if field == "presenter":
        return f"the presenter {HOW.get(was, 'as the style starts')}"
    return named(field, was)


def said(field: str, value) -> str:
    """The switch in words: "The presenter now appears in a corner over the B-roll"."""
    if field == "presenter":
        return f"The presenter now appears {HOW.get(value, 'as the style starts')}"
    return f"Switched the {FIELDS[field]} to {named(field, value)}"


def log(project: Project, user: User, field: str, was, now, by: str, why: str = "") -> None:
    entry = {"field": field, "was": was, "now": now, "by": by, "by_id": user.id,
             "why": why[:300], "at": utcnow().isoformat()}  # fmt: skip
    project.settings_log = [*(project.settings_log or []), entry][-KEPT:]


def persons(project: Project, field: str) -> dict | None:
    """The person's choice that still stands for this setting, else None: their last switch,
    or with none logged a value set (when the video was made, or before the log: QA on #1327);
    an Auto model, the style's own way of appearing and narration off are the director's."""
    mine = [e for e in project.settings_log or [] if e["field"] == field]
    if mine:
        last = mine[-1]
        stands = last["by"] == "person" and getattr(project, field) == last["now"]
        return last if stands else None
    if getattr(project, field) in (None, False):
        return None
    return {"field": field, "by": "person", "by_id": project.created_by_id}


def switch(db: Session, user: User, project: Project, field: str | None, value: str | None,
           why: str) -> str:  # fmt: skip
    """The director's switch of one setting, its price said first; a refusal in plain words."""
    from app.auth import user_name

    if field == "language":
        return LANGUAGE
    if field not in FIELDS:
        return ONE_OF
    value = value or None  # "": Auto
    asked = bool(ASKED.search(why or ""))
    if not asked and plans.status(db, project) != "approved":  # Reed: never an unapproved plan
        return NOT_YET
    if (found := persons(project, field)) and not asked:
        return THEIRS.format(who=user_name(db, found["by_id"]) or "A person", what=FIELDS[field])
    try:
        price = vs.preview(db, user, project, {field: value})
        if price["reason"]:
            return f"Refused: {price['reason']}"
        was = vs.switch(db, user, project, {field: value})[field]
    except HTTPException as no:
        db.rollback()
        return f"Refused: {no.detail}"
    log(project, user, field, was, value, "director", why)
    db.commit()
    hosted = ""
    if field == "presenter" and host.on(db, project) and (cost := host.price(db, project)):
        hosted = f"the presenter's take is made again for it, up to {cost:.1f} credits; "
    left = f"{affected(price)}{hosted}"
    return (f"{said(field, value)}. The switch is free; {left}making what's left costs up to "
            f"{price['to_finish_credits']:.1f} credits (was {price['was_credits']:.1f}). Undo "
            f"puts back {back(field, was)}.")  # fmt: skip


def affected(price: dict) -> str:
    """The work a switch puts out of date, and the looks it sends back to Cast & places for
    approval (Reed: never past that checkpoint), in words; "" for none."""
    parts = [
        f"{n} {what}{'' if n == 1 else 's'}"
        for n, what in (
            (price["stills_out_of_date"], "still"),
            (price["clips_out_of_date"], "clip"),
        )
        if n
    ]
    told = f"{' and '.join(parts)} go out of date; " if parts else ""
    if roles := price.get("roles_needing_look"):
        told += (
            f"{', '.join(roles)} need{'s' if len(roles) == 1 else ''} a new look approved "
            "in Cast & places before anything is made; "
        )
    return told
