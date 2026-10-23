"""Quick clips: one video from a prompt, inside a brand, checked against the model's limits.

The brand's default screens are attached automatically when the prompt mentions one of
their moments (e.g. fomo + "trading"). Files are passed by id; the worker sends them to the
provider when the job starts."""

import re
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.catalogue import CatalogueModel, get_model
from app.credits import estimate, needs_approval
from app.db import get_db
from app.models.accounts import User
from app.models.brands import Brand, BrandScreen
from app.models.jobs import Job
from app.models.library import Kind
from app.routes.brands import get_brand
from app.routes.files import get_file
from app.routes.jobs import JobOut, enqueue
from app.routes.library import get_item

router = APIRouter(prefix="/clips", tags=["clips"])
Prompt = Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=4000)]


class ClipIn(BaseModel):
    brand_id: int
    model_id: str = "seedance-2.5"
    prompt: Prompt
    aspect_ratio: str = "9:16"
    duration: int = Field(5, description="Seconds")
    resolution: str = "480p"
    generate_audio: bool = True
    character_ids: list[int] = []
    place_ids: list[int] = []
    prop_ids: list[int] = []
    screen_ids: list[int] = []
    file_ids: list[int] = []  # extra images, videos or audio
    skip_screen_ids: list[int] = []  # auto-added screens the editor removed: don't re-add


class EstimateOut(BaseModel):
    credits: float
    needs_owner_approval: bool
    reason: str  # plain words for the UI when approval is needed, else ""
    auto_screen_ids: list[int]  # brand screens added because the prompt mentions their moment
    reference_images: int
    reference_videos: int
    reference_audios: int


class _Plan(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    model: CatalogueModel
    files: dict[str, list[int]]
    auto_screen_ids: list[int]
    credits: Decimal


def _mentions(prompt: str, moment: str) -> bool:
    words = re.escape(moment.replace("-", " ")).replace(r"\ ", r"[\s-]+")
    return re.search(rf"\b{words}\b", prompt, re.IGNORECASE) is not None


def _plan(db: Session, user: User, body: ClipIn) -> _Plan:
    """Check everything against the catalogue and the brand; plain-language errors (422)."""
    brand = get_brand(db, user, body.brand_id)
    model = get_model(body.model_id)
    if not model or model.kind != "video":
        raise HTTPException(422, "Pick a video model.")
    if body.resolution not in model.resolutions:
        raise HTTPException(422, f"{model.name} offers {', '.join(model.resolutions)}.")
    if body.aspect_ratio not in model.aspect_ratios:
        raise HTTPException(422, f"{model.name} doesn't do {body.aspect_ratio}.")
    lo, hi = model.duration.min, model.duration.max
    if not lo <= body.duration <= hi:
        raise HTTPException(422, f"{model.name} makes clips from {lo} to {hi} seconds.")

    images: list[int] = []
    for kind, ids in (
        (Kind.character, body.character_ids),
        (Kind.place, body.place_ids),
        (Kind.prop, body.prop_ids),
    ):
        for item_id in dict.fromkeys(ids):
            images += get_item(db, user, kind, item_id).image_file_ids
    screens = _brand_screens(db, brand)
    for screen_id in dict.fromkeys(body.screen_ids):
        if screen_id not in screens:
            raise HTTPException(404, "That screen isn't part of this brand.")
    auto = [
        s.id
        for s in screens.values()
        if s.id not in body.screen_ids
        and s.id not in body.skip_screen_ids
        and any(_mentions(body.prompt, m) for m in s.default_for)
    ]
    images += [screens[i].file_id for i in [*dict.fromkeys(body.screen_ids), *auto]]

    files = {"reference_images": [], "reference_videos": [], "reference_audios": []}
    for file_id in images + list(dict.fromkeys(body.file_ids)):
        stored = get_file(db, user, file_id)
        kind = stored.content_type.split("/")[0]
        files[
            {"image": "reference_images", "video": "reference_videos"}.get(kind, "reference_audios")
        ].append(file_id)
    files = {k: list(dict.fromkeys(v)) for k, v in files.items()}
    for key, limit, label in (
        ("reference_images", model.max_reference_images, "images"),
        ("reference_videos", model.max_reference_videos, "videos"),
        ("reference_audios", model.max_reference_audios, "audio clips"),
    ):
        if len(files[key]) > limit:
            raise HTTPException(
                422,
                f"{model.name} takes up to {limit} reference {label}; this has {len(files[key])}.",
            )
    if files["reference_audios"] and not (files["reference_images"] or files["reference_videos"]):
        raise HTTPException(422, "Audio references need at least one image or video with them.")
    credits = estimate(
        db, user.workspace_id, "video", Decimal(body.duration), _job_input(model, body, files)
    )
    return _Plan(model=model, files=files, auto_screen_ids=auto, credits=credits)


def _brand_screens(db: Session, brand: Brand) -> dict[int, BrandScreen]:
    rows = db.scalars(select(BrandScreen).where(BrandScreen.brand_id == brand.id))
    return {s.id: s for s in rows}


def _job_input(model: CatalogueModel, body: ClipIn, files: dict) -> dict:
    return {
        "model": model.id,
        "brand_id": body.brand_id,
        "input": {
            "prompt": body.prompt,
            "duration": body.duration,
            "resolution": body.resolution,
            "aspect_ratio": body.aspect_ratio,
            "generate_audio": body.generate_audio,
        },
        "files": {k: v for k, v in files.items() if v},  # sent as data when the job starts
        "request": body.model_dump(),  # the editor's original choices, for "Try again"
    }


@router.post("/estimate", response_model=EstimateOut)
def estimate_clip(body: ClipIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """What Generate would cost, and whether it would wait for the owner. Nothing is queued."""
    plan = _plan(db, user, body)
    held = needs_approval(db, user, None, plan.credits)
    return EstimateOut(
        credits=plan.credits,
        needs_owner_approval=held,
        reason="This goes past your weekly quick-clip allowance, so Reed will need to approve it."
        if held
        else "",
        auto_screen_ids=plan.auto_screen_ids,
        **{k: len(v) for k, v in plan.files.items()},
    )


@router.post("", response_model=JobOut, status_code=201)
def create_clip(body: ClipIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = _plan(db, user, body)
    return enqueue(
        db,
        user,
        "video",
        _job_input(plan.model, body, plan.files),
        units=body.duration,
        provider="replicate",
    )


@router.get("/{job_id}/request", response_model=ClipIn)
def clip_request(job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The full request a clip was made from (prompt, settings, brand pieces), for "Try again"
    and "Reuse prompt". Same visibility as the job itself: the caller's workspace."""
    job = db.get(Job, job_id)
    if not job or job.workspace_id != user.workspace_id or "request" not in job.input:
        raise HTTPException(404, "No such clip.")
    return job.input["request"]
