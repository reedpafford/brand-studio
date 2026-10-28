"""Shared request/response field types."""

import re
from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, PlainSerializer, StringConstraints


def _email(value: str) -> str:
    value = value.strip().lower()
    local, _, domain = value.partition("@")
    if not local or "." not in domain or " " in value:
        raise ValueError("Not a valid email address.")
    return value


Email = Annotated[str, StringConstraints(max_length=254), AfterValidator(_email)]
Password = Annotated[str, StringConstraints(min_length=10, max_length=200)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


def _tag(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9-]{1,40}", value):
        raise ValueError("Use 1-40 lowercase letters, digits or dashes.")
    return value


Slug = Annotated[str, AfterValidator(_tag)]
Colour = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]
ShortText = Annotated[str, StringConstraints(max_length=200)]
LongText = Annotated[str, StringConstraints(max_length=5000)]
# A still's or clip's prompt: generated ones run past 5,000 (QA-Live, video #17's clip 1 was
# 5,070), and a saved prompt must always be editable.
PromptText = Annotated[str, StringConstraints(max_length=20_000)]


def slugify(text: str) -> str:
    return "-".join("".join(c if c.isalnum() else " " for c in text.lower()).split())[:120]


def _as_utc(value: datetime) -> datetime:
    # Times are stored as naive UTC (db.utcnow); say so, or browsers read them as local time.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


# Every datetime in a response: written with a "Z" so it means the same moment everywhere.
UtcTime = Annotated[datetime, PlainSerializer(_as_utc, return_type=datetime, when_used="json")]
