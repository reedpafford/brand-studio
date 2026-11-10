"""A brand's Footage tab (Reed, 9 Nov, app/footage.py): its real clips, added once through
Media's checks, each with what it shows and which product. Left blank, the words are one AI
look at two of its frames (a picture check's price, said before the press); typed, they're
the person's own. Anyone with the brand adds, changes and deletes them (Undo brings one back),
as in the rest of the library, and files them in the tab's own folders (Reed, 10 Nov: the
folders' calls, app/folders.py, with `footage`). A clip of another company's product is marked
a competitor's (Reed, 10 Nov: `competitor`): never shown as the brand's own."""

import hashlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import folders, footage
from app.auth import current_user, owner_only
from app.credits import estimate, price
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.brands import Brand
from app.models.files import MediaUpload, StoredFile
from app.models.jobs import Job, JobStatus, Usage
from app.routes.brands import get_brand
from app.routes.library import PriceOut, usd
from app.routes.media import store

router = APIRouter(prefix="/brands/{brand_id}/footage", tags=["footage"])
GONE = "That clip is no longer in this brand's footage."
WORDS = 500  # characters a description keeps
MARKED = ("Marked a competitor’s product. Edit it to say what it shows, without your brand’s "
          "name.")  # fmt: skip


class FootageOut(BaseModel):
    id: int
    file_id: int
    thumb_file_id: int | None  # its first frame
    seconds: float
    description: str  # "" while it's described, or when it couldn't be
    product_id: int | None
    describing: bool  # the AI's words are being written
    note: str = ""  # why they aren't in: refused, waiting for the owner's OK, or failed
    folder_id: int | None = None  # its footage folder (POST /folders/file, kind footage); null: top
    folder: str = ""  # where that is: "Product shots/Close-ups"
    competitor: bool = False  # another company's product: never shown as the brand's own


class FootageIn(BaseModel):
    description: str | None = None
    product_id: int | None = None
    no_product: bool = False  # clear its product
    competitor: bool | None = None  # another company's product (a competitor's has none of ours)


def _out(db: Session, row: MediaUpload) -> FootageOut:
    from app.routes.jobs import HELD

    job = db.get(Job, row.describe_job_id) if row.describe_job_id else None
    waiting = job is not None and job.status in (JobStatus.queued, JobStatus.running)
    held = job is not None and job.status == JobStatus.needs_owner_approval
    note = f"The AI’s description waits for the owner’s OK: {job.input.get(HELD)}" if held else ""
    folder_id = row.live_folder_id
    return FootageOut(id=row.id, file_id=row.file_id, seconds=row.seconds or 0,
                      thumb_file_id=(row.frame_file_ids or [None])[0],
                      description=row.description, product_id=row.product_id,
                      describing=waiting, note=note or row.describe_note,
                      folder_id=folder_id, folder=folders.path(db, folder_id),
                      competitor=row.competitor)  # fmt: skip


def _row(db: Session, user: User, brand_id: int, footage_id: int, removed=False) -> MediaUpload:
    get_brand(db, user, brand_id)
    row = db.get(MediaUpload, footage_id)
    off = row is not None and (row.removed_at is not None) != removed
    if not row or row.brand_id != brand_id or not row.footage or off:
        raise HTTPException(404, GONE)
    return row


def _product(db: Session, brand_id: int, product_id: int | None, name: str = "") -> int | None:
    """One of the brand's products, by its id or its name (any case)."""
    have = footage.products(db, brand_id)
    if name.strip():
        product_id = next((p.id for p in have if p.name.strip().lower() == name.strip().lower()),
                          0)  # fmt: skip
    if product_id is not None and product_id not in {p.id for p in have}:
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


class Spent(BaseModel):
    id: int  # the clip
    usd: float  # its AI description's real cost
    estimated: bool  # the provider didn't say: worked out from its credits


class SpendOut(BaseModel):
    usd: float  # the running total
    clips: list[Spent]


@router.get("/spend", response_model=SpendOut)
def describe_spend(brand_id: int, since: datetime | None = None, user: User = Depends(owner_only),
                   db: Session = Depends(get_db)):  # fmt: skip
    """What each AI description of the brand's footage really cost, and the total (owner only,
    like every dollar): a bulk upload reads its running total. `since`: those asked from then.
    One still being written isn't in yet."""
    get_brand(db, user, brand_id)
    rows = (select(Job.input["media_upload_id"].as_integer(), Usage.cost_usd, Usage.estimated)
            .join(Usage, Usage.job_id == Job.id)
            .where(Job.brand_id == brand_id, Job.input["step"].as_string() == footage.STEP)
            .order_by(Job.id))  # fmt: skip
    if since is not None:
        utc = since.astimezone(UTC).replace(tzinfo=None) if since.tzinfo else since
        rows = rows.where(Job.created_at >= utc)
    each: dict[int, Spent] = {}
    for clip, cost, estimated in db.execute(rows):
        one = each.setdefault(clip, Spent(id=clip, usd=0, estimated=False))
        one.usd, one.estimated = one.usd + float(cost), one.estimated or estimated
    return SpendOut(usd=round(sum(c.usd for c in each.values()), 4), clips=list(each.values()))


@router.post("", response_model=FootageOut, status_code=201)
def add_footage(
    brand_id: int,
    upload: UploadFile,
    request: Request,
    description: str = Form(""),
    product_id: int | None = Form(None),
    product: str = Form(""),  # or its name: "PalaceGuard"
    folder: str = Form(""),  # "Product shots/Close-ups": made where missing; "": the top
    ai_describe: bool = Form(True),  # False: never the paid AI description, even with no words
    competitor: bool = Form(False),  # True: another company's product, never shown as ours
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """A real clip added once (Media's checks: a clip of up to 3 minutes), in its footage
    folder. Its two frames are kept (its thumbnail, and what the AI and the director see);
    with no words, the AI describes it, unless `ai_describe` is off (a bulk upload that writes
    its own words). `competitor`: a competitor's product, of none of the brand's."""
    get_brand(db, user, brand_id)
    product_id = _product(db, brand_id, product_id, product)  # both before the file is stored
    folder_id = folders.made(db, user, brand_id, folder)
    row, data = store(db, user, brand_id, upload, request, clip=True)
    row.footage, row.description = True, description.strip()[:WORDS]
    row.product_id, row.folder_id = None if competitor else product_id, folder_id
    row.competitor = competitor
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
    if not row.description and ai_describe:
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
    """Its words, its product or whether it's a competitor's, as the person sets them (the AI's
    words are never put back). A competitor's clip is of none of the brand's products; marked
    one later with no new words, its old ones go (they may name the brand's product, QA on
    #1518), and the director skips it until it's described again."""
    row = _row(db, user, brand_id, footage_id)
    if body.competitor and not row.competitor and body.description is None:
        row.description, row.describe_job_id = "", None
        row.describe_note = MARKED
    if body.description is not None:
        row.description, row.describe_job_id = body.description.strip()[:WORDS], None
        row.describe_note = ""
    if body.product_id is not None or body.no_product:
        row.product_id = None if body.no_product else _product(db, brand_id, body.product_id)
    if body.competitor is not None:
        row.competitor = body.competitor
    if row.competitor:
        row.product_id = None
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
