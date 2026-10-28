"""Song takes for a song script's version (song ads, spec §1): list, make 2 (or 1), Try again,
Preferred (with Undo), remove (with Undo). Rules: app/song_takes.py."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import music, song_takes
from app import script_library as lib
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.jobs import Job
from app.models.script_library import Script, ScriptDraft
from app.models.songs import SongTake
from app.routes.script_library import Slot
from app.schemas import UtcTime

router = APIRouter(tags=["songs"])
SONGS_OFF = "Songs aren't switched on here."
NOT_A_SONG = "This script isn't a song. Start a Song script to make songs."


class SongTakeOut(BaseModel):
    id: int
    number: int
    status: Literal["making", "timing", "ready", "failed", "timing_failed"]
    failed_reason: str | None  # plain words: what happened and what to do
    retry_helps: bool  # Try again can work (else: use the other take or make more)
    file_id: int | None
    seconds: float | None
    made_at: UtcTime | None
    preferred: bool
    out_of_date: bool  # "Sings older words": other lyrics or style line than the version's now
    peaks: list[float]  # the waveform, 0 to 1 (empty until its timing is read)
    advice: list[str]  # e.g. "Timing guessed: …" (never blocks)
    timing_guessed: bool  # spread evenly, not heard
    refused_for: Literal["words", "style"] | None  # a refusal: change the lyrics or the style
    video_credits: float | None  # about what a video of it costs (its trimmed part, if trimmed)
    over_cap: bool  # that video is over the per-video cap: offer Use the first …
    fits_until: float | None  # where "Use the first 0:55" would end it (a section end)
    trim_to: float | None  # in use: only the take's first this-many seconds


class SongsOut(BaseModel):
    songs_on: bool  # false: this server makes no songs (say so, don't offer Make)
    estimate_credits: float  # "Make 2 takes" (one request)
    takes: list[SongTakeOut]


class SongPreferredOut(BaseModel):
    take: SongTakeOut
    was_preferred_id: int | None  # Undo: make that one Preferred again


def songs_on(request: Request) -> bool:
    """Only the stand-ins make songs until Suno is connected (app/music.py)."""
    return bool(request.app.state.settings.fake_providers)


def _refused_for(reason: str | None) -> str | None:
    if reason and reason.startswith(music.COPYRIGHT.split("“")[0]):
        return "style"
    return "words" if reason == music.REFUSED else None


def _take_out(db: Session, take: SongTake, draft: ScriptDraft) -> SongTakeOut:
    status, reason, helps = song_takes.state(db, take)
    over = song_takes.over_cap(db, take)
    return SongTakeOut(
        id=take.id,
        number=take.number,
        status=status,
        failed_reason=reason,
        retry_helps=helps,
        file_id=take.file_id,
        seconds=take.seconds,
        made_at=db.get(Job, take.job_id).finished_at if take.file_id else None,
        preferred=take.preferred,
        out_of_date=song_takes.out_of_date(take, draft),
        peaks=(take.timing or {}).get("peaks", []),
        advice=take.advice or [],
        timing_guessed=take.timing_guessed,
        refused_for=_refused_for(reason),
        video_credits=float(song_takes.video_credits(db, take)) if take.seconds else None,
        over_cap=over,
        fits_until=song_takes.fits_until(db, take) if over else None,
        trim_to=take.trim_to,
    )


def _song(db: Session, user: User, script_id: int, slot: int, edit: bool) -> ScriptDraft:
    script = lib.get_script(db, user, script_id)
    if edit:
        lib.editable(user, script)
    if script.kind != "song":
        raise HTTPException(409, NOT_A_SONG)
    return lib.get_draft(db, script, slot)


def _songs(request: Request, db: Session, user: User, draft: ScriptDraft) -> SongsOut:
    return SongsOut(
        songs_on=songs_on(request),
        estimate_credits=float(song_takes.price(db, user)),
        takes=[_take_out(db, t, draft) for t in song_takes.takes(db, draft)],
    )


@router.get("/scripts/{script_id}/drafts/{slot}/songs", response_model=SongsOut)
def list_songs(
    script_id: int,
    slot: Slot,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return _songs(request, db, user, _song(db, user, script_id, slot, edit=False))


@router.post("/scripts/{script_id}/drafts/{slot}/songs", response_model=SongsOut, status_code=201)
def make_songs(
    script_id: int,
    slot: Slot,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Make 2 takes (one request) of the version's lyrics in its style line."""
    if not songs_on(request):
        raise HTTPException(503, SONGS_OFF)
    draft = _song(db, user, script_id, slot, edit=True)
    song_takes.make(db, user, draft)
    return _songs(request, db, user, draft)


def _get_take(db: Session, user: User, take_id: int) -> tuple[SongTake, ScriptDraft]:
    """A take of a script the caller may change, or 404/403."""
    take = db.get(SongTake, take_id)
    draft = db.get(ScriptDraft, take.draft_id) if take else None
    script = db.get(Script, draft.script_id) if draft else None
    if not script or script.workspace_id != user.workspace_id:
        raise HTTPException(404, "No such take.")
    lib.editable(user, lib.get_script(db, user, script.id))
    return take, draft


@router.post("/songs/{take_id}/try-again", response_model=SongTakeOut)
def try_again(
    take_id: int,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not songs_on(request):
        raise HTTPException(503, SONGS_OFF)
    take, draft = _get_take(db, user, take_id)
    song_takes.try_again(db, user, take)
    return _take_out(db, take, draft)


@router.post("/songs/{take_id}/spread-timing", response_model=SongTakeOut)
def spread_timing(take_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Timing failed: "Use timing spread evenly" (free)."""
    take, draft = _get_take(db, user, take_id)
    song_takes.spread(db, user, take)
    return _take_out(db, take, draft)


@router.post("/songs/{take_id}/trim", response_model=SongTakeOut)
def trim_take(take_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Over the cap: "Use the first 0:55" (to the last section end that fits)."""
    take, draft = _get_take(db, user, take_id)
    song_takes.trim(db, take, on=True)
    return _take_out(db, take, draft)


@router.delete("/songs/{take_id}/trim", response_model=SongTakeOut)
def untrim_take(take_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Undo: the whole take again."""
    take, draft = _get_take(db, user, take_id)
    song_takes.trim(db, take, on=False)
    return _take_out(db, take, draft)


@router.post("/songs/{take_id}/preferred", response_model=SongPreferredOut)
def set_preferred(take_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    take, draft = _get_take(db, user, take_id)
    was = song_takes.prefer(db, take)
    return SongPreferredOut(take=_take_out(db, take, draft), was_preferred_id=was)


@router.delete("/songs/{take_id}", status_code=204)
def remove_take(take_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    take, _ = _get_take(db, user, take_id)
    if take.deleted_at is None:
        song_takes.remove(db, take)
    return Response(status_code=204)


@router.post("/songs/{take_id}/restore", response_model=SongTakeOut)
def restore_take(take_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    take, draft = _get_take(db, user, take_id)
    song_takes.restore(db, take)
    return _take_out(db, take, draft)
