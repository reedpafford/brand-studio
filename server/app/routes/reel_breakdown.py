"""Review the breakdown (reel-import.md §4): what an imported reel does, shaped for the screen.
Read only and free: the breakdown is what the reel does; fixes go through Read it again."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import prompts
from app import script_library as lib
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User

router = APIRouter(prefix="/scripts", tags=["script library"])
MONTAGE_SHOT, MONTAGE_RUN = 1.0, 5  # shots under 1 s, 5 or more in a row, are one montage


class ShotRow(BaseModel):
    n: int
    start: float
    end: float
    framing: str
    camera: str
    action: str
    speaker: str = ""
    line: str = ""  # what's said in it, as the reel says it
    dropped: bool  # live action: never in the script ("Dropped · live action")


class Montage(BaseModel):
    first: int  # "Shots 17–40 · montage · 11.7 s"
    last: int
    seconds: float


class BreakdownReview(BaseModel):
    logline: str
    hook_seconds: float  # "Hook · 0:00–0:05: …"
    hook: str
    seconds: float
    shots: list[ShotRow]
    dropped: int  # "50 shots · 1 dropped (live action) · 11 lines"
    lines: int
    montages: list[Montage]
    video_file_id: int | None  # the player


def _montages(shots: list[ShotRow]) -> list[Montage]:
    runs, run = [], []
    for shot in [*shots, None]:
        if shot is not None and shot.end - shot.start < MONTAGE_SHOT:
            run.append(shot)
            continue
        if len(run) >= MONTAGE_RUN:
            runs.append(Montage(first=run[0].n, last=run[-1].n,
                                seconds=round(run[-1].end - run[0].start, 1)))  # fmt: skip
        run = []
    return runs


@router.get("/{script_id}/import/breakdown", response_model=BreakdownReview)
def review(script_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    script = lib.get_script(db, user, script_id)
    if script.reel is None:
        raise HTTPException(404, "This script isn't made from a reel.")
    bd = script.reference_breakdown
    if not bd:
        raise HTTPException(409, "The reel hasn't been read yet.")
    shots = [
        ShotRow(
            n=s["n"],
            start=s["start"],
            end=s["end"],
            framing=s["framing"],
            camera=s["camera"],
            action=s["action"],
            speaker=s.get("speaker") or "",
            line=s.get("line") or "",
            dropped=prompts.live_action(s),
        )  # fmt: skip
        for s in bd["shots"]
    ]
    return BreakdownReview(
        logline=bd["logline"],
        hook_seconds=bd["hook"]["seconds"],
        hook=bd["hook"]["mechanic"],
        seconds=bd["duration_seconds"],
        shots=shots,
        dropped=sum(s.dropped for s in shots),
        lines=sum(1 for s in shots if s.line and not s.dropped),
        montages=_montages(shots),
        video_file_id=(script.reel or {}).get("video_file_id"),
    )
