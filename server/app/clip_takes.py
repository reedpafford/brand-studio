"""Generating a project's clips (Seedance, one take per run) and stitching the picked takes
into the finished video (ffmpeg, free)."""

import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.breakdown import video_model
from app.clip_prompts import assets
from app.credits import estimate
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.projects import Project
from app.references import LONG_SIDE
from app.sheets import require_sheet

RESOLUTION = "480p"  # project clips are planned and budgeted at 480p
KEYS = {"image": "reference_images", "video": "reference_videos", "audio": "reference_audios"}


def take_input(db: Session, project: Project, clip: ProjectClip, note: str = "") -> dict:
    """The Seedance job for one clip: its prompt as written (it already says which picture is
    which), the project's aspect ratio, and its references by file id in the clip's order."""
    known = assets(db, project)
    files: dict[str, list[int]] = {key: [] for key in KEYS.values()}
    exact: list[int] = []
    for ref in clip.references:
        if ref["id"] not in known:
            raise HTTPException(409, f"{ref['id']} is no longer part of this project.")
        _, kind, file_ids = known[ref["id"]]
        if not file_ids and ref["id"].startswith(("char:", "place:")):
            require_sheet(db.get(LibraryItem, int(ref["id"].split(":")[1])))
        if not file_ids:
            raise HTTPException(422, f"{ref['id']} has no picture yet. Add one in the library.")
        files[KEYS[kind]].append(file_ids[0])
        if ref["id"].startswith(("screen:", "prop:")):
            exact.append(file_ids[0])  # Reed: screens and products show exactly, never lossy
    model = video_model()
    return {
        "step": "clip_take",
        "project_id": project.id,
        "project_clip_id": clip.id,
        "model": model.id,
        "brand_id": project.brand_id,
        "fit_images_to": LONG_SIDE[RESOLUTION],
        "exact_file_ids": exact,
        "input": {
            "prompt": _with_note(clip.prompt, note),
            "duration": clip.seconds,
            "resolution": RESOLUTION,
            "aspect_ratio": project.aspect_ratio,
            "generate_audio": True,
        },
        "files": {k: v for k, v in files.items() if v},
    }


def _with_note(prompt: str, note: str) -> str:
    """A Redo note ("what's wrong") goes into this take only, before the closing audio line
    so the prompt still opens and closes on the same line."""
    if not note:
        return prompt
    lines = prompt.rstrip().splitlines()
    return "\n".join([*lines[:-1], f"Change from the last take: {note}", lines[-1]])


def take_credits(db: Session, project: Project, clip: ProjectClip) -> Decimal:
    """What one more take costs, the same estimate `enqueue` charges."""
    job = {"model": video_model().id, "input": {"resolution": RESOLUTION}}
    return estimate(db, project.workspace_id, "video", Decimal(clip.seconds), job)


def save_take(db: Session, job: Job) -> None:
    """A new take: numbered, and picked (the newest take is picked when it arrives)."""
    clip = db.get(ProjectClip, job.input["project_clip_id"])
    file_ids = (job.output or {}).get("file_ids") or []
    if not clip or not file_ids:
        return
    count = db.scalar(select(func.count(ClipTake.id)).where(ClipTake.clip_id == clip.id))
    take = ClipTake(clip_id=clip.id, number=count + 1, job_id=job.id, file_id=file_ids[0])
    db.add(take)
    db.flush()
    pick(clip, take)


def pick(clip: ProjectClip, take: ClipTake) -> None:
    clip.picked_take_id, clip.file_id, clip.approved = take.id, take.file_id, False


def stitch(videos: list[bytes]) -> bytes:
    """Join MP4 clips in order into one MP4 with ffmpeg (no credits). Clips from one model share
    a format, so streams are copied; if that fails they are re-encoded."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        names = []
        for n, data in enumerate(videos):
            (folder / f"{n}.mp4").write_bytes(data)
            names.append(f"file '{n}.mp4'")
        (folder / "list.txt").write_text("\n".join(names))
        base = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-i", "list.txt"]
        for codec in (["-c", "copy"], ["-c:v", "libx264", "-c:a", "aac"]):
            done = subprocess.run(  # noqa: S603 - fixed arguments; file names are ours
                [*base, *codec, "out.mp4"], cwd=folder, capture_output=True, timeout=600
            )
            if done.returncode == 0:
                return (folder / "out.mp4").read_bytes()
        raise RuntimeError(done.stderr.decode(errors="replace")[-2000:])
