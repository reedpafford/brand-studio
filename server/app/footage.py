"""Brand footage (Reed, 9 Nov, the runway's item 10): a brand's own real clips on its library's
Footage tab, added once (a Media upload marked `footage`), each with what it shows and which
product: one AI look at two of its frames (a picture check's price) or the owner's own words.
Every style's director gets the clips that fit the video best (footage_rank) as context: their
words in its steps (`block`), and a frame of each in the treatment and the plan (`frame_ids`).
On a video model that takes reference videos (Seedance), a clip may go with a take as a
reference, at the model's dearer rate (`assets`, credits.estimate). In UGC only, a B-roll shot
may BE one of them (footage_shot). A competitor's clip (Reed, 10 Nov: `competitor`) is never
one of the brand's: never listed as its footage, a shot or a reference; a script that compares
is told what never to show as ours."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import folders, footage_rank, looks
from app.models.files import MediaUpload, StoredFile
from app.models.jobs import Job
from app.models.library import Kind, LibraryItem
from app.models.projects import Project

KEY = "footage:"
FRAMES = 2  # kept per clip at upload: the first is its thumbnail
MOST, SEEN = 8, 4  # clips listed for one video (the best fits), and how many with a frame
STEP, KIND = "footage_describe", "check-claude"  # the AI description: a picture check
PLANS = ("breakdown", "narrated_breakdown", "song_breakdown")
TOLD = {"director", "treatment", "plan", "storyboard", "clip_prompts", "narrated_clip_prompts",
        "song_clip_prompts", *PLANS}  # fmt: skip
SHOWN = ("treatment", *PLANS)  # its frames are seen where the story and the shots are made


def live(db: Session, brand_id: int) -> list[MediaUpload]:
    """The brand's footage, oldest first (a deleted one is kept for Undo, never used)."""
    return list(db.scalars(select(MediaUpload).where(
        MediaUpload.brand_id == brand_id, MediaUpload.footage, MediaUpload.removed_at.is_(None)
    ).order_by(MediaUpload.id)))  # fmt: skip


def products(db: Session, brand_id: int) -> list[LibraryItem]:
    """The brand's products a clip can be of (its library's Products tab)."""
    return list(db.scalars(select(LibraryItem).where(
        LibraryItem.brands.any(id=brand_id), LibraryItem.kind == Kind.prop, ~LibraryItem.archived,
        LibraryItem.owner_project_id.is_(None), LibraryItem.owner_script_id.is_(None)
    ).order_by(LibraryItem.id)))  # fmt: skip


def ugc(project: Project) -> bool:
    """The one style whose B-roll is real-looking: its shots may be real footage."""
    return looks.base(looks.drawn(project)) == "ugc"


def relevant(db: Session, project: Project) -> list[MediaUpload]:
    """The clips that fit this video best, at most MOST (footage_rank: free, in code)."""
    return footage_rank.fit(db, project, MOST)


def line(db: Session, row: MediaUpload) -> str:
    from app.enhance import escape  # a person's words never close the tag, nor pose as a line

    item = db.get(LibraryItem, row.product_id) if row.product_id else None
    of = f" | {escape(' '.join(item.name.split()))}" if item else ""
    where = footage_rank.paths(db, row.brand_id).get(row.folder_id or 0)  # says what it is
    of += f" | in {escape(where)}" if where else ""
    said = escape(" ".join(row.description.split()))
    return f"- {KEY}{row.id} | {row.seconds or 0:.1f} s{of} | {said}"


def block(db: Session, project: Project, step: str) -> str:
    """The <footage> part of a step's system prompt: the clips that fit, one line each, then
    what this step may do with them; a script that compares, what never to show as ours
    (footage_rank.rivals). "" when the step isn't told or there are none."""
    from app.breakdown import video_model

    told = step in TOLD and project.id
    rows, theirs = (relevant(db, project), footage_rank.rivals(db, project)) if told else ([], "")
    if not rows:
        return f"<footage>\n{theirs}\n</footage>" if theirs else ""
    what = ("of its products, filmed by the brand: how each product looks, moves and works"
            if footage_rank.drawn(project) else "that best fit this video, filmed by the "
            "brand: its products, places and people")  # fmt: skip
    lines = ["<footage>", f"The brand's own real clips {what}. Show a product as they do; never "
             "invent how it works when a clip shows it.", *(line(db, r) for r in rows)]  # fmt: skip
    if step in SHOWN and (seen := rows[:SEEN]):
        lines.append(f"The first {len(seen)} images given are a frame of "
                     f"{', '.join(KEY + str(r.id) for r in seen)}, in that order.")  # fmt: skip
    if step in PLANS and ugc(project):
        lines.append(
            "This video is UGC: a B-roll shot nobody speaks in may BE one of these clips instead "
            "of being made, where it fits the story and shows what its line says. Set the shot's "
            "`footage` to the clip's id, the stretch it shows (`start` and `end` in the clip's "
            "seconds, as long as the shot) and whether its own sound plays under the voice. A "
            "footage shot is a clip of its own; each clip is used once in the video at most; "
            "never for a shot someone speaks in."
        )  # fmt: skip
    if step.endswith("clip_prompts") and video_model(project).max_reference_videos:
        lines.append(
            "A clip that shows a product working may take one of these as a reference video "
            "(references: kind video, its id; a small extra charge): write 'Show the <product> "
            "working as in [Video1]: the same look and motion; not its setting, hands or text.' "
            "At most one a clip, only where it helps."
        )  # fmt: skip
    if step == "director":
        lines.append("A shot whose `footage` is set is the brand's real clip: free, never "
                     "remade or watched. `find_footage` finds others by words.")  # fmt: skip
    return "\n".join([*lines, *([theirs] if theirs else []), "</footage>"])


def frame_ids(db: Session, project: Project) -> list[int]:
    """A frame of each of the first SEEN clips that fit (the steps in SHOWN see them)."""
    return [r.frame_file_ids[0] for r in relevant(db, project)[:SEEN] if r.frame_file_ids]


def with_frames(db: Session, project: Project, data: dict) -> dict:
    """A step's job with the footage frames as its first pictures (none: as it was)."""
    if not (ids := frame_ids(db, project)):
        return data
    files = data.get("files") or {}
    images = [*ids, *files.get("reference_images", [])]
    return {**data, "files": {**files, "reference_images": images},
            "fit_images_to": data.get("fit_images_to") or 512}  # fmt: skip


def assets(db: Session, project: Project) -> dict:
    """The clips a take may be given as a reference video, on a model that takes them and
    within its seconds: {"footage:N": (line, "video", [file_id])}."""
    from app.breakdown import video_model

    m = video_model(project)
    if not m.max_reference_videos:
        return {}
    room = m.max_reference_media_seconds or 0
    return {f"{KEY}{r.id}": (f"{KEY}{r.id} | real footage | {r.description.strip()}", "video",
                             [r.file_id])
            for r in relevant(db, project) if not room or (r.seconds or 0) <= room}  # fmt: skip


def frames(video: bytes) -> list[bytes]:
    """FRAMES frames of a clip, evenly spaced (ffmpeg, free): its thumbnail and what the AI
    description and the director see."""
    from app.worker import video_frames

    return video_frames(video, FRAMES)


def describe_input(db: Session, row: MediaUpload, brand) -> dict:
    """The AI description's call (prompts/footage_describe.md): the clip's frames, the brand's
    products by name (none for a competitor's clip, said so), its length, its folder and file
    name (they often say what it is)."""
    from app.enhance import escape
    from app.prompts import HERE

    names = "\n".join(p.name for p in products(db, row.brand_id)) or "(none)"
    names, theirs = ("(none)", "<competitor>yes</competitor>\n") if row.competitor else (names, "")
    name = db.get(StoredFile, row.file_id).filename
    prompt = (f"<brand>{brand.name}</brand>\n<products>\n{names}\n</products>\n{theirs}"
              f"<seconds>{row.seconds or 0:.1f}</seconds>\n"
              f"<folder>{escape(folders.path(db, row.live_folder_id))}</folder>\n"
              f"<file>{escape(name)}</file>")  # fmt: skip
    return {"step": STEP, "media_upload_id": row.id, "brand_id": row.brand_id, "effort": "low",
            "system": [(HERE / f"{STEP}.md").read_text()], "prompt": prompt, "max_tokens": 600,
            "files": {"reference_images": row.frame_file_ids}, "fit_images_to": 768}  # fmt: skip


def save_description(db: Session, job: Job) -> None:
    """The AI's words, unless the owner typed their own meanwhile; its product, when it
    named one of the brand's and none was picked (never on a competitor's clip)."""
    row = db.get(MediaUpload, job.input["media_upload_id"])
    if row is None or row.describe_job_id != job.id:
        return
    out = job.output or {}
    row.describe_job_id = None
    if not row.description.strip():
        row.description = (out.get("description") or "").strip()[:500]
    said = (out.get("product") or "").strip().lower()
    if row.product_id is None and said and not row.competitor:
        row.product_id = next((p.id for p in products(db, row.brand_id)
                               if p.name.strip().lower() == said), None)  # fmt: skip


def describe_failed(db: Session, job: Job) -> None:
    """It couldn't be described: the owner types it (the tab says so)."""
    row = db.get(MediaUpload, job.input.get("media_upload_id") or 0)
    if row is not None and row.describe_job_id == job.id:
        row.describe_job_id = None
        row.describe_note = ("The AI couldn’t describe it, and nothing was charged. Edit it to "
                             "say what it shows.")  # fmt: skip
