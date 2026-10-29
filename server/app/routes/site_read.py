"""Import from website (flows BR2), owner only: the price, the read, what it found, Save the
ticked ones (with Undo). Rules: app/site_read.py; the fetching: app/site_fetch.py."""

import hashlib
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

from app import filetypes, site_fetch
from app import site_read as sr
from app.advice import Said, SaidText
from app.credits import estimate
from app.db import get_db
from app.models.accounts import User
from app.models.brands import Brand
from app.models.files import StoredFile
from app.models.jobs import Job
from app.models.library import Kind, LibraryItem
from app.references import too_many_pixels
from app.routes import library
from app.routes.brands import _apply as apply_brand
from app.routes.brands import brand_owner, get_brand
from app.routes.clips import generation_on
from app.routes.jobs import JobOut, enqueue

router = APIRouter(prefix="/brands/{brand_id}/site-read", tags=["brands"])


class EstimateOut(BaseModel):
    credits: float  # "Read the site · about 3 credits"


class ReadIn(BaseModel):
    url: HttpUrl  # "Paste the brand's website"; http(s) only


class Product(BaseModel):
    name: str
    short_description: str


class Found(BaseModel):
    logo_url: str  # "" when none
    colours: list[str]
    products: list[Product]


class ReadOut(BaseModel):
    status: str  # reading | done | failed | empty | saved
    reason: SaidText  # failed / empty: the words to show
    found: Found
    have_colours: list[str]  # the brand's now: "Already in your colours", no tick


class SaveIn(BaseModel):
    logo: bool = False
    colours: list[str] = []  # the ticked ones, from `found`
    products: list[int] = Field(default=[], max_length=12)  # indexes into `found.products`


class SaveOut(BaseModel):
    colours_added: int
    logo: bool
    products_made: int
    products_filled: int  # an existing product's empty description, filled
    problems: Said  # e.g. "Couldn't get the logo from the site."


def _read(db: Session, brand: Brand, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if job is None or (job.input or {}).get("step") != "site_fetch" \
            or job.input.get("brand_id") != brand.id:  # fmt: skip
        raise HTTPException(404, "No such read.")
    return job


def _brand(db: Session, owner: User, brand_id: int) -> Brand:
    return get_brand(db, owner, brand_id)


@router.get("/estimate", response_model=EstimateOut)
def read_estimate(brand_id: int, owner: User = Depends(brand_owner),
                  db: Session = Depends(get_db)):  # fmt: skip
    _brand(db, owner, brand_id)
    return EstimateOut(credits=float(estimate(db, owner.workspace_id, sr.KIND, Decimal(1), {})))


@router.post("", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)])
def start_read(brand_id: int, body: ReadIn, owner: User = Depends(brand_owner),
               db: Session = Depends(get_db)):  # fmt: skip
    """Read the site: a free fetch, then the paid read only if the page had something."""
    brand = _brand(db, owner, brand_id)
    return enqueue(db, owner, "site_fetch", sr.fetch_input(brand, str(body.url)), units=0,
                   provider="local")  # fmt: skip


@router.get("/{job_id}", response_model=ReadOut)
def read_state(brand_id: int, job_id: int, owner: User = Depends(brand_owner),
               db: Session = Depends(get_db)):  # fmt: skip
    brand = _brand(db, owner, brand_id)
    return {**sr.state(db, brand, _read(db, brand, job_id)), "have_colours": brand.colours}


def _logo(db: Session, request: Request, owner: User, url: str) -> StoredFile:
    """The found logo, fetched now (only when ticked) with the same checks and caps."""
    settings = request.app.state.settings
    if settings.fake_providers:
        data, kind = sr.stand_in_logo(url)
    elif settings.site_read_real:
        data, kind, _ = site_fetch.fetch(url, cap=site_fetch.LOGO_BYTES)
    else:
        raise site_fetch.Refused("Reading websites is switched off.")
    if kind not in filetypes.ALLOWED_TYPES or not kind.startswith("image/") \
            or not filetypes.matches(kind, data[:16]) or too_many_pixels(data):  # fmt: skip
        raise site_fetch.Refused(sr.NO_LOGO)
    key = f"{owner.workspace_id}/{uuid.uuid4().hex}"
    request.app.state.storage.put(key, data)
    stored = StoredFile(workspace_id=owner.workspace_id, key=key, uploaded_by_id=owner.id,
                        filename=f"logo.{kind.split('/')[1]}", content_type=kind,
                        size=len(data), sha256=hashlib.sha256(data).hexdigest())  # fmt: skip
    db.add(stored)
    db.flush()
    return stored


@router.post("/{job_id}/save", response_model=SaveOut)
def save_ticked(brand_id: int, job_id: int, body: SaveIn, request: Request,
                owner: User = Depends(brand_owner), db: Session = Depends(get_db)):  # fmt: skip
    """Save the ticked ones, through the brand's own writes (BR1's rules). Colours join the
    brand's, never replace them; a product new to the brand is made, an existing one only
    gets an empty description filled. Undo: POST …/undo."""
    brand = _brand(db, owner, brand_id)
    fetch = _read(db, brand, job_id)
    now = sr.state(db, brand, fetch)
    if now["status"] == "saved":
        raise HTTPException(409, sr.SAVED)
    if now["status"] != "done":
        raise HTTPException(409, "There's nothing to save from this read.")
    found, problems = now["found"], []
    old_logo = brand.logo_file_id
    added = [c for c in dict.fromkeys(body.colours)
             if c in found["colours"] and c not in brand.colours]  # fmt: skip
    values: dict = {"colours": [*brand.colours, *added]} if added else {}
    if body.logo and found["logo_url"]:
        try:
            values["logo_file_id"] = _logo(db, request, owner, found["logo_url"]).id
        except site_fetch.Refused:
            problems.append(sr.NO_LOGO)
    if values:
        apply_brand(db, owner, brand, values)
    made, filled, have = [], [], sr.products(db, brand)
    for i in dict.fromkeys(body.products):
        if not 0 <= i < len(found["products"]):
            raise HTTPException(422, "Pick products from this read.")
        name, line = found["products"][i]["name"], found["products"][i]["short_description"]
        item = have.get(sr.key(name))
        if item is None:
            item = LibraryItem(workspace_id=owner.workspace_id, kind=Kind.prop)
            library._apply(db, owner, item, {"name": " ".join(name.split())[:120],
                                             "brand_ids": [brand.id],
                                             "short_description": line})  # fmt: skip
            db.add(item)
            db.flush()
            made.append(item.id)
            have[sr.key(name)] = item
        elif not item.short_description.strip() and line.strip():
            item.short_description = line
            filled.append([item.id, line])
    fetch.output = {**fetch.output, "saved": True,
                    "undo": {"colours": added, "made": made, "filled": filled,
                             "logo": [old_logo, values.get("logo_file_id")]}}  # fmt: skip
    db.commit()
    return SaveOut(
        colours_added=len(added),
        logo="logo_file_id" in values,
        products_made=len(made),
        products_filled=len(filled),
        problems=problems,
    )


@router.post("/{job_id}/undo", status_code=204)
def undo_save(brand_id: int, job_id: int, owner: User = Depends(brand_owner),
              db: Session = Depends(get_db)):  # fmt: skip
    """Undo Save: the colours it added taken out and its logo replaced by the one before
    (unless changed since), the products it made removed and the descriptions it filled
    cleared (unless edited since). The read can be saved again."""
    brand = _brand(db, owner, brand_id)
    fetch = _read(db, brand, job_id)
    undo = (fetch.output or {}).get("undo")
    if not undo:
        raise HTTPException(409, "There's nothing to undo.")
    # Only what Save did: an edit made since stays (a colour added, a logo changed)
    brand.colours = [c for c in brand.colours if c not in undo["colours"]]
    old, stored = undo["logo"]
    if stored is not None and brand.logo_file_id == stored:
        brand.logo_file_id = old
    for item_id in undo["made"]:
        if item := db.get(LibraryItem, item_id):
            item.archived = True
    for item_id, line in undo["filled"]:  # unless it was edited since
        if (item := db.get(LibraryItem, item_id)) and item.short_description == line:
            item.short_description = ""
    fetch.output = {k: v for k, v in fetch.output.items() if k not in ("saved", "undo")}
    db.commit()
