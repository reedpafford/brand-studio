"""The model catalogue: which models we offer, their limits, and what they cost.
Loaded once from `catalogue.json`. Editors get credits; dollars are owner-only."""

import json
from decimal import ROUND_HALF_UP, Decimal
from functools import cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.models.credits import USD_PER_CREDIT


class Duration(BaseModel):
    min: int
    max: int
    smart: bool = False  # provider can pick the length itself


class Price(BaseModel):
    unit: Literal["second", "image", "call", "song"]
    usd: dict[str, Decimal]  # per resolution ("any" when it doesn't matter)


class CatalogueModel(BaseModel):
    id: str
    name: str
    kind: Literal["video", "image", "watch", "text", "music"]
    provider_model: str
    provider_version: str
    default: bool = False
    duration: Duration | None = None
    resolutions: list[str] = []
    aspect_ratios: list[str] = []
    max_reference_images: int = 0
    max_reference_videos: int = 0
    max_reference_audios: int = 0
    max_reference_media_seconds: int = 0  # videos and audio each, added up (not together)
    recommended_reference_images: int = 0  # works best at or under this (0 = no advice)
    max_character_images: int = 0  # image models: people whose likeness is kept (0 = no limit)
    max_object_images: int = 0  # image models: objects whose likeness is kept (0 = not stated)
    first_frame: bool = False
    last_frame: bool = False
    audio: Literal["switch", "always"] | None = None
    price: Price
    price_source: str

    def usd_per_unit(self, resolution: str | None = None) -> Decimal:
        usd = self.price.usd
        if "any" in usd:
            return usd["any"]
        if resolution not in usd:
            raise ValueError(f"{self.name} has no {resolution!r} resolution.")
        return usd[resolution]

    def credits_per_unit(self, resolution: str | None = None) -> Decimal:
        credits = self.usd_per_unit(resolution) / USD_PER_CREDIT
        return credits.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@cache
def catalogue() -> dict[str, CatalogueModel]:
    data = json.loads((Path(__file__).parent / "catalogue.json").read_text())
    return {m["id"]: CatalogueModel.model_validate(m) for m in data["models"]}


def get_model(model_id: str) -> CatalogueModel | None:
    return catalogue().get(model_id)
