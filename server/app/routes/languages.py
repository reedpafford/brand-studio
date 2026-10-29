"""The languages for the pickers (flows VS1): a script's and the brand's default, and the
owner's sample test and On/Off for each. Rules: app/languages.py, app/language_samples.py."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import credits, language_samples, languages
from app.auth import current_user, owner_only
from app.db import get_db, utcnow
from app.models.accounts import User
from app.routes.brands import get_brand
from app.routes.clips import generation_on

router = APIRouter(prefix="/languages", tags=["languages"], dependencies=[Depends(current_user)])
ENGLISH_STAYS = "English is always on."


class LanguageOut(BaseModel):
    id: str  # "es": what scripts.language and brands.default_language hold
    name: str  # "Spanish"
    on: bool  # editors can pick it (off until its sample test is approved)


class LanguageSwitchIn(BaseModel):
    on: bool


class LanguageSampleOut(BaseModel):
    """Test <language> · credits; the sample to read, then Approve or Reject."""

    status: Literal["none", "making", "ready", "rejected", "failed"]
    text: str | None  # the sample script, once written
    reason: str | None  # why it failed, in plain words
    credits: int  # Test <language> · N credits (one script call)
    language: LanguageOut
    test_site: str | None = None  # real tests on: real, or a stand-in past their budget


class LanguageSampleIn(BaseModel):
    brand_id: int  # the brand the sample is written for


class LanguageRejectIn(BaseModel):
    rejected: bool  # true: Reject; false: Undo


def _out(db: Session, ws: int, language: str) -> LanguageOut:
    return LanguageOut(id=language, name=languages.name(language),
                       on=languages.is_on(db, ws, language))  # fmt: skip


def _sample(db: Session, owner: User, language: str, settings) -> LanguageSampleOut:
    ws = owner.workspace_id
    status, text, reason = language_samples.state(db, ws, language)
    return LanguageSampleOut(status=status, text=text, reason=reason,
                     credits=credits.price(language_samples.price(db, ws)),
                     language=_out(db, ws, language),
                     test_site=language_samples.test_site_note(db, settings, ws))  # fmt: skip


@router.get("", response_model=list[LanguageOut])
def list_languages(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """English first. Editors see the Off ones too, greyed."""
    return [_out(db, user.workspace_id, k) for k in languages.LANGUAGES]


@router.patch("/{language}", response_model=LanguageOut)
def switch_language(
    language: str,
    body: LanguageSwitchIn,
    owner: User = Depends(owner_only),
    db: Session = Depends(get_db),
):
    """Approve: switch on for editors (only with a read, unrejected sample), or off (scripts
    already in it keep it); Undo is the opposite press."""
    ws = owner.workspace_id
    if languages.check(language) == languages.DEFAULT:
        if not body.on:
            raise HTTPException(409, ENGLISH_STAYS)
        return _out(db, ws, language)
    if body.on and not language_samples.ready(db, ws, language):
        raise HTTPException(409, language_samples.NO_SAMPLE)
    row = language_samples.switch_row(db, ws, language)
    row.on, row.switched_by_id, row.switched_at = body.on, owner.id, utcnow()
    db.commit()
    return _out(db, ws, language)


@router.get("/{language}/sample", response_model=LanguageSampleOut)
def sample(
    language: str,
    request: Request,
    owner: User = Depends(owner_only),
    db: Session = Depends(get_db),
):
    languages.check(language)
    return _sample(db, owner, language, request.app.state.settings)


@router.post("/{language}/sample", response_model=LanguageSampleOut, status_code=201,
             dependencies=[Depends(generation_on)])  # fmt: skip
def make_sample(
    language: str,
    body: LanguageSampleIn,
    request: Request,
    owner: User = Depends(owner_only),
    db: Session = Depends(get_db),
):
    """Test <language> (paid: one script call); again replaces the sample."""
    brand = get_brand(db, owner, body.brand_id)
    settings = request.app.state.settings
    language_samples.make(db, owner, language, brand, settings)
    return _sample(db, owner, language, settings)


@router.patch("/{language}/sample", response_model=LanguageSampleOut)
def reject_sample(
    language: str,
    body: LanguageRejectIn,
    request: Request,
    owner: User = Depends(owner_only),
    db: Session = Depends(get_db),
):
    """Reject the sample (the language stays off), or Undo."""
    languages.check(language)
    language_samples.reject(db, owner, language, body.rejected)
    return _sample(db, owner, language, request.app.state.settings)
