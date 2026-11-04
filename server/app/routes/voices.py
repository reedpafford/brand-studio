"""Voices (v6 S8-04, Library › Presenters & voices): a brand's voices with their free
samples, an app voice saved to the brand (free), a voice cloned from a sample (priced first,
up to one clone's real cost), and remove with Undo. Rules: app/voices.py."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import voices
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.voices import Voice
from app.routes.brands import get_brand
from app.routes.files import get_file
from app.schemas import UtcTime

router = APIRouter(tags=["voices"])


class VoiceOut(BaseModel):
    id: int | None  # null: an app voice not saved to this brand (`?all=true`)
    name: str
    kind: Literal["stock", "cloned", "described"]
    stock_key: str | None
    provider: str  # elevenlabs | minimax | omni
    description: str
    look: str | None  # a style's own voice (for every brand), e.g. "dr-pickle"
    brand_id: int | None
    sample_file_id: int | None  # the clone's uploaded sample
    sample_url: str | None  # a free committed sample (an app voice, a style's voice)
    preview_file_id: int | None  # MiniMax's preview of the clone
    cloned_at: UtcTime | None
    last_used_at: UtcTime | None
    expires_at: UtcTime | None  # a clone: 7 days after its last use, MiniMax may delete it
    state: Literal["cloning", "ready", "may_expire", "expired", "failed"]
    error: str  # what to do, in plain words ("" when nothing)
    used_by: list[int]  # library items with this voice


class VoicesOut(BaseModel):
    voices: list[VoiceOut]
    clone_credits: float  # "Clone a voice · up to N credits"
    clone_usd: float | None  # the owner's "$3.00 once"; null for an editor


class VoiceSaveIn(BaseModel):
    stock_key: str


class VoiceCloneIn(BaseModel):
    name: str
    description: str = ""
    sample_file_id: int


def _url(request: Request, name: str | None) -> str | None:
    return str(request.url_for("voice_sample", name=name)) if name else None


def _out(db: Session, request: Request, voice: Voice, used: dict) -> VoiceOut:
    state, why = voices.state(db, voice)
    return VoiceOut(id=voice.id, name=voice.name, kind=voice.kind, stock_key=voice.stock_key,
                    provider=voice.provider, description=voice.description, look=voice.look,
                    brand_id=voice.brand_id, sample_file_id=voice.sample_file_id,
                    sample_url=_url(request, voices.sample_name(voice)),
                    preview_file_id=voice.preview_file_id, cloned_at=voice.cloned_at,
                    last_used_at=voice.last_used_at, expires_at=voices.expires_at(voice),
                    state=state, error=why, used_by=used.get(voice.id, []))  # fmt: skip


def _stock_out(request: Request, key: str) -> VoiceOut:
    given = voices.stock(key)
    return VoiceOut(id=None, look=None, brand_id=None, sample_file_id=None,
                    sample_url=_url(request, voices.sample_name(None, key)),
                    preview_file_id=None, cloned_at=None, last_used_at=None, expires_at=None,
                    state="ready", error="", used_by=[], **given)  # fmt: skip


def _voice(db: Session, user: User, voice_id: int) -> Voice:
    voice = db.get(Voice, voice_id)
    if voice is None or voice.workspace_id != user.workspace_id:
        raise HTTPException(404, voices.NO_VOICE)
    if voice.brand_id is not None:
        get_brand(db, user, voice.brand_id)
    return voice


@router.get("/brands/{brand_id}/voices", response_model=VoicesOut)
def list_voices(brand_id: int, request: Request, all: bool = False,
                user: User = Depends(current_user), db: Session = Depends(get_db)):  # fmt: skip
    """The brand's own voices and the styles' voices; `all` adds every app voice not saved."""
    get_brand(db, user, brand_id)
    rows = voices.rows(db, user.workspace_id, brand_id)
    used = voices.used_by(db, [v.id for v in rows])
    out = [_out(db, request, v, used) for v in rows]
    if all:
        saved = {v.stock_key for v in rows if v.stock_key}
        out += [_stock_out(request, k) for k in voices.stock_keys() if k not in saved]
    db.commit()  # a style's voice made on first read
    usd = voices.clone_usd() if user.is_owner else None
    return VoicesOut(voices=out, clone_credits=float(voices.clone_credits(db, user.workspace_id)),
                     clone_usd=float(usd) if usd is not None else None)  # fmt: skip


@router.post("/brands/{brand_id}/voices", response_model=VoiceOut, status_code=201)
def save_voice(brand_id: int, body: VoiceSaveIn, request: Request,
               user: User = Depends(current_user), db: Session = Depends(get_db)):  # fmt: skip
    """Save an app voice to the brand (free)."""
    get_brand(db, user, brand_id)
    voice = voices.save_stock(db, user, brand_id, body.stock_key)
    db.commit()
    return _out(db, request, voice, {})


@router.post("/brands/{brand_id}/voices/clone", response_model=VoiceOut, status_code=201)
def clone_voice(brand_id: int, body: VoiceCloneIn, request: Request,
                user: User = Depends(current_user), db: Session = Depends(get_db)):  # fmt: skip
    """Clone a voice from a sample (10 s to 5 min): one paid call, up to `clone_credits`; an
    editor's waits for the owner's OK, charged nothing until then."""
    get_brand(db, user, brand_id)
    stored = get_file(db, user, body.sample_file_id, "audio")
    voice = voices.clone(db, user, brand_id, request.app.state.storage, stored, body.name,
                         body.description)  # fmt: skip
    return _out(db, request, voice, {})


@router.delete("/voices/{voice_id}", status_code=204)
def remove_voice(voice_id: int, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):  # fmt: skip
    """Remove a voice (Undo: restore). A style's own voice only by the owner."""
    voices.archive(db, user, _voice(db, user, voice_id))
    db.commit()


@router.post("/voices/{voice_id}/restore", response_model=VoiceOut)
def restore_voice(voice_id: int, request: Request, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):  # fmt: skip
    voice = _voice(db, user, voice_id)
    voices.restore(voice)
    db.commit()
    return _out(db, request, voice, voices.used_by(db, [voice.id]))


@router.get("/voices/samples/{name}.mp3", response_class=FileResponse, name="voice_sample")
def voice_sample(name: str, user: User = Depends(current_user)):
    """A free sample of an app voice or a style's voice (from the paid tests, committed)."""
    if voices.sample_name(None, name) is None:
        raise HTTPException(404, "There's no sample of that voice.")
    return FileResponse(voices.SAMPLES / f"{name}.mp3", media_type="audio/mpeg",
                        headers={"Cache-Control": "private, max-age=86400"})  # fmt: skip
