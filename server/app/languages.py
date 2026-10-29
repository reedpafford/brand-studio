"""Languages (flows VS1, Reed 2026-10-28): what a script can be written in. A fixed list; a
language is On for editors only once its sample test has passed (English alone today), and
switching one on is a change here. The owner may try an Off one, as with looks."""

from fastapi import HTTPException

from app.models.accounts import User

DEFAULT = "en"
LANGUAGES = {  # id -> (name, on)
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


def pick(user: User, language: str) -> str:
    """A language this person may write in: an editor only one that's on; the owner any."""
    name, on = LANGUAGES[check(language)]
    if not on and not user.is_owner:
        raise HTTPException(409, OFF.format(name))
    return language


def starting(language: str | None, owner: bool) -> str:
    """A new script's language from its brand's default: an Off (or unknown) one starts an
    editor's script in English, as an Off default look starts it on House."""
    name, on = LANGUAGES.get(language or "", ("", False))
    return language if name and (on or owner) else DEFAULT
