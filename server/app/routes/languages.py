"""The languages for the pickers (flows VS1): a script's and the brand's default. Rules:
app/languages.py."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import languages
from app.auth import current_user

router = APIRouter(prefix="/languages", tags=["languages"], dependencies=[Depends(current_user)])


class LanguageOut(BaseModel):
    id: str  # "es": what scripts.language and brands.default_language hold
    name: str  # "Spanish"
    on: bool  # editors can pick it (off until its sample test)


@router.get("", response_model=list[LanguageOut])
def list_languages():
    """English first. Editors see the Off ones too, greyed."""
    return [LanguageOut(id=k, name=n, on=on) for k, (n, on) in languages.LANGUAGES.items()]
