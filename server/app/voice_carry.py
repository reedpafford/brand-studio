"""A person's voice carried from clip to clip, on a video model that hears a sample (Seedance
through KIE; Movie Ad 1, Reed, 13 Nov 2026: the voices held once each later clip was sent a few
seconds of the person speaking in an earlier one). `first`: the clips made before the rest, one
for each speaker with no sample yet. `after`: once such a take's free listen is in, a few
seconds of each of those speakers is cut from it and kept on their character (their voice
sample: heard and replaced on the character, and theirs in the next video too). `send`: a
take's speakers' samples, attached and named. Nothing here stops a take: no sample, no line."""

import logging
import re
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.projects import Project

log = logging.getLogger(__name__)
SHORTEST, LONGEST, MOST = 1.5, 5.0, 5  # seconds of one sample; samples a take (KIE: 30 s in all)
# True of a remake of the clip the sample was cut from too, whose lines are the sample's words
LINE = ("[Audio{n}] is a recording of {who}'s voice: match its tone and accent for {who} only. "
        "It is a sample of the voice; the words said are this clip's quoted lines.")  # fmt: skip
OFF = re.compile(r"\s*\(.*?\)")  # a speaker's "(V.O.)": never part of their name


def hears(model) -> bool:
    return model.provider == "kie" and bool(model.max_reference_audios)


def _bare(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", word.lower())


def person(db: Session, project: Project, speaker: str | None) -> LibraryItem | None:
    """The character a speaker's label is (as the plan reads it: one_pass._who)."""
    from app.cast_roles import labels, pick, same, video_slots
    from app.storyboard import cast_looks

    name = OFF.sub("", speaker or "").strip()
    if not name:
        return None
    slots = video_slots(db, project)
    slot = next((s for s in slots if same(name, s.role)), None) or next(
        (s for s in slots if labels(name, s.role)), None)  # fmt: skip
    if slot is not None:
        return db.get(LibraryItem, pick(db, project, slot) or 0)
    return next((i for i in cast_looks(db, project) if same(name, i.name)), None)


def first(db: Session, project: Project, data: dict) -> list[str]:
    """For each speaker with no sample yet, the clip holding their longest line."""
    shots = {s["id"]: s for scene in data.get("scenes", []) for s in scene.get("shots", [])}
    best: dict[int, tuple[int, str]] = {}
    for clip in data.get("clips", []):
        for shot in (shots[i] for i in clip["shot_ids"] if i in shots):
            who = person(db, project, shot.get("speaker")) if shot.get("line") else None
            words = len((shot.get("line") or "").split())
            if who and not who.voice_file_id and words > best.get(who.id, (0, ""))[0]:
                best[who.id] = (words, clip["id"])
    return list(dict.fromkeys(clip for _, clip in best.values()))


def _span(line: dict, heard: list[dict]) -> tuple[float, float] | None:
    """Where a scripted line is said in the take: the longest run of its own words heard in
    its shot's window, so a word of someone else's line beside it is never in the sample."""
    want = {_bare(w) for w in line["text"].split()} - {""}
    got: list[dict] = []
    run: list[dict] = []
    for w in heard:
        near = line["start"] - 0.5 <= (w["start"] + w["end"]) / 2 <= line["end"] + 0.5
        run = [*run, w] if near and _bare(w["word"]) in want else []
        got = run if len(run) > len(got) else got
    if len(got) < max(3, len(want) // 2):
        return None
    start = max(got[0]["start"] - 0.1, 0)
    end = min(got[-1]["end"] + 0.15, start + LONGEST)
    return (start, end) if end - start >= SHORTEST else None


def _cut(video: bytes, start: float, end: float) -> bytes:
    """A piece of a take's sound, as a WAV (ffmpeg, free)."""
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "take.mp4", Path(tmp) / "voice.wav"
        src.write_bytes(video)
        piece = ["-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(src)]
        subprocess.run(  # noqa: S603
            ["ffmpeg", "-v", "error", "-y", *piece, "-vn", "-ac", "1", "-ar", "44100",  # noqa: S607
             str(out)], timeout=60, check=True)  # fmt: skip
        return out.read_bytes()


def after(db: Session, job: Job, storage) -> None:
    """A take's listen is in: each of its speakers with no sample yet gets one, from their
    longest line heard in it. A sample that can't be cut is left for a later take."""
    from app import take_words
    from app.host import _store

    project = db.get(Project, job.project_id or 0)
    lines = job.input.get("lines") or []
    if job.kind != take_words.KIND or not project or not lines or job.input.get("silent"):
        return
    heard = [w for line in (job.output or {}).get("heard") or [] for w in line.get("words") or []]
    for line in sorted(lines, key=lambda x: -len(x["text"].split())):
        who = person(db, project, line["who"])
        span = _span(line, heard) if who and not who.voice_file_id else None
        if not span:
            continue
        try:
            with db.begin_nested():
                sound = _cut(storage.get(job.input["video_key"]), *span)
                who.voice_file_id = _store(db, storage, project, sound, f"{who.name} voice.wav",
                                           "audio/wav").id  # fmt: skip
        except Exception:
            log.exception("job %s: %s's voice sample couldn't be cut", job.id, who.name)


def send(db: Session, project: Project, shots: list[dict], take: dict, files: dict) -> None:
    """The take's speakers' samples: each attached after any audio it has, and named in a
    line at the prompt's end. A take that opens on its own start frame is sent that alone."""
    if files.get("image"):
        return
    audios = files.setdefault("reference_audios", [])
    for name in dict.fromkeys(OFF.sub("", s.get("speaker") or "").strip() for s in shots
                              if s.get("line")):  # fmt: skip
        who = person(db, project, name)
        if who and who.voice_file_id and who.voice_file_id not in audios and len(audios) < MOST:
            audios.append(who.voice_file_id)
            take["prompt"] += "\n" + LINE.format(n=len(audios), who=name)
    if not audios:
        del files["reference_audios"]
