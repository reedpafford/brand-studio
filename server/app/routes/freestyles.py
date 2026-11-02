"""Freestyle (Reed's v4): a video from a pasted script, a type, a look, a shape and an optional
brand, changed by chatting. It replaces Quick clip. An editor's every send (the first and each
change) waits for the owner before anything is spent; the owner's own run straight away. Not
charged to any video's budget, never gated by the Quick clip week; each job carries its
freestyle (`FREESTYLE`) for Usage. One clip works now: a single take, no plan or cut. The
director-run types (dialogue, song, narrated) come next."""

import math
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import looks, prompts
from app.auth import current_user
from app.catalogue import get_model
from app.credits import FREESTYLE, WAIT_OK, estimate
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.freestyles import Freestyle
from app.models.jobs import Job, JobStatus
from app.references import LONG_SIDE
from app.routes.brands import get_brand
from app.routes.clips import generation_on
from app.routes.jobs import DECLINE, enqueue, stop_jobs

router = APIRouter(prefix="/freestyles", tags=["freestyles"])
Type = Literal["dialogue", "song", "narrated", "one_clip"]
Shape = Literal["9:16", "1:1", "16:9"]
Status = Literal["waiting", "working", "delivered", "declined", "stopped", "withdrawn", "failed"]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
Change = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
MODEL, RESOLUTION = "seedance-2.5", "480p"  # Quick clip's defaults
NOT_YET = "Dialogue, Song and Narrated are coming next; One clip works now."
HELD = f"{WAIT_OK}every freestyle send is checked first."
BUSY = "Wait for the last send to finish, or stop it."
NONE = "No such freestyle."
WITHDRAWN = "withdrawn"  # in a job's input: its maker took it back before the owner's OK


class FreestyleIn(BaseModel):
    type: Type
    look: str
    shape: Shape
    brand_id: int | None = None
    text: Text


class MessageIn(BaseModel):
    text: Change


class TitleIn(BaseModel):
    title: Title


class FreestyleItem(BaseModel):
    """One line of the thread, the same shape as a video's director thread."""

    id: str  # m{n} for a message, t{job id} for a move: stable across reads
    kind: Literal["message", "move"]
    at: datetime
    who: str
    text: str
    status: Literal["held", "queued", "running", "refused", "done"] | None


class FreestyleRow(BaseModel):
    id: int
    title: str
    type: Type
    status: Status
    created_at: datetime
    created_by_name: str


class FreestyleOut(FreestyleRow):
    look: str
    shape: Shape
    brand_id: int | None
    credits: float  # everything asked so far that wasn't declined, withdrawn or stopped unstarted
    file_id: int | None  # the delivered take, for the player and Download MP4
    thread: list[FreestyleItem]


class EstimateOut(BaseModel):
    credits: float


def _seconds(text: str) -> int:
    """One clip's length: about 2.5 words a second spoken, within the model's limits."""
    span = get_model(MODEL).duration
    return max(span.min, min(span.max, math.ceil(prompts.spoken_words(text) / 2.5)))


def _job_input(fs: Freestyle, texts: list[str]) -> dict:
    """A single take, drawn in the look: the script, then each change asked since."""
    own, base = (prompts.style(i)["sections"] for i in (fs.look, looks.base(fs.look)))
    style = own.get("clip_style") or base.get("clip_style", "")  # a lane's, else its look's
    changes = "".join(f"\nChange: {t}" for t in texts[1:])
    return {
        FREESTYLE: fs.id,
        "model": MODEL,
        "brand_id": fs.brand_id,
        "fit_images_to": LONG_SIDE[RESOLUTION],
        "input": {
            "prompt": f"{style}\n{texts[0]}{changes}".strip(),
            "duration": _seconds(texts[0]),
            "resolution": RESOLUTION,
            "aspect_ratio": fs.shape,
            "generate_audio": True,
        },
    }


def _check(db: Session, user: User, type: str, look: str, brand_id: int | None) -> None:
    if type != "one_clip":
        raise HTTPException(422, NOT_YET)
    looks.pick(db, user, look)  # an editor: only a look that's on
    if brand_id is not None:
        get_brand(db, user, brand_id)


def _get(db: Session, user: User, freestyle_id: int) -> Freestyle:
    """The maker's or, for the owner, anyone's; to anyone else it isn't there."""
    fs = db.get(Freestyle, freestyle_id)
    if not fs or fs.workspace_id != user.workspace_id:
        raise HTTPException(404, NONE)
    if not (user.is_owner or fs.created_by_id == user.id):
        raise HTTPException(404, NONE)
    return fs


def _jobs(db: Session, fs: Freestyle) -> dict[int, Job]:
    ids = [m["job"] for m in fs.chat if m.get("job")]
    return {j.id: j for j in db.scalars(select(Job).where(Job.id.in_(ids)))} if ids else {}


def _send(db: Session, user: User, fs: Freestyle, text: str) -> None:
    """Add a message and start its take: held for the owner when an editor sends it."""
    texts = [m["text"] for m in fs.chat] + [text]
    input = _job_input(fs, texts)
    job = enqueue(db, user, "video", input, units=input["input"]["duration"],
                  provider="replicate", wait="" if user.is_owner else HELD)  # fmt: skip
    message = {"by": user.id, "text": text, "at": utcnow().isoformat(), "job": job.id}
    fs.chat = [*fs.chat, message]
    db.commit()


def _move(fs: Freestyle, job: Job) -> tuple[str, str, str]:
    """(freestyle status, move status, plain words) for one send's job."""
    s = job.status
    if s == JobStatus.needs_owner_approval:
        return "waiting", "held", "Waiting for Reed's OK."
    if s == JobStatus.queued:
        return "working", "queued", "Starting the clip."
    if s == JobStatus.running:
        return "working", "running", "Making the clip."
    if s == JobStatus.succeeded:
        return "delivered", "done", "Made the clip."
    if s == JobStatus.failed:
        return "failed", "refused", f"Couldn't make it: {job.error or 'it failed'}"
    if job.input.get(DECLINE):
        return "declined", "refused", f"Reed declined: {job.error}"
    if job.input.get(WITHDRAWN):
        return "withdrawn", "refused", "Withdrawn."
    return "stopped", "refused", "Stopped."


def _out(db: Session, fs: Freestyle) -> FreestyleOut:
    jobs = _jobs(db, fs)
    names = dict(db.execute(select(User.id, User.name).where(
        User.id.in_({fs.created_by_id, *(m["by"] for m in fs.chat)}))).all())  # fmt: skip
    thread, status, file_id, credits = [], "waiting", None, Decimal(0)
    for n, m in enumerate(fs.chat, 1):
        at = datetime.fromisoformat(m["at"])
        thread.append(FreestyleItem(id=f"m{n}", kind="message", at=at, who=names.get(m["by"], ""),
                                    text=m["text"], status=None))  # fmt: skip
        job = jobs.get(m.get("job"))
        if job is None:
            continue
        status, move, words = _move(fs, job)
        thread.append(FreestyleItem(id=f"t{job.id}", kind="move", at=job.created_at,
                                    who="Director", text=words, status=move))  # fmt: skip
        if job.status == JobStatus.succeeded:
            file_id = ((job.output or {}).get("file_ids") or [None])[0]
        if job.status != JobStatus.cancelled or job.started_at:
            credits += job.credits
    return FreestyleOut(**_row(fs, names, status).model_dump(), look=fs.look, shape=fs.shape,
                        brand_id=fs.brand_id, credits=credits, file_id=file_id,
                        thread=thread)  # fmt: skip


def _row(fs: Freestyle, names: dict[int, str], status: str) -> FreestyleRow:
    return FreestyleRow(id=fs.id, title=fs.title, type=fs.type, status=status,
                        created_at=fs.created_at,
                        created_by_name=names.get(fs.created_by_id, ""))  # fmt: skip


@router.get("/estimate", response_model=EstimateOut)
def estimate_freestyle(
    type: Type,
    look: str,
    shape: Shape,
    text: Text,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """What a send would cost, at most. Free: nothing is queued and nothing is asked of a model."""
    _check(db, user, type, look, None)
    fs = Freestyle(id=0, look=look, shape=shape, brand_id=None)
    input = _job_input(fs, [text])
    units = Decimal(input["input"]["duration"])
    return EstimateOut(credits=estimate(db, user.workspace_id, "video", units, input))


@router.post("", response_model=FreestyleOut, status_code=201,
             dependencies=[Depends(generation_on)])  # fmt: skip
def create_freestyle(
    body: FreestyleIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    _check(db, user, body.type, body.look, body.brand_id)
    title = next(line.strip() for line in body.text.splitlines() if line.strip())[:60]
    fs = Freestyle(workspace_id=user.workspace_id, created_by_id=user.id, title=title,
                   type=body.type, look=body.look, shape=body.shape, brand_id=body.brand_id,
                   chat=[])  # fmt: skip
    db.add(fs)
    db.flush()
    _send(db, user, fs, body.text)
    return _out(db, fs)


@router.get("", response_model=list[FreestyleRow])
def list_freestyles(
    everyone: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """The caller's freestyles, newest first; `everyone`: the whole team's (owner only)."""
    if everyone and not user.is_owner:
        raise HTTPException(403, "Only the owner can see everyone's freestyles.")
    query = select(Freestyle).where(Freestyle.workspace_id == user.workspace_id)
    if not everyone:
        query = query.where(Freestyle.created_by_id == user.id)
    rows = db.scalars(query.order_by(Freestyle.id.desc()).limit(200)).all()
    names = dict(db.execute(select(User.id, User.name).where(
        User.workspace_id == user.workspace_id)).all())  # fmt: skip
    return [_row(fs, names, _out(db, fs).status) for fs in rows]


@router.get("/{freestyle_id}", response_model=FreestyleOut)
def get_freestyle(
    freestyle_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return _out(db, _get(db, user, freestyle_id))


@router.post("/{freestyle_id}/messages", response_model=FreestyleOut, status_code=201,
             dependencies=[Depends(generation_on)])  # fmt: skip
def send_message(
    freestyle_id: int,
    body: MessageIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """A change: a new take with every change asked so far, held like the first send. Only its
    maker sends (the owner reads anyone's)."""
    fs = _get(db, user, freestyle_id)
    if fs.created_by_id != user.id:
        raise HTTPException(403, "Only whoever made this freestyle can change it.")
    if any(j.status in (JobStatus.needs_owner_approval, JobStatus.queued, JobStatus.running)
           for j in _jobs(db, fs).values()):  # fmt: skip
        raise HTTPException(409, BUSY)
    _send(db, user, fs, body.text)
    return _out(db, fs)


@router.post("/{freestyle_id}/withdraw", response_model=FreestyleOut)
def withdraw_freestyle(
    freestyle_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """The maker takes back a send still waiting for the owner. Nothing was spent."""
    fs = _get(db, user, freestyle_id)
    if fs.created_by_id != user.id:
        raise HTTPException(403, "Only whoever made this freestyle can withdraw it.")
    held = Job.status == JobStatus.needs_owner_approval
    ids = [j.id for j in _jobs(db, fs).values() if j.status == JobStatus.needs_owner_approval]
    done = db.execute(update(Job).where(Job.id.in_(ids), held)  # can't race the owner's OK
                      .values(status=JobStatus.cancelled, finished_at=utcnow()))  # fmt: skip
    if not done.rowcount:
        raise HTTPException(409, "Nothing is waiting to withdraw.")
    for job in db.scalars(select(Job).where(Job.id.in_(ids))):
        job.input = {**job.input, WITHDRAWN: True}
    db.commit()
    return _out(db, fs)


@router.post("/{freestyle_id}/stop", response_model=FreestyleOut)
def stop_freestyle(
    freestyle_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Stop what's waiting or being made, by its maker or the owner. A take already at the
    provider is discarded when it lands."""
    fs = _get(db, user, freestyle_id)
    fs.stopped_at = utcnow()  # when it was last stopped
    stop_jobs(db, Job.id.in_(list(_jobs(db, fs))))
    db.commit()
    return _out(db, fs)


@router.patch("/{freestyle_id}", response_model=FreestyleOut)
def rename_freestyle(
    freestyle_id: int,
    body: TitleIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    fs = _get(db, user, freestyle_id)
    if fs.created_by_id != user.id and not user.is_owner:
        raise HTTPException(403, "Only whoever made this freestyle can rename it.")
    fs.title = body.title
    db.commit()
    return _out(db, fs)
