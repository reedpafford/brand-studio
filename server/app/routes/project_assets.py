"""The Assets step (workflow v2): every character and place the breakdown uses, with its look.
Locked cast slots come preloaded with their look; an unlocked slot gets a character from the
editor (picked or new), whose sheet is made and approved with the library's sheet routes.
Storyboard and takes already refuse until every sheet they need is approved."""

import json
import re
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from app import advice, breakdown, cast_roles, clip_prompts, locks, looks, merge_roles, model_map
from app.auth import current_user
from app.credits import COUNTED, fits, price
from app.db import get_db
from app.enhance import project_screens, screen_name
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job, JobStatus
from app.models.library import Kind, LibraryItem
from app.models.projects import Project
from app.models.script_library import CastMerge, Script, ScriptCastSlot, ScriptDraft
from app.prompts import check
from app.prompts.schemas import Breakdown
from app.routes.clips import generation_on
from app.routes.library import LookFitOut, _waiting_sheets, pick_item, sheet_status
from app.routes.projects import get_project, video_writer
from app.routes.script_cast import (
    MergePreview,
    PairIn,
    Role,
    RoleFacts,
    SamePair,
    UndoIn,
    _unique,
    role_facts,
)
from app.routes.scripts import latest
from app.routes.sheets import SheetIn, check_fit, queue_sheet
from app.schemas import LongText
from app.sheets import (
    check_price,
    is_checked,
    look_copy,
    look_price,
    look_usual,
    own,
    press_price,
    sheet_for,
    sheet_price,
)

router = APIRouter(
    prefix="/projects/{project_id}/assets", tags=["assets"], dependencies=[Depends(video_writer)]
)


class TextFitOut(BaseModel):
    seen: advice.SaidText  # "The approved look shows a French bulldog."
    name: str  # the role's name put right, "" when it fits
    description: str  # the description put right, "" when it fits
    notes: str  # this video's look's notes now (Undo puts them back)
    update_look: bool  # Update to match: this video's own look's notes (any editor)
    update_script: bool  # Update the script's role too (the owner, or its author unpublished)
    note: advice.SaidText = ""  # the script's role still differs; this video follows the look


class AssetOut(BaseModel):
    kind: str  # character | place | product | screen
    ref: str  # as the breakdown names it: char:5, place:2, or slot:3 until it has a character
    role: str  # the cast slot's role, else the item's name
    library_item_id: int | None
    name: str
    locked: bool  # a locked slot: its look is fixed for every version
    sheet_status: str  # none | drawing | waiting_for_owner | needs_approval | approved | missing
    ready: bool  # nothing left to do for it
    slot_id: int | None = None  # the script's cast slot this row fills; null for other rows
    description: str = ""  # the slot's role, as the script describes it (e.g. "teen, shy")
    shots: int = 0  # how many of the breakdown's shots it is in ("In 3 shots")
    file_id: int | None = None  # a product's or screen's picture (the brand's; nothing to make)
    sheet_file_id: int | None = None  # the look's sheet, read with sheet_status so the two agree
    only_here: Literal["video", "script"] | None = None  # "This video only" / "This script only"
    own_look_id: int | None = None  # the look made for this role here; "Not used" if swapped out
    facts: RoleFacts | None = None  # the role's age range, gender and job (a slot's row only)
    look_fit: LookFitOut | None = None  # its sheet doesn't read as the role: advice, Redo it
    declined: bool = False  # Not now on the missing-looks note: never made by itself again
    library_deleted: bool = False  # its Cast & places character was deleted: Make or Pick
    look_credits: int | None = None  # Make a look on a role: "up to" (held at the press)
    # ST2: a Cast & places character with no sheet in the video's look: "Make a {look} look
    # for this video · look_credits" (the look's name); then its copy's sheet is this row's
    look_needed: str | None = None
    look_copy_id: int | None = None
    look_usual_credits: int | None = None  # "Usually N": its sheet and check, no redo
    # The approved look contradicts the role's words (Biscuit: a French bulldog written as a
    # golden retriever): what it shows, and the role's name and description put right.
    text_fit: TextFitOut | None = None
    text_check_credits: int | None = None  # its words not yet read against this sheet: Check
    # The Cast tab (v6 S5): the clips it's in ("in 9 of 9 clips", "Clips 2–4 wait for him"),
    # the picture someone uploaded for it (its sheet is drawn from it), the saved character's
    # version ("Goth GF" v4), the sheet job drawing now (Cancel), and whether this person may
    # unlock a role locked on the script (its author or the owner, before it's published).
    clip_ids: list[str] = []
    photo_file_id: int | None = None
    library_version: int | None = None
    drawing_job_id: int | None = None
    script_unlock: bool = False


class SlotTextIn(BaseModel):
    notes: LongText | None = None  # this video's own look
    role: Role | None = None  # the script's role (rule 31)
    description: LongText | None = None


class SlotCastIn(BaseModel):
    library_item_id: int


def _newest(db: Session, project: Project) -> BreakdownVersion | None:
    return db.scalar(
        select(BreakdownVersion)
        .where(BreakdownVersion.project_id == project.id)
        .order_by(BreakdownVersion.id.desc())
        .limit(1)
    )


def _slots(db: Session, project: Project) -> list[ScriptCastSlot]:
    return cast_roles.video_slots(db, project)


def _row(
    kind: str, ref: str, role: str, item: LibraryItem | None, locked: bool, slot=None,
    project: Project | None = None,
) -> AssetOut:  # fmt: skip
    status = "missing" if item is None else ("approved" if locked else sheet_status(item))
    sheet = None if item is None else slot.sheet_file_id if locked and slot else item.sheet_file_id
    needed, copy = None, None
    if item is not None and project is not None and _other_look(project, item):
        db = object_session(item)
        files, copy = sheet_for(db, project, item), look_copy(db, project, item)
        if files:
            status, sheet = "approved", files[0]
        elif copy and copy.sheet_look == project.look:
            status, sheet = sheet_status(copy), copy.sheet_file_id
        else:  # its sheet is in another look: this video makes its own (ST2)
            status, sheet, needed = "missing", None, looks.get(project.look)["name"]
    only = None
    if item is not None and item.owner_project_id:
        only = "video"
    elif item is not None and item.owner_script_id:
        only = "script"
    return AssetOut(
        only_here=only,
        kind=kind,
        ref=ref,
        role=role or (item.name if item else ""),
        library_item_id=item.id if item else None,
        name=item.name if item else "",
        locked=locked,
        sheet_status=status,
        sheet_file_id=sheet,
        ready=status == "approved",
        slot_id=slot.id if slot else None,
        description=slot.description if slot else "",
        facts=role_facts(slot.description, slot.guessed or []) if slot else None,
        look_fit=item.look_fit if item else None,
        look_needed=needed,
        look_copy_id=copy.id if copy else None,
        photo_file_id=item.source_photo_file_id if item and own(item) else None,
        library_version=item.version if item and not own(item) else None,
        drawing_job_id=next((j.id for j in _waiting_sheets(copy or item)), None) if item else None,
    )


def _drawn_elsewhere(project: Project, item: LibraryItem) -> bool:
    """A role's own look drawn in another look than the video's (Flow-QA on #967): no picture
    here (sheet_for), so the role needs a look made in this one."""
    return item.kind == Kind.character and own(item) and (
        (item.sheet_look or "house") != (project.look or "house"))  # fmt: skip


def _other_look(project: Project, item: LibraryItem) -> bool:
    """A Cast & places character in a video in another look than House (ST2)."""
    return (project.look or "house") != "house" and item.kind == Kind.character and not own(item)


def _text(row: AssetOut, slot, item, project: Project, user: User) -> None:
    """An approved look's role words (Biscuit: a French bulldog written as a golden retriever),
    as its check rewrote them: Update to match saves them into this video's own look; the
    owner (or the author before publishing) can put the script's role right too (rule 31).
    A look approved before the check read them can be Checked, at its price."""
    if row.locked or row.sheet_status != "approved" or not is_checked(item):
        return
    if not (slot.description or "," in slot.role):
        return
    read = item.text_fit or {}
    to = {}  # each of the role's words: as read (offer what it was put right to), or put right
    for key, now in (("role", slot.role), ("description", slot.description)):
        fixed = read.get(f"{key}_to")
        if now == read.get(key):
            to[key] = fixed or ""
        elif fixed and now == fixed:
            to[key] = ""
    same = (read.get("slot_id"), read.get("sheet_file_id")) == (slot.id, item.sheet_file_id)
    if not same or len(to) < 2:  # not read against this sheet and these words yet: Check
        row.text_check_credits = price(check_price(object_session(item), item.workspace_id))
        return
    look = bool(read["description_to"]) and item.owner_project_id == project.id
    look = look and item.notes.strip() != read["description_to"]
    script = any(to.values()) and _script_words(object_session(item), slot, user)
    note = (
        ""
        if script or not any(to.values())
        else ("The script's role still describes the earlier look; this video follows the look.")
    )
    if look or script or note:
        row.text_fit = TextFitOut(
            seen=f"The approved look shows {read['seen'].strip().rstrip('.')}.",
            name=read["role_to"], description=read["description_to"], notes=item.notes,
            update_look=look, update_script=script, note=note)  # fmt: skip


def _script_videos(db: Session, script_id: int) -> list[Project]:
    """The videos made from any version of a script."""
    drafts = select(ScriptDraft.id).where(ScriptDraft.script_id == script_id)
    return list(db.scalars(select(Project).where(Project.script_draft_id.in_(drafts))))


def _script_editable(db: Session, slot, user: User) -> bool:
    """A role locked on its script can be unlocked by the script's author or the owner, until
    the script is published (then it's final for everyone)."""
    script = db.get(Script, slot.script_id)
    return (user.is_owner or script.created_by_id == user.id) and not script.published


def _script_words(db: Session, slot, user: User) -> bool:
    """Rule 31: a published script's role words are the owner's to change; before
    publishing, its author's too."""
    script = db.get(Script, slot.script_id)
    return user.is_owner or (script.created_by_id == user.id and not script.published)


@router.get("", response_model=list[AssetOut])
def list_assets(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Cast slots first (locked, then unlocked), then the breakdown's other characters, its
    places, then the products and screens its shots show, each once."""
    project = get_project(db, user, project_id)
    if breakdown.complete_cast(db, project):  # free: a speaker or a role missing from its shots
        db.commit()
    bd = _newest(db, project)
    data = bd.data if bd else {"scenes": []}
    shots = [s for scene in data["scenes"] for s in scene["shots"]]
    by_id = {s["id"]: s for s in shots}
    used = list(dict.fromkeys(c for s in shots for c in s["character_ids"]))
    places = list(dict.fromkeys(s["place_id"] for s in shots if s.get("place_id")))
    out, seen = [], set()
    look = price(look_price(db, project.workspace_id))
    usual_look = price(look_usual(db, project.workspace_id))
    flagged = _flagged(db, project)
    for slot in _slots(db, project):
        item_id = cast_roles.picked(project, slot)
        live = cast_roles.pick(db, project, slot)  # a deleted look: the role is uncast
        item = db.get(LibraryItem, live) if live else None
        if item and _drawn_elsewhere(project, item):  # its own look is in another look:
            item = live = None  # the role reads as having none here, offering Make a look
        out.append(_row("character", f"char:{live}" if live else f"slot:{slot.id}",
                        slot.role, item, bool(live and slot.library_item_id), slot,
                        project))  # fmt: skip
        own = db.get(LibraryItem, project.slot_looks.get(str(slot.id)) or 0)
        out[-1].own_look_id = own.id if own and not own.archived else None  # removed: gone
        out[-1].declined = project.slot_looks.get(str(slot.id), 0) is None
        out[-1].look_credits, out[-1].look_usual_credits = look, usual_look
        out[-1].ready = out[-1].ready or slot.id in flagged  # counted as the role it may be
        gone = db.get(LibraryItem, item_id) if item_id else None
        out[-1].library_deleted = bool(item_id and (gone is None or gone.archived))
        seen.add(f"char:{item_id}")
        if item:
            _text(out[-1], slot, item, project, user)
        if slot.library_item_id:
            out[-1].script_unlock = _script_editable(db, slot, user)
    for ref in used:
        if ref in seen or not ref.startswith("char:"):
            continue
        out.append(_row("character", ref, "", db.get(LibraryItem, int(ref[5:])), False,
                        project=project))  # fmt: skip
        out[-1].look_credits = out[-1].look_credits or (look if out[-1].look_needed else None)
    from app import host

    # S5-02: a presenter talks over the B-roll, in no shot, yet is in the cast and its OK
    who = host.host_look(db, project) if host.presents(db, project) else None
    if who is not None and f"char:{who.id}" not in {r.ref for r in out}:
        out.append(_row("character", f"char:{who.id}", "", who, False, project=project))
    for ref in places:
        place = db.get(LibraryItem, int(ref.split(":")[1]))
        out.append(_row("place", ref, "", place, False))
        if place is not None and place.owner_project_id == project.id:  # Make a look: "up to"
            out[-1].look_credits = price(press_price(db, place))
    screens = {f"screen:{s.id}": s for s in project_screens(db, project)}
    for ref in dict.fromkeys(r for s in shots for r in s.get("screen_ids", [])):
        if screen := screens.get(ref):
            kind = "product" if "product" in screen.tags else "screen"
            out.append(AssetOut(kind=kind, ref=ref, role="", library_item_id=None,
                                name=screen_name(screen), locked=False, sheet_status="approved",
                                ready=True, file_id=screen.file_id))  # fmt: skip
    roles, other = {s.id: s for s in _slots(db, project)}, set()
    version = db.get(ScriptDraft, project.script_draft_id).slot if project.script_draft_id else None
    for row in out:
        refs = {row.ref, f"slot:{row.slot_id}"}
        if row.slot_id in roles:
            refs.add(f"char:{cast_roles.picked(project, roles[row.slot_id])}")
        row.shots = sum(
            1
            for s in shots
            if refs & {*s["character_ids"], s.get("place_id"), *s.get("screen_ids", [])}
        )
        row.clip_ids = [c["id"] for c in data.get("clips", [])
                        if any(refs & {*by_id[i]["character_ids"], by_id[i].get("place_id"),
                                       *by_id[i].get("screen_ids", [])}
                               for i in c["shot_ids"] if i in by_id)]  # fmt: skip
        slot = roles.get(row.slot_id)
        seen = {f"char:{cast_roles.picked(project, slot)}"} if slot else set()
        if slot and not row.shots and not any(seen & set(s["character_ids"]) for s in shots):
            row.ready = True  # a role this video never shows needs no look here
            if slot.appears_in and version not in slot.appears_in:
                other.add(row.slot_id)  # another version's role (QA-Live run 3: the gym bro)
    return [row for row in out if row.slot_id not in other]


@router.patch("/slots/{slot_id}", response_model=list[AssetOut])
def edit_role_text(
    project_id: int,
    slot_id: int,
    body: SlotTextIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Update to match (or its Undo): `notes` go on this video's own look, which its steps,
    sheets and redraws read. `role` and `description` put the script's role right for every
    version: the owner's (or its author's before publishing), rule 31. The spoken words never
    change, and a name keeps its words up to the first comma."""
    project = get_project(db, user, project_id)
    slot = next((s for s in _slots(db, project) if s.id == slot_id), None)
    if not slot:
        raise HTTPException(404, "No such cast slot in this video.")
    if body.notes is not None:
        item = db.get(LibraryItem, cast_roles.pick(db, project, slot) or 0)
        if not item or item.owner_project_id != project.id:
            raise HTTPException(409, "This look is shared with other videos, so its notes stay.")
        item.notes = body.notes.strip()
    if (body.role, body.description) != (None, None) and not _script_words(db, slot, user):
        raise HTTPException(403, "The script's roles are final once it's published; this video "
                                 "follows its look.")  # fmt: skip
    if body.role is not None:
        if cast_roles.short(body.role) != cast_roles.short(slot.role):
            raise HTTPException(422, f"Keep the name {cast_roles.short(slot.role)}; change "
                                     "only what follows the comma.")  # fmt: skip
        _unique(db, db.get(Script, slot.script_id), body.role.strip(), slot.id)
        slot.role = body.role.strip()
    if body.description is not None:
        slot.description, slot.guessed = body.description.strip(), []
    db.commit()
    return list_assets(project_id, user, db)


@router.post("/slots/{slot_id}/check-text", response_model=list[AssetOut])
def check_role_text(
    project_id: int, slot_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Read the role's words against its approved look (Check, at the price shown): a look
    approved before the check read them, like Biscuit's."""
    project = get_project(db, user, project_id)
    slot = _open_slot(db, project, slot_id)
    item = db.get(LibraryItem, cast_roles.pick(db, project, slot) or 0)
    row = next((r for r in list_assets(project_id, user, db) if r.slot_id == slot.id), None)
    if not item or not row or not row.text_check_credits:
        raise HTTPException(409, "There's nothing to check: its words were read already.")
    check_fit(db, user, item, redo=False, slot=slot, pressed=True)
    return list_assets(project_id, user, db)


@router.put("/slots/{slot_id}", response_model=list[AssetOut])
def cast_slot(
    project_id: int,
    slot_id: int,
    body: SlotCastIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Give an unlocked slot its character: it joins the cast, and the newest breakdown's
    slot:N becomes char:M (saved as a new breakdown version)."""
    project = get_project(db, user, project_id)
    slot = _open_slot(db, project, slot_id)
    item = pick_item(db, user, Kind.character, body.library_item_id, project)
    _cast(db, user, project, slot, item)
    db.commit()
    return list_assets(project_id, user, db)


def _open_slot(db: Session, project: Project, slot_id: int) -> ScriptCastSlot:
    slot = next((s for s in _slots(db, project) if s.id == slot_id), None)
    if not slot:
        raise HTTPException(404, "No such cast slot in this video.")
    if slot.library_item_id:
        raise HTTPException(409, f"{slot.role} is locked to one look for every version.")
    if locks.role_locked(project, slot.id):
        raise HTTPException(409, f"{slot.role}'s look is locked in this video. Unlock it first.")
    return slot


def _cast(
    db: Session, user: User, project: Project, slot, item: LibraryItem, same_look=False
) -> None:
    old = project.slot_cast.get(str(slot.id))
    others = {s.library_item_id for s in _slots(db, project)}
    others |= {v for k, v in project.slot_cast.items() if k != str(slot.id)}
    if old in others:  # another role uses that character too: leave its shots alone
        old = None
    project.slot_cast = {**project.slot_cast, str(slot.id): item.id}
    project.cast_ids = sorted({*(c for c in project.cast_ids if c != old), item.id})
    bd = _newest(db, project)
    if bd:
        text = json.dumps(bd.data)
        for before in (f'"slot:{slot.id}"', f'"char:{old}"' if old else None):
            if before:
                text = text.replace(before, f'"char:{item.id}"')
        # Frames follow the new look for free; stills of the old one are redrawn if covered.
        outdated = _resave(db, user, project, bd, json.loads(text), same_look)
        cast_roles.redraw(db, project, user, outdated)
        clip_prompts.follow(db, project, user)


def _resave(db: Session, user: User, project: Project, bd, data: dict, same_look=False) -> list:
    """`data` as the newest breakdown, landed and checked; frames and clips that only changed
    who plays a role move to it (free). Returns the stills that now show the old look."""
    new, removed = breakdown.land(db, project, Breakdown.model_validate(data))
    script = latest(db, project)
    row = BreakdownVersion(
        project_id=project.id,
        script_version=bd.script_version,
        source="edit",
        data={**new.model_dump(), **breakdown.carried_keys(bd)},
        problems=breakdown.problems(db, project, script.text if script else "", new) + removed,
        created_by_id=user.id,
    )
    row.kept = breakdown.carry_kept(bd.kept, row.problems)
    db.add(row)
    db.flush()
    outdated = cast_roles.carry_frames(db, project, bd, row, same_look)
    cast_roles.carry_clips(db, project, bd, row)
    return outdated


@router.post(
    "/slots/{slot_id}/make-look",
    response_model=list[AssetOut],
    dependencies=[Depends(generation_on)],
)
def make_look(
    project_id: int, slot_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Make a look for this video only, from the role's name and description, cast the role
    to it, and draw its sheet (paid, from this video's budget). Never in Cast & places."""
    project = get_project(db, user, project_id)
    slot = _open_slot(db, project, slot_id)
    mine = db.get(LibraryItem, project.slot_looks.get(str(slot.id)) or 0)
    if mine and not mine.archived and not _drawn_elsewhere(project, mine):  # removed: again
        raise HTTPException(409, f"{slot.role} already has a look for this video.")
    _make_look(db, user, project, slot)
    return list_assets(project_id, user, db)


def own_look(db: Session, project: Project, slot: ScriptCastSlot, notes: str,
             photo: int | None = None) -> LibraryItem:  # fmt: skip
    """A look for this role made for this video only, never the brand's (rule 12), drawn in
    its look (ST2) and kept per look (n12): Make a look's, an upload's (`photo`, its sheet
    drawn from it later), a card's answer's or the director's (`told_look`)."""
    look = LibraryItem(workspace_id=project.workspace_id, kind=Kind.character,
                       name=cast_roles.short(slot.role) or slot.role, notes=notes or slot.role,
                       owner_project_id=project.id, sheet_look=project.look or "house",
                       source_photo_file_id=photo)  # fmt: skip
    db.add(look)
    db.flush()
    project.slot_looks = {**project.slot_looks, str(slot.id): look.id}  # the sheet knows its role
    kept = {**(project.own_looks or {}).get(str(slot.id), {}), look.sheet_look: look.id}
    project.own_looks = {**(project.own_looks or {}), str(slot.id): kept}
    return look


def blind(names: list[str]) -> str:
    """Why a role gets no look: nothing says what it is (video 268)."""
    return (f"Nothing says what {' and '.join(names)} look{'s' if len(names) == 1 else ''} "
            "like, so a look would only guess from the name.")  # fmt: skip


BLIND_FIX = " Upload or pick a look, or tell the director in the chat what they look like."


def _make_look(
    db: Session, user: User, project: Project, slot: ScriptCastSlot, auto: bool = False,
    change: str = "", words: str = "",
) -> None:  # fmt: skip
    """`change`: what the person or the director asked for, added to the role's words. A role
    whose words give no age takes the one the script or a person's note states for it
    ("Jay is 19"), so its sheet and its fit check both know it (video 245). Never from a name
    alone: a role nothing describes, with no change, is refused."""
    words = words or role_words(db, project, slot)
    if not (words or change.strip()):
        name = cast_roles.short(slot.role) or slot.role
        raise HTTPException(409, blind([name]) + BLIND_FIX)
    words = words or slot.role
    if not check.AGE.search(words) and (age := cast_roles.stated_age(
            cast_roles.short(slot.role), _told(db, project))):  # fmt: skip
        words = f"{words.rstrip('. ')}, {age}"
    noted = f"{words.rstrip('. ')}. {change.strip()}" if change.strip() else words
    look = own_look(db, project, slot, noted)
    queue_sheet(db, user, look, SheetIn(), auto=auto)  # commits; a refusal adds nothing
    _cast(db, user, project, slot, look)
    db.commit()


def role_words(db: Session, project: Project, slot: ScriptCastSlot) -> str:
    """What a role looks like, for its sheet and its fit check, from the first of these that
    says it (video 284: Maya was drawn average-build in a hoodie from a shot's action, though
    the brief and the treatment said heavy-set in a satin dress):
    - the script's description of the role;
    - the brief's or a note's brackets after their name ("Maya (30s, heavy-set, satin dress)"),
      never a speaker's cue ("MAYA (quietly): …");
    - a "Maya, 30s, heavy-set, …" or "Maya is …" phrase in the brief, a note or the treatment;
    - the newest shots' sentences that show them (268: "Bruno, a stocky tan clay dog");
    - its script name when it says more than a name ("Kel, a 30-year-old trader"), or an age
      the script or a note states ("Jay is 19": video 245).
    Only sentences that name this role and no other one (284: one sentence about Granny and
    Maya became both their words); up to 300 characters. "" when nothing says anything."""
    if (slot.description or "").strip():
        return slot.description
    name = cast_roles.short(slot.role) or slot.role
    others = [s.role for s in _slots(db, project) if s.id != slot.id]
    brief = [*reversed([m.get("text") or "" for m in project.director_chat or []]),
             project.goal or ""]  # fmt: skip
    if said := _bracketed(name, brief) or _described(name, others, [*brief, *_story(db, project)]):
        return f"{slot.role.rstrip('. ')}, {said}"
    bd, refs = _newest(db, project), {f"slot:{slot.id}", f"char:{cast_roles.picked(project, slot)}"}
    said = [s for sc in (bd.data["scenes"] if bd else []) for shot in sc["shots"]
            if refs & set(shot["character_ids"])
            for s in _sentences(shot.get("action") or "") if _only(name, others, s)]  # fmt: skip
    out = ""
    for s in dict.fromkeys(said):
        if len(out) + len(s) >= 300:
            break
        out = f"{out} {s}".strip()
    if out or slot.role.partition(",")[2].strip():
        return out or slot.role
    age = cast_roles.stated_age(name, _told(db, project))
    return f"{slot.role.rstrip('. ')}, {age}" if age else ""


LOOKS = re.compile(  # words that say what someone looks like, not what they do
    r"(?i)\b(\d+s?|teen\w*|elderly|old|young|heavy-set|stocky|slim|thin|tall|short|curvy|fit|"
    r"toned|muscular|plump|build|\w*hair\w*|bald|beard\w*|dress|suit|shirt|hoodie|jacket|coat|"
    r"jeans|sweater|uniform|wearing|glasses|skin|freckled|blonde?|brunette|redhead)\b"
)


def _sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+", text or "")


def _only(name: str, others: list[str], sentence: str) -> bool:
    """The sentence names this role and no other one."""
    return cast_roles.named(name, sentence) and not any(cast_roles.named(o, sentence)
                                                       for o in others)  # fmt: skip


def _bracketed(name: str, texts: list[str]) -> str:
    """What the brief or a note says of someone in brackets after their name, in order
    ("Maya (30s, heavy-set, satin dress)", "from Bruno's point of view (a young pitbull…; his
    owner Maya, 30s)": up to the first ";"), never a speaker's cue: the name starting a line,
    its brackets then ending it or followed by ":" ("MAYA (quietly): I'm not pregnant.")."""
    cue = rf"(?im)^\s*{re.escape(name)}\s*\(([^()]*)\)\s*(:|$)"
    pattern = re.compile(
        rf"(?<!\w){re.escape(name)}(?:'s\b[^().;:]{{0,30}}?)?\s*\(([^()]{{2,200}})\)", re.I
    )
    for text in texts:
        cues = {m.start(1) for m in re.finditer(cue, text or "")}
        for found in pattern.finditer(text or ""):
            if found.start(1) not in cues:
                return found.group(1).split(";")[0].strip()
    return ""


def _described(name: str, others: list[str], texts: list[str]) -> str:
    """A "Maya, 30s, heavy-set, champagne-coloured satin dress: …" or "Maya is in her 30s,
    heavy-set" phrase that says how they look, in a sentence or clause about them alone ("his
    owner Maya, 30s" inside a bracket about Bruno), in order."""
    phrase = re.compile(rf"(?<!\w){re.escape(name)}(?:,| is| was)\s+([^:;.!?]{{2,200}})", re.I)
    for text in texts:
        for sentence in re.split(r"(?<=[.!?])\s+|[;()]", text or ""):
            if not _only(name, others, sentence):
                continue
            for found in phrase.finditer(sentence):
                if LOOKS.search(said := found.group(1).strip()):  # "is 19": "aged 19" (245)
                    return re.sub(r"^(\d+)(?=,|$)", r"aged \1", said)
    return ""


def _story(db: Session, project: Project) -> list[str]:
    """The treatment's words, as the director wrote them: its hook, logline and beats."""
    from app.director import treatment

    t = treatment(db, project) or {}
    beats = [b.get("picture") or "" for b in t.get("beats") or []]
    return [t.get("hook") or "", t.get("logline") or "", *beats, t.get("ending") or ""]


def _told(db: Session, project: Project) -> list[str]:
    """What the video's own words say about its people: its script, its brief and notes."""
    from app.routes.scripts import latest

    version = latest(db, project)
    notes = [m.get("text") or "" for m in project.director_chat or []]
    return [version.text if version else "", project.goal or "", *notes]


class PhotoIn(BaseModel):
    file_id: int


@router.post("/slots/{slot_id}/upload", response_model=list[AssetOut])
def upload_look(
    project_id: int,
    slot_id: int,
    body: PhotoIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Upload (the Cast tab, free): the picture becomes the role's look for this video only,
    never the brand's (rule 12). Its sheet is drawn from it later: by the director's run, or by
    Make a look on the role (priced there)."""
    from app.routes.files import get_file

    project = get_project(db, user, project_id)
    slot = _open_slot(db, project, slot_id)
    photo = get_file(db, user, body.file_id, "image")
    look = own_look(db, project, slot, slot.description, photo.id)
    _cast(db, user, project, slot, look)
    db.commit()
    return list_assets(project_id, user, db)


@router.delete("/slots/{slot_id}/script-lock", response_model=list[AssetOut])
def unlock_on_script(
    project_id: int, slot_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Unlock a role locked on its script (every version): its author or the owner, until the
    script is published."""
    project = get_project(db, user, project_id)
    slot = next((s for s in _slots(db, project) if s.id == slot_id), None)
    if not slot or not slot.library_item_id:
        raise HTTPException(404, "That role isn't locked on the script.")
    if not _script_editable(db, slot, user):
        raise HTTPException(403, f"{slot.role} is locked on the script. Only its author or "
                                 "the owner can unlock it, before it's published.")  # fmt: skip
    for video in _script_videos(db, slot.script_id):  # every video of it keeps the character
        if str(slot.id) not in (video.slot_cast or {}):
            video.slot_cast = {**(video.slot_cast or {}), str(slot.id): slot.library_item_id}
    slot.library_item_id = slot.sheet_file_id = slot.locked_by_id = None
    db.commit()
    return list_assets(project_id, user, db)


NOT_IN_LOOK = "This character isn't one that needs its own look in this video."
HAS_LOOK = "{} already has a look in this video's style."


@router.post(
    "/looks/{item_id}/copy", response_model=list[AssetOut], dependencies=[Depends(generation_on)]
)
def make_look_copy(
    project_id: int, item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Make a {look} look for this video (flows ST2; paid from this video's budget): a Cast &
    places character with no sheet in the video's look gets its own copy here (`_copy`). Used
    in this video only, never saved to Cast & places (rule 12); its library character and its
    locked roles stay as they are."""
    project = get_project(db, user, project_id)
    item = db.get(LibraryItem, item_id)
    if item is None or item.workspace_id != project.workspace_id or item.archived:
        raise HTTPException(404, "No such character.")
    if not _other_look(project, item):
        raise HTTPException(409, NOT_IN_LOOK)
    copy = look_copy(db, project, item)
    if sheet_for(db, project, item) or (copy and copy.sheet_look == project.look):
        raise HTTPException(409, HAS_LOOK.format(item.name))
    _copy(db, user, project, item)
    return list_assets(project_id, user, db)


def _copy(db: Session, user: User, project: Project, item: LibraryItem, auto=False) -> None:
    """A Cast & places character's look for this video, drawn in the video's look from its
    approved sheet (who they are: face, build, outfit and signature items), else its photo.
    A photoreal style (Movie, UGC) draws from the photo when there is one: a sheet is a
    drawing."""
    real = looks.base(project.look) in model_map.PHOTOREAL and item.source_photo_file_id
    house = item.sheet_file_id if item.sheet_approved and not real else None
    new = LibraryItem(workspace_id=project.workspace_id, kind=Kind.character, name=item.name,
                      notes=item.notes, short_description=item.short_description or "",
                      source_photo_file_id=house or item.source_photo_file_id,
                      owner_project_id=project.id, sheet_look=project.look)  # fmt: skip
    db.add(new)
    db.flush()
    project.look_copies = {**(project.look_copies or {}), str(item.id): new.id}
    queue_sheet(db, user, new, SheetIn(), auto=auto)  # commits; a refusal adds nothing


def missing_copies(db: Session, project: Project) -> list[LibraryItem]:
    """The Cast & places characters the newest shots show (cast or locked in a role, or named
    in a shot) with no sheet in this video's look and no look of their own here yet: make-
    missing makes each one (`_copy`), so a brand character with only a House sheet never
    stops a video in another style. Made once in each look, never again by itself (Not now
    keeps it out); a copy made in another look before a style switch counts as none."""
    bd = _newest(db, project)
    if bd is None or (project.look or "house") == "house":
        return []
    shown = list(dict.fromkeys(c for s in bd.data["scenes"] for x in s["shots"]
                               for c in x["character_ids"]))  # fmt: skip
    picks = {f"slot:{s.id}": cast_roles.pick(db, project, s) for s in _slots(db, project)}
    ids = [picks.get(r) if r.startswith("slot:") else int(r[5:]) if r.startswith("char:")
           else None for r in shown]  # fmt: skip
    out = []
    for item in (db.get(LibraryItem, i) for i in dict.fromkeys(i for i in ids if i)):
        if (item is not None and not item.archived and _other_look(project, item)
                and not _copied(db, project, item)
                and (item.sheet_approved and item.sheet_file_id or item.source_photo_file_id)
                and not sheet_for(db, project, item)):  # fmt: skip
            out.append(item)
    return out


def _copied(db: Session, project: Project, item: LibraryItem) -> bool:
    """Not now was said to its look here, or its copy is a live one in this video's look."""
    if (project.look_copies or {}).get(str(item.id), 0) is None:
        return True
    copy = look_copy(db, project, item)
    return bool(copy and copy.sheet_look == project.look)


class MadeOut(BaseModel):
    looks: int  # looks Assets made by itself for this video
    credits_used: int  # what they really cost, whole credits: sheets, checks and any redo
    drawing: bool  # some are still being made or checked: the figure may still grow


class MissingLooksOut(BaseModel):
    slot_ids: list[int]  # roles in this video's shots with no character and no look made yet
    roles: list[str]
    credits: int  # "up to": each look's sheet, check and one redo, held at the press
    usual_credits: int = 0  # "Usually N": the sheets and checks, no redo
    made: MadeOut | None = None  # "Made 3 looks · 7 credits", once Assets has made some
    reason: str | None = None  # why they can't all be made (plain), or null when they fit


def _flagged(db: Session, project: Project) -> set[int]:
    """Roles that may be a locked or cast one by another name (`merge_roles.video_pairs`):
    the look gate counts them as that role, so they never hold the video up (rule 22)."""
    bd = _newest(db, project)
    pairs = merge_roles.video_pairs(db, project, Breakdown.model_validate(bd.data) if bd else None)
    return {slot.id for slot, _, sure in pairs if not sure}


def _missing(db: Session, project: Project) -> list[ScriptCastSlot]:
    """The roles Assets makes looks for by itself (Reed, 2026-10-26): every cast slot (a main
    or recurring role; background people are never slots) that the newest breakdown's shots
    show, with no character picked and no look made for it here. A look the editor removed,
    or a role they said Not now to (kept as no look), is never made again by itself."""
    bd = _newest(db, project)
    shown = {
        c for s in (bd.data["scenes"] if bd else []) for x in s["shots"] for c in x["character_ids"]
    }
    flagged = _flagged(db, project)  # maybe another role: its look waits for the editor
    return [
        s
        for s in _slots(db, project)
        if (
            cast_roles.pick(db, project, s) is None  # a deleted look counts as none
            and s.id not in flagged
            and str(s.id) not in project.slot_looks
            or _undrawn(db, project, s)
        )
        and {f"slot:{s.id}", f"char:{cast_roles.picked(project, s)}"} & shown
    ]


def _undrawn(db: Session, project: Project, slot) -> LibraryItem | None:
    """The role's look made here from a picture someone gave in the chat (an ask's upload,
    rule 12) whose sheet isn't drawn or being drawn: make-missing draws it from that photo."""
    item = db.get(LibraryItem, project.slot_looks.get(str(slot.id)) or 0)
    if not (item and item.owner_project_id == project.id and item.source_photo_file_id):
        return None
    drawing = db.scalar(select(Job.id).where(
        Job.workspace_id == project.workspace_id,  # its workspace's jobs, never the table's
        Job.input["library_item_id"].as_integer() == item.id,
        Job.status.in_((*COUNTED, JobStatus.needs_owner_approval))).limit(1))  # fmt: skip
    return None if item.sheet_file_id or drawing else item


def missing_places(db: Session, project: Project) -> list[LibraryItem]:
    """The places made for this video that its newest shots show with no look drawn or being
    drawn: the director's make_looks draws them (from the uploaded photo, if one was given)."""
    bd = _newest(db, project)
    refs = {s.get("place_id") for sc in (bd.data["scenes"] if bd else []) for s in sc["shots"]}
    items = [db.get(LibraryItem, int(r.split(":")[1])) for r in sorted(r for r in refs if r)]
    return [i for i in items if i is not None and i.owner_project_id == project.id
            and not i.archived and not i.sheet_file_id and not _waiting_sheets(i)]  # fmt: skip


def _missing_out(db: Session, user: User, project: Project) -> MissingLooksOut:
    if breakdown.complete_cast(db, project):  # as when Assets opens: every role in its shots
        db.commit()
    slots, places = _missing(db, project), missing_places(db, project)
    copies = missing_copies(db, project)  # a brand character in this video's look
    total = look_price(db, project.workspace_id) * (len(slots) + len(copies))
    total += sum((press_price(db, p) for p in places), Decimal(0))
    n = len(slots) + len(copies) + len(places)
    why = fits(db, project, user, total) if n else ""
    said = f"Making {'a look' if n == 1 else f'{n} looks'} (up to {price(total)} credits) {why}"
    usual = look_usual(db, project.workspace_id) * len(slots)
    usual += sheet_price(db, project.workspace_id) * len(copies)  # from its sheet: unchecked
    usual += sum((press_price(db, p) for p in places), Decimal(0))  # a place isn't checked
    return MissingLooksOut(
        slot_ids=[s.id for s in slots],
        roles=[cast_roles.short(s.role) or s.role for s in slots]
        + [c.name for c in copies]
        + [p.name for p in places],
        credits=price(total) if n else 0,
        usual_credits=price(usual) if n else 0,
        reason=said if why else None,
        made=_made(db, project),
    )


def _made(db: Session, project: Project) -> MadeOut | None:
    """The looks Assets made by itself (make-missing) and their real cost: the jobs it started
    for them (sheet, check, the one redo), stopped ones not counted."""
    own = {v for v in [*project.slot_looks.values(), *(project.look_copies or {}).values()] if v}
    jobs = [
        j
        for j in db.scalars(
            select(Job).where(  # its own rows only, never every turn's prompt
                Job.project_id == project.id,
                Job.status.in_(COUNTED),
                Job.input["auto_made"].as_boolean(),
            )
        )  # fmt: skip
        if j.input.get("library_item_id") in own
    ]
    if not jobs:
        return None
    return MadeOut(
        looks=len({j.input["library_item_id"] for j in jobs}),
        credits_used=price(sum((j.credits for j in jobs), Decimal(0))),
        drawing=any(j.status != JobStatus.succeeded for j in jobs),
    )


@router.get("/missing-looks", response_model=MissingLooksOut)
def missing_looks(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """What opening Assets will make by itself, with its price and, if it doesn't fit, why."""
    return _missing_out(db, user, get_project(db, user, project_id))


@router.post(
    "/make-missing",
    response_model=list[AssetOut],
    dependencies=[Depends(generation_on)],
)
def make_missing_looks(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Make a look for every role that has none (`_missing`), each for this video only, paid
    from its budget or the editor's week. All or none: if they don't all fit, nothing is made
    and the plain reason comes back (409). Each sheet still needs the editor's Approve (or a
    Redo, or a swap) before Storyboard; Storyboard refuses until then. A role nothing
    describes stops it too (409, saying which)."""
    make_missing(db, user, get_project(db, user, project_id), whole=True)
    return list_assets(project_id, user, db)


def make_missing(db: Session, user: User, project: Project, told=("", ""),
                 whole=False) -> tuple[int, list]:  # fmt: skip
    """`make_missing_looks`; `told`: a role's name and what it looks like, as the director gives
    it, added to the plan's words for them (video 294: "Maya, 30s" alone lost her messy bun
    and grey sleep tee). A role nothing describes is left without a look, never drawn from its
    name alone (video 268); `whole`: then nothing is made. How many looks it started, and the
    roles it left."""
    out = _missing_out(db, user, project)
    if out.reason:
        raise HTTPException(409, out.reason)
    slots = [(s, None if _undrawn(db, project, s) else role_words(db, project, s),
              told[1].strip() if cast_roles.same(told[0], s.role) else "")
             for s in _missing(db, project)]  # fmt: skip
    left = [cast_roles.short(s.role) or s.role for s, words, said in slots
            if words == "" and not said]  # fmt: skip
    if left and whole:
        raise HTTPException(409, blind(left) + BLIND_FIX)
    made = 0
    for slot, words, said in slots:
        if words is None:  # from the photo given for it
            queue_sheet(db, user, _undrawn(db, project, slot), SheetIn(), auto=True)
        elif words or said:
            _make_look(db, user, project, slot, auto=True, words=words or said,
                       change=said if words else "")  # fmt: skip
        else:
            continue
        made += 1
    for item in missing_copies(db, project):  # a brand character, in this video's look
        _copy(db, user, project, item, auto=True)
        made += 1
    for place in missing_places(db, project):  # a place made for this video
        queue_sheet(db, user, place, SheetIn(), auto=True)
        made += 1
    return made, left


@router.post("/missing-looks/decline", response_model=MissingLooksOut)
def decline_missing_looks(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Not now: the roles waiting for a look are left for the editor's own Make a look, and
    opening Assets never makes them by itself again."""
    project = get_project(db, user, project_id)
    waiting = {str(s.id): None for s in _missing(db, project)}
    project.slot_looks = {**project.slot_looks, **waiting}
    copies = {str(c.id): None for c in missing_copies(db, project)}  # Make a look stays
    project.look_copies = {**(project.look_copies or {}), **copies}
    db.commit()
    return _missing_out(db, user, project)


class MergeIn(BaseModel):
    into_slot_id: int


class VideoMerged(MergePreview):
    token: int  # for Undo
    assets: list[AssetOut]


def _pair(db: Session, project: Project, slot_id: int, into_id: int):
    slots = {s.id: s for s in _slots(db, project)}
    if slot_id not in slots or into_id not in slots:
        raise HTTPException(404, "That role isn't in this video.")
    if slot_id == into_id:
        raise HTTPException(422, "A role can't be merged into itself.")
    return slots[slot_id], slots[into_id]


def _preview(db: Session, project: Project, slot, into) -> tuple[dict, Breakdown | None]:
    """What a merge on this video moves (its shots, and the script lines they speak), and the
    newest breakdown with them moved."""
    bd = _newest(db, project)
    plan = Breakdown.model_validate(bd.data) if bd else None
    shots = [s for sc in plan.scenes for s in sc.shots] if plan else []
    spoken = [n for s in shots if s.speaker and cast_roles.same(s.speaker, slot.role)
              for n in s.script_lines]  # fmt: skip
    moved = cast_roles.merge_shots(db, project, plan, slot, into) if plan else []
    letter = merge_roles.LETTERS[db.get(ScriptDraft, project.script_draft_id).slot]
    look = db.get(LibraryItem, cast_roles.picked(project, slot) or 0)
    unused = look is not None and look.id != cast_roles.picked(project, into)
    out = {"moved": {"shots": moved, "lines": [{"version": letter, "line": n} for n in spoken]},
           "look_unused": {"name": look.name} if unused else None}  # fmt: skip
    return out, plan


@router.get("/slots/{slot_id}/merge/preview", response_model=MergePreview)
def merge_preview(
    project_id: int,
    slot_id: int,
    into: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """What merging this role into `into` would move on this video, before it's done."""
    project = get_project(db, user, project_id)
    return _preview(db, project, *_pair(db, project, slot_id, into))[0]


@router.post("/slots/{slot_id}/merge", response_model=VideoMerged)
def merge(
    project_id: int,
    slot_id: int,
    body: MergeIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Merge this role into another on this video only (merge-roles.md §1): its shots and their
    lines go to the other, and its look is left unused. The script's cast stays as it is.
    Free: stills that showed its look are marked out of date, never redrawn by themselves."""
    project = get_project(db, user, project_id)
    slot, into = _pair(db, project, slot_id, body.into_slot_id)
    out, plan = _preview(db, project, slot, into)
    bd = _newest(db, project)
    saved = {"slot_merged": project.slot_merged or {}, "slot_cast": project.slot_cast or {},
             "cast_ids": project.cast_ids or [], "breakdown": bd.data if bd else None}  # fmt: skip
    old = (project.slot_cast or {}).get(str(slot.id))
    project.slot_cast = {k: v for k, v in (project.slot_cast or {}).items() if k != str(slot.id)}
    project.slot_merged = {**(project.slot_merged or {}), str(slot.id): into.id}
    still = {cast_roles.picked(project, s) for s in _slots(db, project)}
    project.cast_ids = [c for c in project.cast_ids or [] if c != old or c in still]
    if bd:  # the shots move first, while the role's look still names them
        _resave(db, user, project, bd, plan.model_dump())
        clip_prompts.follow(db, project, user)
    made = _newest(db, project)
    saved["made"] = made.id if made else None  # Undo only while the plan is still this one
    draft = db.get(ScriptDraft, project.script_draft_id)
    record = CastMerge(workspace_id=project.workspace_id, script_id=draft.script_id,
                       project_id=project.id, data=saved)  # fmt: skip
    db.add(record)
    db.commit()
    return {**out, "token": record.id, "assets": list_assets(project_id, user, db)}


def _recast_only(db: Session, project: Project, made: dict, now: dict, data: dict):
    """Who now plays whom ({"slot:3": "char:9"}) when the shots changed since the merge only
    by roles getting their looks (Assets making the missing ones): each swap puts a role's
    own look where the role (slot:N) or its look at the merge was. None for any other change,
    such as another person in a shot (QA on #614)."""
    a, b = Breakdown.model_validate(made), Breakdown.model_validate(now)
    blank = {"scenes": {"__all__": {"shots": {"__all__": {"character_ids"}}}}}
    if a.model_dump(exclude=blank) != b.model_dump(exclude=blank):
        return None
    was = {f"slot:{k}": f"char:{v}" for k, v in data["slot_cast"].items()}
    own = {cast_roles.ref(db, project, s): {f"slot:{s.id}", was.get(f"slot:{s.id}")}
           for s in _slots(db, project)}  # fmt: skip
    swaps = cast_roles._swaps(a, b).values()
    if None in swaps or any(
        old not in own.get(new, ()) for one in swaps for old, new in one.items()
    ):
        return None
    return {old: new for one in swaps for old, new in one.items()}


def _undoable(db: Session, project: Project, data: dict) -> dict | None:
    """Who now plays whom since a merge ({} if the shots are as it left them), or None when
    the shots changed otherwise and it can't be undone."""
    if not (now := _newest(db, project)) or now.id == data.get("made"):
        return {}
    made = db.get(BreakdownVersion, data.get("made") or 0)
    return _recast_only(db, project, made.data, now.data, data) if made else None


def _put_back(db: Session, project: Project, slot_id: int, into_id: int, moved: list) -> dict:
    """The newest shots with a role merged by itself back in the shots it was moved from, when
    they changed since (rule 9: its Undo is the video's, not one breakdown version's)."""
    bd = Breakdown.model_validate(_newest(db, project).data)
    into = cast_roles.ref(db, project, db.get(ScriptCastSlot, into_id))
    for shot in (s for sc in bd.scenes for s in sc.shots if s.id in moved):
        shot.character_ids = [f"slot:{slot_id}" if r == into else r for r in shot.character_ids]
    return bd.model_dump()


@router.post("/merge/undo", response_model=list[AssetOut])
def undo_merge(
    project_id: int, body: UndoIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Put a role merged on this video back, with its shots, lines and look as they were."""
    project = get_project(db, user, project_id)
    record = db.get(CastMerge, body.token)
    if record is None or record.project_id != project.id:
        raise HTTPException(404, "There's nothing to undo here any more.")
    data = record.data
    if (swap := _undoable(db, project, data)) is None and (pair := data.get("auto")):
        swap, data = {}, {**data, "breakdown": _put_back(db, project, *pair, data.get("moved", []))}
    if swap is None:
        raise HTTPException(
            409, "This can't be undone any more: the shots were changed after the merge."
        )
    # Looks given to other roles since (Assets making the missing ones) stay.
    merged = {k for k in project.slot_merged or {} if k not in data["slot_merged"]}
    project.slot_merged = {k: v for k, v in project.slot_merged.items() if k not in merged}
    project.slot_cast = {**{k: v for k, v in project.slot_cast.items() if k not in merged},
                         **{k: v for k, v in data["slot_cast"].items() if k in merged}}  # fmt: skip
    project.cast_ids = sorted({*project.cast_ids, *data["cast_ids"]})
    if pair := data.get("auto"):  # merged by itself: never again on this video
        project.cast_apart = [*(project.cast_apart or []), sorted(pair)]
    bd = _newest(db, project)
    if bd and data["breakdown"]:
        text = json.dumps(data["breakdown"])
        for was, now_ref in swap.items():
            text = text.replace(f'"{was}"', f'"{now_ref}"')
        _resave(db, user, project, bd, json.loads(text))
        clip_prompts.follow(db, project, user)
    db.delete(record)
    db.commit()
    return list_assets(project_id, user, db)


@router.get("/maybe-same", response_model=list[SamePair])
def maybe_same(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The script's roles that may be one person, less those merged or kept apart on this
    video."""
    project = get_project(db, user, project_id)
    if not project.script_draft_id:
        return []
    script = db.get(Script, db.get(ScriptDraft, project.script_draft_id).script_id)
    here = {s.id for s in _slots(db, project)}
    apart = {frozenset(p) for p in project.cast_apart or []}
    bd = _newest(db, project)  # a role that may be a locked one by another name ("Girl")
    plan = Breakdown.model_validate(bd.data) if bd else None
    unsure = [{"a_slot_id": b.id, "b_slot_id": a.id, "into_slot_id": b.id,
               "why": "Their shots show the same person."}
              for a, b, sure in merge_roles.video_pairs(db, project, plan) if not sure]  # fmt: skip
    auto = []  # merged by itself, with Undo whatever the shots did since (QA-2)
    for r in db.scalars(select(CastMerge).where(CastMerge.project_id == project.id)):
        roles = [db.get(ScriptCastSlot, i) for i in r.data.get("auto") or [0]]
        if None not in roles:  # Undo stays while the record does (rule 9)
            pair, (one, into) = r.data["auto"], (cast_roles.short(x.role) for x in roles)
            auto.append({"a_slot_id": pair[1], "b_slot_id": pair[0], "into_slot_id": pair[1],
                         "why": f"{one} is {into} in this video, so they're one role.",
                         "undo_token": r.id})  # fmt: skip
    return auto + [p for p in [*merge_roles.maybe_same(db, script), *unsure]
                   if {p["a_slot_id"], p["b_slot_id"]} <= here
                   and frozenset((p["a_slot_id"], p["b_slot_id"])) not in apart]  # fmt: skip


def _apart(project_id: int, body: PairIn, user: User, db: Session, undo: bool) -> list[dict]:
    project = get_project(db, user, project_id)
    here = {s.id for s in _slots(db, project)}
    if body.a_slot_id == body.b_slot_id or not {body.a_slot_id, body.b_slot_id} <= here:
        raise HTTPException(404, "Those two roles aren't both in this video.")
    pairs = [p for p in project.cast_apart or [] if set(p) != {body.a_slot_id, body.b_slot_id}]
    project.cast_apart = pairs if undo else [*pairs, sorted((body.a_slot_id, body.b_slot_id))]
    db.commit()
    return maybe_same(project_id, user, db)


@router.post("/maybe-same/dismiss", response_model=list[SamePair])
def dismiss(
    project_id: int, body: PairIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """They're different, on this video only: the pair isn't flagged here again. The script's
    Cast is untouched. Free."""
    return _apart(project_id, body, user, db, undo=False)


@router.delete("/maybe-same/dismiss", response_model=list[SamePair])
def undo_dismiss(
    project_id: int, body: PairIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Undo "They're different" on this video."""
    return _apart(project_id, body, user, db, undo=True)
