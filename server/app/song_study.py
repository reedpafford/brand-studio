"""A study of someone else's song ad (flows S3a), free on our own server: its length, BPM,
sections with their lines, the words with their times, and one frame per shot. It guides the
song directions' shape (the Director's prompts.song_study_block); it never fills the lyrics
or the style line (rule 19), and the directions never reuse its lines (check.copied_lines).

The study lives on the version as ScriptDraft.song_study: {job_id, source, link, seconds,
bpm, sections: [{name, start, end, lines, guessed}], lines: [{text, start, end}], words:
[{word, start, end}], frames: [{file_id, t}], use_as_guide, problem, problem_code,
removed_at}. While the job runs only job_id, source and link are set.

A reference has no [Verse]/[Chorus] tags, so its sections are inferred: lines are grouped
where the singing pauses for a bar or more, or where it moves in or out of lines that repeat;
a repeated group is a Chorus, others are Verses, and a lone Verse just before the last Chorus
(after one between Choruses) a Bridge. Music before the first word is the Intro, after the
last the Outro. Names that rest on a guess are marked `guessed`."""

import json
import re
import subprocess  # noqa: S404 - fixed argument lists, never a shell
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel
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
HEAR_TIMEOUT = 600  # a 4-minute song on the CPU model
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
}
FAILED = "studying it didn't finish"
BUSY = "A song ad is already being studied here. Wait for it, or cancel it."


def hear(path: Path) -> list[dict]:
    """Local Whisper, unprompted: [{start, end, text, words: [{word, start, end}]}]."""
    args = [sys.executable, "-m", "app.whisper", str(path), "--study"]
    try:
        done = subprocess.run(args, capture_output=True, timeout=HEAR_TIMEOUT)  # noqa: S603
    except subprocess.TimeoutExpired:
        raise RuntimeError("Reading the song ad's words took too long.") from None
    if done.returncode != 0:
        raise RuntimeError(f"Reading the song ad's words failed ({done.returncode}).")
    return json.loads(done.stdout)


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


def study(video: Path, folder: Path, hear=hear) -> tuple[dict, list[tuple[Path, float]]]:
    """The study of one video and its frames. Raises reel.Refused with a plain reason."""
    seconds = reel.probe(video, MAX_SECONDS)
    heard = [x for x in hear(video) if x["text"].strip()]
    if not heard:
        raise reel.Refused("no_words", PROBLEMS["no_words"])
    samples = song_timing._samples(video)
    bpm, beat_times = song_timing.beats(samples, seconds)
    lines = [{"text": x["text"].strip(), "start": x["start"], "end": x["end"]} for x in heard]
    words = [w for x in heard for w in x.get("words", [])]
    found = {"seconds": seconds, "bpm": bpm, "lines": lines, "words": words,
             "sections": sections(lines, beat_times, bpm, seconds)}  # fmt: skip
    return found, frames(video, seconds, folder)


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


class SongStudyOut(BaseModel):
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


# --- On the version -------------------------------------------------------------------------


def busy(db: Session, draft: ScriptDraft) -> bool:
    job = db.get(Job, (draft.song_study or {}).get("job_id") or 0)
    return job is not None and job.status in WAITING


def start(db: Session, user, draft: ScriptDraft, job_input: dict, source: str, link=None) -> Job:
    """Queue the free study in place of the version's study (the caller drops its frames)."""
    from app.routes.jobs import enqueue

    if busy(db, draft):
        raise HTTPException(409, BUSY)
    job = enqueue(db, user, "song_study", {"step": STEP, "draft_id": draft.id, **job_input},
                  units=0, provider="local")  # fmt: skip
    draft.song_study = {"job_id": job.id, "source": source, "link": link}
    db.commit()
    return job


def drop_files(db: Session, study: dict | None) -> list[str]:
    """Delete an old study's frame rows, and its upload's row if its job never saved (it
    failed); returns their storage keys (delete those after the commit)."""
    found = [db.get(StoredFile, f["file_id"]) for f in (study or {}).get("frames", [])]
    job = db.get(Job, (study or {}).get("job_id") or 0)
    upload = db.get(StoredFile, (job.input.get("video_file_id") if job else None) or 0)
    if upload is not None and upload.key == job.input.get("video_key"):
        found.append(upload)
    for stored in (x for x in found if x is not None):
        db.delete(stored)
    return [x.key for x in found if x is not None]


def save(db: Session, job: Job) -> None:
    """The worker's answer onto the version, unless a newer study replaced it."""
    draft = db.get(ScriptDraft, job.input["draft_id"])
    if (upload := db.get(StoredFile, job.input.get("video_file_id") or 0)) is not None:
        db.delete(upload)  # the local provider already removed its bytes
    if draft is None or (draft.song_study or {}).get("job_id") != job.id:
        return
    output = job.output or {}
    kept = {k: draft.song_study.get(k) for k in ("job_id", "source", "link")}
    if output.get("problem"):
        code = output.get("problem_code")
        problem = PROBLEMS.get(code, output["problem"])
        draft.song_study = {**kept, "problem": problem, "problem_code": code}
        return
    ids = output.get("file_ids", [])
    frames = [{"file_id": i, "t": t} for i, t in zip(ids, output["frame_times"], strict=False)]
    found = {k: output[k] for k in ("seconds", "bpm", "sections", "lines", "words")}
    draft.song_study = {**kept, **found, "frames": frames, "use_as_guide": True}


def shown(db: Session, draft: ScriptDraft) -> SongStudyOut | None:
    """What the version's card shows; None when there's no study, or it was removed."""
    found = draft.song_study
    if not found or found.get("removed_at"):
        return None
    if found.get("problem"):
        return SongStudyOut(**found, status="failed")
    if found.get("seconds") is not None:
        return SongStudyOut(**found, status="done")
    job = db.get(Job, found.get("job_id") or 0)
    if job is None:
        return SongStudyOut(**found, status="studying")
    if job.status in WAITING:
        state = StudyJob(id=job.id, status=str(job.status), started_at=job.started_at)
        return SongStudyOut(**found, status="studying", job=state)
    gone = StudyJob(id=job.id, status="failed", started_at=job.started_at)
    return SongStudyOut(**found, status="failed", job=gone, problem=FAILED)  # or cancelled, lost


def guide(draft: ScriptDraft) -> dict | None:
    """The study the song directions follow (flows S3a "Used as a guide"), or None."""
    found = draft.song_study or {}
    usable = found.get("seconds") is not None and not found.get("removed_at")
    return found if usable and found.get("use_as_guide") else None


def set_guide(db: Session, draft: ScriptDraft, on: bool) -> None:
    found = draft.song_study or {}
    if found.get("seconds") is None or found.get("removed_at"):
        raise HTTPException(409, "There's no finished study to use.")
    draft.song_study = {**draft.song_study, "use_as_guide": on}
    db.commit()


def remove(db: Session, draft: ScriptDraft, back: bool = False) -> None:
    """Remove (Undo: back=True). Its frames stay until a new study replaces it."""
    if not draft.song_study:
        raise HTTPException(404, "There's no song ad study here.")
    if not back and busy(db, draft):
        raise HTTPException(409, "It's still being studied. Cancel it instead.")
    draft.song_study = {**draft.song_study, "removed_at": None if back else utcnow().isoformat()}
    db.commit()
