"""Shared request/response field types."""

from typing import Annotated

from pydantic import AfterValidator, StringConstraints


def _email(value: str) -> str:
    value = value.strip().lower()
    local, _, domain = value.partition("@")
    if not local or "." not in domain or " " in value:
        raise ValueError("Not a valid email address.")
    return value


Email = Annotated[str, StringConstraints(max_length=254), AfterValidator(_email)]
Password = Annotated[str, StringConstraints(min_length=10, max_length=200)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
