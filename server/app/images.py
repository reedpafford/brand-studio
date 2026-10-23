"""Nano Banana jobs (storyboard frames, character sheets): the input we send, built in one
place so the settings FIT.md rows 5, 6 and 24 ask for are never left to a default."""

from collections.abc import Sequence

from fastapi import HTTPException

from app.catalogue import CatalogueModel


def image_job_input(
    model: CatalogueModel,
    prompt: str,
    aspect_ratio: str,
    *,
    characters: Sequence[int] = (),
    objects: Sequence[int] = (),
    resolution: str = "1K",
) -> dict:
    """Job input for an image model. Always sends `aspect_ratio` (the default follows the
    first reference's shape) and never `allow_fallback_model` (another model can't hold
    brand screens exactly). Reference files go by id, characters first."""
    if model.kind != "image":
        raise ValueError(f"{model.id} isn't an image model.")
    if aspect_ratio not in model.aspect_ratios or aspect_ratio == "match_input_image":
        raise HTTPException(422, f"{model.name} doesn't do {aspect_ratio}.")
    for ids, limit, label in (
        (characters, model.max_character_images, "character sheets"),
        (objects, model.max_object_images, "other references"),
        ([*characters, *objects], model.max_reference_images, "references"),
    ):
        if limit and len(ids) > limit:
            raise HTTPException(
                422, f"{model.name} keeps likeness for up to {limit} {label}; this has {len(ids)}."
            )
    files = [*characters, *objects]
    return {
        "model": model.id,
        "input": {"prompt": prompt, "aspect_ratio": aspect_ratio, "resolution": resolution},
        "files": {"image_input": files} if files else {},
    }


def image_model_block(model: CatalogueModel, aspect_ratio: str) -> str:
    """The <image_model> part of the storyboard prompt."""
    return (
        f"<image_model>\nname: {model.name}\nmax reference images: {model.max_reference_images}\n"
        f"max character sheets: {model.max_character_images}\n"
        f"max other references: {model.max_object_images or model.max_reference_images}\n"
        f"aspect: {aspect_ratio}\n</image_model>"
    )
