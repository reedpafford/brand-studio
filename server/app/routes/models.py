"""The model catalogue for the UI picker, limits and the live cost on the Generate button.
Everyone sees credits; dollar prices are owner-only."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import current_user, owner_only
from app.catalogue import CatalogueModel, Duration, catalogue, get_model
from app.models.accounts import User

router = APIRouter(prefix="/models", tags=["models"])

_PUBLIC = set(CatalogueModel.model_fields) - {"price", "price_source", "provider_version"}


class ModelOut(BaseModel):
    """A catalogue entry without dollars: `credits_per_unit` is by resolution."""

    id: str
    name: str
    kind: str
    provider_model: str
    default: bool
    duration: Duration | None
    resolutions: list[str]
    aspect_ratios: list[str]
    max_reference_images: int
    max_reference_videos: int
    max_reference_audios: int
    max_reference_media_seconds: int
    recommended_reference_images: int
    max_character_images: int
    max_object_images: int
    first_frame: bool
    last_frame: bool
    audio: str | None
    unit: str
    credits_per_unit: dict[str, float]
    lip_sync: bool = False  # video models: false shows "No lip-sync" (VS1)


class ModelPriceOut(BaseModel):
    id: str
    unit: str
    price_per_unit_usd: dict[str, Decimal]
    price_source: str


def _public(model: CatalogueModel) -> dict:
    return {
        **model.model_dump(include=_PUBLIC),
        "unit": model.price.unit,
        "credits_per_unit": {r: float(model.credits_per_unit(r)) for r in model.price.usd},
    }


@router.get("", response_model=list[ModelOut])
def list_models(kind: str | None = None, user: User = Depends(current_user)):
    return [_public(m) for m in catalogue().values() if kind is None or m.kind == kind]


@router.get("/prices", response_model=list[ModelPriceOut])
def list_prices(owner: User = Depends(owner_only)):
    return [
        ModelPriceOut(
            id=m.id,
            unit=m.price.unit,
            price_per_unit_usd=m.price.usd,
            price_source=m.price_source,
        )
        for m in catalogue().values()
    ]


@router.get("/{model_id}", response_model=ModelOut)
def read_model(model_id: str, user: User = Depends(current_user)):
    model = get_model(model_id)
    if not model:
        raise HTTPException(404, "No such model.")
    return _public(model)
