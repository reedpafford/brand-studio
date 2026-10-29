"""Generating a project's clips (Seedance, one take per run) and stitching the picked takes
into the finished video (ffmpeg, free)."""

import logging
import re
import subprocess
import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import video_settings
from app.advice import names, stops
from app.breakdown import video_model
from app.clip_prompts import MODERATED, assets, prompt_version
from app.credits import estimate, fits
from app.db import utcnow
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import WAITING, Job, JobStatus
from app.models.library import LibraryItem
from app.models.projects import Project
from app.references import LONG_SIDE
from app.sheets import require_cast_sheets, require_looks, require_sheet
from app.storyboard import say_logo

log = logging.getLogger(__name__)
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
    model = video_model(project)
    return {
        "step": "clip_take",
        "project_id": project.id,
        "project_clip_id": clip.id,
        "clip_prompt": clip.prompt,  # kept with the take, so picking it back restores it
        "model": model.id,
        "made_with": {  # VS1: what the take is made with; OR3: its prompt's version
            **video_settings.made_with(
                db, project, images, model.id, (clip.song_slice or {}).get("sung_shots")
            ),
            **({"prompt_version": v} if (v := prompt_version(clip)) else {}),
        },
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
    job.error = (f"{REFUSED} Try another look for {lead}, or use Change this… on the opening "
                 "shot. Nothing was charged.")  # fmt: skip


BUSY_SAID = re.compile(r"service is (temporarily|currently) unavailable|^No answer within", re.I)
RETRY_WAIT = timedelta(seconds=30)  # a busy service gets a moment before the one retry


def why_failed(job: Job) -> str:
    """ "busy" (the service was busy or didn't answer), "refused" (its content check or
    copyright refusal: never charged), or "" for anything else."""
    detail = job.error_detail or ""
    if BUSY_SAID.search(detail):
        return "busy"
    return "refused" if moderated(detail) or "copyright" in detail.lower() else ""


def retry(db: Session, job: Job) -> None:
    """P3 (flows.md 1b): a take refused or not finished because the service was busy is
    tried again once on its own. A busy service gets a short wait; a refusal read as
    something ("flagged for: sexual") is reworded first by the free fix, then retried
    (`after_fix`). Never a second automatic retry, never on a video that's gone, and never
    past the video's limit, budget or the editor's week. The failed take isn't counted, so
    the credits are held once and come back if the retry fails too."""
    from app.clip_prompts import fix_job, is_stale, newest

    why = why_failed(job)
    if job.auto or not why or job.input.get("discard") or not job.project_id:
        return
    if db.scalar(select(Job.id).where(Job.retry_of_id == job.id)):
        return
    project = db.get(Project, job.project_id)
    row = db.get(ProjectClip, job.input.get("project_clip_id") or 0)
    if not row or project.archived_at is not None or row.prompt != job.input.get("clip_prompt"):
        return
    term = moderated(job.error_detail or "")
    if why == "refused" and term and term != "sensitive":
        if row.free_fix_used or is_stale(db, row, newest(db, project)):
            return
        user = db.get(User, job.created_by_id)
        fix = fix_job(db, user, project, row, stops(row))
        fix.input = {**fix.input, "then_take": job.id}
        row.free_fix_used = True
        return
    _again(db, job, job.input, wait=why == "busy")


def after_fix(db: Session, row: ProjectClip, failed_id: int) -> None:
    """The free rewording of a refused take landed: its one retry, from the new prompt, if
    nothing else stops it."""
    failed = db.get(Job, failed_id)
    project = db.get(Project, row.project_id)
    if not failed or stops(row) or project.archived_at is not None:
        return
    if db.scalar(select(Job.id).where(Job.retry_of_id == failed.id)):
        return
    try:
        again = take_input(db, project, row)
    except HTTPException as exc:  # e.g. a look unapproved since: the editor decides
        log.info("clip %s: no automatic retry: %s", row.id, exc.detail)
        return
    _again(db, failed, again, wait=False)


def _again(db: Session, job: Job, data: dict, wait: bool) -> None:
    project = db.get(Project, job.project_id)
    user = db.get(User, job.created_by_id)
    if not user or fits(db, project, user, job.credits):
        return  # it would go over: nothing more runs on its own
    if wait:
        data = {**data, "wait_until": (utcnow() + RETRY_WAIT).isoformat()}
    db.add(Job(workspace_id=job.workspace_id, created_by_id=job.created_by_id, kind=job.kind,
               provider=job.provider, input=data, project_id=job.project_id,
               brand_id=job.brand_id, credits=job.credits, approved_by_id=job.approved_by_id,
               status="queued", retry_of_id=job.id, auto=True))  # fmt: skip
    db.flush()


def retried(db: Session, row: ProjectClip) -> str | None:
    """Why the clip's newest take came from an automatic retry ("refused" or "busy"); None
    once a person has made a newer take."""
    query = select(ClipTake).where(ClipTake.clip_id == row.id).order_by(ClipTake.number.desc())
    take = db.scalar(query.limit(1))
    job = db.get(Job, take.job_id) if take else None
    return (why_failed(db.get(Job, job.retry_of_id)) or None) if job and job.auto else None


def still_wanted(db: Session, job: Job) -> bool:
    """An automatic retry still fits its clip when it starts: the video isn't archived and the
    prompt is the one it was made from (Flow-QA: an edit during a busy wait)."""
    row = db.get(ProjectClip, job.input.get("project_clip_id") or 0)
    project = db.get(Project, job.project_id) if job.project_id else None
    return bool(row and project and project.archived_at is None
                and row.prompt == job.input.get("clip_prompt"))  # fmt: skip


def retrying(db: Session, row: ProjectClip) -> str | None:
    """Why this clip's take is being tried again on its own ("refused" or "busy"), while it is."""
    jobs = db.scalars(select(Job).where(Job.project_id == row.project_id, Job.status.in_(WAITING)))
    for j in jobs:
        if j.auto and j.input.get("project_clip_id") == row.id and still_wanted(db, j):
            return why_failed(db.get(Job, j.retry_of_id)) or None
        if j.input.get("then_take") and j.input.get("clip_ids") == [row.clip_id]:
            return "refused"
    return None


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
    job = {"model": video_model(project).id, "input": {"resolution": RESOLUTION}}
    return estimate(db, project.workspace_id, "video", Decimal(clip.seconds), job)


def save_take(db: Session, job: Job) -> None:
    """A new take: numbered, and picked (the newest take is picked when it arrives)."""
    clip = db.get(ProjectClip, job.input["project_clip_id"])
    file_ids = (job.output or {}).get("file_ids") or []
    if not clip or not file_ids:
        return
    count = db.scalar(select(func.count(ClipTake.id)).where(ClipTake.clip_id == clip.id))
    take = ClipTake(clip_id=clip.id, number=count + 1, job_id=job.id, file_id=file_ids[0],
                    prompt=job.input.get("clip_prompt"),
                    look=db.get(Project, clip.project_id).look,
                    made_with=job.input.get("made_with") or {})  # fmt: skip
    db.add(take)
    db.flush()
    pick(clip, take)
    from app.item_checks import queue_safely  # P4: Advice only, never a block

    breakdown = db.get(BreakdownVersion, clip.breakdown_id).data
    shots = next((c["shot_ids"] for c in breakdown["clips"] if c["id"] == clip.clip_id), [])
    refs = [r["id"] for r in clip.references or [] if r["kind"] == "image"]
    queue_safely(db, job, "take", take.id, take.file_id, refs, clip.breakdown_id, shots)


def pick(clip: ProjectClip, take: ClipTake) -> None:
    """Use this take; its prompt comes back with it (Undo of a change note)."""
    clip.picked_take_id, clip.file_id, clip.approved = take.id, take.file_id, False
    if take.prompt is not None:
        clip.prompt = take.prompt
    v = (take.made_with or {}).get("prompt_version")  # OR3: its version is the one in hand
    if back := [e for e in clip.prompt_history or [] if e["v"] == v]:
        clip.prompt_history = [back[0], *(e for e in clip.prompt_history if e["v"] != v)]


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


FADE = 1.5  # seconds: a song video's end fades out (flows V6)
# A narrated video's mix (flows V6n): the takes' own sound under the narration, the music
# lower still and ducked while the narrator speaks, the whole about -14 LUFS
TAKES, MUSIC, LOUD = 0.75, 0.30, "loudnorm=I=-14:TP=-1.5:LRA=11"
DUCK = "sidechaincompress=threshold=0.05:ratio=6:attack=20:release=400"  # under the voice
SAME = "aformat=sample_rates=44100:channel_layouts=stereo"


def _probe(folder: Path, name: str, stream: str, entries: str) -> str:
    probe = ["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries",
             f"stream={entries}", "-of", "csv=p=0:s=x", name]  # fmt: skip
    return subprocess.run(  # noqa: S603 - fixed arguments; file names are ours
        probe, cwd=folder, capture_output=True, text=True, timeout=60,
    ).stdout.strip()  # fmt: skip


def _narrated_mix(folder: Path, lengths: list[float], music: bool, fade: str) -> list[str]:
    """Each take's own sound (silence if it has none), the narration on top, the music under
    it ducked by the voice, made loud enough and faded."""
    n, total = len(lengths), sum(lengths)
    takes = [f"[{i}:a]{SAME},atrim=duration={d},asetpts=PTS-STARTPTS,apad=whole_dur={d},"
             f"volume={TAKES}[a{i}]" if _probe(folder, f"{i}.mp4", "a:0", "index")
             else f"anullsrc=r=44100:cl=stereo,atrim=duration={d}[a{i}]"
             for i, d in enumerate(lengths)]  # fmt: skip
    joined = "".join(f"[a{i}]" for i in range(n))
    voice = f"[{n}:a]{SAME},atrim=duration={total},apad=whole_dur={total}"
    graph = [*takes, f"{joined}concat=n={n}:v=0:a=1[takes]"]
    if music:
        graph += [f"{voice},asplit=2[voice][key]",
                  f"[{n + 1}:a]{SAME},atrim=duration={total},volume={MUSIC}[bed]",
                  f"[bed][key]{DUCK}[under]"]  # fmt: skip
    else:
        graph.append(f"{voice}[voice]")
    parts = "[takes][voice][under]" if music else "[takes][voice]"
    graph.append(f"{parts}amix=inputs={3 if music else 2}:normalize=0:duration=first,{LOUD},"
                 f"aresample=44100,afade=t=out:{fade}[a]")  # fmt: skip
    return graph


def song_cut(
    videos: list[bytes], lengths: list[float], song: bytes,
    narrated: bool = False, music: bytes | None = None,
) -> bytes:  # fmt: skip
    """A song video (flows V6, free): each picked take cut to its piece of the song, counting
    from its start (a short one holds its last frame), joined in order with its own sound
    dropped, the song laid under the whole picture, and the end faded. A narrated video
    (V6n) keeps each take's own sound under the narration, with its music bed if made."""
    total = sum(lengths)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for n, data in enumerate(videos):
            (folder / f"{n}.mp4").write_bytes(data)
        (folder / "song").write_bytes(song)
        size = _probe(folder, "0.mp4", "v:0", "width,height") or "720x1280"
        parts = [f"[{n}:v]trim=duration={d},setpts=PTS-STARTPTS,tpad=stop_mode=clone:"
                 f"stop_duration={d},trim=duration={d},scale={size.replace('x', ':')},setsar=1,"
                 f"fps=30,format=yuv420p[v{n}]" for n, d in enumerate(lengths)]  # fmt: skip
        joined = "".join(f"[v{n}]" for n in range(len(videos)))
        fade = f"st={max(total - FADE, 0):.2f}:d={FADE}"
        sound = (_narrated_mix(folder, lengths, music is not None, fade) if narrated else [
            f"[{len(videos)}:a]atrim=duration={total},asetpts=PTS-STARTPTS,"
            f"apad=whole_dur={total},afade=t=out:{fade}[a]"])  # fmt: skip
        graph = ";".join(
            [*parts, f"{joined}concat=n={len(videos)}:v=1:a=0,fade=t=out:{fade}[v]", *sound]
        )
        inputs = [arg for n in range(len(videos)) for arg in ("-i", f"{n}.mp4")]
        if narrated and music is not None:  # a bed shorter than the video loops
            (folder / "music").write_bytes(music)
            inputs += ["-i", "song", "-stream_loop", "-1", "-i", "music"]
        else:
            inputs += ["-i", "song"]
        command = ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex",
                   graph, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-c:a", "aac", "-t",
                   str(total), "-movflags", "+faststart", "out.mp4"]  # fmt: skip
        done = subprocess.run(  # noqa: S603 - fixed arguments; file names are ours
            command, cwd=folder, capture_output=True, timeout=600,
        )  # fmt: skip
        if done.returncode:
            raise RuntimeError(done.stderr.decode(errors="replace")[-2000:])
        return (folder / "out.mp4").read_bytes()
