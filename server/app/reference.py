"""A reference reel's breakdown, stored on a project for "adapt this reel" drafts. The shape
is docs/references/*/BREAKDOWN.json; only the parts the prompts use are kept."""

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

Text = Field(max_length=2000)


class Hook(BaseModel):
    seconds: float = Field(ge=0)
    mechanic: str = Text


class Beat(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    summary: str = Text
    emotion: str = Text


class RefShot(BaseModel):
    n: int
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    framing: str = Text
    camera: str = Text
    action: str = Text
    emotion: str = Text
    speaker: str | None = None
    line: str | None = Field(None, max_length=2000)


class ReferenceBreakdown(BaseModel):
    model_config = ConfigDict(extra="ignore")
    logline: str = Text
    duration_seconds: float = Field(gt=0, le=600)
    hook: Hook
    beats: list[Beat] = Field(max_length=100)
    shots: list[RefShot] = Field(min_length=1, max_length=500)


def checked(value: dict) -> dict:
    """The breakdown trimmed to what we use, or a plain 422 naming the first problem."""
    try:
        return ReferenceBreakdown.model_validate(value).model_dump()
    except ValidationError as exc:
        error = exc.errors()[0]
        where = ".".join(str(p) for p in error["loc"]) or "it"
        raise HTTPException(
            422, f"The reference breakdown doesn't fit: {where}: {error['msg']}."
        ) from None
