"""Song takes for a song script's version (song ads, spec §1): list, make 2 (or 1), Try again,
Preferred (with Undo), remove (with Undo). Rules: app/song_takes.py."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, StringConstraints
from sqlalchemy.orm import Session

from app import music, narration, song_directions, song_takes
from app import script_library as lib
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.jobs import Job
from app.models.script_library import Script, ScriptDraft
from app.models.songs import SongTake
from app.routes.clips import generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.projects import get_project
from app.routes.script_library import Slot
from app.schemas import LongText, UtcTime

router = APIRouter(tags=["songs"])
SONGS_OFF = "Songs aren't switched on here."
NOT_A_SONG = "This script isn't a song. Start a Song script to make songs."


class Sentence(BaseModel):
    text: str
    start: float
    end: float


class SongTakeOut(BaseModel):
    id: int
    number: int
    status: Literal["making", "timing", "ready", "failed", "timing_failed"]
    failed_reason: str | None  # plain words: what happened and what to do
    retry_helps: bool  # Try again can work (else: use the other take or make more)
    retry_credits: float  # what Try again costs (0: a timing, or a reply short of a song)
    file_id: int | None
    seconds: float | None
    made_at: UtcTime | None
    preferred: bool
    in_video: bool  # made in this video (not one of its version's takes)
    out_of_date: bool  # "Sings older words": other lyrics or style line than the version's now
    peaks: list[float]  # the waveform, 0 to 1 (empty until its timing is read)
    advice: list[str]  # e.g. "Timing guessed: …" (never blocks)
    timing_guessed: bool  # spread evenly, not heard
    refused_for: Literal["words", "style"] | None  # a refusal: change the lyrics or the style
    video_credits: float | None  # about what a video of it costs (its trimmed part, if trimmed)
    over_cap: bool  # that video is over the per-video cap: offer Use the first …
    fits_until: float | None  # where "Use the first 0:55" would end it (a section end)
    trim_to: float | None  # in use: only the take's first this-many seconds
    kind: Literal["song", "narration"] = "song"  # a narration: one voice reads the words (N1)
    voice: str = ""  # a narration's voice ("Sarah")
    # A narration's music bed (N1): none | making | ready | failed, its reason and file, and
    # what Try the music again costs
    music_status: Literal["none", "making", "ready", "failed"] = "none"
    music_reason: str | None = None
    music_file_id: int | None = None
    music_credits: float = 0
    sentences: list[Sentence] = []  # a narration's sentences, each with its measured times
    untrimmed_seconds: float | None = None  # a narration whose pauses were trimmed: "2:26 → 2:19"


class SongsOut(BaseModel):
    songs_on: bool  # false: this server makes no songs (say so, don't offer Make)
    estimate_credits: float  # "Make 2 takes" (one request)
    video_estimate_credits: float  # about what a video of these lyrics costs (a guess)
    keep_lines: int | None  # over the cap: keep the first this-many sung lines to fit
    takes: list[SongTakeOut]
    voice: str = ""  # a Narrated version's narrator ("Sarah"); "" for a song
    songs_note: str | None = None  # e.g. real songs for this test are used up: stand-ins now


class SongPreferredOut(BaseModel):
    take: SongTakeOut
    was_preferred_id: int | None  # Undo: make that one Preferred again


def songs_on(request: Request, db: Session | None = None, draft: ScriptDraft | None = None):
    """The stand-ins, or Suno through KIE once Reed switches it on (app/providers/kie.py). A
    narration's voice is on Replicate, so it's on wherever paid generation is."""
    settings = request.app.state.settings
    if draft is not None and song_takes.narrated(db, draft):
        return bool(settings.fake_providers or settings.generation_enabled)
    return bool(settings.fake_providers or settings.kie_suno)


def _real(request: Request, db: Session, draft: ScriptDraft) -> float:
    """A real song through KIE's price (song_takes.real_songs); a narration is never one."""
    if song_takes.narrated(db, draft):
        return 0.0
    return song_takes.real_songs(db, request.app.state.settings)


def _music(db: Session, take: SongTake) -> dict:
    from app import narration_music

    if take.kind != narration.KIND:
        return {}
    status, reason = narration_music.state(db, take)
    ws = db.get(Script, db.get(ScriptDraft, take.draft_id).script_id).workspace_id
    credits = float(narration_music.price(db, ws)) if status == "failed" else 0
    return {
        "music_status": status,
        "music_reason": reason,
        "music_file_id": take.music_file_id,
        "music_credits": credits,
    }


def _refused_for(reason: str | None) -> str | None:
    if reason and reason.startswith(music.COPYRIGHT.split("“")[0]):
        return "style"
    return "words" if reason in (music.REFUSED, music.REFUSED_IN_VIDEO) else None


def _take_out(db: Session, take: SongTake, draft: ScriptDraft) -> SongTakeOut:
    status, reason, helps = song_takes.state(db, take)
    over = song_takes.over_cap(db, take)
    return SongTakeOut(
        id=take.id,
        number=take.number,
        status=status,
        failed_reason=reason,
        retry_helps=helps,
        retry_credits=float(song_takes.retry_credits(db, take)),
        file_id=take.file_id,
        seconds=take.seconds,
        made_at=db.get(Job, take.job_id).finished_at if take.file_id else None,
        preferred=take.preferred,
        in_video=take.project_id is not None,
        out_of_date=song_takes.out_of_date(take, draft),
        peaks=(take.timing or {}).get("peaks", []),
        advice=take.advice or [],
        timing_guessed=take.timing_guessed,
        refused_for=_refused_for(reason),
        video_credits=float(song_takes.video_credits(db, take)) if take.seconds else None,
        over_cap=over,
        fits_until=song_takes.fits_until(db, take) if over else None,
        trim_to=take.trim_to,
        kind=take.kind,
        voice=take.voice,
        **_music(db, take),
        sentences=[
            Sentence(text=x["text"], start=x["start"], end=x["end"])
            for x in (take.timing or {}).get("lines", [])
        ]
        if take.kind == narration.KIND
        else [],
        untrimmed_seconds=(take.timing or {}).get("untrimmed_seconds") if take.trimmed else None,
    )


def _song(db: Session, user: User, script_id: int, slot: int, edit: bool) -> ScriptDraft:
    script = lib.get_script(db, user, script_id)
    if edit:
        lib.editable(user, script)
    if script.kind not in narration.TIMED:
        raise HTTPException(409, NOT_A_SONG)
    return lib.get_draft(db, script, slot)


def _songs(request: Request, db: Session, user: User, draft: ScriptDraft) -> SongsOut:
    video, keep = song_takes.lyrics_estimate(db, draft)
    return SongsOut(
        songs_on=songs_on(request, db, draft),
        voice=narration.VOICE if song_takes.narrated(db, draft) else "",
        estimate_credits=float(song_takes.price(db, user.workspace_id, draft)),
        video_estimate_credits=float(video),
        keep_lines=keep,
        takes=[_take_out(db, t, draft) for t in song_takes.takes(db, draft)],
        songs_note=song_takes.BUDGET_USED
        if song_takes.budget_used(db, request.app.state.settings)
        else None,
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
    """Make 2 takes (one request) of the version's lyrics in its style line; on a Narrated
    script, one narration of its words (flows N1)."""
    draft = _song(db, user, script_id, slot, edit=True)
    if not songs_on(request, db, draft):
        raise HTTPException(503, SONGS_OFF)
    song_takes.make(db, user, draft, kie=_real(request, db, draft))
    return _songs(request, db, user, draft)


def _get_take(db: Session, user: User, take_id: int) -> tuple[SongTake, ScriptDraft]:
    """A take the caller may change (a script's: its author or the owner, before it's
    published; a video's own: anyone on the video), or 404/403."""
    take = db.get(SongTake, take_id)
    draft = db.get(ScriptDraft, take.draft_id) if take else None
    script = db.get(Script, draft.script_id) if draft else None
    if not script or script.workspace_id != user.workspace_id:
        raise HTTPException(404, "No such take.")
    if take.project_id:
        get_project(db, user, take.project_id)
    else:
        lib.editable(user, lib.get_script(db, user, script.id))
    return take, draft


@router.post("/songs/{take_id}/try-again", response_model=SongTakeOut)
def try_again(
    take_id: int,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    take, draft = _get_take(db, user, take_id)
    if not songs_on(request, db, draft):
        raise HTTPException(503, SONGS_OFF)
    paid = song_takes.state(db, take)[0] == "failed"  # a timing is read again free
    kie = paid and _real(request, db, draft)
    song_takes.try_again(db, user, take, kie=kie)
    return _take_out(db, take, draft)


@router.post("/songs/{take_id}/music-again", response_model=SongTakeOut)
def music_again(
    take_id: int,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """A narration's music failed: Try the music again (the prompt and the bed, at
    music_credits); the narration is kept as it is."""
    from app import narration_music

    take, draft = _get_take(db, user, take_id)
    if not songs_on(request, db, draft):
        raise HTTPException(503, SONGS_OFF)
    narration_music.try_again(db, take, user)
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


class VideoSongsOut(SongsOut):
    song_take_id: int | None  # the take this video is timed to


class VideoSongIn(BaseModel):
    take_id: int


class VideoSongOut(BaseModel):
    song_take_id: int
    was_song_take_id: int | None  # Undo: use that one again


def _song_video(db: Session, user: User, project_id: int):
    project = get_project(db, user, project_id)
    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    if not draft or db.get(Script, draft.script_id).kind not in narration.TIMED:
        raise HTTPException(409, NOT_A_SONG)
    return project, draft


def _video_songs(request: Request, db: Session, user: User, project, draft) -> VideoSongsOut:
    return VideoSongsOut(
        **_songs(request, db, user, draft).model_dump(exclude={"takes"}),
        takes=[_take_out(db, t, draft) for t in song_takes.for_video(db, project)],
        song_take_id=project.song_take_id,
    )


@router.get("/projects/{project_id}/songs", response_model=VideoSongsOut)
def video_songs(
    project_id: int,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """The takes this video can use (its version's, then its own) and the one it uses."""
    project, draft = _song_video(db, user, project_id)
    return _video_songs(request, db, user, project, draft)


@router.post("/projects/{project_id}/songs", response_model=VideoSongsOut, status_code=201)
def make_video_songs(
    project_id: int,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """More takes for this video only, charged to its budget (or the editor's week)."""
    project, draft = _song_video(db, user, project_id)
    if not songs_on(request, db, draft):
        raise HTTPException(503, SONGS_OFF)
    song_takes.make(db, user, draft, project, _real(request, db, draft))
    return _video_songs(request, db, user, project, draft)


@router.put("/projects/{project_id}/song", response_model=VideoSongOut)
def use_video_song(
    project_id: int,
    body: VideoSongIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Time this video to another take (Undo: put `was_song_take_id` back)."""
    project, _ = _song_video(db, user, project_id)
    take = db.get(SongTake, body.take_id)
    if take is None:
        raise HTTPException(404, "No such take for this video.")
    was = song_takes.use_in_video(db, project, take)
    from app import song_breakdown

    song_breakdown.follow_take(db, project, user.id)  # the shots move to the new take, free
    db.commit()
    return VideoSongOut(song_take_id=take.id, was_song_take_id=was)


class DirectionsIn(BaseModel):
    source: LongText = ""  # a script or voice-over to adapt into lyrics
    sounds_like: Annotated[str, StringConstraints(max_length=300)] = ""
    note: LongText = ""


class DirectionUsed(BaseModel):
    was_text: str  # Undo: PUT the version back with these
    was_style_line: str


def _song_version(db: Session, user: User, script_id: int, slot: int):
    draft = _song(db, user, script_id, slot, edit=True)
    return db.get(Script, draft.script_id), draft


@router.post("/scripts/{script_id}/drafts/{slot}/directions", response_model=JobOut,
             status_code=201, dependencies=[Depends(generation_on)])  # fmt: skip
def write_directions(
    script_id: int,
    slot: Slot,
    body: DirectionsIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Write 2 song directions (one paid Claude call); a press again writes 2 more."""
    script, draft = _song_version(db, user, script_id, slot)
    if reason := song_directions.stop(db, script, draft, body.source):
        raise HTTPException(409, reason)
    if lib.writing(db, script.id, song_directions.STEP):
        raise HTTPException(409, "Song directions are already being written for this version.")
    data = song_directions.job_input(db, script, draft, body.source, body.sounds_like, body.note)
    return enqueue(db, user, "write-claude", data, provider="claude")


@router.post("/scripts/{script_id}/drafts/{slot}/directions/{direction_id}/use",
             response_model=DirectionUsed)  # fmt: skip
def use_direction(
    script_id: int,
    slot: Slot,
    direction_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Its lyrics and style line become the version's (Undo: PUT the was_ values back)."""
    _, draft = _song_version(db, user, script_id, slot)
    was_text, was_style = song_directions.use(db, draft, direction_id)
    return DirectionUsed(was_text=was_text, was_style_line=was_style)


@router.post("/scripts/{script_id}/drafts/{slot}/claims/keep", status_code=204)
def keep_claims(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """The owner vouches for the used direction's claims ("Keep it")."""
    _, draft = _song_version(db, user, script_id, slot)
    song_directions.keep_claims(db, draft)
    return Response(status_code=204)


@router.delete("/scripts/{script_id}/drafts/{slot}/directions/{direction_id}", status_code=204)
def remove_direction(
    script_id: int,
    slot: Slot,
    direction_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    _, draft = _song_version(db, user, script_id, slot)
    song_directions.remove(db, draft, direction_id)
    return Response(status_code=204)


@router.post("/scripts/{script_id}/drafts/{slot}/directions/{direction_id}/restore",
             status_code=204)  # fmt: skip
def restore_direction(
    script_id: int,
    slot: Slot,
    direction_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Undo a remove."""
    _, draft = _song_version(db, user, script_id, slot)
    song_directions.remove(db, draft, direction_id, back=True)
    return Response(status_code=204)
