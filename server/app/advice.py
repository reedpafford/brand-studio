"""Advice is never a dead end (Reed, 2026-10-25): a check's problem that starts "Advice: " never
blocks a step; the editor can keep it ("Keep anyway") and it isn't shown as open again."""

import re
from typing import Annotated

from fastapi import HTTPException
from pydantic import AfterValidator, BaseModel

PREFIX = "Advice: "
# The cast in a shot looks wrong (cast_roles.mismatches): stills wait until it's fixed or kept.
CAST = "Check the cast: "


# Ids people never read (Reed's live test: "c3: char:3 in the shot without a sheet").
ID = re.compile(r"\b(char|slot|place|prop|screen|frame|voice):[\w.]+")
CLIP = re.compile(r"^c\d+: ")
KIND = {"char": "a character", "slot": "a character", "place": "a place", "prop": "a prop",
        "screen": "a screen", "frame": "a still", "voice": "a voice"}  # fmt: skip


def names(known: dict) -> dict[str, str]:
    """What people call each asset id, from its prompt line ("char:3 | character | Mia | …")."""
    out = {}
    for key, value in known.items():
        parts = value[0].split(" | ")
        name = parts[2].split(",")[0].strip() if len(parts) > 2 else ""
        if key.startswith("frame:"):
            name = f"clip {key.split(':')[1].lstrip('c')}'s still"
        elif key.startswith("voice:") and name:
            name = f"{name}'s voice"
        if name:
            out[key] = name
    return out


def plain(problems: list[str], called: dict[str, str]) -> list[str]:
    """Problems as people read them: no clip id in front (they're shown on their clip) and
    every id named ("Mia"), or said for what it is when it isn't in the video any more."""

    def what(m: re.Match) -> str:
        return called.get(m[0], KIND[m[1]])

    out = []
    for p in problems:
        lead = next((x for x in (PREFIX, CAST) if p.startswith(x)), "")
        body, clipped = CLIP.subn("", p[len(lead) :])
        body = re.sub(
            rf"unknown (?:reference )?({ID.pattern})",
            lambda m: f"{called.get(m[1], KIND[m[2]])} that isn't part of this video",
            body,
        )
        body = ID.sub(what, body)
        out.append(lead + (body[:1].upper() + body[1:] if clipped else body))
    return list(dict.fromkeys(out))


def said(text: str) -> str:
    """One message as people read it: an id still in it (an AI's note, an older saved check)
    said for what it is ("a character")."""
    return plain([text], {})[0] if text else text


# What a response shows people (Reed saw "slot:28"): every problem, kept advice and note
# goes through `said` on the way out, whatever made it.
Said = Annotated[list[str], AfterValidator(lambda ps: [said(p) for p in ps])]
SaidText = Annotated[str, AfterValidator(said)]


class KeepIn(BaseModel):
    problem: str  # the advice text, exactly as shown


def blocking(problems: list[str]) -> list[str]:
    """The problems that must be fixed before the step can go on."""
    return [p for p in problems if not p.startswith(PREFIX)]


def stops(row) -> list[str]:
    """A frame's or clip's problems that must be fixed first: advice never blocks, nor does a
    cast problem kept anyway (as the screens' `blocking`)."""
    kept = row.kept or []
    return [p for p in blocking(row.problems or []) if not (p.startswith(CAST) and p in kept)]


class ApproveAllOut(BaseModel):
    approved: list[int]  # what this press approved: Undo sends exactly these back
    skipped: list[dict]  # [{id, reason}] in plain words ("no still yet")


class UndoIn(BaseModel):
    ids: list[int]


def open_cast(row) -> list[str]:
    """A breakdown's cast problems that aren't fixed or kept: they stop stills."""
    if row is None:
        return []
    return [p for p in row.problems or [] if p.startswith(CAST) and p not in (row.kept or [])]


def keep(row, problem: str) -> None:
    """Record "Keep anyway" for one piece of advice on a breakdown, frame or clip row."""
    problem = next((p for p in row.problems or [] if problem in (p, said(p))), None)
    if problem is None:
        raise HTTPException(404, "That advice isn't on this one any more.")
    if not problem.startswith((PREFIX, CAST)):
        raise HTTPException(409, "Only advice can be kept; this one needs fixing.")
    if problem not in (row.kept or []):
        row.kept = [*(row.kept or []), problem]


def unkeep(row, problem: str) -> None:
    """Undo "Keep anyway": the advice shows as new again (nothing to do if it wasn't kept)."""
    row.kept = [p for p in (row.kept or []) if problem not in (p, said(p))]
