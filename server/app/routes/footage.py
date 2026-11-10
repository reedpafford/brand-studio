"""A brand's Footage tab (Reed, 9 Nov, app/footage.py): its real clips, added once through
Media's checks, each with what it shows and which product. Left blank, the words are one AI
look at two of its frames (a picture check's price, said before the press); typed, they're
the person's own. Anyone with the brand adds, changes and deletes them (Undo brings one back),
as in the rest of the library."""

import hashlib
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import footage
from app.auth import current_user
from app.credits import estimate, price
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.brands import Brand
from app.models.files import MediaUpload, StoredFile
from app.models.jobs import Job, JobStatus
from app.routes.brands import get_brand
from app.routes.library import PriceOut, usd
from app.routes.media import store

router = APIRouter(prefix="/brands/{brand_id}/footage", tags=["footage"])
GONE = "That clip is no longer in this brand's footage."
WORDS = 500  # characters a description keeps


class FootageOut(BaseModel):
    id: int
    file_id: int
    thumb_file_id: int | None  # its first frame
    seconds: float
    description: str  # "" while it's described, or when it couldn't be
    product_id: int | None
    describing: bool  # the AI's words are being written
    note: str = ""  # why they aren't in: refused, waiting for the owner's OK, or failed


class FootageIn(BaseModel):
    description: str | None = None
    product_id: int | None = None
    no_product: bool = False  # clear its product


def _out(db: Session, row: MediaUpload) -> FootageOut:
    from app.routes.jobs import HELD

    job = db.get(Job, row.describe_job_id) if row.describe_job_id else None
    waiting = job is not None and job.status in (JobStatus.queued, JobStatus.running)
    held = job is not None and job.status == JobStatus.needs_owner_approval
    note = f"The AI’s description waits for the owner’s OK: {job.input.get(HELD)}" if held else ""
    return FootageOut(id=row.id, file_id=row.file_id, seconds=row.seconds or 0,
                      thumb_file_id=(row.frame_file_ids or [None])[0],
                      description=row.description, product_id=row.product_id,
                      describing=waiting, note=note or row.describe_note)  # fmt: skip


def _row(db: Session, user: User, brand_id: int, footage_id: int, removed=False) -> MediaUpload:
    get_brand(db, user, brand_id)
    row = db.get(MediaUpload, footage_id)
    off = row is not None and (row.removed_at is not None) != removed
    if not row or row.brand_id != brand_id or not row.footage or off:
        raise HTTPException(404, GONE)
    return row


def _product(db: Session, brand_id: int, product_id: int | None) -> int | None:
    if product_id is not None and product_id not in {p.id for p in footage.products(db, brand_id)}:
        raise HTTPException(422, "Pick one of this brand's products.")
    return product_id


def _describe_price(db: Session, workspace_id: int) -> Decimal:
    return estimate(db, workspace_id, footage.KIND, Decimal(1))


@router.get("", response_model=list[FootageOut])
def list_footage(brand_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    get_brand(db, user, brand_id)
    return [_out(db, r) for r in footage.live(db, brand_id)]


@router.get("/price", response_model=PriceOut)
def describe_price(brand_id: int, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):  # fmt: skip
    """What the AI description of one clip costs at most, said before a clip is added blank."""
    get_brand(db, user, brand_id)
    most = _describe_price(db, user.workspace_id)  # the owner's dollars from it, not a whole credit
    return PriceOut(credits=price(most), usd=usd(user, float(most)))


@router.post("", response_model=FootageOut, status_code=201)
def add_footage(
    brand_id: int,
    upload: UploadFile,
    request: Request,
    description: str = Form(""),
    product_id: int | None = Form(None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """A real clip added once (Media's checks: a clip of up to 3 minutes). Its two frames are
    kept (its thumbnail, and what the AI and the director see); with no words, the AI
    describes it."""
    row, data = store(db, user, brand_id, upload, request, clip=True)
    row.footage, row.description = True, description.strip()[:WORDS]
    row.product_id = _product(db, brand_id, product_id)
    ids = []
    for n, jpeg in enumerate(footage.frames(data)):
        key = f"{user.workspace_id}/{uuid.uuid4().hex}"
        request.app.state.storage.put(key, jpeg)
        frame = StoredFile(workspace_id=user.workspace_id, key=key, size=len(jpeg),
                           filename=f"frame-{n + 1}.jpg", content_type="image/jpeg",
                           sha256=hashlib.sha256(jpeg).hexdigest(),
                           uploaded_by_id=user.id)  # fmt: skip
        db.add(frame)
        db.flush()
        ids.append(frame.id)
    row.frame_file_ids = ids
    db.commit()
    if not row.description:
        _ask(db, user, row)
    return _out(db, row)


def _ask(db: Session, user: User, row: MediaUpload) -> None:
    """The AI's one look (a picture check); refused (the test site's budget), the clip stays
    and its words are the person's to type."""
    from app.routes.jobs import enqueue

    data = footage.describe_input(db, row, db.get(Brand, row.brand_id))
    try:
        job = enqueue(db, user, footage.KIND, data, provider="claude")
    except HTTPException as no:  # the card says why; its words are the person's to type
        db.rollback()
        row.describe_note = f"The AI didn’t describe it: {no.detail} Edit it to say what it shows."
        db.commit()
        return
    row.describe_job_id = job.id
    db.commit()


@router.patch("/{footage_id}", response_model=FootageOut)
def change_footage(brand_id: int, footage_id: int, body: FootageIn,
                   user: User = Depends(current_user), db: Session = Depends(get_db)):  # fmt: skip
    """Its words or its product, as the person sets them (the AI's are never put back)."""
    row = _row(db, user, brand_id, footage_id)
    if body.description is not None:
        row.description, row.describe_job_id = body.description.strip()[:WORDS], None
        row.describe_note = ""
    if body.product_id is not None or body.no_product:
        row.product_id = None if body.no_product else _product(db, brand_id, body.product_id)
    db.commit()
    return _out(db, row)


@router.delete("/{footage_id}", status_code=204)
def delete_footage(brand_id: int, footage_id: int, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> None:  # fmt: skip
    """Off the tab, Media and the director's list (Undo: …/restore). A video already cut
    from it keeps its take."""
    _row(db, user, brand_id, footage_id).removed_at = utcnow()
    db.commit()


@router.post("/{footage_id}/restore", response_model=FootageOut)
def restore_footage(brand_id: int, footage_id: int, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):  # fmt: skip
    row = _row(db, user, brand_id, footage_id, removed=True)
    row.removed_at = None
    db.commit()
    return _out(db, row)
