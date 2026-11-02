"""Media (flows OR2): one list of everything made in a brand: stills, sheets, takes (quick clips
too), songs and final videos, newest first. Read only and free. The owner sees everything; an
editor sees their own videos' media, their own quick clips and songs, and the brand's Cast &
places sheets, so nothing new becomes visible through Media."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import folders
from app.auth import current_user, owner_only
from app.credits import FREESTYLE
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.files import StoredFile
from app.models.jobs import Job, JobStatus
from app.models.library import Kind, LibraryItem
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft
from app.models.songs import SongTake
from app.models.storyboards import StoryboardFrame
from app.routes.brands import get_brand
from app.schemas import UtcTime

router = APIRouter(tags=["media"])
PAGE = 60
MediaKind = Literal["still", "sheet", "take", "song", "final"]
Step = Literal["storyboard", "cast", "clips", "song", "final", "quick"]


class Maker(BaseModel):
    id: int
    name: str


class MediaItem(BaseModel):
    key: str  # "take:12": unique in the list, and the cursor's tie-break
    kind: MediaKind
    file_id: int
    content_type: str
    poster_file_id: int | None = None  # a take's: the still it was made from
    made_at: UtcTime
    made_by: Maker | None
    project_id: int | None  # its video
    folder_id: int | None  # its project (OR1): its video's, or a quick clip's own
    video_name: str | None
    script_id: int | None = None  # a script's own song
    freestyle_id: int | None = None  # a Freestyle take's freestyle (open it at /freestyle/<id>)
    open_step: Step
    from_deleted_video: bool = False
    deleted_video_by: Maker | None = None  # that deleted video's maker: they or the owner restore
    deleted_video_released: bool = False  # it went by Release: Undo of Restore releases it again
    source: Literal["director", "person"] = "person"  # made during a director run of its video
    library_item_id: int | None = None  # a sheet's character, place or prop (Open in Cast)
    library_kind: Kind | None = None


class MediaPage(BaseModel):
    items: list[MediaItem]
    next: str | None  # pass as ?before= for the next page


def _videos(db: Session, user: User, brand_id: int) -> dict[int, Project]:
    query = select(Project).where(Project.brand_id == brand_id)
    if not user.is_owner:
        query = query.where(Project.created_by_id == user.id)
    return {p.id: p for p in db.scalars(query)}


def _rows(db: Session, user: User, brand_id: int, kind: str | None) -> list[dict]:
    """(kind, file, …) for every item the caller may see, before files are read."""
    videos, out = _videos(db, user, brand_id), []
    ids = list(videos)

    def add(what, key, file_id, project_id=None, by=None, step=None, folder_id=None, **more):
        if file_id and (kind is None or kind == what):
            video = videos.get(project_id)
            out.append({"kind": what, "key": key, "file_id": file_id, "project_id": project_id,
                        "by": video.created_by_id if by is None and video else by,
                        "folder_id": video.live_folder_id if video else folder_id,
                        "open_step": step, **more})  # fmt: skip

    for f in db.scalars(select(StoryboardFrame).where(StoryboardFrame.project_id.in_(ids))):
        add("still", f"still:{f.id}", f.file_id, f.project_id, step="storyboard")
    stills = {r["file_id"] for r in out if r["kind"] == "still"}
    takes = select(ClipTake, ProjectClip.project_id, Job).select_from(ClipTake).join(
        ProjectClip, ProjectClip.id == ClipTake.clip_id).join(Job, Job.id == ClipTake.job_id
    ).where(ProjectClip.project_id.in_(ids))  # fmt: skip
    for take, pid, job in db.execute(takes):
        given = (job.input.get("files") or {}).get("reference_images") or []
        poster = next((i for i in given if i in stills), None)
        add("take", f"take:{take.id}", take.file_id, pid, job.created_by_id, "clips",
            poster_file_id=poster)  # fmt: skip
    finals = select(FinalVideo).where(FinalVideo.project_id.in_(ids),
                                      FinalVideo.off_media_at.is_(None))  # fmt: skip
    for final in db.scalars(finals):
        add("final", f"final:{final.id}", final.file_id, final.project_id, final.created_by_id,
            "final")  # fmt: skip
    quick = select(Job).where(
        Job.brand_id == brand_id, Job.project_id.is_(None), Job.status == JobStatus.succeeded,
        Job.removed_at.is_(None),
        or_(Job.kind.startswith("video"), Job.kind.startswith("image")))  # fmt: skip
    for job in db.scalars(quick):
        if "step" in job.input or not (user.is_owner or job.created_by_id == user.id):
            continue  # a step's own job (a sheet, a frame) is listed with what it made
        for n, file_id in enumerate((job.output or {}).get("file_ids") or []):
            what = "take" if job.kind.startswith("video") else "still"
            add(what, f"quick:{job.id}:{n}", file_id, by=job.created_by_id, step="quick",
                folder_id=job.live_folder_id, freestyle_id=job.input.get(FREESTYLE))  # fmt: skip
    songs = select(SongTake, Script.id).select_from(SongTake).join(
        ScriptDraft, ScriptDraft.id == SongTake.draft_id).join(
        Script, Script.id == ScriptDraft.script_id).where(
        Script.brand_id == brand_id, SongTake.deleted_at.is_(None))  # fmt: skip
    for song, script_id in db.execute(songs):
        if song.project_id is not None and song.project_id not in videos:
            continue
        if song.project_id is None and not (user.is_owner or song.created_by_id == user.id):
            continue
        add("song", f"song:{song.id}", song.file_id, song.project_id, song.created_by_id, "song",
            script_id=None if song.project_id else script_id)  # fmt: skip
    items = select(LibraryItem).where(
        or_(LibraryItem.brands.any(id=brand_id), LibraryItem.owner_project_id.in_(ids)),
        ~LibraryItem.archived, LibraryItem.kind.in_([Kind.character, Kind.place]),
        LibraryItem.owner_script_id.is_(None))  # fmt: skip
    for item in db.scalars(items):
        if item.owner_project_id is not None and item.owner_project_id not in videos:
            continue  # a video's own look copy: listed with that video
        others = [(s or {}).get("file_id") for s in item.look_sheets.values()]
        sheets = [item.sheet_file_id, *others]
        for n, file_id in enumerate(sheets):
            add("sheet", f"sheet:{item.id}:{n}", file_id, item.owner_project_id, step="cast",
                library_item_id=item.id, library_kind=item.kind)  # fmt: skip
    return out


def _director_runs(db: Session, video_ids: list[int]) -> dict[int, list[tuple]]:
    """Each video's director runs, first turn to last: what was made in one is the
    director's ("Made by the director")."""
    from app.director import RUN, STEP

    out: dict[int, dict[str, list]] = {}
    turns = select(Job.project_id, Job.input, Job.created_at, Job.finished_at).where(
        Job.project_id.in_(video_ids), Job.input["step"].as_string() == STEP)  # fmt: skip
    for pid, data, made, done in db.execute(turns):
        span = out.setdefault(pid, {}).setdefault((data.get(RUN) or {}).get("id"), [made, made])
        span[0], span[1] = min(span[0], made), max(span[1], done or made)
    return {pid: [tuple(s) for s in runs.values()] for pid, runs in out.items()}


def _folder_id(folder: str) -> int:
    try:
        return int(folder)
    except ValueError:
        raise HTTPException(422, folders.PICK) from None


def _cursor(made_at: datetime, key: str) -> str:
    return f"{made_at.isoformat()}|{key}"


@router.get("/brands/{brand_id}/media", response_model=MediaPage)
def list_media(
    brand_id: int,
    kind: MediaKind | None = None,
    folder: str | None = None,  # a project's id, or none: No project
    by: int | None = None,  # who made it
    before: str | None = None,  # the last page's `next`
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    get_brand(db, user, brand_id)
    rows = _rows(db, user, brand_id, kind)
    files = _files(db, user, rows)
    rows = [r for r in rows if r["file_id"] in files and (by is None or r["by"] == by)]
    if folder is not None:  # the brand's own sheets are in no project: listed only unfiltered
        want = None if folder == folders.NONE else _folder_id(folder)
        rows = [r for r in rows if r["folder_id"] == want
                and (r["project_id"] or r["kind"] != "sheet")]  # fmt: skip
    for r in rows:
        r["made_at"] = files[r["file_id"]].created_at
    rows.sort(key=lambda r: (r["made_at"], r["key"]), reverse=True)
    if before:
        try:
            at, key = before.split("|", 1)
            mark = (datetime.fromisoformat(at), key)
        except ValueError:
            raise HTTPException(422, "That page link is out of date. Start from the top.") from None
        rows = [r for r in rows if (r["made_at"], r["key"]) < mark]
    page = rows[:PAGE]
    items = _items(db, page, files)
    last = page[-1] if len(rows) > PAGE else None
    return MediaPage(items=items, next=last and _cursor(last["made_at"], last["key"]))


def _files(db: Session, user: User, rows: list[dict]) -> dict[int, StoredFile]:
    return {f.id: f for f in db.scalars(select(StoredFile).where(
        StoredFile.id.in_({r["file_id"] for r in rows}),
        StoredFile.workspace_id == user.workspace_id))}  # fmt: skip


def _items(db: Session, page: list[dict], files: dict[int, StoredFile]) -> list[MediaItem]:
    videos = {p.id: p for p in db.scalars(select(Project).where(
        Project.id.in_({r["project_id"] for r in page if r["project_id"]})))}  # fmt: skip
    people = {r["by"] for r in page if r["by"]} | {v.created_by_id for v in videos.values()}
    names = {u.id: u.name for u in db.scalars(select(User).where(User.id.in_(people)))}

    def maker(user_id: int | None) -> Maker | None:
        return Maker(id=user_id, name=names[user_id]) if user_id in names else None

    runs = _director_runs(db, list(videos))
    items = []
    for r in page:
        video = videos.get(r["project_id"])
        gone = bool(video and video.archived_at)
        made = files[r["file_id"]].created_at
        directed = any(s <= made <= e for s, e in runs.get(r["project_id"], []))
        items.append(MediaItem(
            **{k: v for k, v in r.items() if k not in ("by", "made_at")},
            content_type=files[r["file_id"]].content_type, made_by=maker(r["by"]),
            made_at=made, video_name=video.name if video else None,
            source="director" if directed else "person",
            from_deleted_video=gone,
            deleted_video_by=maker(video.created_by_id) if gone else None,
            deleted_video_released=gone and video.released_draft_id is not None))  # fmt: skip
    return items


NOT_FOUND = "That's no longer in Media."


def _one(db: Session, user: User, brand_id: int, key: str) -> tuple[dict, StoredFile]:
    get_brand(db, user, brand_id)
    rows = [r for r in _rows(db, user, brand_id, None) if r["key"] == key]
    files = _files(db, user, rows)
    if not rows or rows[0]["file_id"] not in files:
        raise HTTPException(404, NOT_FOUND)
    return rows[0], files[rows[0]["file_id"]]


@router.get("/brands/{brand_id}/media/{key}", response_model=MediaItem)
def read_media(
    brand_id: int, key: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """One item of Media (its own page), as the list shows it: only what the caller may see."""
    row, file = _one(db, user, brand_id, key)
    return _items(db, [row], {file.id: file})[0]


SHEET = "This is a sheet in Cast & places. Change it there."


@router.delete("/brands/{brand_id}/media/{key}", status_code=204)
def remove_media(
    brand_id: int, key: str, owner: User = Depends(owner_only), db: Session = Depends(get_db)
) -> None:
    """Owner only: a Quick clip or a script's own song leaves Media (Undo: the clip's or the
    song's restore); a final cut leaves Media only, its video keeps it. A still or take a video
    is made of, or a Cast & places sheet, is removed where it's used, so a video never loses a
    part without its maker seeing it."""
    from app import song_takes

    row, _ = _one(db, owner, brand_id, key)
    what, rest = key.split(":", 1)
    if what == "final":
        db.get(FinalVideo, int(rest)).off_media_at = utcnow()
        db.commit()
        return
    if row["project_id"]:
        video = db.get(Project, row["project_id"])
        raise HTTPException(409, f"This is part of {video.name}. Remove it from the video instead.")
    if what == "quick":
        db.get(Job, int(rest.split(":")[0])).removed_at = utcnow()
        db.commit()
    elif what == "song":
        song_takes.remove(db, db.get(SongTake, int(rest)))
    else:
        raise HTTPException(409, SHEET)
