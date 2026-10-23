"""Quick clips: one video from a prompt, inside a brand, checked against the model's limits.

The brand's default screens are attached automatically when the prompt mentions one of
their moments (e.g. fomo + "trading"). The prompt sent to the model starts with one line per
picture ("[Image1] is Aiden.") and '@Name' becomes its [ImageN]; the editor's words stay as
written. Files are passed by id; the worker sends them (images scaled to the video's size)
when the job starts."""

import re
from datetime import timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.catalogue import CatalogueModel, get_model
from app.credits import estimate, needs_approval
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.brands import Brand, BrandScreen
from app.models.files import StoredFile
from app.models.jobs import Job
from app.models.library import Kind
from app.references import LONG_SIDE, bind_names, media_seconds, reference_lines
from app.routes.brands import get_brand
from app.routes.files import get_file
from app.routes.jobs import JobOut, enqueue
from app.routes.library import get_item
from app.storage import Storage

router = APIRouter(prefix="/clips", tags=["clips"])
OVER_ALLOWANCE = "This goes past your weekly quick-clip allowance, so the owner must approve it."
MAX_REFERENCE_BYTES = 100 * 1024 * 1024
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
    prompt: str  # what the model gets: reference lines + the editor's words
    exact: list[int]  # brand screens and props (products): never lossy
    credits: Decimal


def _mentions(prompt: str, moment: str) -> bool:
    words = re.escape(moment.replace("-", " ")).replace(r"\ ", r"[\s-]+")
    return re.search(rf"\b{words}\b", prompt, re.IGNORECASE) is not None


def _plan(db: Session, user: User, body: ClipIn, storage: Storage) -> _Plan:
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
    labels: list[tuple[str, str, list[int]]] = []  # (name, what it is, its file ids)
    exact: list[int] = []
    for kind, ids in (
        (Kind.character, body.character_ids),
        (Kind.place, body.place_ids),
        (Kind.prop, body.prop_ids),
    ):
        for item_id in dict.fromkeys(ids):
            item = get_item(db, user, kind, item_id)
            images += item.image_file_ids
            label = item.name if kind == Kind.character else f"the {item.name}"
            labels.append((item.name, label, item.image_file_ids))
            if kind == Kind.prop:
                exact += item.image_file_ids
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
    for i in [*dict.fromkeys(body.screen_ids), *auto]:
        s = screens[i]
        images.append(s.file_id)
        exact.append(s.file_id)
        labels.append((s.name, f'the {brand.name} "{s.name}" screen, shown exactly', [s.file_id]))

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
    total = sum(db.get(StoredFile, i).size for ids in files.values() for i in ids)
    if total > MAX_REFERENCE_BYTES:
        raise HTTPException(422, "The references are too big together (100 MB max). Use fewer.")
    if files["reference_audios"] and not (files["reference_images"] or files["reference_videos"]):
        raise HTTPException(422, "Audio references need at least one image or video with them.")
    _check_media_length(db, storage, model, files)
    prompt = _prompt(body.prompt, labels, files["reference_images"])
    credits = estimate(
        db,
        user.workspace_id,
        "video",
        Decimal(body.duration),
        _job_input(model, body, files, prompt, exact),
    )
    return _Plan(
        model=model, files=files, auto_screen_ids=auto, prompt=prompt, exact=exact, credits=credits
    )


def _prompt(text: str, labels: list[tuple[str, str, list[int]]], images: list[int]) -> str:
    """Say which picture is which (FIT row 4): Seedance only knows them by upload number."""
    number = {file_id: n for n, file_id in enumerate(images, 1)}
    found = [
        (name, label, sorted({number[f] for f in ids if f in number}))
        for name, label, ids in labels
    ]
    lines = [(label, numbers) for _, label, numbers in found if numbers]
    names = {name: numbers[0] for name, _, numbers in found if numbers}
    head = reference_lines(lines)
    return f"{head}\n{bind_names(text, names)}" if head else bind_names(text, names)


def _check_media_length(db: Session, storage: Storage, model: CatalogueModel, files) -> None:
    """Reference videos and audio each add up to at most the model's limit (FIT row 15)."""
    limit = model.max_reference_media_seconds
    for key, label in (("reference_videos", "videos"), ("reference_audios", "audio")):
        total = 0.0
        for file_id in files[key]:
            stored = db.get(StoredFile, file_id)
            seconds = media_seconds(storage.get(stored.key), stored.content_type)
            if seconds is None:
                raise HTTPException(
                    422, f"We couldn't tell how long {stored.filename} is. Try an MP4 or MP3."
                )
            total += seconds
        if limit and total > limit:
            raise HTTPException(
                422, f"Reference {label} add up to {total:.0f} s; {model.name} takes {limit} s."
            )


def _not_twice(db: Session, user: User, body: ClipIn) -> None:
    """Stop an accidental double press: the same request by the same person in 10 s."""
    since = utcnow() - timedelta(seconds=10)
    recent = db.scalars(select(Job).where(Job.created_by_id == user.id, Job.created_at >= since))
    request = body.model_dump()
    if any(job.input.get("request") == request for job in recent):
        raise HTTPException(409, "That clip was just started. Check your history.")


def _brand_screens(db: Session, brand: Brand) -> dict[int, BrandScreen]:
    rows = db.scalars(select(BrandScreen).where(BrandScreen.brand_id == brand.id))
    return {s.id: s for s in rows}


def _job_input(
    model: CatalogueModel, body: ClipIn, files: dict, prompt: str, exact: list[int]
) -> dict:
    return {
        "model": model.id,
        "brand_id": body.brand_id,
        "fit_images_to": LONG_SIDE[body.resolution],  # long side in px; never scaled up
        "exact_file_ids": sorted(set(exact)),  # kept lossless (Reed: screens show exactly)
        "input": {
            "prompt": prompt,
            "duration": body.duration,
            "resolution": body.resolution,
            "aspect_ratio": body.aspect_ratio,
            "generate_audio": body.generate_audio,
        },
        "files": {k: v for k, v in files.items() if v},  # sent as data when the job starts
        "request": body.model_dump(),  # the editor's original choices, for "Try again"
    }


@router.post("/estimate", response_model=EstimateOut)
def estimate_clip(
    body: ClipIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """What Generate would cost, and whether it would wait for the owner. Nothing is queued."""
    plan = _plan(db, user, body, request.app.state.storage)
    held = needs_approval(db, user, None, plan.credits)
    return EstimateOut(
        credits=plan.credits,
        needs_owner_approval=held,
        reason=OVER_ALLOWANCE if held else "",
        auto_screen_ids=plan.auto_screen_ids,
        **{k: len(v) for k, v in plan.files.items()},
    )


def generation_on(request: Request) -> None:
    """Paid generation can be switched off per server (BS_GENERATION_ENABLED)."""
    if not request.app.state.settings.generation_enabled:
        raise HTTPException(503, "Generation is switched off on this server.")


@router.post("", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)])
def create_clip(
    body: ClipIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    plan = _plan(db, user, body, request.app.state.storage)
    _not_twice(db, user, body)
    return enqueue(
        db,
        user,
        "video",
        _job_input(plan.model, body, plan.files, plan.prompt, plan.exact),
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
