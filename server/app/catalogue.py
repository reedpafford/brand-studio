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
    unit: Literal["second", "image", "call", "thousand_characters"]
    usd: dict[str, Decimal]  # per resolution ("any" when it doesn't matter)
    gpu_usd_per_second: Decimal | None = None  # billed by GPU time: the real cost is its run time
    with_video: dict[str, Decimal] | None = None  # per resolution, when a reference video goes too


class Edit(BaseModel):
    """A model that edits a clip it's given (Omni 1.2's `video`): how long, and its price."""

    max_seconds: int
    price: Price
    price_source: str


class CatalogueModel(BaseModel):
    id: str
    name: str
    kind: Literal["video", "image", "watch", "text", "speech", "music", "sound", "voice"]
    provider_model: str
    provider_version: str
    default: bool = False
    offered: bool = True  # in the pickers; off for a model only a later step will use
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
    lip_sync: bool = False  # video models: a song slice sets the mouth (Sung shots, VS1)
    prompt_max: int = 0  # the longest prompt it takes, in characters (0: none stated)
    # about how long a clip prompt for it is written, in characters, well under any limit:
    # BytePlus keeps Seedance prompts under 600 words; Omni fills in detail itself (0: none)
    prompt_target: int = 0
    price: Price
    price_source: str
    edit: Edit | None = None

    @property
    def take_resolution(self) -> str:
        """What takes of this model are made and priced at: 480p when it has it, else the
        lowest it lists (P-Video: 720p)."""
        if "480p" in self.resolutions:
            return "480p"
        return min(self.resolutions, key=lambda r: int(r[:-1]) * (1000 if r.endswith("k") else 1))

    def usd_per_unit(self, resolution: str | None = None, edit: bool = False,
                     video_in: bool = False) -> Decimal:  # fmt: skip
        """`video_in`: a reference video goes with it (Seedance: a dearer rate)."""
        price = self.edit.price if edit and self.edit else self.price
        usd = price.with_video if video_in and price.with_video else price.usd
        if "any" in usd:
            return usd["any"]
        if resolution not in usd:
            raise ValueError(f"{self.name} has no {resolution!r} resolution.")
        return usd[resolution]

    def credits_per_unit(self, resolution: str | None = None, edit: bool = False,
                         video_in: bool = False) -> Decimal:  # fmt: skip
        credits = self.usd_per_unit(resolution, edit, video_in) / USD_PER_CREDIT
        return credits.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@cache
def catalogue() -> dict[str, CatalogueModel]:
    data = json.loads((Path(__file__).parent / "catalogue.json").read_text())
    return {m["id"]: CatalogueModel.model_validate(m) for m in data["models"]}


def get_model(model_id: str) -> CatalogueModel | None:
    return catalogue().get(model_id)
