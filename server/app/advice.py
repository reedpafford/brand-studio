"""Advice is never a dead end (Reed, 2026-10-25): a check's problem that starts "Advice: " never
blocks a step; the editor can keep it ("Keep anyway") and it isn't shown as open again."""

from fastapi import HTTPException
from pydantic import BaseModel

PREFIX = "Advice: "


class KeepIn(BaseModel):
    problem: str  # the advice text, exactly as shown


def blocking(problems: list[str]) -> list[str]:
    """The problems that must be fixed before the step can go on."""
    return [p for p in problems if not p.startswith(PREFIX)]


def keep(row, problem: str) -> None:
    """Record "Keep anyway" for one piece of advice on a breakdown, frame or clip row."""
    if problem not in (row.problems or []):
        raise HTTPException(404, "That advice isn't on this one any more.")
    if not problem.startswith(PREFIX):
        raise HTTPException(409, "Only advice can be kept; this one needs fixing.")
    if problem not in (row.kept or []):
        row.kept = [*(row.kept or []), problem]


def unkeep(row, problem: str) -> None:
    """Undo "Keep anyway": the advice shows as new again (nothing to do if it wasn't kept)."""
    row.kept = [p for p in (row.kept or []) if p != problem]
