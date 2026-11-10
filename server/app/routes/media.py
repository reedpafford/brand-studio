"""Media (flows OR2): one list of everything made in a brand: stills, sheets, takes (quick clips
too), songs and final videos, newest first. Read only and free. The owner sees everything; an
editor sees their own videos' media, their own quick clips and songs, and the brand's Cast &
places sheets, so nothing new becomes visible through Media."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import folders
from app.auth import current_user, owner_only
from app.credits import FREESTYLE
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.files import MediaUpload, StoredFile
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
MediaKind = Literal["still", "sheet", "take", "song", "final", "upload"]
Step = Literal["storyboard", "cast", "clips", "song", "final", "quick", "upload"]
Group = Literal["clip", "still", "song"]  # v5 C_Media's tabs
GROUPS = {"take": "clip", "final": "clip", "still": "still", "sheet": "still", "song": "song"}


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
    group: Group  # clip (takes, finals, uploaded clips), still (stills, sheets, pictures), song
    duration_seconds: float | None = None  # a clip's or a song's length; null for a picture


class MediaCounts(BaseModel):
    all: int
    clips: int
    stills: int
    songs: int


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
            more.setdefault("group", GROUPS.get(what))
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
            poster_file_id=poster, duration_seconds=_asked(job))  # fmt: skip
    finals = select(FinalVideo).where(FinalVideo.project_id.in_(ids),
                                      FinalVideo.off_media_at.is_(None))  # fmt: skip
    for final in db.scalars(finals):
        add("final", f"final:{final.id}", final.file_id, final.project_id, final.created_by_id,
            "final", duration_seconds=final.seconds)  # fmt: skip
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
                folder_id=job.live_folder_id, freestyle_id=job.input.get(FREESTYLE),
                duration_seconds=_asked(job) if what == "take" else None)  # fmt: skip
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
            script_id=None if song.project_id else script_id,
            duration_seconds=song.seconds)  # fmt: skip
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
    uploads = select(MediaUpload).where(MediaUpload.brand_id == brand_id,
                                        MediaUpload.removed_at.is_(None))  # fmt: skip
    for up in db.scalars(uploads):  # everyone with the brand sees what was added to its Media
        add(
            "upload",
            f"upload:{up.id}",
            up.file_id,
            by=up.created_by_id,
            step="upload",
            group="still" if up.seconds is None else "clip",
            duration_seconds=up.seconds,
        )
    return out


def _asked(job: Job) -> float | None:
    """A take's length, as it was asked for (the video model makes that many seconds)."""
    seconds = (job.input.get("input") or {}).get("duration")
    return float(seconds) if seconds else None


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
    request: Request,
    kind: MediaKind | None = None,
    group: Group | None = None,  # v5's tabs: clip, still or song
    folder: str | None = None,  # a project's id, or none: No project
    by: int | None = None,  # who made it
    sort: Literal["newest", "oldest"] = "newest",
    before: str | None = None,  # the last page's `next`
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    rows, files = _seen(db, user, brand_id, kind, folder, by)
    if group is not None:
        rows = [r for r in rows if r["group"] == group]
    newest = sort == "newest"
    rows.sort(key=lambda r: (r["made_at"], r["key"]), reverse=newest)
    if before:
        try:
            at, key = before.split("|", 1)
            mark = (datetime.fromisoformat(at), key)
        except ValueError:
            raise HTTPException(422, "That page link is out of date. Start from the top.") from None
        rows = [r for r in rows if ((r["made_at"], r["key"]) < mark) == newest
                and (r["made_at"], r["key"]) != mark]  # fmt: skip
    page = rows[:PAGE]
    reads = 0
    for r in page:  # a final cut made before lengths were kept: read once, then kept
        if r["kind"] == "final" and r["duration_seconds"] is None and reads < READS:
            reads += 1
            final_id = int(r["key"].split(":")[1])
            r["duration_seconds"] = _length(db, request.app.state.storage, final_id,
                                            files[r["file_id"]])  # fmt: skip
        elif r["kind"] == "final":
            r["duration_seconds"] = r["duration_seconds"] or None  # UNREAD: none
    items = _items(db, page, files)
    last = page[-1] if len(rows) > PAGE else None
    return MediaPage(items=items, next=last and _cursor(last["made_at"], last["key"]))


def _seen(db: Session, user: User, brand_id: int, kind, folder, by) -> tuple[list, dict]:
    """The rows the caller may see with their files, by kind, project and maker."""
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
    return rows, files


@router.get("/brands/{brand_id}/media-counts", response_model=MediaCounts)
def media_counts(
    brand_id: int,
    folder: str | None = None,
    by: int | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """How many items each of v5's tabs has, with the same project and maker filters."""
    rows, _ = _seen(db, user, brand_id, None, folder, by)
    groups = [r["group"] for r in rows]
    return MediaCounts(all=len(rows), clips=groups.count("clip"), stills=groups.count("still"),
                       songs=groups.count("song"))  # fmt: skip


PROBE_SECONDS = 30  # a clip's check takes at most this long; longer is refused plainly


class ProbeTimeout(Exception):
    """The clip took longer than PROBE_SECONDS to check."""


def _probe(data: bytes, stop_after: float | None = None) -> tuple[set[str], float | None]:
    """A video's streams ({"video", "audio"}) and its length in seconds: the longer of what its
    header says and where its last video packet ends (QA-13: a header can be patched to lie).
    The packets are read as a stream, keeping only the latest end, and the read stops once
    one ends past `stop_after` (the answer is known). Raises ProbeTimeout past PROBE_SECONDS."""
    import json
    import math
    import subprocess
    import tempfile
    import threading
    import time
    from pathlib import Path

    from app.reel import _run

    deadline = time.monotonic() + PROBE_SECONDS
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "media"
        path.write_bytes(data)
        try:
            done = _run(["ffprobe", "-v", "error", "-show_entries",
                         "format=duration:stream=codec_type", "-of", "json", str(path)],
                        PROBE_SECONDS)  # fmt: skip
        except subprocess.TimeoutExpired:
            raise ProbeTimeout from None
        info = json.loads(done.stdout or "{}") if done.returncode == 0 else {}
        kinds = {st.get("codec_type") for st in info.get("streams", [])}
        seconds = _num((info.get("format") or {}).get("duration"))
        if "video" in kinds:
            args = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                    "packet=pts_time,duration_time", "-of", "csv=p=0", str(path)]  # fmt: skip
            reading = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,  # noqa: S603
                                       text=True)  # fmt: skip
            left = max(0.0, deadline - time.monotonic())
            timer = threading.Timer(left, reading.kill)  # a stalled read is stopped too
            timer.start()
            try:
                for line in reading.stdout:
                    pts, _, length = line.strip().partition(",")
                    seconds = max(seconds, _num(pts) + _num(length))
                    if stop_after is not None and seconds > stop_after:
                        break  # past the cap: no need to read the rest
            finally:
                timer.cancel()
                reading.kill()  # stopped early, or done: either way it's gone
                reading.wait()
            if time.monotonic() >= deadline:  # the timer stopped it before the end
                raise ProbeTimeout
    up = math.ceil(seconds * 100) / 100  # rounded up: just past the cap stays past it
    return kinds, up if seconds > 0 else None


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


UNREAD = 0.0  # a final's seconds when its file couldn't be read: tried once, shown as none
READS = 5  # older finals read for their length on one Media load; the rest wait for the next


def _length(db: Session, storage, final_id: int, file: StoredFile) -> float | None:
    """A final cut's length in seconds: kept on it when it's made; one made before that is read
    from its file once and kept, UNREAD when it can't be (so it isn't read again)."""
    final = db.get(FinalVideo, final_id)
    if final.seconds is None:
        try:
            final.seconds = _probe(storage.get(file.key))[1] or UNREAD
        except (OSError, ProbeTimeout):  # its file is gone, or too slow to read
            final.seconds = UNREAD
        db.commit()
    return final.seconds or None


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
    song's restore); a final cut leaves Media only, its video keeps it, and an added picture or
    clip leaves Media (Undo for both: POST …/restore). A still or take a video
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
    elif what == "upload":
        db.get(MediaUpload, int(rest)).removed_at = utcnow()
        db.commit()
    else:
        raise HTTPException(409, SHEET)


@router.post("/brands/{brand_id}/media/{key}/restore", status_code=204)
def restore_media(
    brand_id: int, key: str, owner: User = Depends(owner_only), db: Session = Depends(get_db)
) -> None:
    """Undo for the owner's Delete on an added picture or clip, or on a final cut taken off
    Media. (A Quick clip or a song comes back through its own restore.)"""
    get_brand(db, owner, brand_id)
    what, _, rest = key.partition(":")
    row = None
    if what == "upload" and rest.isdigit():
        row = db.get(MediaUpload, int(rest))
        row = row if row and row.brand_id == brand_id and row.removed_at else None
        if row:
            row.removed_at = None
    elif what == "final" and rest.isdigit():
        row = db.get(FinalVideo, int(rest))
        video = row and db.get(Project, row.project_id)
        row = row if video and video.brand_id == brand_id and row.off_media_at else None
        if row:
            row.off_media_at = None
    if row is None:
        raise HTTPException(404, NOT_FOUND)
    db.commit()


SNIFFED = {"image/png": "image", "image/jpeg": "image", "image/webp": "image",
           "video/mp4": "video", "video/webm": "video"}  # fmt: skip
NOT_MEDIA = "That isn't a picture or clip we can use. Add a PNG, JPEG or WebP, or an MP4 or WebM."
CLIP_MAX = 180  # seconds a clip added to Media may be
SLOW = "That clip took too long to check. Add a shorter or smaller copy."
TOO_LONG = f"That clip is longer than {CLIP_MAX // 60} minutes. Add one of up to {CLIP_MAX // 60}."


def _whole_picture(data: bytes) -> bool:
    """The picture reads to its end (a PNG cut off mid-way isn't stored broken)."""
    import io

    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as picture:
            picture.load()
        return True
    except Exception:  # noqa: BLE001 - any reading error: not a usable picture
        return False


def _sniff(head: bytes) -> str | None:
    """The file's type from its first bytes, whatever its name or label says."""
    from app.filetypes import matches

    return next((t for t in SNIFFED if matches(t, head)), None)


@router.post("/brands/{brand_id}/media", response_model=MediaItem, status_code=201)
def add_media(
    brand_id: int,
    upload: UploadFile,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Add a picture or a clip to a brand's Media (anyone with the brand; free)."""
    added, _ = store(db, user, brand_id, upload, request)
    db.commit()
    row, file = _one(db, user, brand_id, f"upload:{added.id}")
    return _items(db, [row], {file.id: file})[0]


NOT_CLIP = "That isn't a clip we can use. Add an MP4 or WebM."


def store(db: Session, user: User, brand_id: int, upload: UploadFile, request: Request,
          clip: bool = False) -> tuple[MediaUpload, bytes]:  # fmt: skip
    """A picture or a clip added to a brand's Media, stored and flushed with its bytes, checked
    by its contents: its type, its size, a picture's pixels, a clip's video and length. `clip`:
    only a clip (the library's Footage tab, app/footage.py)."""
    import hashlib
    import uuid

    from app.references import too_many_pixels

    get_brand(db, user, brand_id)
    limit = request.app.state.settings.max_upload_mb * 1024 * 1024
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"That file is over {limit >> 20} MB. Add a smaller copy.")
    content_type = _sniff(data[:16])
    if content_type is None or (clip and SNIFFED[content_type] != "video"):
        raise HTTPException(415, NOT_CLIP if clip else NOT_MEDIA)
    seconds = None
    if SNIFFED[content_type] == "image":
        problem = too_many_pixels(data)  # from its header, before it is decoded
        if problem and "megapixels" in problem:  # too big to decode
            raise HTTPException(422, problem)
        if problem or not _whole_picture(data):  # an unreadable header, or cut off part way
            raise HTTPException(415, NOT_MEDIA)
    if SNIFFED[content_type] == "video":
        try:
            kinds, seconds = _probe(data, stop_after=CLIP_MAX)
        except ProbeTimeout:  # never a 500, and never a worker held for long
            raise HTTPException(422, SLOW) from None
        if "video" not in kinds or seconds is None:
            raise HTTPException(415, NOT_MEDIA)
        if seconds > CLIP_MAX:
            raise HTTPException(422, TOO_LONG)  # (read until past the cap: no exact length)
    key = f"{user.workspace_id}/{uuid.uuid4().hex}"
    request.app.state.storage.put(key, data)
    stored = StoredFile(workspace_id=user.workspace_id, key=key, size=len(data),
                        filename=(upload.filename or "media")[:255], content_type=content_type,
                        sha256=hashlib.sha256(data).hexdigest(),
                        uploaded_by_id=user.id)  # fmt: skip
    db.add(stored)
    db.flush()
    added = MediaUpload(workspace_id=user.workspace_id, brand_id=brand_id, created_by_id=user.id,
                        file_id=stored.id, seconds=seconds)  # fmt: skip
    db.add(added)
    db.flush()
    return added, data
