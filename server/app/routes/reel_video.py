"""Use a reel (v6 S2-07, S-gaps-01 option 2): a video adapted from a reel the person uploaded
(`/scripts/import/upload` gets it and prepares it, free).

Copy it shot by shot keeps its lines and shots; Just its structure writes new lines for this
brand on its beats. The press reads the reel (watch, write, cast: the read's own "up to"), and
the video is made at once in the open folder with the reel's script. When the script is
written (`then_direct`, after the read's last step), the director's first turn waits for the
owner's OK at the run's "up to": nothing past the read is spent before that press (the
start-of-run card, piece B, takes this wait over).

Just its look: the person's own words (the pasted send), made in the reel's look. The reel's
prepared cuts and its contact sheet reach the director as its look reference (free)."""

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import director, looks, scorecard, script_write
from app import reel_read as read
from app import script_library as lib
from app.auth import current_user
from app.credits import WAIT_OK
from app.db import utcnow
from app.models.accounts import User
from app.models.freestyles import Freestyle
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft
from app.models.scripts import ScriptVersion
from app.routes import freestyles as fs_routes
from app.routes.clips import generation_on
from app.routes.estimate import run_price
from app.routes.jobs import CHANGE, PRICE, SAID

router = APIRouter(prefix="/freestyles/reel", tags=["freestyles"])
Mode = Literal["copy", "structure", "look"]
NOT_A_REEL = "That isn't a reel you uploaded."
NOT_READY = "The reel is still being prepared."
READ_ALREADY = "This reel has been read already. Start from its script instead."
WORDS = "Paste your script: Just its look makes your words in the reel's look."
WRITTEN = f"{WAIT_OK}the reel's script is written. Make it starts the video."
HOW = {"copy": "copy it shot by shot", "structure": "just its structure", "look": "just its look"}
THEN = "then_direct"  # on the reel's script: the video its read starts, once written


class ReelVideoIn(BaseModel):
    script_id: int  # the uploaded reel's script
    mode: Mode
    type: str = "dialogue"
    look: str | None = None
    shape: fs_routes.Shape
    folder_id: int | None = None
    cast_ids: list[int] | None = None
    broll_look: str | None = None
    attachments: list[int] | None = None
    text: fs_routes.Text | None = None  # Just its look: your own script


class _Send(fs_routes.FreestyleIn):
    """A send New video makes from a reel (`_setup` keeps the reel on its video)."""

    reel_script_id: int | None = None


def _picks_hold(db: Session, user: User, body: ReelVideoIn, script: Script) -> None:
    """Copy and Structure set the video's picks once the script is written: the cast, the
    attachments and a B-roll look are checked at the press instead, so nothing is refused
    after the read is paid."""
    from app import brand_setup, guides
    from app.models.brands import Brand

    if body.cast_ids:
        brand_setup.check_cast(db, db.get(Brand, script.brand_id), body.cast_ids)
    fs_routes.attachments(db, user, body.attachments)
    if body.broll_look and looks.base(body.broll_look) != looks.base(body.look or looks.DEFAULT):
        if not guides.format_(body.type).get("host"):
            raise HTTPException(409, looks.BROLL_HOSTED)
        if looks.get(body.broll_look)["kind"] != "look":
            raise HTTPException(422, looks.UNKNOWN)
        looks.pick(db, user, body.broll_look)


class ReelEstimateOut(BaseModel):
    credits: float  # what the read can charge (Copy, Structure); nothing past it runs unasked
    usd: float | None  # the owner's
    ready: bool  # prepared, and not read yet


def _reel(db: Session, user: User, script_id: int) -> Script:
    script = lib.get_script(db, user, script_id)
    if script.reel is None or not (user.is_owner or script.created_by_id == user.id):
        raise HTTPException(404, NOT_A_REEL)
    return script


@router.get("/estimate", response_model=ReelEstimateOut)
def reel_estimate(script_id: int, user: User = Depends(current_user),
                  db: Session = Depends(fs_routes._db)):  # fmt: skip
    """The read's "up to", free."""
    script = _reel(db, user, script_id)
    status, failed = read.state(db, script)
    ready = status in ("ready", "failed") and failed != "prepare"
    credits = read.price(db, user, read.remaining(script)) if ready else Decimal(0)
    return fs_routes._out_estimate(user, credits).model_dump() | {"ready": ready}


@router.post("", response_model=fs_routes.FreestyleOut, status_code=201,
             dependencies=[Depends(generation_on)])  # fmt: skip
def make_from_reel(body: ReelVideoIn, request: Request, user: User = Depends(current_user),
                   db: Session = Depends(fs_routes._db)):  # fmt: skip
    script = _reel(db, user, body.script_id)
    status, failed = read.state(db, script)
    if status == "preparing" or failed == "prepare":
        raise HTTPException(409, NOT_READY)
    send = _Send(**body.model_dump(exclude={"script_id", "mode"}), brand_id=script.brand_id,
                 reel_script_id=script.id)  # fmt: skip
    if body.mode == "look":  # your words, the reel's look (kept on the video before it starts)
        if not body.text:
            raise HTTPException(422, WORDS)
        return fs_routes.create_freestyle(send, request, user, db)
    if script.reference_breakdown or status in ("reading", "done"):
        raise HTTPException(409, READ_ALREADY)
    look = looks.pick(db, user, body.look or looks.DEFAULT)
    fs_routes._check(db, user, request, body.type, look, script.brand_id, body.folder_id)
    _picks_hold(db, user, body, script)  # checked now: never refused after the read is paid
    script.new_lines, script.format, script.look = body.mode == "structure", body.type, look
    script.kind = lib.pick_format(body.type)
    fs = Freestyle(workspace_id=user.workspace_id, created_by_id=user.id, title=script.title[:60],
                   type=body.type, look=look, shape=body.shape, brand_id=script.brand_id,
                   chat=[])  # fmt: skip
    db.add(fs)
    db.flush()
    project = Project(workspace_id=user.workspace_id, brand_id=script.brand_id,
                      hidden=not user.is_owner, name=f"{script.title[:100]} · freestyle {fs.id}",
                      created_by_id=user.id, look=look, aspect_ratio=body.shape,
                      folder_id=body.folder_id, reel_script_id=script.id)  # fmt: skip
    db.add(project)
    db.flush()
    fs.project_id = project.id
    picks = send.model_dump(include={"folder_id", "cast_ids", "broll_look", "attachments",
                                     "brand_id", "reel_script_id"})  # fmt: skip
    script.reel = {**script.reel, THEN: {"freestyle": fs.id, "by": user.id, "mode": body.mode,
                                         "picks": picks}}  # fmt: skip
    read.queue(db, user, script, read.remaining(script)[0])  # the paid read: commits
    return fs_routes._out(db, fs)


def then_direct(db: Session, script: Script) -> None:
    """The reel's script is written: its video's director run, the first turn waiting for the
    owner's OK at the run's "up to" (the owner's own press too: nothing more is spent unasked)."""
    then = (script.reel or {}).get(THEN)
    fs = db.get(Freestyle, then["freestyle"]) if then else None
    if fs is None or fs.chat or then.get("started"):
        return
    user, project = db.get(User, then["by"]), db.get(Project, fs.project_id)
    draft = script_write.original(db, script)
    if not draft.text.strip():
        return
    project.script_draft_id = draft.id  # the written script is the video's from here on
    fs_routes._setup(db, user, project, _Send(shape=fs.shape, text=draft.text, **then["picks"]),
                     pasted=True)  # fmt: skip
    scorecard.record_forecast(db, project, draft)
    db.add(ScriptVersion(project_id=project.id, version=1, text=draft.text, source="library",
                         created_by_id=user.id))  # fmt: skip
    fs.up_to = run_price(db, draft, project)
    said, at = f"Make it from {script.title}, {HOW[then['mode']]}.", utcnow().isoformat()
    what = {"project": project.id, "draft": draft.id, "show": True}
    script.reel = {**script.reel, THEN: {**then, "started": True}}  # before the run holds it
    db.flush()
    turn = director.start(db, user, project, wait=WRITTEN, frozen=False,
                          extra={fs_routes.FREESTYLE: fs.id, SAID: said, CHANGE: False,
                                 PRICE: str(fs.up_to), fs_routes.FREEZE: what})  # fmt: skip
    fs.chat = [{"by": user.id, "text": said, "at": at, "job": turn.id,
                "price": str(fs.up_to)}]  # fmt: skip


def look_reference(db: Session, project: Project) -> dict | None:
    """Just its look: the reel the video follows the look of, as the director reads it (free:
    its measured cuts and contact sheet; seeing the sheet comes with piece B)."""
    script = db.get(Script, project.reel_script_id) if project.reel_script_id else None
    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    if script is None or draft is None or draft.script_id == script.id:
        return None  # none, or a copy or structure video: the reel is its script
    reel = script.reel or {}
    seconds, cuts = reel.get("seconds") or 0, len(reel.get("cuts") or [])
    return {"use": "Make this video's script in this reel's look: its camera, light, colour and "
                   "cut pace. Never use its words or its story.",
            "reel": script.title, "seconds": seconds, "shots": cuts + 1,
            "cuts_per_10_s": round(10 * cuts / seconds, 1) if seconds else None,
            "contact_sheet_file_id": reel.get("contact_file_id"),
            "video_file_id": reel.get("video_file_id")}  # fmt: skip
