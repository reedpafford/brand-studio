"""Voices (v6 S8-04, the voice record in app/models/voices.py): the app's own voices, a
brand's saved, cloned and described ones, and a style's own voice (Dr. Pickle's clone, Reed 3
Nov: "Dr. Pickle voice = clone"). A narration in a saved voice names it "voice:<id>"
(SongTake.voice) and is read through the model it was cloned for.

Cloning (replicate.com/minimax/voice-cloning, its API schema and billing table, read 3 Nov,
fixture tests/fixtures/replicate/minimax_voice-cloning.json): `voice_file` "MP3, M4A, or WAV
format, 10s to 5min duration, and less than 20MB", `model` one of speech-2.6-turbo/-hd,
speech-02-turbo/-hd, `need_noise_reduction`, `need_volume_normalization`; it returns
{voice_id, preview, model}; $3 an output. We clone for speech-02-hd, where batch-b's clone of
Dr. Pickle was made and proven (same pitch and pace, words exact); speech-02-hd takes pauses
<#x#> and an emotion, but not the sounds like (breath) that only 2.8 reads (MiniMax's T2A
docs). A cloned voice "reportedly expires if unused 7 days" (batch-b): that's shown plainly,
and a narration in a voice that may be gone is refused with what to do, never read in another
voice instead."""

import re
import subprocess
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import narration
from app.catalogue import get_model
from app.credits import estimate
from app.db import utcnow
from app.models.accounts import User
from app.models.files import StoredFile
from app.models.jobs import WAITING, Job, JobStatus
from app.models.library import LibraryItem
from app.models.voices import Voice

STEP, CLONER, SPEAKS = "voice_clone", "minimax-voice-cloning", "minimax-speech-02-hd"
TRAINED_FOR = "speech-02-hd"  # minimax/voice-cloning's `model`: what SPEAKS reads
KEEPS = timedelta(days=7)  # a clone unused this long may be deleted by MiniMax
SOON = timedelta(days=2)  # "may expire" from here on
SAMPLES = Path(__file__).parent / "samples" / "voices"
SHORTEST, LONGEST, LARGEST = 10.0, 300.0, 20 * 1024 * 1024  # the cloning model's limits
SAMPLE_TYPES = ("audio/mpeg", "audio/wav", "audio/mp4")  # MP3, WAV, M4A
PREFIX = "voice:"
ELEVENLABS = set(narration.ELEVENLABS)
# The app's own voices: their names and what they sound like (song-ad-workflow.md, the
# presenter-1 and th-20s tests, MiniMax's system voice list). Only those narration offers.
ABOUT = {
    "Sarah": ("Sarah", "Warm woman, the narrator's default"),
    "Alexandra": ("Alexandra", "Natural woman's voice"),
    "Hope": ("Hope", "Natural woman's voice"),
    "Jane": ("Jane", "Natural woman's voice"),
    "Austin": ("Austin", "Deep man, about 81 Hz"),
    "Roger": ("Roger", "Relaxed man, about 115 Hz"),
    "English_FriendlyPerson": ("Friendly Guy", "Friendly man, a UGC talker's default"),
    "English_Trustworth_Man": ("Trustworthy Man", "Steady, trustworthy man"),
    "English_Upbeat_Woman": ("Upbeat Woman", "Upbeat woman"),
    "English_ConfidentWoman": ("Confident Woman", "Confident woman"),
    "English_Graceful_Lady": ("Graceful Lady", "Older woman, low and warm, about 186 Hz"),
}
# A style's own voice, in every workspace (made the first time voices are read)
STYLE_VOICES = (
    {"look": "dr-pickle", "name": "Dr. Pickle", "kind": "cloned", "provider": "minimax",
     "provider_voice_id": "R8_CJRWYITM", "speech_model": SPEAKS,
     "description": "Deep male voice, blunt and fast, cloned from Dr. Pickle's reference videos",
     "cloned_at": "2026-11-03T20:50:18"},
)  # fmt: skip

NOT_STOCK = "There's no app voice called that."
SAVED_ALREADY = "This brand has that voice already."
NO_VOICE = "There's no such voice."
STYLE_OWNER = "Only the owner removes a style's own voice."
NOT_ARCHIVED = "This voice isn't removed, so there's nothing to bring back."
SAMPLE_KIND = "The sample must be an MP3, WAV or M4A recording."
SAMPLE_SHORT = "The sample must be at least 10 seconds of the voice. This one is {:.0f} s."
SAMPLE_LONG = "The sample can be 5 minutes at most. This one is {:.0f} s."
SAMPLE_BIG = "The sample must be under 20 MB."
SAMPLE_UNREADABLE = "This sample can't be read as audio. Upload it again as an MP3 or WAV."
NO_NAME = "Give the voice a name."
HELD = "Cloning a voice costs money, so it waits for the owner's OK. Nothing is charged yet."
CLONE_FAILED = "The voice couldn't be cloned. Nothing was charged. Try another sample."
GONE = ("{name}'s cloned voice hasn't been used for 7 days and MiniMax may have deleted it. "
        "Clone it again in Library > Presenters & voices (up to {credits} credits) or pick "
        "another voice.")  # fmt: skip
LOST = ("MiniMax no longer has {name}'s cloned voice. Clone it again in Library > Presenters "
        "& voices (up to {credits} credits) or pick another voice.")  # fmt: skip
NOT_READY = "{name}'s voice is still being cloned. It's ready in a moment."
NO_SOUNDS = ("{name}'s cloned voice can't read sounds like (breath): leave them out and keep "
             "the pause marks.")  # fmt: skip
VOICE_GONE = re.compile(r"voice[ _-]?id[^.]*(?:not (?:exist|found)|invalid)|2054", re.I)


# --- Reading ---------------------------------------------------------------------------------


def ensure_style_voices(db: Session, workspace_id: int) -> None:
    """Each style's own voice, once per workspace (an archived one stays archived)."""
    have = set(db.scalars(select(Voice.look).where(Voice.workspace_id == workspace_id,
                                                   Voice.look.is_not(None))))  # fmt: skip
    for given in STYLE_VOICES:
        if given["look"] in have:
            continue
        made = datetime.fromisoformat(given["cloned_at"])
        db.add(Voice(workspace_id=workspace_id, **{**given, "cloned_at": made},
                     last_used_at=made))  # fmt: skip
    db.flush()


def rows(db: Session, workspace_id: int, brand_id: int, archived: bool = False) -> list[Voice]:
    """The brand's own voices, then the styles' voices (every brand's), oldest first."""
    ensure_style_voices(db, workspace_id)
    gone = Voice.archived_at.is_not(None) if archived else Voice.archived_at.is_(None)
    found = db.scalars(select(Voice).where(
        Voice.workspace_id == workspace_id, gone,
        (Voice.brand_id == brand_id) | Voice.brand_id.is_(None)).order_by(Voice.id))  # fmt: skip
    return sorted(found, key=lambda v: (v.brand_id is None, v.id))


def expires_at(voice: Voice):
    """When MiniMax may delete a clone: 7 days after its last use (or its making)."""
    last = voice.last_used_at or voice.cloned_at
    return last + KEEPS if voice.kind == "cloned" and last else None


def state(db: Session, voice: Voice) -> tuple[str, str]:
    """(cloning | ready | may_expire | expired | failed, the plain reason)."""
    if voice.kind != "cloned":
        return "ready", ""
    job = db.get(Job, voice.job_id) if voice.job_id else None
    if not voice.provider_voice_id:
        if job and job.status in WAITING:
            return "cloning", HELD if job.status == JobStatus.needs_owner_approval else ""
        return "failed", (job.error if job and job.error else CLONE_FAILED)
    credits = clone_credits(db, voice.workspace_id)
    if voice.lost_at:
        return "expired", LOST.format(name=voice.name, credits=credits)
    ends = expires_at(voice)
    if ends and utcnow() >= ends:
        return "expired", GONE.format(name=voice.name, credits=credits)
    return ("may_expire", "") if ends and utcnow() >= ends - SOON else ("ready", "")


def used_by(db: Session, voice_ids: list[int]) -> dict[int, list[int]]:
    """Each voice's library items (a character's voice, S8-03)."""
    out: dict[int, list[int]] = {}
    for item_id, voice_id in db.execute(select(LibraryItem.id, LibraryItem.voice_id).where(
            LibraryItem.voice_id.in_(voice_ids), LibraryItem.archived.is_(False))):  # fmt: skip
        out.setdefault(voice_id, []).append(item_id)
    return out


def sample_name(voice: Voice | None, stock_key: str | None = None) -> str | None:
    """The committed free sample's name (an app voice's key, or a style voice's look)."""
    key = stock_key or (voice.stock_key or voice.look if voice else None)
    plain = bool(key) and re.fullmatch(r"[A-Za-z][\w-]*", key) is not None  # a name, no path
    return key if plain and (SAMPLES / f"{key}.mp3").is_file() else None


def stock_keys() -> list[str]:
    """The app's voices, in narration's order (only those it can read)."""
    return [k for k in narration.VOICES if k in ABOUT]


def stock(key: str) -> dict:
    if key not in stock_keys():
        raise HTTPException(422, NOT_STOCK)
    name, about = ABOUT[key]
    return {"name": name, "description": about, "stock_key": key, "kind": "stock",
            "provider": "elevenlabs" if key in ELEVENLABS else "minimax"}  # fmt: skip


def clone_credits(db: Session, workspace_id: int) -> Decimal:
    """One clone's price, up to (one call at the catalogue's real cost)."""
    return estimate(db, workspace_id, "voice", Decimal(1), {"model": CLONER})


def clone_usd() -> Decimal:
    return get_model(CLONER).usd_per_unit()


# --- Saving and cloning ----------------------------------------------------------------------


def save_stock(db: Session, user: User, brand_id: int, key: str) -> Voice:
    """An app voice saved to the brand (free)."""
    given = stock(key)
    taken = db.scalar(select(Voice.id).where(Voice.brand_id == brand_id, Voice.stock_key == key,
                                             Voice.archived_at.is_(None)))  # fmt: skip
    if taken:
        raise HTTPException(409, SAVED_ALREADY)
    voice = Voice(workspace_id=user.workspace_id, brand_id=brand_id, created_by_id=user.id,
                  **given)  # fmt: skip
    db.add(voice)
    db.flush()
    return voice


def _seconds(data: bytes) -> float:
    """The recording's length (ffprobe, free); 0 when it can't be read."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sample"
        path.write_bytes(data)
        probe = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                 "csv=p=0", str(path)]  # fmt: skip
        done = subprocess.run(probe, capture_output=True, text=True, timeout=60)  # noqa: S603
    try:
        return float(done.stdout.strip())
    except ValueError:
        return 0.0


def check_sample(storage, stored: StoredFile) -> None:
    """The cloning model's own limits, before anything is spent."""
    if stored.content_type not in SAMPLE_TYPES:
        raise HTTPException(422, SAMPLE_KIND)
    if stored.size >= LARGEST:
        raise HTTPException(422, SAMPLE_BIG)
    seconds = _seconds(storage.get(stored.key))
    if not seconds:
        raise HTTPException(422, SAMPLE_UNREADABLE)
    if seconds < SHORTEST:
        raise HTTPException(422, SAMPLE_SHORT.format(seconds))
    if seconds > LONGEST:
        raise HTTPException(422, SAMPLE_LONG.format(seconds))


def clone(db: Session, user: User, brand_id: int, storage, stored: StoredFile, name: str,
          description: str) -> Voice:  # fmt: skip
    """Clone a voice from a sample: one paid call, held for the owner when an editor asks."""
    from app.routes.jobs import enqueue

    if not name.strip():
        raise HTTPException(422, NO_NAME)
    check_sample(storage, stored)
    voice = Voice(workspace_id=user.workspace_id, brand_id=brand_id, name=name.strip()[:120],
                  kind="cloned", provider="minimax", speech_model=SPEAKS,
                  description=description.strip(), sample_file_id=stored.id,
                  created_by_id=user.id)  # fmt: skip
    db.add(voice)
    db.flush()
    job = enqueue(db, user, "voice", {
        "step": STEP, "model": CLONER, "voice_row_id": voice.id, "brand_id": brand_id,
        "input": {"model": TRAINED_FOR, "need_volume_normalization": True,
                  "need_noise_reduction": False},
        "files": {"voice_file": [stored.id]}}, units=1, provider="replicate",
        wait="" if user.is_owner else HELD)  # fmt: skip
    voice.job_id = job.id
    db.commit()
    return voice


def saved(db: Session, job: Job) -> None:
    """The clone is made: its voice id and MiniMax's preview of it."""
    voice = db.get(Voice, job.input["voice_row_id"])
    fields = (job.output or {}).get("fields") or {}
    if voice is None or not fields.get("voice_id"):
        return
    files = (job.output or {}).get("file_ids") or []
    now = utcnow()
    voice.provider_voice_id = str(fields["voice_id"])[:120]
    voice.preview_file_id = files[0] if files else None
    voice.cloned_at = voice.last_used_at = now
    voice.lost_at = None


def archive(db: Session, user: User, voice: Voice) -> None:
    if voice.look and not user.is_owner:
        raise HTTPException(403, STYLE_OWNER)
    voice.archived_at = utcnow()


def restore(voice: Voice) -> None:
    if voice.archived_at is None:
        raise HTTPException(409, NOT_ARCHIVED)
    voice.archived_at = None


# --- Speaking --------------------------------------------------------------------------------


def named(db: Session, workspace_id: int, said: str) -> Voice | None:
    """A saved voice from its narration name "voice:<id>", in this workspace."""
    if not (said or "").startswith(PREFIX) or not said[len(PREFIX) :].isdigit():
        return None
    voice = db.get(Voice, int(said[len(PREFIX) :]))
    return voice if voice and voice.workspace_id == workspace_id else None


def ready(db: Session, voice: Voice) -> None:
    """A narration in this voice can be made, or it's refused saying what to do."""
    status, why = state(db, voice)
    if status == "cloning":
        raise HTTPException(409, NOT_READY.format(name=voice.name))
    if status in ("expired", "failed"):
        raise HTTPException(409, why)


def narration_job(db: Session, workspace_id: int, script: str, said: str, note: str = "",
                  emotion: str | None = None, reading: str = "") -> dict:  # fmt: skip
    """The voice call in a saved voice: MiniMax's own inputs (narration's), its voice id, on
    the model it was cloned for. A voice that may be gone is refused (409), never swapped."""
    voice = named(db, workspace_id, said)
    if voice is None or voice.archived_at is not None:
        raise HTTPException(422, NO_VOICE)
    if voice.kind == "stock":  # an app voice saved to a brand reads as itself
        return narration.job(script, voice.stock_key, note, emotion, reading)
    if voice.kind != "cloned":
        raise HTTPException(422, NO_VOICE)
    ready(db, voice)
    if voice.speech_model != narration.MINIMAX and any(
        f"({s})" in (reading or "") for s in narration.SOUNDS
    ):
        raise HTTPException(422, NO_SOUNDS.format(name=voice.name))
    try:
        built = narration.job(script, narration.MINIMAX_VOICES[0], note, emotion, reading)
    except ValueError as no:
        raise HTTPException(422, str(no)) from None
    built["input"]["voice_id"] = voice.provider_voice_id
    return {**built, "model": voice.speech_model, "saved_voice": voice.id}


def used(db: Session, job: Job) -> None:
    """A narration in a saved voice was made: MiniMax keeps it 7 more days."""
    if voice := db.get(Voice, job.input.get("saved_voice") or 0):
        voice.last_used_at = utcnow()


def failed(db: Session, job: Job) -> None:
    """A narration in a cloned voice MiniMax no longer has: the voice is lost, said plainly."""
    voice = db.get(Voice, job.input.get("saved_voice") or 0)
    if voice is None or not VOICE_GONE.search(job.error_detail or ""):
        return
    voice.lost_at = utcnow()
    job.error = LOST.format(name=voice.name, credits=clone_credits(db, voice.workspace_id))


def default_for(db: Session, project) -> str | None:
    """A video's own narrator, when it has one: its host's voice (a character's voice), else
    its style's voice ("voice:<id>"); None: narration's own default."""
    from app import host

    ensure_style_voices(db, project.workspace_id)
    item = host.host_look(db, project) if host.on(db, project) else None
    if item is not None and item.voice_id:
        return f"{PREFIX}{item.voice_id}"
    look = project.look or ""
    found = db.scalar(
        select(Voice.id).where(
            Voice.workspace_id == project.workspace_id,
            Voice.look == look,
            Voice.archived_at.is_(None),
        )
    )
    return f"{PREFIX}{found}" if found else None


def for_director(db: Session, workspace_id: int, said: str | None) -> dict | None:
    """The saved voice a narration is (or will be) read in, as the director reads it."""
    voice = named(db, workspace_id, said or "")
    if voice is None:
        return None
    status, why = state(db, voice)
    ends = expires_at(voice)
    return {"name": voice.name, "kind": voice.kind, "state": status, "why": why,
            "expires_at": ends.isoformat() if ends else None}  # fmt: skip
