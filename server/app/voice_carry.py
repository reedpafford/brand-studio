"""A person's voice carried from clip to clip, on a video model that hears a sample (Seedance
through KIE; Movie Ad 1, Reed, 13 Nov 2026: the voices held once each later clip was sent a few
seconds of the person speaking in an earlier one). `design`: before any take, each speaker
with no sample gets a voice ElevenLabs designs from the plan's words for it (Reed, 17 Nov,
after his by-hand test: "the voice and elevenlabs touch was amazing ... I trust the directors
choice on voice"); with no ElevenLabs key, or a design that fails, the rest is as before.
`first`: the clips made before the rest, one for each speaker with no sample yet. `after`:
once such a take's free listen is in, a few seconds of each of those speakers is cut from it
and kept on their character (their voice sample: heard and replaced on the character, and
theirs in the next video too). `send`: a take's speakers' samples, attached and named. Nothing
here stops a take: no sample, no line."""

import logging
import re
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.files import StoredFile
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.projects import Project

log = logging.getLogger(__name__)
SHORTEST, LONGEST, MOST = 1.5, 5.0, 5  # seconds of one sample; samples a take (KIE: 30 s in all)
STEP, MODEL = "voice_design", "elevenlabs-voice-design"  # a speaker's designed voice (`design`)
# Seedance's own wording for a recording's role, placed with the pictures' lines; the voice is
# then not described in words as well (RP14, 18 Nov: treble across clips spread 31 dB, then 8)
# The second sentence: without it 3 of RP19's 26 clips spoke the sample's own words first (20 Nov)
LINE = ("[Audio{n}] is used for {who}'s voice: its timbre, accent and speaking rate. "
        "It is a sample of the voice only: none of its own words are said.")  # fmt: skip
KEEP = "Keep {who}'s voice the same from the first word to the last: the voice of [Audio{n}]."
VOICES = re.compile(r" Voices: (.+)\.(?= No music, no subtitles\.$)")
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


def undesigned(db: Session, project: Project, data: dict) -> dict[int, str]:
    """The speakers with no sample yet and the plan's words for their voice, by character:
    those a voice can be designed for, when ElevenLabs is reachable from here."""
    from app.settings import get_settings

    settings = get_settings()  # the stand-ins have one; for real, only with its key
    if not (settings.fake_providers or settings.elevenlabs_api_key.get_secret_value()):
        return {}
    out: dict[int, str] = {}
    for voice in (data.get("shooting_plan") or {}).get("voices") or []:
        who = person(db, project, voice.get("who"))
        if who is not None and not who.voice_file_id and (voice.get("sounds") or "").strip():
            out.setdefault(who.id, f"{voice['sounds'].strip()}. Real and natural, not a narrator.")
    return out


def design(db: Session, user, project: Project, data: dict) -> str:
    """Queue one design for each speaker with no sample (paid from the video's budget, a few
    cents each). The run waits for them as it waits for any job of the video's."""
    from app.routes.jobs import enqueue

    asked = undesigned(db, project, data)
    for item_id, words in asked.items():
        enqueue(db, user, "voice", {"model": MODEL, "step": STEP, "library_item_id": item_id,
                                    "input": {"voice_description": words}},
                project=project, provider="elevenlabs")  # fmt: skip
    names = ", ".join(db.get(LibraryItem, i).name for i in asked)
    return f"Designing a voice for {names}." if asked else "Every speaker has a voice already."


def first(db: Session, project: Project, data: dict) -> list[str]:
    """For each speaker with no sample yet who speaks in more than one clip, the clip holding
    their longest line (someone heard in one clip has nowhere to carry a voice to)."""
    shots = {s["id"]: s for scene in data.get("scenes", []) for s in scene.get("shots", [])}
    best: dict[int, tuple[int, str]] = {}
    heard: dict[int, set[str]] = {}
    for clip in data.get("clips", []):
        for shot in (shots[i] for i in clip["shot_ids"] if i in shots):
            who = person(db, project, shot.get("speaker")) if shot.get("line") else None
            if who is None or who.voice_file_id:
                continue
            heard.setdefault(who.id, set()).add(clip["id"])
            if (words := len(shot["line"].split())) > best.get(who.id, (0, ""))[0]:
                best[who.id] = (words, clip["id"])
    return list(dict.fromkeys(c for who, (_, c) in best.items() if len(heard[who]) > 1))


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
    if project and job.input.get("step") == STEP:  # a designed voice is in: theirs from now on
        who = db.get(LibraryItem, job.input.get("library_item_id") or 0)
        made = db.get(StoredFile, ((job.output or {}).get("file_ids") or [0])[0])
        if who is not None and made is not None and not who.voice_file_id:
            sound = _cut(storage.get(made.key), 0, LONGEST)  # its first seconds: KIE's 30 s
            who.voice_file_id = _store(db, storage, project, sound, f"{who.name} voice.wav",
                                       "audio/wav").id  # fmt: skip
        return
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


def _bound(prompt: str, who: str, n: int) -> str:
    """The prompt with `who`'s recording bound: its line after the last picture's (else the
    scene's, else first), their worded voice gone from the Sound line, and the voice held."""
    lines = prompt.split("\n")
    at = max((i for i, x in enumerate(lines) if x.startswith(("[Image", "[Audio"))),
             default=0 if lines[0].startswith("Scene context:") else -1)  # fmt: skip
    for i, x in enumerate(lines):
        if x.startswith("Sound:") and (m := VOICES.search(x)):
            mine = f"{who.casefold()}, "
            rest = "; ".join(v for v in m[1].split("; ") if not v.casefold().startswith(mine))
            lines[i] = x[: m.start()] + (f" Voices: {rest}." if rest else "") + x[m.end() :]
    lines.insert(at + 1, LINE.format(n=n, who=who))
    return "\n".join([*lines, KEEP.format(n=n, who=who)])


def send(db: Session, project: Project, shots: list[dict], take: dict, files: dict) -> None:
    """The take's speakers' samples: each attached after any audio it has, named in a line
    with the pictures' lines, and its voice's words taken off the Sound line. A take that
    opens on its own start frame is sent that alone."""
    if files.get("image"):
        return
    audios = files.setdefault("reference_audios", [])
    for name in dict.fromkeys(OFF.sub("", s.get("speaker") or "").strip() for s in shots
                              if s.get("line")):  # fmt: skip
        who = person(db, project, name)
        if who and who.voice_file_id and who.voice_file_id not in audios and len(audios) < MOST:
            audios.append(who.voice_file_id)
            take["prompt"] = _bound(take["prompt"], name, len(audios))
    if not audios:
        del files["reference_audios"]
