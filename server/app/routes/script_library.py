"""The Script Library (workflow v2): scripts owned by a brand, each with up to three versions
(the original in slot 0 and up to two variations). Rules: `app/script_library.py`."""

from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app import advice, looks, merge_roles, music, narration, rewritten, song_study
from app import script_library as lib
from app.advice import Said
from app.auth import current_user, user_name
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.files import StoredFile
from app.models.jobs import Job
from app.models.script_library import Script, ScriptCastSlot, ScriptDraft, ScriptDraftText
from app.models.scripts import Suggestion
from app.purge import PURGE_AFTER
from app.reel import reel_link
from app.routes.brands import get_brand
from app.routes.estimate import version_cost
from app.routes.jobs import stop_jobs
from app.routes.references import catalogue
from app.routes.references import find as find_reference
from app.routes.script_cast import SamePair, SlotOut, slots
from app.routes.script_import import UNTITLED, one_at_a_time, prepare
from app.routes.scripts import ScriptText
from app.routes.uploads import get_upload
from app.schemas import LongText, UtcTime
from app.song_study import SongStudyOut

router = APIRouter(prefix="/scripts", tags=["script library"])
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Slot = Annotated[int, Field(ge=0, le=lib.MAX_SLOT)]
# The length is checked in write_draft, so a long line gets the plain reason (not pydantic's)
StyleLine = Annotated[str, StringConstraints(strip_whitespace=True, max_length=20_000)]


SONG_STAYS = (
    "A song's words are lyrics, so it stays a song. To try this another way, start a new script."
)


class ScriptIn(BaseModel):
    brand_id: int
    title: Title
    description: LongText = ""
    notes: LongText = ""
    reference_id: str | None = None  # a reel from GET /references
    reference_replace: LongText = ""
    new_lines: bool | None = None  # write new lines in the reel's style, not its own
    text: Annotated[str, StringConstraints(max_length=50_000)] = ""  # the original, if ready
    kind: Literal["story", "song", "narrated"] = "story"  # song: lyrics; narrated: one voice
    look: str | None = None  # how the pictures are drawn (ST1); None: House


class BulkRow(ScriptIn):
    title: Title | None = None  # needed unless the row is a reel link ("Untitled reel")
    reel_url: Annotated[str, StringConstraints(max_length=500)] | None = None  # an Instagram reel
    upload_id: int | None = None  # or a video from POST /uploads/video (reel-import.md §8)


class BulkIn(BaseModel):
    """Bulk create (Reed): titles, descriptions and an optional reel only; nothing is written
    until "Write all". A row with a reel link fetches and prepares that reel (free)."""

    scripts: list[BulkRow] = Field(min_length=1, max_length=50)


MAX_REELS = 20  # links and uploaded videos together, per batch


class DialogueLine(BaseModel):
    line: int  # numbered as the script's lines are
    text: str


class ScriptPatch(BaseModel):
    title: Title | None = None
    description: LongText | None = None
    notes: LongText | None = None
    reference_id: str | None = None
    reference_replace: LongText | None = None
    new_lines: bool | None = None  # until version A is approved
    kind: Literal["story", "narrated"] | None = (
        None  # ST0: Dialogue <-> Narrated, before publishing
    )
    look: str | None = None  # ST1: before publishing; Undo is a PATCH back (changing back is free)


class DraftIn(BaseModel):
    text: ScriptText
    target_seconds: int | None = Field(None, gt=0, le=3600)  # null: the breakdown decides
    style_line: StyleLine | None = None  # a song's music style; left out: kept as it is
    singer: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    spoken_end_line: LongText | None = None  # rule 18: spoken over the song's last seconds


class Person(BaseModel):
    id: int
    name: str


class SongDirectionOut(BaseModel):
    id: str
    title: str
    concept: str
    lyrics: str
    style_line: str
    visual_concept: str
    recommended: bool
    left_out: list[str] = []  # adapting a script: what this direction leaves out
    unchecked_claims: list[str] = []
    length_note: str = ""  # "75 sung words: a song of about 0:31–0:38."
    style_names: list[str] = []  # a name from "sounds like" still in the style line
    advice: list[str] = []  # the Director's check (never blocks)
    used: bool = False  # Use was pressed on it
    made_at: str


class DirectionsJob(BaseModel):
    id: int
    status: str  # queued | running | failed
    reason: str | None  # plain words, when it failed
    started_at: UtcTime | None


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
    problems: Said
    changed_lines: list[str]  # the reel's lines rewritten for the brand swap
    # "Was:" marks until approval: [{line_index (0-based line of text), text, was}]
    rewritten: list[dict] = []
    has_breakdown: bool
    approved_at: UtcTime | None
    variation_of: str | None = None  # "A": a variation of the original; null for the original
    estimate_credits: float = 0  # to make it, every step included: estimate.version_cost
    clips: int = 0  # in the saved breakdown
    planned_by: Person | None = None  # who saved the breakdown
    style_line: str = ""  # a song's music style
    singer: str = ""  # the cast role seen singing ("": nobody on camera)
    spoken_end_line: str = ""
    song_directions: list[SongDirectionOut] = []  # offered, newest pair first (flows S3)
    directions_estimate_credits: float = 0  # "Write 2 song directions"
    directions_stop: str | None = None  # why that press can't run, in plain words
    directions_stop_kind: Literal["no_facts", "other"] | None = (
        None  # no_facts: link the brand page
    )
    directions_job: DirectionsJob | None = None  # the press in hand (None: idle or done)
    claims_to_check: list[str] = []  # the used direction's claims, until the owner keeps them
    # The narrator check (flows ST0, N1): a Dialogue version all one narrator could be
    # Narrated; on a Narrated one, the lines spoken on camera the narrator will read
    reads_narrated: bool = False
    dialogue_lines: list[DialogueLine] = []
    song_study: SongStudyOut | None = None  # S3a (app/song_study.shown)


class ReelRow(BaseModel):
    status: Literal["preparing", "ready", "reading", "done", "failed"]
    seconds: float | None  # once prepared (an uploaded video's at once)
    source: Literal["link", "file"] = "link"
    url: str | None = None  # a link's
    file_name: str | None = None  # an uploaded video's
    fetch_error: str | None = None  # the reel couldn't be got or prepared: the plain reason


class ScriptRow(BaseModel):
    id: int
    brand_id: int
    title: str
    kind: Literal["story", "song", "narrated"]
    look: str = "house"
    description: str
    reference_id: str | None
    published: bool
    status: str  # draft | published | in_production | done
    created_by_id: int | None
    created_by_name: str
    created_at: UtcTime
    versions: list[VersionSummary]
    versions_left: int  # approved versions not produced yet
    poster_file_id: int | None = None  # the first still of its newest finished video
    reference_name: str | None = None  # the reel it adapts, by name
    removed: Literal["deleted", "archived"] | None = None  # in the removed list; archived: it
    # has videos, which are kept, so it never goes for good
    removed_at: UtcTime | None = None  # in the removed list: when it was removed
    purge_on: UtcTime | None = None  # deleted only: when it goes for good (30 days on)
    reel_imported: bool = False  # adapts its own imported reel, not a catalogue one
    reel: ReelRow | None = None  # made from a reel link or upload: where its reel is
    running: bool = False  # its own work is being made (not its videos'), whoever started it


class ScriptOut(ScriptRow):
    notes: str
    reference_replace: str
    new_lines: bool
    versions: list[VersionOut]
    cast: list[SlotOut]  # roles shared by every version, locked or not
    maybe_same: list[SamePair] = []  # roles that may be one person (advice, never blocks)


def _person(db: Session, user_id: int | None) -> Person | None:
    user = db.get(User, user_id) if user_id else None
    return Person(id=user.id, name=user.name) if user else None


def _narrator(db: Session, draft: ScriptDraft) -> dict:
    """The Director's narrator check on the version's format (check.format_advice)."""
    from app.prompts import check

    kind = db.get(Script, draft.script_id).kind
    if kind == "story":
        return {"reads_narrated": bool(check.format_advice(draft.text, "dialogue"))}
    if kind != "narrated":
        return {}
    lines = draft.text.splitlines()
    numbers = [int(a.split("line ", 1)[1].split(":", 1)[0])
               for a in check.format_advice(draft.text, "narrated")]  # fmt: skip
    return {"dialogue_lines": [DialogueLine(line=n, text=lines[n - 1].strip()) for n in numbers]}


def _directions(db: Session, draft: ScriptDraft) -> dict:
    """A Song version's song directions and the press that writes them (flows S3)."""
    from app import song_directions as sd
    from app.credits import estimate

    script = db.get(Script, draft.script_id)
    if script.kind != "song":
        return {}
    return {
        "song_directions": sd.shown(draft),
        "directions_estimate_credits": float(
            estimate(db, script.workspace_id, "write-claude", Decimal(1))
        ),
        "directions_stop": (stop := sd.stop(db, script, draft)),
        "directions_stop_kind": stop and ("no_facts" if stop == sd.NOTHING else "other"),
        "directions_job": sd.job_state(db, script, draft),
        "claims_to_check": sd.claims_to_check(draft),
    }


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
        rewritten=[
            {**m, "text": lines[m["line_index"]]}
            for lines in [draft.text.splitlines()]
            for m in draft.rewritten or []
            if m["line_index"] < len(lines)
        ],
        has_breakdown=draft.breakdown is not None,
        approved_at=draft.approved_at,
        variation_of="A" if draft.slot else None,
        estimate_credits=float(version_cost(db, draft)),
        clips=len((draft.breakdown or {}).get("clips", [])),
        planned_by=_person(db, draft.breakdown_by_id) if draft.breakdown else None,
        style_line=draft.style_line,
        singer=draft.singer,
        spoken_end_line=draft.spoken_end_line,
        **_directions(db, draft),
        **_narrator(db, draft),
        song_study=song_study.shown(db, draft),
    )


def _reel(db: Session, script: Script) -> ReelRow | None:
    if script.reel is None:
        return None
    from app import reel_read

    status, failed = reel_read.state(db, script)
    problem = script.reel.get("problem") or "We couldn't prepare this reel. Upload it again."
    upload = script.reel.get("source") == "upload"
    return ReelRow(
        status=status,
        seconds=script.reel.get("seconds"),
        fetch_error=problem if failed == "prepare" else None,
        source="file" if upload else "link",
        url=script.reel.get("url"),
        file_name=script.reel.get("file_name") if upload else None,
    )


def _out(db: Session, script: Script, full: bool = True) -> ScriptRow | ScriptOut:
    versions = [_version(db, d, full) for d in lib.drafts(db, script)]
    statuses = [v.status for v in versions]
    row = dict(
        id=script.id,
        brand_id=script.brand_id,
        title=script.title,
        kind=script.kind,
        look=script.look,
        description=script.description,
        reference_id=script.reference_id,
        reel_imported=script.reference_breakdown is not None,
        reel=_reel(db, script),
        published=script.published,
        status=lib.script_status(script, statuses),
        created_by_id=script.created_by_id,
        created_by_name=user_name(db, script.created_by_id),
        created_at=script.created_at,
        versions=versions,
        versions_left=statuses.count("approved"),
        running=bool(lib.own_jobs(db, script)),
    )
    if not full:
        return ScriptRow(**row)
    return ScriptOut(
        **row,
        notes=script.notes,
        reference_replace=script.reference_replace,
        new_lines=script.new_lines,
        cast=slots(db, script),
        maybe_same=merge_roles.maybe_same(db, script),
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
    removed: bool = False,  # true: the deleted (archived) scripts instead, to restore
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """The Script Library: what the caller may see, newest first, filtered."""
    query = select(Script).where(
        Script.workspace_id == user.workspace_id,
        Script.archived if removed else ~Script.archived,
    )
    if not user.is_owner and removed:  # only the ones they could restore: their own
        query = query.where(Script.created_by_id == user.id, ~Script.published)
    elif not user.is_owner:
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
        if script.archived:
            row.removed_at = script.deleted_at
            row.removed = "archived" if lib.has_videos(db, script) else "deleted"
            if row.removed == "deleted" and script.deleted_at:
                row.purge_on = script.deleted_at + PURGE_AFTER
    return rows


@router.post("", response_model=ScriptOut, status_code=201)
def create_script(
    body: ScriptIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    brand = get_brand(db, user, body.brand_id)
    _check_reference(request, body.reference_id)
    if body.look:
        looks.pick(db, user, body.look)
    script = Script(
        workspace_id=user.workspace_id,
        created_by_id=user.id,
        **body.model_dump(exclude={"text"}, exclude_none=True),
    )
    if not body.look:  # the brand's default look; an Off one starts editors on House (BR1)
        on = user.is_owner or looks.is_on(db, user.workspace_id, brand.default_look)
        script.look = brand.default_look if on else looks.DEFAULT
    db.add(script)
    db.flush()
    style = brand.music_style.strip() if script.kind == "song" else ""  # S2: prefilled
    db.add(ScriptDraft(script_id=script.id, slot=0, text=body.text.strip(), style_line=style))
    db.commit()
    return _out(db, script)


@router.post("/bulk", response_model=list[ScriptRow], status_code=201)
def create_many(
    body: BulkIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Up to 50 scripts at once, all or none: a plain error names the first bad row. Rows
    with a reel link or an uploaded video (up to 20 together) are prepared one after another,
    in this order."""
    if sum(bool(i.reel_url or i.upload_id) for i in body.scripts) > MAX_REELS:
        raise HTTPException(422, f"Up to {MAX_REELS} reels at once.")
    links, uploads = [], []
    for n, item in enumerate(body.scripts, 1):
        row = f"Row {n}"
        try:
            get_brand(db, user, item.brand_id)
            _check_reference(request, item.reference_id)
            links.append(item.reel_url and reel_link(item.reel_url))
            uploads.append(item.upload_id and get_upload(db, user, item.upload_id))
            if uploads[-1]:
                row += f" ({db.get(StoredFile, uploads[-1].file_id).filename})"
                if uploads[-1] in uploads[:-1]:  # one video, one draft: never two sharing it
                    first = uploads.index(uploads[-1]) + 1
                    raise HTTPException(422, f"That video is already in row {first}.")
            if item.reel_url and not links[-1]:
                raise HTTPException(422, "That isn't an Instagram reel link.")
            if item.reel_url and item.upload_id:
                raise HTTPException(422, "Give it a reel link or a video, not both.")
            if (item.reel_url or item.upload_id) and item.reference_id:
                raise HTTPException(422, "Pick a catalogue reel or your own reel, not both.")
            if uploads[-1] and uploads[-1].brand_id != item.brand_id:
                raise HTTPException(422, "That video was added for another brand.")
            if not (item.title or item.reel_url or item.upload_id):
                raise HTTPException(422, "Give it a title.")
        except HTTPException as exc:
            raise HTTPException(exc.status_code, f"{row}: {exc.detail}") from None
    if any(links) or any(uploads):  # one batch at a time; the reel worker spaces its fetches
        one_at_a_time(
            db, user, "Your last reels are still being prepared. Try again when they're done."
        )
    made = []
    for item, url, upload in zip(body.scripts, links, uploads, strict=True):
        if item.look:
            looks.pick(db, user, item.look)
        script = Script(
            workspace_id=user.workspace_id,
            created_by_id=user.id,
            **item.model_dump(
                exclude={"text", "reel_url", "upload_id", "title"}, exclude_none=True
            ),
            title=item.title or UNTITLED,
        )
        db.add(script)
        db.flush()
        db.add(ScriptDraft(script_id=script.id, slot=0, text=item.text.strip()))
        made.append(script)
        if url:  # each its own free prep job; the reel worker fetches them one at a time
            prepare(db, user, script, {"source": "link", "url": url}, {"url": url})
        elif upload:  # the video is here already: it is prepared like a single upload
            upload.used = True
            video = db.get(StoredFile, upload.file_id)
            reel = {"source": "upload", "video_file_id": video.id, "file_name": video.filename,
                    "seconds": upload.seconds}  # fmt: skip
            prepare(db, user, script, reel, {"video_key": video.key})
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
    script = lib.get_script(db, user, script_id)
    values = body.model_dump(exclude_unset=True)
    # Once published only the owner may still tidy its title, about and notes (Reed, 2026-10-28).
    if not (
        script.published and user.is_owner and values.keys() <= {"title", "description", "notes"}
    ):
        lib.editable(user, script)
    if "reference_id" in values:
        _check_reference(request, values["reference_id"])
    if values.get("kind") is not None:  # ST0: same words, other steps; Undo is a PATCH back
        lib.editable(user, script)
        if script.kind == "song":
            raise HTTPException(409, SONG_STAYS)
    if values.get("look") is not None:
        lib.editable(user, script)  # a published script's look is final (ST1)
        values["look"] = looks.pick(db, user, values["look"])
    if values.get("new_lines") is not None and any(
        d.slot == 0 and d.status == "approved" for d in lib.drafts(db, script)
    ):
        raise HTTPException(409, "Version A is approved, so its lines are final.")
    for field, value in values.items():
        if value is not None or field == "reference_id":
            setattr(script, field, value)
    db.commit()
    return _out(db, script)


def _removable(db: Session, user: User, script_id: int, archived: bool = False) -> Script:
    script = lib.get_script(db, user, script_id, archived)
    if not (user.is_owner or (script.created_by_id == user.id and not script.published)):
        raise HTTPException(403, "Only its author (before publishing) or the owner can remove it.")
    return script


@router.delete("/{script_id}", status_code=204)
def delete_script(
    script_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Delete it, undoably (Reed, 2026-10-25): it leaves every list but keeps its versions,
    history, cast, reel files and videos, so Restore brings it back as it was. Its own work
    stops, as on Release (a reel read, a Write, variations, a cast read, its own looks'
    sheets); Restore doesn't start it again. Its videos are their own and go on."""
    script = _removable(db, user, script_id)
    script.archived, script.deleted_at = True, utcnow()
    stop_jobs(db, Job.id.in_([j.id for j in lib.own_jobs(db, script)]))
    # app.purge removes it for good PURGE_AFTER on (never one with videos).
    db.commit()


@router.post("/{script_id}/restore", response_model=ScriptOut)
def restore_script(
    script_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Undo a delete: who may delete it may restore it."""
    script = _removable(db, user, script_id, archived=True)  # 404 unless it's deleted
    script.archived, script.deleted_at = False, None
    db.commit()
    return _out(db, script)


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
    if draft.rewritten:  # the "Was:" marks follow their lines until approval
        draft.rewritten = rewritten.follow(draft.text or "", body.text, draft.rewritten)
    if script.kind == "song" and len(body.text.strip()) > music.MAX_OWN_LYRICS:
        raise HTTPException(422, music.TOO_LONG)
    if body.style_line and len(body.style_line) > music.MAX_OWN_STYLE:
        raise HTTPException(422, music.STYLE_TOO_LONG)
    draft.text, draft.target_seconds = body.text, body.target_seconds
    for song_field in ("style_line", "singer", "spoken_end_line"):  # song ads; None: as is
        if (value := getattr(body, song_field)) is not None:
            setattr(draft, song_field, value)
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
        draft.rewritten = []  # approved: the "Was:" marks and the banner go
        db.commit()
    return _out(db, script)


@router.post("/{script_id}/drafts/approve-all", response_model=advice.ApproveAllOut)
def approve_all_drafts(
    script_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Approve all (Reed, 2026-10-26): every version that's written and still a draft; one
    still being written, or with no words yet, is listed with why ("C: still writing").
    Undo takes back exactly these (ids are the versions' slots)."""
    script = lib.editable(user, lib.get_script(db, user, script_id))
    rows = db.scalars(
        select(ScriptDraft).where(ScriptDraft.script_id == script.id).order_by(ScriptDraft.slot)
    )
    busy = lib.writing(db, script.id, "variations")
    approved, skipped = [], []
    for draft in rows:
        if draft.status == "approved":
            continue
        why = (
            "still writing" if busy and draft.slot > 0
            else "no words yet" if not draft.text.strip()
            else ""
        )  # fmt: skip
        if why:
            skipped.append({"id": draft.slot, "label": chr(ord("A") + draft.slot), "reason": why})
            continue
        draft.status, draft.approved_at, draft.approved_by_id = "approved", utcnow(), user.id
        draft.rewritten = []
        approved.append(draft.slot)
    db.commit()
    return advice.ApproveAllOut(approved=approved, skipped=skipped)


@router.post("/{script_id}/drafts/approve-all/undo", response_model=ScriptOut)
def undo_approve_all_drafts(
    script_id: int,
    body: advice.UndoIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Undo Approve all: exactly the versions it approved go back to drafts."""
    script = lib.editable(user, lib.get_script(db, user, script_id))
    rows = db.scalars(
        select(ScriptDraft).where(
            ScriptDraft.script_id == script.id, ScriptDraft.slot.in_(body.ids)
        )
    )
    for draft in rows:
        if draft.status == "approved":
            draft.status, draft.approved_at, draft.approved_by_id = "draft", None, None
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
    source: str  # edit | variations | write | enhance: what replaced it
    created_at: UtcTime  # when it was replaced
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
    db.execute(delete(Suggestion).where(Suggestion.script_draft_id == draft.id))  # SQLite too
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
    if script.kind in narration.TIMED:  # its videos are timed to the take: one must exist
        from app import song_takes

        if songless := [d for d in versions if song_takes.preferred(db, d) is None]:
            name = "ABC"[songless[0].slot]
            if script.kind == "narrated":
                said = f"Make the narration first: version {name} has no narration yet."
                raise HTTPException(409, f"{said} Press Make the narration.")
            raise HTTPException(409, f"Make the song first: version {name} has no Preferred take "
                                     "of its lyrics. Press Make 2 takes.")  # fmt: skip
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
        kind=source.kind,
        look=source.look,
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
                style_line=d.style_line,
                singer=d.singer,
                spoken_end_line=d.spoken_end_line,
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
