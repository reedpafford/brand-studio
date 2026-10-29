"""A look's sample (flows ST3, owner only): one still and one 5 s clip of the brand's hero in
the look, so the owner can see it before switching it on for editors. The hero is the
brand's default cast's first character; with none, the owner picks one of the brand's
characters, or the look's own sample character is used (its `## sample` section). One press
pays for both: the still, then the clip made from it (prepaid). The newest jobs say where it
is; the files are kept on the look's switch (look_switches.sample_still_id/_clip_id, n07)."""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import looks, prompts
from app.breakdown import video_model
from app.clip_takes import KEYS, LONG_SIDE, RESOLUTION
from app.credits import estimate
from app.images import image_job_input
from app.models.accounts import User
from app.models.brands import Brand
from app.models.jobs import Job, JobStatus
from app.models.library import LibraryItem
from app.models.looks import LookSwitch
from app.storyboard import image_model

STILL, CLIP = "look_sample", "look_sample_clip"
SECONDS, ASPECT = 5, "9:16"
WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)
STAND_IN = "A friendly adult in their thirties in one plain outfit in one clear colour"
NOT_THEIRS = "That character isn't one of this brand's."
ALREADY = "This look's sample is already being made."
HOUSE = "House is the default look: it needs no sample."
NO_STILL = "The sample's still didn't come back. Make a sample to try again."


def characters(db: Session, brand: Brand) -> list[LibraryItem]:
    """The brand's library characters, to pick the sample's person from."""
    rows = db.scalars(select(LibraryItem).where(LibraryItem.workspace_id == brand.workspace_id,
                                                LibraryItem.kind == "character",
                                                LibraryItem.archived.is_(False),
                                                LibraryItem.owner_project_id.is_(None))
                      .order_by(LibraryItem.id))  # fmt: skip
    return [c for c in rows if brand in c.brands]


def hero(db: Session, brand: Brand) -> LibraryItem | None:
    """The brand's default cast's first character, if it's still there."""
    mine = {c.id: c for c in characters(db, brand)}
    return next((mine[i] for i in brand.default_cast or [] if i in mine), None)


def _who(db: Session, brand: Brand, look_id: str, character_id: int | None):
    """(name, words, picture ids): a picked character, the hero, or the look's own one."""
    if character_id is not None:
        person = next((c for c in characters(db, brand) if c.id == character_id), None)
        if person is None:
            raise HTTPException(422, NOT_THEIRS)
    else:
        person = hero(db, brand)
    if person is None:
        words = prompts.style(look_id)["sections"].get("sample", "").strip() or STAND_IN
        return "the character", words, []
    pictures = [person.sheet_file_id] if person.sheet_file_id else person.image_file_ids[:1]
    return person.name, f"{person.name}, exactly as in [Image1]", pictures


def still_input(db: Session, brand: Brand, look_id: str, character_id: int | None) -> dict:
    name, words, pictures = _who(db, brand, look_id, character_id)
    look = prompts.style(look_id)["sections"]
    pose = "a calm, friendly portrait, looking into the camera, the whole figure in frame"
    prompt = f"{look.get('still_look', '').strip()}\n{words}: {pose}. No text on screen."
    job = image_job_input(image_model(), prompt, ASPECT, characters=pictures)
    return {**job, "step": STILL, "look_id": look_id, "brand_id": brand.id, "name": name}


def clip_input(look_id: str, brand_id: int, still_id: int, name: str) -> dict:
    style = prompts.style(look_id)["sections"].get("clip_style", "").strip()
    prompt = (f"{style}. [Image1] is the first frame: {name} turns to the camera and smiles, "
              "a slow push-in. No one speaks; soft room sound only.")  # fmt: skip
    return {"step": CLIP, "look_id": look_id, "brand_id": brand_id, "model": video_model().id,
            "fit_images_to": LONG_SIDE[RESOLUTION], "files": {KEYS["image"]: [still_id]},
            "input": {"prompt": prompt, "duration": SECONDS, "resolution": RESOLUTION,
                      "aspect_ratio": ASPECT, "generate_audio": True}}  # fmt: skip


def price(db: Session, ws: int) -> Decimal:
    """The still and the 5 s clip, as one press."""
    still = image_job_input(image_model(), "", ASPECT)
    clip = clip_input(looks.DEFAULT, 0, 0, "")
    return estimate(db, ws, "image", Decimal(1), still) + estimate(db, ws, "video", SECONDS, clip)


def newest(db: Session, ws: int, look_id: str) -> Job | None:
    rows = db.scalars(select(Job).where(Job.workspace_id == ws,
                                        Job.input["step"].as_string().in_((STILL, CLIP)))
                      .order_by(Job.id.desc()))  # fmt: skip
    return next((j for j in rows if j.input.get("look_id") == look_id), None)


def state(db: Session, ws: int, look_id: str) -> tuple[str, str | None]:
    """(none | making | ready | failed, a plain reason)."""
    job = newest(db, ws, look_id)
    row = looks.switch(db, ws, look_id)
    if job is None:
        return ("ready", None) if row and row.sample_clip_id else ("none", None)
    if job.input.get("no_still"):  # finished with no picture: never "making" for ever
        return "failed", NO_STILL
    if job.input.get("clip_refused"):
        return "failed", job.input["clip_refused"]
    if job.status in WAITING or (job.status == JobStatus.succeeded and job.input["step"] == STILL):
        return "making", None
    if job.status == JobStatus.succeeded:
        return "ready", None
    return "failed", job.error or "The sample didn't finish. Nothing was charged for it."


def _failed_clip(db: Session, ws: int, look_id: str) -> dict | None:
    """A clip that didn't finish (or was refused) after its still was kept: the clip's job
    input to make again from that still, or None."""
    job, row = newest(db, ws, look_id), looks.switch(db, ws, look_id)
    if not (job and row and row.sample_still_id) or state(db, ws, look_id)[0] != "failed":
        return None
    if job.input["step"] == CLIP:
        return {k: v for k, v in job.input.items() if k != "clip_refused"}
    if job.input.get("clip_refused"):  # refused before it started: from the still's job
        return clip_input(look_id, job.input["brand_id"], row.sample_still_id, job.input["name"])
    return None


def retry_price(db: Session, ws: int, look_id: str) -> Decimal:
    """Make a sample's price now: only the clip when its still is kept, else both."""
    if again := _failed_clip(db, ws, look_id):
        return estimate(db, ws, "video", SECONDS, again)
    return price(db, ws)


def make(db: Session, owner: User, look_id: str, brand: Brand, character_id: int | None) -> None:
    """The still now, checked with the clip's price too (`hold`); the clip follows it. After
    a clip that didn't finish, only the clip again, from the kept still (as Clips' Try again)."""
    from app.routes.jobs import enqueue

    if look_id == looks.DEFAULT:
        raise HTTPException(409, HOUSE)
    if state(db, owner.workspace_id, look_id)[0] == "making":
        raise HTTPException(409, ALREADY)
    if again := _failed_clip(db, owner.workspace_id, look_id):
        enqueue(db, owner, "video", again, units=SECONDS, provider="replicate")
        return
    job = still_input(db, brand, look_id, character_id)
    clip = estimate(db, owner.workspace_id, "video", SECONDS, clip_input(look_id, 0, 0, ""))
    enqueue(db, owner, "image", job, provider="replicate", hold=clip)


def save_still(db: Session, job: Job) -> None:
    """The still is in: it's the sample's (the old clip goes with the old still), then the
    clip is made from it, already paid for."""
    from app.routes.jobs import enqueue

    file_ids = (job.output or {}).get("file_ids") or []
    if not file_ids:  # a still with no picture: it says so, and Make a sample makes both
        job.input = {**job.input, "no_still": True}
        return
    ws, look_id = job.workspace_id, job.input["look_id"]
    row = looks.switch(db, ws, look_id)
    if row is None:
        row = LookSwitch(workspace_id=ws, look_id=look_id)
        db.add(row)
    row.sample_still_id, row.sample_clip_id = file_ids[0], None
    owner = db.get(User, job.created_by_id)
    db.commit()  # a refusal of the clip rolls back: never lose the still with it
    try:
        enqueue(db, owner, "video", clip_input(look_id, job.input["brand_id"], file_ids[0],
                                                job.input["name"]),
                units=SECONDS, provider="replicate", prepaid=True)  # fmt: skip
    except HTTPException as exc:  # the still stays; Make a sample again makes both
        job.input = {**job.input, "clip_refused": exc.detail}


def save_clip(db: Session, job: Job) -> None:
    file_ids = (job.output or {}).get("file_ids") or []
    row = looks.switch(db, job.workspace_id, job.input["look_id"])
    if row and file_ids:
        row.sample_clip_id = file_ids[0]
