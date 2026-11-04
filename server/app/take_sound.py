"""Sound effects on request (Reed, 3 Nov: "On b-roll, they wont all need sound. Maybe it is
better to just go in and add sound effects if i request after video generation"). MMAudio
(zsxkib/mmaudio on Replicate; replicate.com/zsxkib/mmaudio/api, github.com/hkchengrex/MMAudio)
watches a made take and makes its sound: inputs `video`, `prompt`, `negative_prompt` (its
default "music"), `duration` (seconds; trained on 8 s, "a large deviation ... may result in a
lower quality"), `num_steps` 25, `cfg_strength` 4.5, `seed`. Given a video it returns that video
with the new sound (an MP4). The prompt is the person's words and what the shot shows; the
negative prompt keeps out the music and speech-like sounds its README warns of, since the voice
and the music bed are their own layers. Each effect has its own loudness against the voice
(`LEVELS`, or the decibels asked for): MMAudio's sound comes back very quiet (th-20s: -30 to
-60 dB against a voice at -16 LUFS), so scaling it alone lost most of it under a narration;
its loudness is measured and brought to the target, then a limiter keeps its peaks at -4 dBFS (the
alarm in th-20s was the one effect louder than the voice). The sound is the take's sound
layer (its made_with "sound"): the final cut mixes it under the take's own sound, so a narrated
video keeps it under the voice with the music ducked (cut_render.level), and a new or
removed one puts the cut out of date. Priced and charged like a take (about $0.0061 a run,
billed by GPU time); a failed run is tried again once on its own, then Make again (rule 22).
Remove takes it off: the take is as it was made, silent B-roll silent again."""

import re
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import room
from app.credits import estimate
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.files import StoredFile
from app.models.jobs import WAITING, Job, JobStatus
from app.models.projects import Project
from app.models.songs import SongTake

STEP, MODEL = "take_sound", "mmaudio"
NEGATIVE = "music, speech, voices, singing"
STEPS, CFG = 25, 4.5  # the model's own defaults
# Each effect's loudness in LU against the voice (room.LUFS, our voice's level): under it,
# "slight" well under, "over" the one moment louder than the voice (th-20s: the alarm)
LEVELS = {"slight": -18.0, "normal": -12.0, "strong": -6.0, "over the voice": 3.0}
LOWEST, LOUDEST = -30.0, 6.0  # a level asked for in decibels, at most this far either side
GAIN = 30.0  # the most it's turned up or down (th-20s set them by hand: +2 to +19 dB)
VOICE = room.LUFS
LIMIT = -4.0  # dBFS: the limiter's ceiling on samples, so after AAC's overshoot an effect's
# true peak stays under the voice's -1.5 dBTP (QA on #1316: at -3 a pushed effect reached +0.3)
CEILING = 10 ** (LIMIT / 20)
SLIGHT = re.compile(r"\b(?:slight(?:ly)?|subtle|soft|quiet|gentle|faint|light|low|a (?:little|"
                    r"touch|bit))\b", re.I)  # fmt: skip
STRONG = re.compile(r"\b(?:loud|strong|big|punchy|heavy|bold)\b", re.I)
OVER = re.compile(r"\b(?:louder than|over|above|on top of) the (?:voice|narrat\w*|talk\w*|"
                  r"speaker|words)\b", re.I)  # fmt: skip
DB = re.compile(r"([-+−]?)(\d{1,2}(?:\.\d)?)\s*dB\b", re.I)
UP = re.compile(r"\b(?:over|above|louder)\b", re.I)
DOWN = re.compile(r"\b(?:under|below|beneath|quieter|softer)\b", re.I)
PLAIN = "Sound effects that fit what happens on screen"
NO_TAKE = "Make a take of this clip first."
MAKING = "Sound is being added to this take already."
ALL_HAVE = ("Every take in the cut has sound already. Name the clip to add sound effects "
            "under its own sound.")  # fmt: skip
NOT_ADDED = "This take has no added sound."
SONG = "A song video's only sound is its song, so sound effects can't go under its takes."


def how(asked: str) -> str:
    """How loud, from the person's words: "slight" sounds lower, "loud" louder, "louder than
    the voice" over it."""
    if OVER.search(asked):
        return "over the voice"
    return "slight" if SLIGHT.search(asked) else "strong" if STRONG.search(asked) else "normal"


def level(asked: str) -> float:
    """The effect's loudness against the voice, in LU: the decibels asked for, under the voice
    unless they say "+" or over, above or louder ("10 dB under the voice", "-10 dB", "+3 dB",
    "3 dB over the voice"), else its `how`."""
    if found := DB.search(asked):
        up = found[1] == "+" or (not found[1] and UP.search(asked) and not DOWN.search(asked))
        db = float(found[2]) * (1 if up else -1)
        return min(max(db, LOWEST), LOUDEST)
    return LEVELS[how(asked)]


def prompt(asked: str, shown: list[str]) -> str:
    """The person's words, then what the shot shows (MMAudio reads both with the picture)."""
    said = asked.strip().rstrip(".") or PLAIN
    seen = " ".join(a.strip() for a in shown if a and a.strip())
    return f"{said}. On screen: {seen}"[:600] if seen else f"{said}."


def _shown(db: Session, row: ProjectClip) -> list[str]:
    data = db.get(BreakdownVersion, row.breakdown_id).data
    ids = next((c["shot_ids"] for c in data.get("clips", []) if c["id"] == row.clip_id), [])
    shots = {s["id"]: s for sc in data.get("scenes", []) for s in sc.get("shots", [])}
    return [shots[i].get("action", "") for i in ids if i in shots]


def price(db: Session, workspace_id: int) -> Decimal:
    """One take's sound: one MMAudio run, at its real cost."""
    return estimate(db, workspace_id, "sound", Decimal(1), {"model": MODEL})


def sung(db: Session, project: Project) -> bool:
    """A song video: its cut drops the takes' own sound for the song (cut_render.song_cut)."""
    from app.narration import KIND

    song = db.get(SongTake, project.song_take_id) if project.song_take_id else None
    return bool(song and song.kind != KIND)


def _job(db: Session, take: ClipTake) -> Job | None:
    """The take's newest sound job."""
    row = db.get(ProjectClip, take.clip_id)
    jobs = db.scalars(select(Job).where(Job.project_id == row.project_id,
                                        Job.input["step"].as_string() == STEP)
                      .order_by(Job.id.desc()))  # fmt: skip
    return next((j for j in jobs if j.input.get("take_id") == take.id), None)


def added(take: ClipTake | None) -> dict | None:
    return (take.made_with or {}).get("sound") if take else None


def state(db: Session, take: ClipTake | None) -> dict | None:
    """{state none | making | ready | failed, how, asked, error, credits} for a take, as its
    clip card and the director read it; None with no take, or in a song video."""
    project = db.get(Project, db.get(ProjectClip, take.clip_id).project_id) if take else None
    if take is None or sung(db, project):
        return None
    job, made, ws = _job(db, take), added(take), project.workspace_id
    lost = job and job.status in (JobStatus.failed, JobStatus.cancelled) and (
        not made or made["job"] < job.id)  # fmt: skip
    now = ("making" if job and job.status in WAITING else "failed" if lost
           else "ready" if made else "none")  # fmt: skip
    told = made if now == "ready" else (job.input if job else {})
    return {"state": now, "how": told.get("how", ""), "asked": told.get("asked", ""),
            "error": (job.error or "") if lost else "",
            "credits": float(price(db, ws))}  # fmt: skip


def job_input(db: Session, project: Project, row: ProjectClip, take: ClipTake,
              asked: str) -> dict:  # fmt: skip
    return {"step": STEP, "project_id": project.id, "take_id": take.id, "model": MODEL,
            "asked": asked, "how": how(asked), "db": level(asked), "brand_id": project.brand_id,
            "input": {"prompt": prompt(asked, _shown(db, row)), "negative_prompt": NEGATIVE,
                      "duration": row.seconds, "num_steps": STEPS, "cfg_strength": CFG},
            "files": {"video": [take.file_id]}}  # fmt: skip


def add(db: Session, user: User, project: Project, rows: list[ProjectClip], asked: str) -> str:
    """Add sound to each clip's picked take, each one MMAudio run priced like a take."""
    from app.routes.jobs import enqueue

    takes = [(r, db.get(ClipTake, r.picked_take_id)) for r in rows if r.picked_take_id]
    if sung(db, project):
        raise HTTPException(409, SONG)
    if not takes:
        raise HTTPException(409, NO_TAKE)
    if any(state(db, t)["state"] == "making" for _, t in takes):
        raise HTTPException(409, MAKING)
    for row, take in takes:
        enqueue(db, user, "sound", job_input(db, project, row, take, asked[:300]), units=1,
                project=project, provider="replicate")  # fmt: skip
    db.commit()
    n = len(takes)
    return f"Adding {how(asked)} sound effects to {n} take{'' if n == 1 else 's'}."


def silent(db: Session, storage, take: ClipTake) -> bool:
    """The take was made with no sound (B-roll asked for none, or a model with none), or its
    file has no audio."""
    from app.cut_render import _probe

    made = db.get(Job, take.job_id)
    if not ((made.input if made else {}).get("input") or {}).get("generate_audio"):
        return True
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "take.mp4").write_bytes(storage.get(db.get(StoredFile, take.file_id).key))
        return not _probe(Path(tmp), "take.mp4", "a:0", "index")


def to_cut(db: Session, user: User, project: Project, storage, clip_id: str | None,
           asked: str) -> str:  # fmt: skip
    """The director's add_sound: one clip, or with none named every picked take in the cut
    that is silent and has none added yet (the B-roll made without sound)."""
    rows = db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)
                      .order_by(ProjectClip.id)).all()  # fmt: skip
    if clip_id:
        rows = [r for r in rows if r.clip_id == clip_id]
        if not rows:
            return f"Refused: there's no clip {clip_id}."
    else:
        picked = [(r, db.get(ClipTake, r.picked_take_id)) for r in rows if r.picked_take_id]
        rows = [r for r, t in picked if not added(t) and silent(db, storage, t)]
        if not rows:
            return f"Refused: {ALL_HAVE}"
    return add(db, user, project, rows, asked)


def saved(db: Session, job: Job) -> None:
    """MMAudio's video with its sound: the take's sound layer from now on."""
    take = db.get(ClipTake, job.input["take_id"])
    file_ids = (job.output or {}).get("file_ids") or []
    if take is None or not file_ids:
        return
    sound = {"file_id": file_ids[0], "how": job.input["how"], "asked": job.input["asked"],
             "db": job.input.get("db", LEVELS[job.input["how"]]), "job": job.id}  # fmt: skip
    take.made_with = {**(take.made_with or {}), "sound": sound}


def remove(take: ClipTake) -> None:
    """Undo: the take's added sound is taken off; it plays as it was made."""
    if not added(take):
        raise HTTPException(404, NOT_ADDED)
    take.made_with = {k: v for k, v in (take.made_with or {}).items() if k != "sound"}


def labels(clip: ProjectClip, take: ClipTake | None) -> list[str]:
    """How the final cut remembers the sound it was made with (so a change shows as waiting)."""
    made = added(take)
    return [f"{clip.clip_id}/sound:{made['file_id']}@{loudness(made)}dB"] if made else []


def loudness(made: dict) -> float:
    """An added sound's loudness against the voice (one added before levels: its `how`)."""
    return float(made.get("db", LEVELS.get(made["how"], LEVELS["normal"])))


def measured(folder: Path, name: str) -> float | None:
    """A file's integrated loudness (LUFS, ffmpeg's loudnorm measurement); None when it has
    nothing loud enough to measure."""
    command = ["ffmpeg", "-v", "info", "-nostats", "-i", name, "-vn", "-af",
               "loudnorm=print_format=json", "-f", "null", "-"]  # fmt: skip
    done = subprocess.run(command, cwd=folder, capture_output=True, text=True,  # noqa: S603
                          timeout=120).stderr  # fmt: skip
    found = re.search(r'"input_i"\s*:\s*"(-?[\d.]+|-inf)"', done)
    said = float(found[1]) if found and found[1] != "-inf" else None
    return said if said is not None and said > -70 else None


def gain(loud: float | None, level: float) -> float:
    """Decibels that bring a sound at `loud` LUFS to `level` LU against the voice (within
    GAIN); 0 for one that can't be measured."""
    if loud is None:
        return 0.0
    return round(min(max(VOICE + level - loud, -GAIN), GAIN), 1)


def apply(video: bytes, sound: bytes, level: float) -> bytes:
    """`sound`'s audio brought to `level` LU against the voice and limited, under the take's
    own (or alone, a silent take); the picture copied as it is, the length the take's."""
    from app.cut_render import _probe

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "in.mp4").write_bytes(video)
        (folder / "sound").write_bytes(sound)
        own = _probe(folder, "in.mp4", "a:0", "index")
        up = gain(measured(folder, "sound"), level)
        effect = f"[1:a]volume={up}dB,alimiter=limit={CEILING:.3f}:level=disabled"
        graph = (f"{effect}[s];[0:a][s]amix=inputs=2:normalize=0:duration=first[a]"
                 if own else f"{effect},apad[a]")  # fmt: skip
        command = ["ffmpeg", "-v", "error", "-y", "-i", "in.mp4", "-i", "sound",
                   "-filter_complex", graph, "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                   "-c:a", "aac", "-shortest", "out.mp4"]  # fmt: skip
        done = subprocess.run(command, cwd=folder, capture_output=True, timeout=600)  # noqa: S603
        if done.returncode != 0:
            raise RuntimeError(done.stderr.decode(errors="replace")[-2000:])
        return (folder / "out.mp4").read_bytes()
