"""The Cast view's checkpoint and its places (Reed, 4 Nov, on S-gaps-07; boards S5-01 to
S5-04, P-09). GET: every character and place the video shows, each with where it came from,
its picture, whether it's ready and whether it's approved as it is, and the checkpoint's state.
POST approve: "Approve cast & places", the whole set at once (app/cast_gate.py). Places: a
place for some shots, from the brand's places or made for this video only (never the brand's,
rule 12), an uploaded photo as its look, or a look drawn for this video. The plan's shots name
it (`place_id`), so its stills and takes use it. The card's other presses are the Assets
routes (app/routes/project_assets.py)."""

import copy
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import cast_gate, clip_prompts
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.clips import ProjectClip
from app.models.library import Kind, LibraryItem
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.routes.clips import generation_on
from app.routes.library import _waiting_sheets, pick_item
from app.routes.project_assets import _newest, _resave
from app.routes.projects import get_project, video_writer
from app.routes.sheets import SheetIn, queue_sheet
from app.schemas import LongText, Name

router = APIRouter(
    prefix="/projects/{project_id}/cast", tags=["assets"], dependencies=[Depends(video_writer)]
)
NO_PLAN = "Make the plan first: a place belongs to its scenes."
NO_PLACE = "No such place in this video."
NOT_THE_BRANDS = "Pick one of the brand's places."


class CastVoiceOut(BaseModel):
    name: str
    sample_url: str | None  # an API path ("/voices/samples/Roger.mp3"): the web adds /api


class CastItemOut(BaseModel):
    ref: str  # as the shots name it: char:12, slot:3 (a role with no look yet), place:7
    kind: Literal["character", "place"]
    name: str
    library_item_id: int | None
    version: int | None  # the item's version ("Goth GF" v4)
    source: Literal["library", "uploaded", "video", "script"] | None  # None: no look yet
    preview_file_id: int | None  # the picture its stills and takes use
    readiness: Literal["ready", "needs_look", "drawing", "waiting_for_owner"]
    approval: Literal["approved", "changed", "new"]  # as it is now, against the last OK
    sig: str  # send back with Approve: what you saw
    clip_ids: list[str]  # the clips that show it
    changes: list[Literal["look", "words", "voice"]]  # what changed since the OK (approval
    # "changed"): its picture, its words (name, role, outfit) or a character's voice
    voice: CastVoiceOut | None = None  # a character's voice now, with its sample to play
    was_voice: CastVoiceOut | None = None  # its voice at the last OK, only when it changed
    # A look made for this video: "Made by the director in the chat · 09:06" ("director", or
    # the person's name; an upload's, who gave the photo), and its last revision ("Revised
    # 09:21 after your note · was ▣"): when, by whom, why (the change asked for, "" for none)
    # and the picture before it. Null for a brand look.
    made_by: str | None = None
    made_at: str | None = None
    revised_by: str | None = None
    revised_at: str | None = None
    revised_why: str | None = None
    was_preview_file_id: int | None = None


class CastNotReadyOut(BaseModel):
    ref: str
    name: str
    why: str  # "Chase needs a look"


class KeptOut(BaseModel):
    kind: Literal["still", "clip"]
    id: str  # its shot id, or its clip id
    by: str
    at: str


class CastUpdateOut(BaseModel):
    stills: list[str]  # shot ids of stills made with an earlier version of an item
    clips: list[str]  # clip ids whose picked take was made with one
    credits: int  # remaking them all, up to (rule 36); never done by itself
    clips_credits: int  # the clips alone: "Remake clips 2–4 · up to"
    kept_items: list[KeptOut]  # made with an earlier look, and the person said Keep them


class PreviewsOut(BaseModel):
    """ "Previews so far: $0.48 of the approved budget": the looks made for this video."""

    credits: float
    usd: float | None  # the owner only (rule 4)
    budget_credits: float
    budget_usd: float | None


class CastOut(BaseModel):
    # none: nothing shown needs a look; not_ready: something has no look or is being drawn;
    # ready: all drawn, something new or changed waits for the OK; approved
    state: Literal["none", "not_ready", "ready", "approved"]
    approved_by: str | None
    approved_at: str | None
    asked: bool  # the director asked for the OK in the chat
    can_approve: bool = False  # this person may press Approve (whoever made it, or the owner)
    items: list[CastItemOut]
    waiting: list[str]  # names new or changed since the last OK
    not_ready: list[CastNotReadyOut]
    paused_clips: list[str]  # clips whose stills and takes wait for the OK
    update: CastUpdateOut
    previews: PreviewsOut


class CastApproveIn(BaseModel):
    seen: dict[str, str]  # each item's `sig` as the person saw it


class CastKeepIn(BaseModel):
    stills: list[str] | None = None  # shot ids; null: every still listed in `update`
    clips: list[str] | None = None  # clip ids; null: every clip listed in `update`


class PlaceIn(BaseModel):
    shot_ids: list[str]  # the plan's shots at this place
    library_item_id: int | None = None  # one of the brand's places; else a new one:
    name: Name | None = None
    description: LongText = ""  # what it looks like, for its look


class PlacePickIn(BaseModel):
    library_item_id: int  # one of the brand's places


class PlaceUploadIn(BaseModel):
    file_id: int  # a photo of it


def _out(db: Session, user: User, project: Project) -> CastOut:
    mine = user.is_owner or project.created_by_id == user.id
    return CastOut.model_validate({**cast_gate.state(db, project, user), "can_approve": mine})


@router.get("", response_model=CastOut)
def read(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The Cast view's set and its checkpoint. Free."""
    return _out(db, user, get_project(db, user, project_id))


@router.post("/approve", response_model=CastOut)
def approve(
    project_id: int,
    body: CastApproveIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Approve cast & places: the person making the video (or the owner) approves the whole
    set as they saw it. Stills and takes that waited for it go on. Free."""
    project = get_project(db, user, project_id)
    cast_gate.approve(db, user, project, body.seen)
    return _out(db, user, project)


@router.post("/keep", response_model=CastOut)
def keep(
    project_id: int, body: CastKeepIn, user: User = Depends(current_user),
    db: Session = Depends(get_db),
):  # fmt: skip
    """Keep them: stills and takes made with an earlier look stay as they are and stop
    counting as needing an update (who and when are kept). Free; Remake stays priced."""
    project = get_project(db, user, project_id)
    cast_gate.keep(db, user, project, body.stills, body.clips)
    return _out(db, user, project)


# --- Places --------------------------------------------------------------------------------------


def _shots(project: Project, db: Session) -> tuple:
    bd = _newest(db, project)
    if bd is None:
        raise HTTPException(409, NO_PLAN)
    return bd, [s for sc in bd.data["scenes"] for s in sc["shots"]]


def _place(db: Session, project: Project, item_id: int) -> tuple[LibraryItem, list[str]]:
    """A place this video's shots show, and those shots."""
    _, shots = _shots(project, db)
    at = [s["id"] for s in shots if s.get("place_id") == f"place:{item_id}"]
    item = db.get(LibraryItem, item_id)
    if not at or item is None:
        raise HTTPException(404, NO_PLACE)
    return item, at


def _own(project: Project, name: str, notes: str, photo: int | None = None,
         was: LibraryItem | None = None) -> LibraryItem:  # fmt: skip
    """A place for this video only; `was`: the one it replaces here ("was ▣" on its card)."""
    return LibraryItem(workspace_id=project.workspace_id, kind=Kind.place, name=name,
                       notes=notes or name, owner_project_id=project.id,
                       sheet_look=project.look or "house", source_photo_file_id=photo,
                       copied_from_id=was.id if was else None)  # fmt: skip


def _brand_place(db: Session, user: User, project: Project, item_id: int,
                 own: bool = False) -> LibraryItem:  # fmt: skip
    """One of this video's brand's saved places (`own`: or one made for this video): only
    those can be in its shots."""
    item = pick_item(db, user, Kind.place, item_id, project)
    if own and item.owner_project_id == project.id:
        return item
    if not any(b.id == project.brand_id for b in item.brands):
        raise HTTPException(422, NOT_THE_BRANDS)
    return item


def repoint(db: Session, user: User, project: Project, moves: dict[str, str]) -> None:
    """The plan's shots `moves` ({shot_id: "place:N"}) now happen there, as a new breakdown
    version. Their stills attach the new place and are marked out of date (drawn again once
    the cast and places OK covers it). Their clips stay behind as stale, so their prompts and
    references are written again (`clip_prompts.follow`); their takes are kept."""
    bd, shots = _shots(project, db)
    moves = {
        s["id"]: moves[s["id"]]
        for s in shots
        if s["id"] in moves and s.get("place_id") != moves[s["id"]]
    }  # already there: as is
    if not moves:
        return
    data, was = copy.deepcopy(bd.data), {}
    for shot in (s for sc in data["scenes"] for s in sc["shots"] if s["id"] in moves):
        was[shot["id"]], shot["place_id"] = shot.get("place_id"), moves[shot["id"]]
    _resave(db, user, project, bd, data)
    new = _newest(db, project)
    moved = select(StoryboardFrame).where(StoryboardFrame.breakdown_id == new.id,
                                          StoryboardFrame.shot_id.in_(list(moves)))  # fmt: skip
    for frame in db.scalars(moved):
        old, now = was.get(frame.shot_id), moves[frame.shot_id]
        refs = [now if r == old else r for r in frame.reference_ids if r != now]
        frame.reference_ids = refs if now in refs else [*refs, now]
        frame.prompt = _renamed(db, frame.prompt, old, now)
        frame.approved = False
        frame.still_stale = bool(frame.file_id)
    behind = [c["id"] for c in new.data["clips"] if set(c["shot_ids"]) & set(moves)]
    rows = select(ProjectClip).where(ProjectClip.breakdown_id == new.id,
                                     ProjectClip.clip_id.in_(behind))  # fmt: skip
    for row in db.scalars(rows):
        row.breakdown_id, row.approved, row.prompt_ok = bd.id, False, False
    clip_prompts.follow(db, project, user)
    db.commit()


def _renamed(db: Session, prompt: str, old: str | None, now: str) -> str:
    """A still's prompt calls the place by its new name (free)."""
    a = db.get(LibraryItem, int(old.split(":")[1])) if old else None
    b = db.get(LibraryItem, int(now.split(":")[1]))
    return prompt.replace(a.name, b.name) if a and b else prompt


def _unplaced(db: Session, project: Project, name: str, shots: list) -> LibraryItem | None:
    """This video's own place of that name that no shot is at yet (a place card's answer)."""
    from app.cast_roles import same

    at = {s.get("place_id") for s in shots}
    rows = db.scalars(select(LibraryItem).where(LibraryItem.owner_project_id == project.id,
                                                LibraryItem.kind == Kind.place,
                                                LibraryItem.archived.is_(False))
                      .order_by(LibraryItem.id.desc()))  # fmt: skip
    return next((i for i in rows if same(i.name, name) and f"place:{i.id}" not in at), None)


def add_place(db: Session, user: User, project: Project, body: PlaceIn) -> LibraryItem:
    """A place for some shots: one of the brand's, or a new one for this video only, with no
    look yet (Pick, Upload or Make a look on its card; the director's make_looks draws it)."""
    _, shots = _shots(project, db)
    known = {s["id"] for s in shots}
    if not body.shot_ids or (gone := [s for s in body.shot_ids if s not in known]):
        raise HTTPException(422, f"No shot {gone[0]} in this video's plan." if body.shot_ids
                            else "Say which shots happen there.")  # fmt: skip
    if body.library_item_id is not None:
        item = _brand_place(db, user, project, body.library_item_id, own=True)
    elif body.name and (kept := _unplaced(db, project, body.name, shots)):
        item = kept  # a place card's answer made it before any shot was there: its photo stays
    elif body.name:
        item = _own(project, body.name, body.description.strip())
        db.add(item)
        db.flush()
    else:
        raise HTTPException(422, "Name the place, or pick one of the brand's.")
    repoint(db, user, project, dict.fromkeys(body.shot_ids, f"place:{item.id}"))
    return item


@router.post("/places", response_model=CastOut, status_code=201)
def new_place(
    project_id: int, body: PlaceIn, user: User = Depends(current_user),
    db: Session = Depends(get_db),
):  # fmt: skip
    """Set where some of the plan's shots happen: a brand place, or one made for this video
    only (never in Cast & places). Free; its look is a separate press, and the clip prompts of
    those shots are rewritten within the budget, as after a cast change."""
    project = get_project(db, user, project_id)
    add_place(db, user, project, body)
    return _out(db, user, project)


@router.put("/places/{item_id}", response_model=CastOut)
def pick_place(
    project_id: int, item_id: int, body: PlacePickIn, user: User = Depends(current_user),
    db: Session = Depends(get_db),
):  # fmt: skip
    """Pick from the brand's places: every shot at this place happens there instead. Free; its
    clip prompts are then rewritten within the budget, as after a cast change."""
    project = get_project(db, user, project_id)
    _, at = _place(db, project, item_id)
    picked = _brand_place(db, user, project, body.library_item_id)
    repoint(db, user, project, dict.fromkeys(at, f"place:{picked.id}"))
    return _out(db, user, project)


@router.post("/places/{item_id}/upload", response_model=CastOut)
def upload_place(
    project_id: int, item_id: int, body: PlaceUploadIn, user: User = Depends(current_user),
    db: Session = Depends(get_db),
):  # fmt: skip
    """Upload a photo of the place: it's this video's look for it, never the brand's (rule
    12). Free: its sheet is drawn by Make a look or the director's make_looks (a brand place's
    shots then move to it, and their clip prompts are rewritten within the budget)."""
    from app.routes.files import get_file

    project = get_project(db, user, project_id)
    item, at = _place(db, project, item_id)
    photo = get_file(db, user, body.file_id, "image").id
    if item.owner_project_id == project.id and not item.sheet_file_id:
        if _waiting_sheets(item):
            raise HTTPException(409, f"{item.name}'s look is being drawn. Cancel it first.")
        item.source_photo_file_id = photo
        db.commit()
    else:  # a brand place, or one drawn already: a new look for this video from the photo
        own = _own(project, item.name, item.notes, photo, was=item)
        db.add(own)
        db.flush()
        repoint(db, user, project, dict.fromkeys(at, f"place:{own.id}"))
    return _out(db, user, project)


@router.post(
    "/places/{item_id}/make-look", response_model=CastOut, dependencies=[Depends(generation_on)]
)
def make_place_look(
    project_id: int, item_id: int, user: User = Depends(current_user),
    db: Session = Depends(get_db),
):  # fmt: skip
    """Make a look for this video only (paid from its budget, "up to" its row's look_credits):
    a place with none is drawn from its words or uploaded photo; a brand place gets a copy
    drawn for this video. It's shown with the rest for the cast and places OK."""
    project = get_project(db, user, project_id)
    item, at = _place(db, project, item_id)
    if item.owner_project_id != project.id:
        own = _own(project, item.name, item.notes, was=item)
        db.add(own)
        db.flush()
        queue_sheet(db, user, own, SheetIn())  # commits; a refusal adds nothing
        repoint(db, user, project, dict.fromkeys(at, f"place:{own.id}"))
    elif item.sheet_file_id or _waiting_sheets(item):
        raise HTTPException(409, f"{item.name} has a look already. Use Change this… on it.")
    else:
        queue_sheet(db, user, item, SheetIn())
    return _out(db, user, project)


def answer_place(db: Session, user: User, project: Project, subject: str, data: dict) -> None:
    """A place card's answer: a brand place picked, or a photo or a generated option as this
    video's own look (never the brand's). On the place of that name the plan's shots are at,
    its shots move there. One no shot is at yet is still made for this video, so the director
    puts it in its shots with `add_place` (its `library_item_id`)."""
    from app.asks import _picture
    from app.cast_roles import same

    found = next((i for i in cast_gate.current(db, project) if i["kind"] == "place"
                  and subject and same(i["name"], subject)), None)  # fmt: skip
    item, at = None, []
    if found is not None:
        try:
            item, at = _place(db, project, int(found["ref"].split(":")[1]))
        except HTTPException:  # only a still attaches it: the answer steers the director
            item = None
    option = str(data.get("option", ""))
    if data.get("how") == "saved" and option.startswith("item:"):
        picked = db.get(LibraryItem, int(option.split(":")[1]))
        if at and picked is not None and picked.kind == Kind.place and not picked.owner_project_id:
            repoint(db, user, project, dict.fromkeys(at, f"place:{picked.id}"))
        return
    if data.get("how") not in ("upload", "option") or not _picture(db, data.get("file_id")):
        return  # a picture only: a clip is never a place's photo
    name = item.name if item else (subject or "A place")
    own = _own(project, name, item.notes if item else name,
               None if data["how"] == "option" else data["file_id"], was=item)  # fmt: skip
    if data["how"] == "option":  # drawn in the video's look: it is the look
        own.sheet_file_id, own.sheet_approved = data["file_id"], True
    db.add(own)
    db.flush()
    if at:
        repoint(db, user, project, dict.fromkeys(at, f"place:{own.id}"))


def change_look(db: Session, user: User, project: Project, name: str, note: str) -> str:
    """The director's change_look, as Change this… on the card: a look made for this video is
    drawn again with the change; a role played by a saved character, or a brand place, gets
    a look made for this video with it (the saved one stays as it is). Paid; the new look is
    shown with the rest for the cast and places OK. Plain words for its log."""
    from app import cast_roles, locks
    from app.routes.project_assets import _make_look, _open_slot

    if no := locks.refusal(project, "cast"):
        return f"Refused: {no}"
    note = note.strip()[:500]
    found = next((i for i in cast_gate.current(db, project)
                  if cast_roles.same(i["name"], name)), None)  # fmt: skip
    item = db.get(LibraryItem, (found or {}).get("library_item_id") or 0)
    if found is None or not note:
        return f"Refused: there's no {name} in this video." if not found else (
            "Refused: say what to change.")  # fmt: skip
    if item is not None and _waiting_sheets(item):
        return f"Refused: {found['name']} is still being drawn."
    if item is not None and item.owner_project_id == project.id:
        queue_sheet(db, user, item, SheetIn(change=note))
        return f"Drawing {found['name']} again: {note}"
    if found["kind"] == "place":
        try:  # only a place the plan's shots are at: nothing is drawn for one they aren't
            _, at = _place(db, project, int(found["ref"].split(":")[1]))
        except HTTPException:
            return f"Refused: no shot in the plan is at {found['name']}."
        words = f"{(item.notes if item else '').rstrip('. ')}. {note}"
        own = _own(project, found["name"], words, was=item)
        db.add(own)
        db.flush()
        queue_sheet(db, user, own, SheetIn())
        repoint(db, user, project, dict.fromkeys(at, f"place:{own.id}"))
        return f"Making a look of {found['name']} for this video: {note}"
    slot = next((s for s in cast_roles.video_slots(db, project)
                 if found["ref"] in (f"slot:{s.id}", f"char:{cast_roles.pick(db, project, s)}")),
                None)  # fmt: skip
    if slot is None:
        return f"Refused: {found['name']} isn't one of the script's roles here."
    _make_look(db, user, project, _open_slot(db, project, slot.id), change=note)
    return f"Making a look of {found['name']} for this video: {note}"
