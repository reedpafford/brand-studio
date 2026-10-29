"""A study of someone else's song ad (flows S3a), free on our own server: its length, BPM,
sections with their lines, the words with their times, and one frame per shot. It guides the
song directions' shape (the Director's prompts.song_study_block); it never fills the lyrics
or the style line (rule 19), and the directions never reuse its lines (check.copied_lines).

The study lives on the version as ScriptDraft.song_study: {job_id, source, link, seconds,
bpm, sections: [{name, start, end, lines, guessed}], lines: [{text, start, end}], words:
[{word, start, end}], frames: [{file_id, t}], use_as_guide, removed_at, attempt,
stale_frames} (see "On the version" below for `attempt` and `stale_frames`).

A reference has no [Verse]/[Chorus] tags, so its sections are inferred: lines are grouped
where the singing pauses for a bar or more, or where it moves in or out of lines that repeat;
a repeated group is a Chorus, others are Verses, and a lone Verse just before the last Chorus
(after one between Choruses) a Bridge. Music before the first word is the Intro, after the
last the Outro. Names that rest on a guess are marked `guessed`."""

import json
import re
import subprocess  # noqa: S404 - fixed argument lists, never a shell
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session

from app import reel, song_timing
from app.advice import SaidText
from app.db import utcnow
from app.models.files import StoredFile
from app.models.jobs import Job, JobStatus
from app.models.script_library import ScriptDraft
from app.schemas import UtcTime

STEP = "song_study"
MAX_SECONDS = 240  # Reed's references run 2:30; the reel import's 90 s is for Gemini's copy
LIMIT = 600  # s for a whole study: a 4-minute song's words take a few on the CPU model
POLL = 0.5  # s between looks at Stop while the words are read
FRAMES = 16
FRAME_WIDTH = 360
PAUSE = 1.5  # s of no singing that ends a group, unless a bar is longer
SAME = 0.8  # how alike two lines are to count as the same line
WAITING = (JobStatus.queued, JobStatus.running)
# `problem` is a short phrase the card puts in "We couldn't open that reel: {problem}. Nothing
# was charged." (Next-Screens), by the reel import's refusal codes and ours.
PROBLEMS = {
    "blocked": "Instagram didn't let us download it (upload the video instead)",
    "gone": "it's private or was removed",
    "bad_file": "it isn't a video we can read (an MP4 or MOV with sound, up to 100 MB)",
    "too_long": "it's longer than 4 minutes",
    "no_words": "we couldn't hear any singing in it",
    "too_slow": "it took over 10 minutes to study",
}
FAILED = "studying it didn't finish"
BUSY = "A song ad is already being studied here. Wait for it, or cancel it."


class Stopped(Exception):
    """Stop was pressed while it ran: nothing is kept (the job is already cancelled)."""


@dataclass
class Watch:
    """Stop and the time limit, looked at between steps and while the words are read."""

    stopped: Callable[[], bool] = lambda: False
    until: float = float("inf")  # time.monotonic() deadline

    def check(self) -> None:
        if self.stopped():
            raise Stopped
        if time.monotonic() > self.until:
            raise reel.Refused("too_slow", PROBLEMS["too_slow"])


def wait(args: list[str], watch: Watch) -> bytes:
    """Run a command to its end and return its output, killing it at Stop or the limit."""
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as proc:  # noqa: S603
        while True:
            try:
                out, _ = proc.communicate(timeout=POLL)
                break
            except subprocess.TimeoutExpired:
                try:
                    watch.check()
                except BaseException:
                    proc.kill()
                    raise
    if proc.returncode != 0:
        raise RuntimeError(f"Reading the song ad's words failed ({proc.returncode}).")
    return out


def hear(path: Path, watch: Watch) -> list[dict]:
    """Local Whisper, unprompted: [{start, end, text, words: [{word, start, end}]}]."""
    return json.loads(wait([sys.executable, "-m", "app.whisper", str(path), "--study"], watch))


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w' ]", " ", text.lower()).split())


def _alike(a: str, b: str) -> bool:
    return bool(a) and SequenceMatcher(None, a, b, autojunk=False).ratio() >= SAME


def sections(lines: list[dict], beat_times: list[float], bpm: float, seconds: float):
    """The song's parts in order: [{name, start, end, lines, guessed}] (see the module)."""
    if not lines:
        return []
    said = [_norm(x["text"]) for x in lines]
    repeats = [any(_alike(s, o) for j, o in enumerate(said) if j != i) for i, s in enumerate(said)]
    pause = max(PAUSE, 4 * 60 / bpm) if bpm else PAUSE
    groups: list[list[int]] = [[0]]
    for i in range(1, len(lines)):
        gap = lines[i]["start"] - lines[i - 1]["end"]
        if gap >= pause or repeats[i] != repeats[i - 1]:
            groups.append([])
        groups[-1].append(i)
    has_chorus = any(repeats)
    parts = [{"name": "Chorus" if repeats[g[0]] else "Verse", "first": g[0], "last": g[-1],
              "guessed": not has_chorus} for g in groups]  # fmt: skip
    choruses = [k for k, p in enumerate(parts) if p["name"] == "Chorus"]
    between = [k for k, p in enumerate(parts)
               if p["name"] == "Verse" and choruses and choruses[0] < k < choruses[-1]]  # fmt: skip
    if len(between) >= 2 and between[-1] + 1 == choruses[-1]:
        parts[between[-1]] |= {"name": "Bridge", "guessed": True}
    bars = beat_times[::4] or beat_times
    out = []
    for p in parts:
        start = lines[p["first"]]["start"]
        floor = out[-1]["start"] if out else 0  # from the last bar line before its first word
        before = [b for b in bars if floor < b <= start + 0.15]
        start = before[-1] if before else start
        out.append({"name": p["name"], "start": round(start, 2),
                    "lines": [lines[i]["text"] for i in range(p["first"], p["last"] + 1)],
                    "guessed": p["guessed"]})  # fmt: skip
    if out[0]["start"] > 1:
        out.insert(0, {"name": "Intro", "start": 0.0, "lines": [], "guessed": False})
    out[0]["start"] = 0.0
    last = lines[-1]["end"]
    if seconds - last > 2:
        out.append({"name": "Outro", "start": round(last, 2), "lines": [], "guessed": False})
    for part, after in zip(out, [*out[1:], None], strict=True):
        part["end"] = after["start"] if after else round(seconds, 2)
    return [p for p in out if p["end"] > p["start"]]


def frames(video: Path, seconds: float, folder: Path) -> list[tuple[Path, float]]:
    """One frame from the middle of each shot (sampled evenly past FRAMES), with its time."""
    spans = reel._spans(reel.cuts(video), seconds)
    if len(spans) > FRAMES:
        spans = [spans[i * len(spans) // FRAMES] for i in range(FRAMES)]
    found = []
    for n, (a, b) in enumerate(spans):
        t = round((a + b) / 2, 2)
        if reel._grab(video, t, path := folder / f"frame{n}.jpg", FRAME_WIDTH):
            found.append((path, t))
    return found


def study(
    video: Path, folder: Path, hear=hear, watch: Watch | None = None
) -> tuple[dict, list[tuple[Path, float]]]:
    """The study of one video and its frames. Raises reel.Refused with a plain reason, and
    Stopped when Stop is pressed."""
    watch = watch or Watch()
    seconds = reel.probe(video, MAX_SECONDS)
    watch.check()
    heard = [x for x in hear(video, watch) if x["text"].strip()]
    watch.check()
    if not heard:
        raise reel.Refused("no_words", PROBLEMS["no_words"])
    samples = song_timing._samples(video)
    bpm, beat_times = song_timing.beats(samples, seconds)
    lines = [{"text": x["text"].strip(), "start": x["start"], "end": x["end"]} for x in heard]
    words = [w for x in heard for w in x.get("words", [])]
    found = {"seconds": seconds, "bpm": bpm, "lines": lines, "words": words,
             "sections": sections(lines, beat_times, bpm, seconds)}  # fmt: skip
    watch.check()
    return found, frames(video, seconds, folder)


def stop_key(job_id: int) -> str:
    """A marker in the shared storage that the worker's study looks for (Stop)."""
    return f"song-study-stop/{job_id}"


class StudySection(BaseModel):
    name: Literal["Intro", "Verse", "Chorus", "Bridge", "Outro"]
    start: float
    end: float
    lines: list[str]
    guessed: bool  # the name is a guess (a Bridge, or nothing repeats)


class StudyLine(BaseModel):
    text: str
    start: float
    end: float


class StudyWord(BaseModel):
    word: str
    start: float
    end: float


class StudyFrame(BaseModel):
    file_id: int
    t: float  # where in the song ad it was taken (s)


class StudyJob(BaseModel):
    id: int  # Cancel: POST /jobs/{id}/cancel
    status: Literal["queued", "running", "failed"]
    started_at: UtcTime | None


class StudyAttempt(BaseModel):
    """A newer study that hasn't replaced the one shown: still running, or failed."""

    status: Literal["studying", "failed"]
    job: StudyJob | None = None
    source: Literal["link", "upload"]
    link: str | None = None
    problem: SaidText = ""  # failed: a short phrase, no full stop (PROBLEMS)
    problem_code: str | None = None


class SongStudyOut(BaseModel):
    """The version's study. With no finished study, the status and its fields are the newest
    attempt's; with one, it shows (done) and a newer attempt still running or failed is in
    `attempt` (Flow-QA: a failed re-study never takes the good one away)."""

    status: Literal["studying", "done", "failed"]
    job: StudyJob | None = None  # while studying, or when the job itself failed
    source: Literal["link", "upload"]
    link: str | None = None
    seconds: float | None = None
    bpm: float | None = None  # 0: no steady beat
    sections: list[StudySection] = []
    lines: list[StudyLine] = []
    words: list[StudyWord] = []
    frames: list[StudyFrame] = []
    use_as_guide: bool = False
    problem: SaidText = ""  # failed: a short phrase, no full stop (PROBLEMS); "" otherwise
    problem_code: str | None = None  # blocked, gone, bad_file, too_long, no_words
    attempt: StudyAttempt | None = None


# --- On the version -------------------------------------------------------------------------
# ScriptDraft.song_study holds the finished study (when there is one) and, under `attempt`,
# the newest press while it runs or after it failed: {job_id, source, link, problem,
# problem_code}. A study that saves replaces the finished one; its old frames wait in
# `stale_frames` until the next press deletes them (only a route can delete stored bytes).


def _attempt(draft: ScriptDraft) -> dict:
    return (draft.song_study or {}).get("attempt") or {}


def busy(db: Session, draft: ScriptDraft) -> bool:
    job = db.get(Job, _attempt(draft).get("job_id") or 0)
    return job is not None and job.status in WAITING


def _finished(found: dict) -> bool:
    return found.get("seconds") is not None and not found.get("removed_at")


def start(
    db: Session, user, draft: ScriptDraft, job_input: dict, source: str, link=None
) -> tuple[Job, list[str]]:
    """Queue the free study. The finished study stays until it saves (a removed one goes
    now). Returns the job and the storage keys to delete once committed."""
    from app.routes.jobs import enqueue

    if busy(db, draft):
        raise HTTPException(409, BUSY)
    found = draft.song_study or {}
    gone = [*found.get("stale_frames", [])]
    if not _finished(found):
        gone += [f["file_id"] for f in found.get("frames", [])]
        found = {}
    old = db.get(Job, _attempt(draft).get("job_id") or 0)  # its upload, if it never saved
    upload = db.get(StoredFile, (old.input.get("video_file_id") if old else None) or 0)
    stored = [db.get(StoredFile, i) for i in gone]
    if upload is not None and upload.key == old.input.get("video_key"):
        stored.append(upload)
    keys = []
    for x in (x for x in stored if x is not None):
        keys.append(x.key)
        db.delete(x)
    job = enqueue(db, user, "song_study", {"step": STEP, "draft_id": draft.id, **job_input},
                  units=0, provider="local")  # fmt: skip
    job.input = {**job.input, "job_id": job.id}  # its Stop marker (stop_key)
    kept = {k: v for k, v in found.items() if k not in ("attempt", "stale_frames")}
    draft.song_study = {**kept, "attempt": {"job_id": job.id, "source": source, "link": link}}
    db.commit()
    return job, keys


def save(db: Session, job: Job) -> None:
    """The worker's answer onto the version, unless a newer press replaced it."""
    draft = db.get(ScriptDraft, job.input["draft_id"])
    if (upload := db.get(StoredFile, job.input.get("video_file_id") or 0)) is not None:
        db.delete(upload)  # the local provider already removed its bytes
    if draft is None or _attempt(draft).get("job_id") != job.id:
        return
    found, attempt, output = draft.song_study, _attempt(draft), job.output or {}
    if output.get("problem"):
        code = output.get("problem_code")
        problem = PROBLEMS.get(code, output["problem"])
        draft.song_study = {**found, "attempt": {**attempt, "problem": problem,
                                                 "problem_code": code}}  # fmt: skip
        return
    ids = output.get("file_ids", [])
    frames = [{"file_id": i, "t": t} for i, t in zip(ids, output["frame_times"], strict=False)]
    stale = [*found.get("stale_frames", []), *(f["file_id"] for f in found.get("frames", []))]
    draft.song_study = {
        **{k: attempt[k] for k in ("job_id", "source", "link")},
        **{k: output[k] for k in ("seconds", "bpm", "sections", "lines", "words")},
        "frames": frames, "use_as_guide": True, "stale_frames": stale,
    }  # fmt: skip


def _attempt_out(db: Session, attempt: dict) -> StudyAttempt | None:
    """The attempt's state; None once cancelled (as if never pressed) or when there's none."""
    if not attempt:
        return None
    fields = {k: attempt.get(k) for k in ("source", "link")}
    if attempt.get("problem"):
        return StudyAttempt(**fields, status="failed", problem=attempt["problem"],
                            problem_code=attempt.get("problem_code"))  # fmt: skip
    job = db.get(Job, attempt.get("job_id") or 0)
    if job is None or job.status in WAITING:
        state = job and StudyJob(id=job.id, status=str(job.status), started_at=job.started_at)
        return StudyAttempt(**fields, status="studying", job=state)
    if job.status == JobStatus.cancelled:
        return None
    gone = StudyJob(id=job.id, status="failed", started_at=job.started_at)
    return StudyAttempt(**fields, status="failed", job=gone, problem=FAILED)  # or lost


def shown(db: Session, draft: ScriptDraft) -> SongStudyOut | None:
    """What the version's card shows; None when there's nothing (or only a cancelled try),
    or the study was removed."""
    found = draft.song_study or {}
    attempt = _attempt_out(db, found.get("attempt") or {})
    if _finished(found):
        return SongStudyOut(**{**found, "attempt": attempt}, status="done")
    if found.get("removed_at") or attempt is None:
        return None
    return SongStudyOut(**attempt.model_dump())


def guide(draft: ScriptDraft) -> dict | None:
    """The study the song directions follow (flows S3a "Used as a guide"), or None."""
    found = draft.song_study or {}
    return found if _finished(found) and found.get("use_as_guide") else None


def set_guide(db: Session, draft: ScriptDraft, on: bool) -> None:
    if not _finished(draft.song_study or {}):
        raise HTTPException(409, "There's no finished study to use.")
    draft.song_study = {**draft.song_study, "use_as_guide": on}
    db.commit()


def remove(db: Session, draft: ScriptDraft, back: bool = False) -> None:
    """Remove the finished study (Undo: back=True). Its frames stay until the next press."""
    found = draft.song_study or {}
    if found.get("seconds") is None:
        raise HTTPException(404, "There's no song ad study here.")
    if not back and busy(db, draft):
        raise HTTPException(409, "A newer study is still running. Cancel it first.")
    draft.song_study = {**found, "removed_at": None if back else utcnow().isoformat()}
    db.commit()


def stop(db: Session, storage, draft: ScriptDraft) -> None:
    """Stop the study in hand, queued or running: nothing is charged and nothing it made is
    kept; a finished study stays as it was. A running one is cancelled now and told through
    the shared storage, where the worker looks every POLL seconds."""
    job = db.get(Job, _attempt(draft).get("job_id") or 0)
    if job is None or job.status not in WAITING:
        raise HTTPException(409, "Nothing is being studied here.")
    running = job.status == JobStatus.running
    db.execute(update(Job).where(Job.id == job.id, Job.status.in_(WAITING))
               .values(status=JobStatus.cancelled, finished_at=utcnow()))  # fmt: skip
    db.commit()
    if running:
        storage.put(stop_key(job.id), b"")
