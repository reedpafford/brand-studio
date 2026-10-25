"""The Script Library (workflow v2): scripts owned by a brand, each with up to three versions
(the original in slot 0 and up to two variations). Rules: `app/script_library.py`."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app import script_library as lib
from app.auth import current_user, user_name
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.files import StoredFile
from app.models.projects import Project
from app.models.script_library import Script, ScriptCastSlot, ScriptDraft, ScriptDraftText
from app.reel import reel_link
from app.routes.brands import get_brand
from app.routes.references import catalogue
from app.routes.references import find as find_reference
from app.routes.script_cast import SlotOut, slots
from app.routes.script_import import UNTITLED, prepare
from app.routes.scripts import ScriptText
from app.schemas import LongText

router = APIRouter(prefix="/scripts", tags=["script library"])
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Slot = Annotated[int, Field(ge=0, le=lib.MAX_SLOT)]


class ScriptIn(BaseModel):
    brand_id: int
    title: Title
    description: LongText = ""
    notes: LongText = ""
    reference_id: str | None = None  # a reel from GET /references
    reference_replace: LongText = ""
    new_lines: bool | None = None  # write new lines in the reel's style, not its own
    text: Annotated[str, StringConstraints(max_length=50_000)] = ""  # the original, if ready


class BulkRow(ScriptIn):
    title: Title | None = None  # needed unless the row is a reel link ("Untitled reel")
    reel_url: Annotated[str, StringConstraints(max_length=500)] | None = None  # an Instagram reel


class BulkIn(BaseModel):
    """Bulk create (Reed): titles, descriptions and an optional reel only; nothing is written
    until "Write all". A row with a reel link fetches and prepares that reel (free)."""

    scripts: list[BulkRow] = Field(min_length=1, max_length=50)


class ScriptPatch(BaseModel):
    title: Title | None = None
    description: LongText | None = None
    notes: LongText | None = None
    reference_id: str | None = None
    reference_replace: LongText | None = None
    new_lines: bool | None = None  # until version A is approved


class DraftIn(BaseModel):
    text: ScriptText
    target_seconds: int | None = Field(None, gt=0, le=3600)  # null: the breakdown decides


class Person(BaseModel):
    id: int
    name: str


class VersionSummary(BaseModel):
    slot: int
    status: str  # draft | approved | in_production | clips_ready | failed | done
    title: str
    seconds: int  # the saved breakdown's, else the target, else spoken words at 4.8 a second
    project_id: int | None  # the video made from it
    editor: Person | None = None  # who's making it (reserved it), once in production


class VersionOut(VersionSummary):
    text: str
    words: int
    target_seconds: int | None
    premise: str
    changes: list[str]
    problems: list[str]
    changed_lines: list[str]  # the reel's lines rewritten for the brand swap
    has_breakdown: bool
    approved_at: datetime | None
    variation_of: str | None = None  # "A": a variation of the original; null for the original
    estimate_credits: float = 0  # to make it: 1 credit a second (480p), from its length
    clips: int = 0  # in the saved breakdown
    planned_by: Person | None = None  # who saved the breakdown


class ScriptRow(BaseModel):
    id: int
    brand_id: int
    title: str
    description: str
    reference_id: str | None
    published: bool
    status: str  # draft | published | in_production | done
    created_by_id: int | None
    created_by_name: str
    created_at: datetime
    versions: list[VersionSummary]
    versions_left: int  # approved versions not produced yet
    poster_file_id: int | None = None  # the first still of its newest finished video
    reference_name: str | None = None  # the reel it adapts, by name
    reel_imported: bool = False  # adapts its own imported reel, not a catalogue one


class ScriptOut(ScriptRow):
    notes: str
    reference_replace: str
    new_lines: bool
    versions: list[VersionOut]
    cast: list[SlotOut]  # roles shared by every version, locked or not


def _person(db: Session, user_id: int | None) -> Person | None:
    user = db.get(User, user_id) if user_id else None
    return Person(id=user.id, name=user.name) if user else None


def _version(db: Session, draft: ScriptDraft, full: bool) -> VersionSummary | VersionOut:
    status, project_id = lib.version_status(db, draft)
    base = dict(
        slot=draft.slot,
        status=status,
        title=draft.title,
        seconds=lib.seconds(draft),
        project_id=project_id,
        editor=_person(db, draft.reserved_by_id) if project_id else None,
    )
    if not full:
        return VersionSummary(**base)
    return VersionOut(
        **base,
        text=draft.text,
        words=len(draft.text.split()),
        target_seconds=draft.target_seconds,
        premise=draft.premise,
        changes=draft.changes,
        problems=draft.problems,
        changed_lines=draft.changed_lines or [],
        has_breakdown=draft.breakdown is not None,
        approved_at=draft.approved_at,
        variation_of="A" if draft.slot else None,
        estimate_credits=lib.seconds(draft),
        clips=len((draft.breakdown or {}).get("clips", [])),
        planned_by=_person(db, draft.breakdown_by_id) if draft.breakdown else None,
    )


def _out(db: Session, script: Script, full: bool = True) -> ScriptRow | ScriptOut:
    versions = [_version(db, d, full) for d in lib.drafts(db, script)]
    statuses = [v.status for v in versions]
    row = dict(
        id=script.id,
        brand_id=script.brand_id,
        title=script.title,
        description=script.description,
        reference_id=script.reference_id,
        reel_imported=script.reference_breakdown is not None,
        published=script.published,
        status=lib.script_status(script, statuses),
        created_by_id=script.created_by_id,
        created_by_name=user_name(db, script.created_by_id),
        created_at=script.created_at,
        versions=versions,
        versions_left=statuses.count("approved"),
    )
    if not full:
        return ScriptRow(**row)
    return ScriptOut(
        **row,
        notes=script.notes,
        reference_replace=script.reference_replace,
        new_lines=script.new_lines,
        cast=slots(db, script),
    )


def _check_reference(request: Request, ref_id: str | None) -> None:
    if ref_id:
        find_reference(request, ref_id)  # 404 if it isn't in the catalogue


SORTS = {
    "newest": lambda r: -r.id,
    "title": lambda r: r.title.lower(),
    "seconds": lambda r: max((v.seconds for v in r.versions), default=0),
    "versions_left": lambda r: -r.versions_left,
}


@router.get("", response_model=list[ScriptRow])
def list_scripts(
    request: Request,
    response: Response,
    brand_id: int | None = None,
    status: str | None = None,
    q: str = "",
    reference: bool | None = None,  # true: adapted from a reel; false: not
    reference_id: str | None = None,  # adapted from this reel
    sort: Literal["newest", "title", "seconds", "versions_left"] = "newest",
    limit: int | None = Query(None, ge=1, le=200),  # a page; X-Total-Count has the total
    offset: int = Query(0, ge=0),
    versions_left: int | None = None,  # at least this many versions left to produce
    min_seconds: int | None = None,
    max_seconds: int | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """The Script Library: what the caller may see, newest first, filtered."""
    query = select(Script).where(Script.workspace_id == user.workspace_id, ~Script.archived)
    if not user.is_owner:
        query = query.where(or_(Script.published, Script.created_by_id == user.id))
    if brand_id is not None:
        query = query.where(Script.brand_id == brand_id)
    if reference_id is not None:
        query = query.where(Script.reference_id == reference_id)
    if reference is not None:
        adapts = or_(Script.reference_id.is_not(None), Script.reference_breakdown.is_not(None))
        query = query.where(adapts if reference else ~adapts)
    if q.strip():
        like = f"%{q.strip()}%"
        in_text = select(ScriptDraft.script_id).where(ScriptDraft.text.ilike(like))
        query = query.where(
            or_(Script.title.ilike(like), Script.description.ilike(like), Script.id.in_(in_text))
        )
    computed = status or {versions_left, min_seconds, max_seconds} != {None}
    if not computed and sort in ("newest", "title"):  # page in the query: build only the page
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        order = [func.lower(Script.title)] if sort == "title" else []
        query = query.order_by(*order, Script.id.desc()).offset(offset).limit(limit)
        rows = [_out(db, s, full=False) for s in db.scalars(query)]
    else:  # status, versions left and seconds come from each script's versions
        rows = [_out(db, s, full=False) for s in db.scalars(query.order_by(Script.id.desc()))]
        if status:
            rows = [r for r in rows if r.status == status]
        if versions_left is not None:
            rows = [r for r in rows if r.versions_left >= versions_left]
        if min_seconds is not None or max_seconds is not None:
            lo, hi = min_seconds or 0, max_seconds or 10**6
            rows = [r for r in rows if any(lo <= v.seconds <= hi for v in r.versions)]
        rows.sort(key=SORTS[sort])
        total = len(rows)
        rows = rows[offset : offset + limit] if limit else rows[offset:]
    response.headers["X-Total-Count"] = str(total)
    names = {
        ref.id: ref.name for ref, _ in catalogue(request.app.state.settings.references_dir).values()
    }
    for row in rows:
        script = db.get(Script, row.id)
        row.poster_file_id = lib.poster(db, script)
        row.reference_name = names.get(row.reference_id) if row.reference_id else None
        if script.reference_breakdown:
            row.reference_name = lib.reel_name(script.reference_breakdown)
    return rows


@router.post("", response_model=ScriptOut, status_code=201)
def create_script(
    body: ScriptIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    get_brand(db, user, body.brand_id)
    _check_reference(request, body.reference_id)
    script = Script(
        workspace_id=user.workspace_id,
        created_by_id=user.id,
        **body.model_dump(exclude={"text"}, exclude_none=True),
    )
    db.add(script)
    db.flush()
    db.add(ScriptDraft(script_id=script.id, slot=0, text=body.text.strip()))
    db.commit()
    return _out(db, script)


@router.post("/bulk", response_model=list[ScriptRow], status_code=201)
def create_many(
    body: BulkIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Up to 50 scripts at once, all or none: a plain error names the first bad row."""
    links = []
    for n, item in enumerate(body.scripts, 1):
        try:
            get_brand(db, user, item.brand_id)
            _check_reference(request, item.reference_id)
            links.append(item.reel_url and reel_link(item.reel_url))
            if item.reel_url and not links[-1]:
                raise HTTPException(422, "That isn't an Instagram reel link.")
            if item.reel_url and item.reference_id:
                raise HTTPException(422, "Pick a catalogue reel or a reel link, not both.")
            if not (item.title or item.reel_url):
                raise HTTPException(422, "Give it a title.")
        except HTTPException as exc:
            raise HTTPException(exc.status_code, f"Row {n}: {exc.detail}") from None
    made = []
    for item, url in zip(body.scripts, links, strict=True):
        script = Script(
            workspace_id=user.workspace_id,
            created_by_id=user.id,
            **item.model_dump(exclude={"text", "reel_url", "title"}, exclude_none=True),
            title=item.title or UNTITLED,
        )
        db.add(script)
        db.flush()
        db.add(ScriptDraft(script_id=script.id, slot=0, text=item.text.strip()))
        made.append(script)
        if url:  # each its own free prep job; the reel worker fetches them one at a time
            prepare(db, user, script, {"source": "link", "url": url}, {"url": url})
    db.commit()
    return [_out(db, s, full=False) for s in made]


@router.get("/{script_id}", response_model=ScriptOut)
def read_script(script_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _out(db, lib.get_script(db, user, script_id))


@router.patch("/{script_id}", response_model=ScriptOut)
def update_script(
    script_id: int,
    body: ScriptPatch,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    script = lib.editable(user, lib.get_script(db, user, script_id))
    values = body.model_dump(exclude_unset=True)
    if "reference_id" in values:
        _check_reference(request, values["reference_id"])
    if values.get("new_lines") is not None and any(
        d.slot == 0 and d.status == "approved" for d in lib.drafts(db, script)
    ):
        raise HTTPException(409, "Version A is approved, so its lines are final.")
    for field, value in values.items():
        if value is not None or field == "reference_id":
            setattr(script, field, value)
    db.commit()
    return _out(db, script)


@router.delete("/{script_id}", status_code=204)
def delete_script(
    script_id: int,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Delete it, or archive it if a video was made from any version (videos stay)."""
    script = lib.get_script(db, user, script_id)
    if not (user.is_owner or (script.created_by_id == user.id and not script.published)):
        raise HTTPException(403, "Only its author (before publishing) or the owner can remove it.")
    ids = [d.id for d in lib.drafts(db, script)]
    if ids and db.scalar(select(Project.id).where(Project.script_draft_id.in_(ids)).limit(1)):
        script.archived = True
    else:
        db.execute(delete(ScriptCastSlot).where(ScriptCastSlot.script_id == script.id))
        db.execute(delete(ScriptDraftText).where(ScriptDraftText.draft_id.in_(ids)))
        db.execute(delete(ScriptDraft).where(ScriptDraft.script_id == script.id))
        reel = script.reel or {}
        db.delete(script)
        for key in ("video_file_id", "contact_file_id"):  # an imported reel's own files
            if (stored := db.get(StoredFile, reel.get(key) or 0)) is not None:
                request.app.state.storage.delete(stored.key)
                db.delete(stored)
    db.commit()


@router.put("/{script_id}/drafts/{slot}", response_model=ScriptOut)
def write_draft(
    script_id: int,
    slot: Slot,
    body: DraftIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Write or edit a version's words (draft only). Slot 0 is the original; 1 and 2 are
    variations, written here by hand or by the variations step."""
    script = lib.editable(user, lib.get_script(db, user, script_id))
    draft = db.scalar(
        select(ScriptDraft).where(ScriptDraft.script_id == script.id, ScriptDraft.slot == slot)
    )
    if draft and draft.status == "approved":
        raise HTTPException(409, "These words are approved and can't change.")
    if not draft:
        draft = ScriptDraft(script_id=script.id, slot=slot)
        db.add(draft)
    lib.keep_text(db, draft, body.text, "edit", user.id)
    draft.text, draft.target_seconds = body.text, body.target_seconds
    db.commit()
    return _out(db, script)


@router.post("/{script_id}/drafts/{slot}/approve", response_model=ScriptOut)
def approve_draft(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Lock a version's words for good."""
    script = lib.editable(user, lib.get_script(db, user, script_id))
    draft = lib.get_draft(db, script, slot)
    if not draft.text.strip():
        raise HTTPException(422, "Write the script first.")
    if draft.status != "approved":
        draft.status, draft.approved_at, draft.approved_by_id = "approved", utcnow(), user.id
        db.commit()
    return _out(db, script)


@router.delete("/{script_id}/drafts/{slot}/approve", response_model=ScriptOut)
def unapprove_draft(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Undo approval while the script isn't published: the words can change again."""
    script = lib.editable(user, lib.get_script(db, user, script_id))
    draft = lib.get_draft(db, script, slot)
    if draft.status == "approved":
        draft.status, draft.approved_at, draft.approved_by_id = "draft", None, None
        db.commit()
    return _out(db, script)


class EarlierText(BaseModel):
    id: int
    text: str
    title: str
    words: int
    source: str  # edit | variations | write: what replaced it
    created_at: datetime  # when it was replaced
    created_by_name: str


@router.get("/{script_id}/drafts/{slot}/history", response_model=list[EarlierText])
def draft_history(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """A version's earlier texts, newest first (the newest 20). To bring one back, write it
    as the words. Only the script's author and the owner see them; others see the final words."""
    script = lib.get_script(db, user, script_id)
    if not (user.is_owner or script.created_by_id == user.id):
        raise HTTPException(403, "Only the script's author and the owner see its earlier texts.")
    draft = lib.get_draft(db, script, slot)
    rows = db.scalars(
        select(ScriptDraftText)
        .where(ScriptDraftText.draft_id == draft.id)
        .order_by(ScriptDraftText.id.desc())
    )
    return [
        EarlierText(
            id=r.id,
            text=r.text,
            title=r.title,
            words=len(r.text.split()),
            source=r.source,
            created_at=r.created_at,
            created_by_name=user_name(db, r.created_by_id),
        )
        for r in rows
    ]


@router.delete("/{script_id}/drafts/{slot}", response_model=ScriptOut)
def remove_draft(
    script_id: int, slot: Slot, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Remove a variation that isn't approved yet. The original can't be removed."""
    script = lib.editable(user, lib.get_script(db, user, script_id))
    draft = lib.get_draft(db, script, slot)
    if slot == 0 or draft.status == "approved":
        raise HTTPException(409, "Only a variation that isn't approved yet can be removed.")
    db.execute(delete(ScriptDraftText).where(ScriptDraftText.draft_id == draft.id))
    db.delete(draft)
    db.commit()
    return _out(db, script)


@router.post("/{script_id}/publish", response_model=ScriptOut)
def publish(script_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Put it in the team's library. Every version must be approved first; after this it's
    final (duplicate it to change it)."""
    script = lib.editable(user, lib.get_script(db, user, script_id))
    versions = lib.drafts(db, script)
    if not versions or any(d.status != "approved" for d in versions):
        raise HTTPException(409, "Approve or remove every version first.")
    if lib.writing(db, script.id):
        raise HTTPException(409, "Claude is still writing for this script. Publish when it's done.")
    script.published = True
    db.commit()
    return _out(db, script)


@router.post("/{script_id}/duplicate", response_model=ScriptOut, status_code=201)
def duplicate(script_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """A private copy to change: same brand, reel, words and cast slots, as drafts."""
    source = lib.get_script(db, user, script_id)
    copy = Script(
        workspace_id=user.workspace_id,
        brand_id=source.brand_id,
        title=f"{source.title} (copy)"[:200],
        description=source.description,
        notes=source.notes,
        reference_id=source.reference_id,
        reference_replace=source.reference_replace,
        reference_breakdown=source.reference_breakdown,
        new_lines=source.new_lines,
        created_by_id=user.id,
    )
    db.add(copy)
    db.flush()
    for d in lib.drafts(db, source):
        db.add(
            ScriptDraft(
                script_id=copy.id,
                slot=d.slot,
                text=d.text,
                target_seconds=d.target_seconds,
                title=d.title,
                premise=d.premise,
                changes=d.changes,
                breakdown=d.breakdown,
                breakdown_problems=d.breakdown_problems,
                breakdown_by_id=d.breakdown_by_id,
            )
        )
    for slot in db.scalars(select(ScriptCastSlot).where(ScriptCastSlot.script_id == source.id)):
        db.add(
            ScriptCastSlot(
                script_id=copy.id,
                role=slot.role,
                kind=slot.kind,
                description=slot.description,
                position=slot.position,
                appears_in=slot.appears_in,
                library_item_id=slot.library_item_id,
                sheet_file_id=slot.sheet_file_id,
                locked_by_id=slot.locked_by_id,
            )
        )
    db.commit()
    return _out(db, copy)
