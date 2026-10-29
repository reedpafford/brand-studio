"""Languages (flows VS1, Reed 2026-10-28): what a script can be written in. A fixed list; a
language is On for editors only once the owner switches it on, and that needs its sample
test read and approved first (app/language_samples.py). With no switch, the list's own `on`
applies (English alone). The owner may try an Off one, as with looks."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accounts import User
from app.models.languages import LanguageSwitch

DEFAULT = "en"
LANGUAGES = {  # id -> (name, on with no switch)
    "en": ("English", True),
    "es": ("Spanish", False),
    "fr": ("French", False),
    "de": ("German", False),
    "pt": ("Portuguese", False),
    "it": ("Italian", False),
    "nl": ("Dutch", False),
}
UNKNOWN = "There's no such language."
OFF = "{} is off for editors until its sample test. Pick a language that's on."


def check(language: str) -> str:
    """A language on the list (422 otherwise)."""
    if language not in LANGUAGES:
        raise HTTPException(422, UNKNOWN)
    return language


def name(language: str) -> str:
    return LANGUAGES[check(language)][0]


def _mine(workspace_id: int, language: str):
    return LanguageSwitch.workspace_id == workspace_id, LanguageSwitch.language_id == language


def switch(db: Session, workspace_id: int, language: str) -> LanguageSwitch | None:
    return db.scalar(select(LanguageSwitch).where(*_mine(workspace_id, language)))


def is_on(db, workspace_id: int, language: str) -> bool:
    """`db` is a session or a connection (a new script's insert reads it too)."""
    on = db.scalar(select(LanguageSwitch.on).where(*_mine(workspace_id, language)))
    return LANGUAGES[language][1] if on is None else on


def pick(db: Session, user: User, language: str) -> str:
    """A language this person may write in: an editor only one that's on; the owner any."""
    check(language)
    if not user.is_owner and not is_on(db, user.workspace_id, language):
        raise HTTPException(409, OFF.format(name(language)))
    return language


def starting(db, workspace_id: int, language: str | None, owner: bool) -> str:
    """A new script's language from its brand's default: an Off (or unknown) one starts an
    editor's script in English, as an Off default look starts it on House."""
    if language not in LANGUAGES:
        return DEFAULT
    return language if owner or is_on(db, workspace_id, language) else DEFAULT
