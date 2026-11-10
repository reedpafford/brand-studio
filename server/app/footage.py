"""Brand footage (Reed, 9 Nov, the runway's item 10): a brand's own real clips on its library's
Footage tab, added once (a Media upload marked `footage`), each with what it shows and which
product: one AI look at two of its frames (a picture check's price) or the owner's own words.
Every style's director gets the clips that fit the video (by product) as context: their words
in its steps (`block`), and a frame of each in the treatment and the plan (`frame_ids`). On a
video model that takes reference videos (Seedance), a clip may go with a take as a reference,
at the model's dearer rate (`assets`, credits.estimate). In UGC only, a B-roll shot nobody
speaks in may BE one of them, from its in point to its out point, instead of being made
(`checked`): its take is cut from the clip on our server, free (`settle`), laid over or under
the voice like any B-roll (cut.py), shown once in the video, never watched or remade. Rule 13
(Reed, 9 Nov): it stops screenshots and stills being dropped onto the screen out of context;
real B-roll footage used as a B-roll shot in UGC, within the story, is allowed."""

import math
import subprocess
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import looks
from app.models.clips import ClipTake, ProjectClip
from app.models.files import MediaUpload, StoredFile
from app.models.jobs import Job, JobStatus
from app.models.library import Kind, LibraryItem
from app.models.projects import Project

KEY = "footage:"
FRAMES = 2  # kept per clip at upload: the first is its thumbnail
MOST, SEEN = 6, 4  # clips listed for one video, and how many of them with a frame
STEP, KIND = "footage_describe", "check-claude"  # the AI description: a picture check
TAKE = "footage_take"  # a footage shot's take, cut from its clip (the local lane, free)
SHORTEST = 0.5  # seconds a footage shot is at least
PLANS = ("breakdown", "narrated_breakdown", "song_breakdown")
TOLD = {"director", "treatment", "plan", "storyboard", "clip_prompts", "narrated_clip_prompts",
        "song_clip_prompts", *PLANS}  # fmt: skip
SHOWN = ("treatment", *PLANS)  # its frames are seen where the story and the shots are made
NOT_MADE = ("This shot is the brand's real footage: it's cut from the clip, never made. Change "
            "its in and out points in the plan, or take the footage off the shot.")  # fmt: skip


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
    """The described clips that fit this video, at most MOST: when its script or goal names
    some of the brand's products, only theirs (and clips of no product); else all of them."""
    from app.routes.scripts import latest

    script = latest(db, project)
    words = " ".join((script.text if script else "", project.goal or "", project.name or ""))
    words = words.lower()
    have = {p.id: p for p in products(db, project.brand_id)}
    named = {i for i, p in have.items() if p.name.strip().lower() in words}
    rows = [r for r in live(db, project.brand_id) if r.description.strip()
            and (r.product_id is None or r.product_id in have)]  # fmt: skip
    if named:
        rows = [r for r in rows if r.product_id is None or r.product_id in named]
    return rows[:MOST]


def _line(db: Session, row: MediaUpload) -> str:
    from app.enhance import escape  # a person's words never close the tag

    item = db.get(LibraryItem, row.product_id) if row.product_id else None
    of = f" | {escape(item.name)}" if item else ""
    return f"- {KEY}{row.id} | {row.seconds or 0:.1f} s{of} | {escape(row.description.strip())}"


def block(db: Session, project: Project, step: str) -> str:
    """The <footage> part of a step's system prompt: the clips that fit, one line each, then
    what this step may do with them. "" when the step isn't told or there are none."""
    from app.breakdown import video_model

    rows = relevant(db, project) if step in TOLD and project.id else []
    if not rows:
        return ""
    lines = ["<footage>", "The brand's own real clips of its products, filmed by the brand: how "
             "each product looks, moves and works. Show the product as they do; never invent how "
             "it works when a clip shows it.", *(_line(db, r) for r in rows)]  # fmt: skip
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
                     "remade or watched.")  # fmt: skip
    return "\n".join([*lines, "</footage>"])


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


# --- A footage shot in UGC: the plan's check, and its take ---


def _talks(shot) -> bool:
    return bool(shot.line or shot.speaker or getattr(shot, "sung", False))


def checked(db: Session, project: Project, bd, timed: bool = False):
    """Each footage shot as it can be used (free, in code; each change said as Advice): only
    in UGC, only on a B-roll shot nobody speaks in that is a clip of its own, only a clip of the
    brand's, each once in the video; its stretch kept inside the clip. It shows the real thing:
    no cast sheet or screen goes with it. Not `timed` (a song's or a narration's clock): the
    shot is as long as its stretch."""
    shots = [s for scene in bd.scenes for s in scene.shots]
    if not any(s.footage for s in shots):
        return bd, []
    clips = {sid: c for c in bd.clips for sid in c.shot_ids}
    have = {f"{KEY}{r.id}": r for r in live(db, project.brand_id)}
    seen, notes = set(), []
    for s in (s for s in shots if s.footage):
        use, clip = s.footage, clips.get(s.id)
        why = ("real footage is a shot only in UGC" if not ugc(project)
               else "someone speaks in it" if _talks(s)
               else "that clip isn't in the brand's footage" if use.id not in have
               else f"{use.id} is already shown in this video" if use.id in seen
               else "it shares its clip with other shots" if clip and len(clip.shot_ids) > 1
               else "")  # fmt: skip
        if why:
            s.footage = None
            notes.append(f"Advice: Shot {s.id} is made, not real footage: {why}.")
            continue
        seen.add(use.id)
        length = have[use.id].seconds or 0
        start = round(min(max(use.start, 0.0), max(length - SHORTEST, 0.0)), 2)
        end = round(min(max(use.end, start + SHORTEST), length), 2)
        s.footage = use.model_copy(update={"start": start, "end": end})
        s.character_ids, s.screen_ids, s.screen_figure = [], [], None
        if not timed:
            s.seconds = round(end - start, 1)
            if clip:
                clip.seconds = max(1, math.ceil(end - start - 0.01))
    return bd, notes


def uses(data: dict) -> dict[str, dict]:
    """The plan's footage clips: clip id -> its one shot's footage ({id, start, end, sound})."""
    shots = {s["id"]: s for sc in data.get("scenes", []) for s in sc.get("shots", [])}
    out = {}
    for c in data.get("clips", []):
        mine = [shots[i] for i in c.get("shot_ids", []) if i in shots]
        if len(mine) == 1 and mine[0].get("footage"):
            out[c["id"]] = mine[0]["footage"]
    return out


def of_clip(db: Session, row: ProjectClip) -> dict | None:
    """The footage a clip's plan shows, or None (a clip that's made)."""
    from app.models.breakdowns import BreakdownVersion

    plan = db.get(BreakdownVersion, row.breakdown_id) if row.breakdown_id else None
    return uses(plan.data).get(row.clip_id) if plan else None


def is_footage(take: ClipTake | None) -> bool:
    return bool(take and (take.made_with or {}).get("footage"))


def _prompt(row: MediaUpload, use: dict) -> str:
    return (f"Real footage from the brand's library ({KEY}{row.id}, {use['start']:.1f}–"
            f"{use['end']:.1f} s{'' if use.get('sound') else ', muted'}): "
            f"{row.description.strip()}")  # fmt: skip


def settle(db: Session, project: Project, user_id: int | None = None, first: bool = True) -> None:
    """The newest plan's footage clips, free: each has its row (the plan's, so its prompt is
    never written) and its take, cut from the clip on our server (`TAKE`), picked once it's
    made; one cut for this use already is picked again. A clip the plan now makes stops using
    a footage take. Not `first`: only once the video's clips are written (their prompts come
    first, as the director asks for them)."""
    from app.clip_prompts import newest

    bd = newest(db, project)
    rows = {r.clip_id: r for r in db.scalars(select(ProjectClip).where(
        ProjectClip.project_id == project.id))}  # fmt: skip
    if bd is None or not (first or rows):
        return
    wanted = uses(bd.data)
    for clip_id, row in rows.items():
        if clip_id not in wanted and is_footage(db.get(ClipTake, row.picked_take_id or 0)):
            row.picked_take_id = row.file_id = None
    for clip_id, use in wanted.items():
        source = db.get(MediaUpload, int(use["id"].removeprefix(KEY)))
        row = rows.get(clip_id)
        if row is None:
            row = ProjectClip(project_id=project.id, clip_id=clip_id, references=[], prompt="")
            db.add(row)
        row.breakdown_id, row.seconds = bd.id, max(1, math.ceil(use["end"] - use["start"] - 0.01))
        row.prompt, row.references, row.problems, row.kept = _prompt(source, use), [], [], []
        row.job_id = None
        db.flush()
        takes = db.scalars(select(ClipTake).where(ClipTake.clip_id == row.id)).all()
        same = next((t for t in takes if (t.made_with or {}).get("footage") == use), None)
        if same is not None:
            row.picked_take_id, row.file_id = same.id, same.file_id
            continue
        if _cutting(db, row.id, use):
            continue
        db.add(Job(workspace_id=project.workspace_id, created_by_id=user_id or
                   project.created_by_id, kind=TAKE, provider="local", credits=0,
                   status=JobStatus.queued, project_id=project.id, brand_id=project.brand_id,
                   input={"step": TAKE, "project_id": project.id, "project_clip_id": row.id,
                          "footage": use, "video_key": db.get(StoredFile, source.file_id).key,
                          "clip_prompt": row.prompt}))  # fmt: skip
    db.flush()


def _cutting(db: Session, row_id: int, use: dict) -> bool:
    waiting = db.scalars(select(Job).where(Job.kind == TAKE, Job.status.in_(
        (JobStatus.queued, JobStatus.running))))  # fmt: skip
    return any(j.input.get("project_clip_id") == row_id and j.input.get("footage") == use
               for j in waiting)  # fmt: skip


def save_take(db: Session, job: Job) -> None:
    """The cut is made: a take of its clip, picked, as made from the footage (no watch: real
    footage is never checked or remade)."""
    from app.clip_takes import pick

    row = db.get(ProjectClip, job.input["project_clip_id"])
    file_ids = (job.output or {}).get("file_ids") or []
    if row is None or not file_ids or of_clip(db, row) != job.input["footage"]:
        return  # the plan moved on while it was cut
    count = len(db.scalars(select(ClipTake.id).where(ClipTake.clip_id == row.id)).all())
    take = ClipTake(clip_id=row.id, number=count + 1, job_id=job.id, file_id=file_ids[0],
                    prompt=row.prompt, look=looks.drawn(db.get(Project, row.project_id)),
                    made_with={"footage": job.input["footage"]})  # fmt: skip
    db.add(take)
    db.flush()
    pick(row, take)


def cut(video: bytes, start: float, end: float, sound: bool, folder: Path) -> Path:
    """The stretch of a clip from `start` to `end`, as an H.264 MP4 (its sound only with
    `sound`): the footage shot's take."""
    src, out = folder / "footage.mp4", folder / "cut.mp4"
    src.write_bytes(video)
    audio = ["-c:a", "aac", "-b:a", "128k"] if sound else ["-an"]
    subprocess.run(  # noqa: S603
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-i", str(src),  # noqa: S607
         "-t", f"{end - start:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", *audio,
         "-movflags", "+faststart", str(out)], timeout=120, check=True)  # fmt: skip
    src.unlink()
    return out


def frames(video: bytes) -> list[bytes]:
    """FRAMES frames of a clip, evenly spaced (ffmpeg, free): its thumbnail and what the AI
    description and the director see."""
    from app.worker import video_frames

    return video_frames(video, FRAMES)


def describe_input(db: Session, row: MediaUpload, brand) -> dict:
    """The AI description's call (prompts/footage_describe.md): the clip's frames, the
    brand's products by name, its length."""
    from app.prompts import HERE

    names = "\n".join(p.name for p in products(db, row.brand_id)) or "(none)"
    prompt = (f"<brand>{brand.name}</brand>\n<products>\n{names}\n</products>\n"
              f"<seconds>{row.seconds or 0:.1f}</seconds>")  # fmt: skip
    return {"step": STEP, "media_upload_id": row.id, "brand_id": row.brand_id, "effort": "low",
            "system": [(HERE / f"{STEP}.md").read_text()], "prompt": prompt, "max_tokens": 600,
            "files": {"reference_images": row.frame_file_ids}, "fit_images_to": 768}  # fmt: skip


def save_description(db: Session, job: Job) -> None:
    """The AI's words, unless the owner typed their own meanwhile; its product, when it
    named one of the brand's and none was picked."""
    row = db.get(MediaUpload, job.input["media_upload_id"])
    if row is None or row.describe_job_id != job.id:
        return
    out = job.output or {}
    row.describe_job_id = None
    if not row.description.strip():
        row.description = (out.get("description") or "").strip()[:500]
    said = (out.get("product") or "").strip().lower()
    if row.product_id is None and said:
        row.product_id = next((p.id for p in products(db, row.brand_id)
                               if p.name.strip().lower() == said), None)  # fmt: skip


def describe_failed(db: Session, job: Job) -> None:
    """It couldn't be described: the owner types it (the tab says so)."""
    row = db.get(MediaUpload, job.input.get("media_upload_id") or 0)
    if row is not None and row.describe_job_id == job.id:
        row.describe_job_id = None
