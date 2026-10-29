"""Generating a project's clips (Seedance, one take per run) and stitching the picked takes
into the finished video (ffmpeg, free)."""

import re
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.advice import names
from app.breakdown import video_model
from app.clip_prompts import MODERATED, assets
from app.credits import estimate
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.library import LibraryItem
from app.models.projects import Project
from app.references import LONG_SIDE
from app.sheets import require_cast_sheets, require_looks, require_sheet
from app.storyboard import say_logo

RESOLUTION = "480p"  # project clips are planned and budgeted at 480p
KEYS = {"image": "reference_images", "video": "reference_videos", "audio": "reference_audios"}


def take_input(db: Session, project: Project, clip: ProjectClip, note: str = "") -> dict:
    """The Seedance job for one clip: its prompt as written (it already says which picture is
    which), the project's aspect ratio, and its references by file id in the clip's order."""
    from app.breakdown import would_show

    known = assets(db, project)
    breakdown = db.get(BreakdownVersion, clip.breakdown_id).data
    shots = next((c["shot_ids"] for c in breakdown["clips"] if c["id"] == clip.clip_id), [])
    require_cast_sheets(db, breakdown, shots, known)
    require_looks(would_show(db, project, breakdown, shots), known)
    files: dict[str, list[int]] = {key: [] for key in KEYS.values()}
    exact: list[int] = []
    images = [r["id"] for r in clip.references if r["kind"] == "image"]  # never a logo as a chart
    for ref in clip.references:
        if ref["id"] not in known:
            raise HTTPException(
                409, "A picture on this clip is no longer part of this video. Edit the prompt."
            )
        _, kind, file_ids = known[ref["id"]]
        if not file_ids and ref["id"].startswith(("char:", "place:")):
            require_sheet(db.get(LibraryItem, int(ref["id"].split(":")[1])))
        if not file_ids:
            name = names(known).get(ref["id"], "A picture on this clip")
            raise HTTPException(422, f"{name} has no picture yet. Add one in Cast & places.")
        files[KEYS[kind]].append(file_ids[0])
        if ref["id"].startswith(("screen:", "prop:")):
            exact.append(file_ids[0])  # Reed: screens and products show exactly, never lossy
    model = video_model()
    return {
        "step": "clip_take",
        "project_id": project.id,
        "project_clip_id": clip.id,
        "clip_prompt": clip.prompt,  # kept with the take, so picking it back restores it
        "model": model.id,
        "brand_id": project.brand_id,
        "fit_images_to": LONG_SIDE[RESOLUTION],
        "exact_file_ids": exact,
        "input": {
            "prompt": _with_note(in_english(say_logo(known, clip.prompt, images, clip=True)), note),
            "duration": clip.seconds,
            "resolution": RESOLUTION,
            "aspect_ratio": project.aspect_ratio,
            "generate_audio": True,
        },
        "files": {k: v for k, v in files.items() if v},
    }


ENGLISH = "Use English: every spoken line is in English, and any text on screen is in English."


def in_english(prompt: str) -> str:
    """Every take is asked for in English (Reed, 2026-10-27: takes came out in another language
    after "Change this…"): one fixed line right after the References line, so the prompt still
    opens and closes on the same audio line. Free; the saved prompt is unchanged."""
    lines = prompt.splitlines()
    if ENGLISH in lines:
        return prompt
    at = next((i for i, x in enumerate(lines) if x.startswith("References: ")), 0)
    return "\n".join([*lines[: at + 1], ENGLISH, *lines[at + 1 :]])


BUSY = ("The video service was busy and couldn't finish this. Nothing was charged; press {} "
        "to try again.")  # fmt: skip
REFUSED = "The video model thinks this clip looks too much like someone else's character or video."


SENSITIVE = ("The video model flagged this take as sensitive. Nothing was charged. Its check is "
             "a little random, so making it again may pass; if it keeps failing, change the "
             "wording.")  # fmt: skip


def moderated(detail: str) -> str:
    """What the video model's content check read a take as: the prompt refused ("flagged for:
    sexual", ContentModerationError), or "sensitive" for E005's "flagged as sensitive" (a
    take, at random); "" when it didn't refuse it that way. Seedance's copyright E005 says
    what to do itself."""
    if "copyright" in detail.lower():
        return ""
    if said := re.search(r"flagged for:?\s*([a-z][a-z ,/-]*[a-z])", detail, re.I):
        return said.group(1).lower()
    if "ContentModeration" in detail:
        return "unsafe content"
    return "sensitive" if re.search(r"flagged as sensitive|E005", detail, re.I) else ""


def refused(db: Session, job: Job) -> None:
    """Seedance's copyright refusal ("…may be related to copyright restrictions") in plain
    words with a next step (rules 4 and 22), never "Ask the owner". Refused takes aren't
    counted (credits.COUNTED), so nothing is charged. A busy service ("Service is temporarily
    unavailable") says to try again (Producer, rule 22)."""
    row = db.get(ProjectClip, job.input.get("project_clip_id") or 0)
    if re.search(r"service is (temporarily|currently) unavailable", job.error_detail or "", re.I):
        took = row and db.scalar(select(ClipTake.id).where(ClipTake.clip_id == row.id).limit(1))
        job.error = BUSY.format("Make another take" if took else "Make clip")  # its button
        return
    if term := moderated(job.error_detail or ""):  # Reed's c4: "flagged for: sexual", 4 times
        job.error = (
            f"{MODERATED}{term}. Nothing was charged. Change the wording, then make it again."
        )
        if term == "sensitive":  # at random: make it again, or reword it once it keeps failing
            job.error = SENSITIVE
            videos = select(Job).where(Job.project_id == job.project_id, Job.kind == "video",
                                       Job.id < job.id).order_by(Job.id.desc())  # fmt: skip
            last = row and next((j for j in db.scalars(videos)
                                 if j.input.get("project_clip_id") == row.id), None)  # fmt: skip
            if not last or last.error != SENSITIVE:
                return
        if row and row.prompt == job.input.get("clip_prompt"):  # the prompt it was made from
            said = (f"{MODERATED}{term}. Keep the story and the spoken lines; remove what "
                    f"reads as {term}.")  # fmt: skip
            row.problems = [p for p in row.problems or [] if not p.startswith(MODERATED)] + [said]
            row.free_fix_used = False  # Fix this clip's prompt rewords it, free, once per refusal
        return
    if "copyright" not in (job.error_detail or "").lower():
        return
    char = next((r["id"] for r in (row.references if row else None) or []
                 if r["id"].startswith("char:")), None)  # fmt: skip
    item = db.get(LibraryItem, int(char.split(":")[1])) if char else None
    lead = item.name if item else "the main character"
    job.error = (f"{REFUSED} This check can be a little random, so try making it again first; "
                 f"a refused take costs nothing. If it's refused again, try another look for "
                 f"{lead}, or use Change this… on the opening shot.")  # fmt: skip


def take_warning(db: Session, row: ProjectClip) -> str | None:
    """Said before the next take is paid for, once its last two takes were both refused that
    way (Kel retried 7 times)."""
    videos = select(Job).where(Job.project_id == row.project_id, Job.kind == "video")
    last = [j for j in db.scalars(videos.order_by(Job.id.desc()))
            if j.input.get("project_clip_id") == row.id][:2]  # fmt: skip
    if len(last) == 2 and all(
        j.status == JobStatus.failed and (j.error or "").startswith(REFUSED) for j in last
    ):
        return ("The last two takes of this clip were refused: the video model thought they "
                "looked too much like someone else's character or video. Change the look or "
                "the opening shot first, or this take may be refused too.")  # fmt: skip
    return None


def _with_note(prompt: str, note: str) -> str:
    """A Redo note ("what's wrong") goes into this take only, before the closing audio line
    so the prompt still opens and closes on the same line."""
    if not note:
        return prompt
    lines = prompt.rstrip().splitlines()
    keep = "The spoken lines stay exactly as written above; nobody else speaks."
    return "\n".join([*lines[:-1], f"Change from the last take: {note} {keep}", lines[-1]])


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
    take = ClipTake(clip_id=clip.id, number=count + 1, job_id=job.id, file_id=file_ids[0],
                    prompt=job.input.get("clip_prompt"))  # fmt: skip
    db.add(take)
    db.flush()
    pick(clip, take)


def pick(clip: ProjectClip, take: ClipTake) -> None:
    """Use this take; its prompt comes back with it (Undo of a change note)."""
    clip.picked_take_id, clip.file_id, clip.approved = take.id, take.file_id, False
    if take.prompt is not None:
        clip.prompt = take.prompt


def stitch(videos: list[bytes], reencode: bool = False) -> bytes:
    """Join MP4 clips in order into one MP4 with ffmpeg (no credits). Clips from one model share
    a format, so streams are copied; if that fails (or some clips have cut-ins, so formats may
    differ) they are re-encoded."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        names = []
        for n, data in enumerate(videos):
            (folder / f"{n}.mp4").write_bytes(data)
            names.append(f"file '{n}.mp4'")
        (folder / "list.txt").write_text("\n".join(names))
        base = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-i", "list.txt"]
        codecs = [["-c", "copy"], ["-c:v", "libx264", "-c:a", "aac"]][int(reencode) :]
        for codec in codecs:
            done = subprocess.run(  # noqa: S603 - fixed arguments; file names are ours
                [*base, *codec, "out.mp4"], cwd=folder, capture_output=True, timeout=600
            )
            if done.returncode == 0:
                return (folder / "out.mp4").read_bytes()
        raise RuntimeError(done.stderr.decode(errors="replace")[-2000:])
