"""An Omni talker's cut, sound and checks (app/omni_talker.py): the outside editor's UGC
playbook, adopted by Reed on 9 Nov (§4-§7, §9).

- Trim by numbers (§5). Each piece's speech is found from its own sound: its noise floor and a
  voice detector (`measure`, on our server after each take), never the transcript's word times.
  A join keeps HEAD before the first sound and SENTENCE (a comma's piece: COMMA) after the last;
  a silence inside a piece over LONG is cut down to BEAT; every cut point sits in quiet (under
  QUIET, or the piece's own floor in a loud room) on the cut's frame grid, so a last word rings
  out and lips stay on the voice. The video's first piece starts and its last ends as made
  (rule 29). `keep` says which stretches play; the cut lays them back to back (cut.base).
- Steady sound (§6). Each talker take's voice is separated from its room (Demucs on Replicate,
  STEP: a paid call a piece, priced in the catalogue; the stand-ins pass the take's sound
  through), every take is brought to the same speech loudness by one fixed gain (`even`), one
  room tone lies under the whole talker at a fixed level, and the whole mix gets one fixed
  gain, never loudnorm's dynamic mode (it pumps the room up in every pause) (`finish`).
- Speed (Reed, 9 Nov). The final cut plays SPEED times faster, pitch kept, once, at the end
  (`finish`); the cut's timeline keeps the takes' own seconds and says its `speed`.
- Checks before the cut (§4, §9: `findings`): a word held over HELD, fillers and doubled
  words (a filler-primed transcript: plain ones skip "um" and merge "done done"), the talker
  moving about in the kept stretch, and the room's level, which the take's watch also reads
  as measured facts that can confirm its notes (watch_report.confirmed)."""

import logging
import math
import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import room
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import WAITING, Job, JobStatus

log = logging.getLogger(__name__)
HEAD = 0.05  # s kept before a piece's first sound
SENTENCE, COMMA = 0.13, 0.05  # s kept after its last word: a sentence's end, a comma's
LONG, BEAT = 0.26, 0.2  # a silence inside a piece longer than LONG is cut down to BEAT
# A muted word's sound runs on past where the transcript ends it (video 399: muted to 7.48 s,
# heard to 7.77): within this of the piece's last sound, the muted words are its end
OVERHANG = 0.5
QUIET = -42.0  # dB: every cut point is quieter than this...
ROOM = 10.0  # ...or than this far over the piece's own noise floor (above its flicker)
SOFT = 6.0  # dB over the floor: the soft edge of a word (an "s", a fade), kept with it
FLOOR = 0.05  # the share of a piece's quietest moments that is its noise floor
FRAME = 1 / 30  # s: the cut's frame grid (cut_render.joined makes 30 a second)
HELD, MOVES = 0.55, 8.0  # s a word may be held; picture change a second (0-255) of a talker
LOUD_ROOM = -45.0  # dB: a room louder than this between words is said in the measured facts
FILLERS = {"uh", "um", "umm", "uhm", "ah", "er", "erm", "hmm", "mm"}
STEP, MODEL, KEY = "voice_split", "demucs", "voice_only"  # a take's made_with[KEY]: its voice
SPEECH = float(room.LUFS)  # every take's speech loudness, LUFS
# One room tone under the whole talker: room.BED measures -17.6 LUFS, so it sits about 37 dB
# under the speech, as room.py's room does.
BED, BED_DB = room.BED, -35.0
AIM, PEAK = -14.0, -1.5  # the final mix, by one gain: about -14 LUFS, never past PEAK dBTP
SPEED = 1.1
GAP = 1.4  # s: back-to-back B-roll runs together, or leaves the talker on longer than this
WAIT = "The talker's pieces are still being measured and their voices cleaned. Ready in a moment."
WAIT_FOR = timedelta(minutes=3)  # past this a separation isn't waited for: the take's own sound
# Nor a piece's free measure (whisper can queue): as made. 15 minutes, and a minute more for each
# talker piece, all queued on the one local whisper lane (a 1,000-word talker has ~25: long scripts)
MEASURE_FOR, PER_PIECE = timedelta(minutes=15), timedelta(minutes=1)


def measure(path: Path, lines: list[dict], vad=None) -> dict:
    """A talker piece's own sound and picture, free: its length, its noise floor and quiet
    level, its runs of sound (`sounds`), where its speech starts and ends (`speech`, the first
    and last sound a voice detector hears in: `voiced`), whether its last line ends on a comma,
    and how much the picture changes each second."""
    from app import deep_watch, song_timing

    facts = deep_watch.probe(path)
    said = (lines[-1]["text"] if lines else "").rstrip(" \"'”’)")
    out = {"length": facts["length"], "comma": said[-1:] in (",", ";", ":", "-", "—"),
           "sounds": [], "speech": None, "floor": None, "quiet": QUIET,
           "motion": deep_watch.motion(path, [])["per_second"]}  # fmt: skip
    if facts["audio"]:
        levels = song_timing.levels(song_timing._samples(path, song_timing.CLEAR),
                                    song_timing.CLEAR)  # fmt: skip
        out |= sounds(levels, (vad or voiced)(path))
    return out


def sounds(levels: list[float], speech: list[list[float]] | None = None) -> dict:
    """From each 10 ms frame's level (dBFS): the piece's floor (its quietest FLOOR), what's
    quiet here, its runs of sound, each with the soft sound at its edges (SOFT over the floor:
    an "s" or "f" starting a word, a word fading out), and the first to last that `speech` (a
    voice detector's spans; None: every sound) overlaps."""
    from app.song_timing import HOP

    ranked = sorted(levels)
    floor = ranked[int(FLOOR * (len(ranked) - 1))] if ranked else -120.0
    quiet, n = max(QUIET, floor + ROOM), len(levels)
    soft = [floor + SOFT <= x < quiet for x in levels]
    runs, start = [], None
    for k, level in enumerate([*levels, -999.0]):
        if level >= quiet and start is None:
            start = k
        elif level < quiet and start is not None:
            a, b = start, k
            while a > 0 and soft[a - 1]:
                a -= 1
            while b < n and soft[b]:
                b += 1
            if runs and a <= runs[-1][1]:
                runs[-1][1] = b
            else:
                runs.append([a, b])
            start = None
    runs = [[round(a * HOP, 2), round(b * HOP, 2)] for a, b in runs]
    said = [r for r in runs if speech is None or any(a < r[1] and r[0] < b for a, b in speech)]
    return {"floor": round(floor, 1), "quiet": round(quiet, 1), "sounds": runs,
            "speech": [said[0][0], said[-1][1]] if said else None}  # fmt: skip


def voiced(path: Path) -> list[list[float]] | None:
    """Where the voice detector faster-whisper ships with (Silero) hears speech, in seconds;
    None where it isn't installed (the tests: every sound counts)."""
    try:
        from faster_whisper.audio import decode_audio
        from faster_whisper.vad import VadOptions, get_speech_timestamps
    except ImportError:
        return None
    found = get_speech_timestamps(
        decode_audio(str(path)), VadOptions(min_silence_duration_ms=100, speech_pad_ms=0)
    )
    return [[s["start"] / 16000, s["end"] / 16000] for s in found]  # fmt: skip


def _grid(t: float, lo: float, hi: float, up: bool) -> float:
    """`t` on the frame grid, rounded `up` (else down) unless that leaves lo..hi."""
    a, b = math.floor(t / FRAME + 1e-6) * FRAME, math.ceil(t / FRAME - 1e-6) * FRAME
    first, other = (b, a) if up else (a, b)
    return round(first if lo <= first <= hi else other if lo <= other <= hi else t, 3)


def keep(m: dict | None, first: bool, last: bool, muted=()) -> list[tuple[float, float]]:
    """The stretches of a piece the cut plays, in its own seconds, as `measure` found it: from
    HEAD before its first sound (the video's first piece from 0) to SENTENCE or COMMA after its
    last (the last piece to its end), never into another sound; each silence inside it over
    LONG cut down to BEAT. All of it when nothing in it was heard. Words `muted` at its end (a
    sentence the talker made up after their line, video 390) aren't played at all: the piece
    ends on the last sound before them, so nobody mouths words in silence."""
    if not m or not m.get("speech"):
        return [(0.0, float(m["length"]) if m else 0.0)]
    length, runs, (start, end) = float(m["length"]), m["sounds"], m["speech"]
    for s, e in muted:
        if start < s < end <= e + OVERHANG:
            end = max([b for _, b in runs if b <= s + HEAD], default=s)
    before = max([b for _, b in runs if b <= start], default=0.0)  # a sound before the speech
    after = min([a for a, _ in runs if a >= end], default=length)  # and one after it
    a = 0.0 if first else _grid(max(start - HEAD, before), before, start, up=False)
    tail = COMMA if m.get("comma") else SENTENCE
    b = length if last else _grid(min(end + tail, after), end, after, up=True)
    out, at = [], a
    for (_, s), (e, _) in zip(runs, runs[1:], strict=False):
        if start <= s and e <= end and e - s > LONG:  # a silence inside it: BEAT of it stays
            x, y = (round(round(t / FRAME) * FRAME, 3) for t in (s + BEAT / 2, e - BEAT / 2))
            if y - x >= FRAME:
                out.append((at, x))
                at = y
    return [*out, (at, b)]


def findings(m: dict | None, heard: list[dict], lines: list[dict]) -> list[dict]:
    """A talker piece's checks before the cut (§4), as words-check findings: a word held over
    HELD (as long as its sound really lasts, not the transcript's span), a filler or a doubled
    word the script doesn't have, and the talker moving about in the stretch the cut keeps."""
    from app.take_words import _bare, _clock, _finding

    words = [w for line in heard for w in line.get("words") or [] if _bare(w["word"])]
    script = [w for line in lines for w in _bare(line["text"]).split()]
    doubled = {(x, y) for x, y in zip(script, script[1:], strict=False) if x == y}
    runs, out = (m or {}).get("sounds") or [], []
    for w in words:
        held = (
            sum(max(0.0, min(w["end"], b) - max(w["start"], a)) for a, b in runs)
            if runs
            else w["end"] - w["start"]
        )  # how long it really sounds inside its transcript span
        said, at = w["word"].strip(), _clock(w["start"])
        if held > HELD:
            out.append(_finding("held", w["start"], f"“{said}” at {at} is held {held:.2f} s "
                                f"(over {HELD} s): it drags.", "Say every word at an even "
                                "pace, none drawn out."))  # fmt: skip
        if _bare(said) in FILLERS and _bare(said) not in script:
            out.append(_finding("filler", w["start"], f"“{said}” at {at}: a filler the script "
                                "doesn't have.", "Say only the script's words: no “um” or "
                                "“uh”.", span=[w["start"], w["end"]]))  # fmt: skip
    for x, y in zip(words, words[1:], strict=False):
        pair = (_bare(x["word"]), _bare(y["word"]))
        if pair[0] == pair[1] and pair not in doubled and pair[0] not in FILLERS:
            out.append(_finding("stutter", x["start"], f"“{x['word'].strip()} "
                                f"{y['word'].strip()}” at {_clock(x['start'])}: a word said "
                                "twice.", "Say each word once.",
                                span=[x["start"], y["end"]]))  # fmt: skip
    if m and (moved := _moved(m)) is not None:
        out.append(_finding("motion", float(moved), f"The talker moves about at "
                            f"{_clock(moved)}: check they stay seated and in frame.",
                            "Stays seated the whole clip, never stands up, never leaves the "
                            "frame."))  # fmt: skip
    return out


def _moved(m: dict) -> int | None:
    """The first second of the kept stretch whose picture changes more than MOVES."""
    a, b = m["speech"] or (0.0, m["length"])
    return next((t for t, x in enumerate(m.get("motion") or [])
                 if int(a) <= t <= b and x > MOVES), None)  # fmt: skip


def told(m: dict, heard: list[dict], lines: list[dict]) -> str:
    """The checks as measured facts, for the take watch's <measured>."""
    found = findings(m, heard, lines)
    said = (
        "; ".join(f["text"].rstrip(".") for f in found) or "no word held, no filler or doubled word"
    )
    room_db = m.get("floor")
    loud = f" (loud: over {LOUD_ROOM} dB)" if room_db is not None and room_db > LOUD_ROOM else ""
    return f"Talker checks (measured): {said}. Room between words: {room_db} dB{loud}."


def facts(m: dict | None, heard: list[dict], lines: list[dict]) -> dict:
    """What a watch note can be confirmed by (watch_report.confirmed): a held word, movement."""
    kinds = {f["kind"] for f in findings(m, heard, lines)} if m else set()
    return {"held": "held" in kinds, "moved": "motion" in kinds}


def measured(db: Session, take: ClipTake | None) -> dict | None:
    """A talker take's `measure`, from its words check (app/take_words), once it's done."""
    from app import item_checks

    row = item_checks.latest(db, "words", [take.id]).get(take.id) if take else None
    job = db.get(Job, row.job_id) if row and row.job_id else None
    return (job.output or {}).get("talker") if job and row.status == "done" else None


# --- The voice, separated (Demucs on Replicate, a paid call a talker piece) ---


def price(db: Session, workspace_id: int) -> Decimal:
    from app.credits import estimate

    return estimate(db, workspace_id, STEP, Decimal(1), {"model": MODEL})


def planned(db: Session, video, clips: int) -> Decimal:
    """For a video's estimate (credits.plan_cost): an Omni talker's every clip separated once
    (B-roll counted too: an estimate is never below what's charged)."""
    from app import omni_talker

    on = video is not None and video.script_draft_id and omni_talker.on(db, video)
    return clips * price(db, video.workspace_id) if on else Decimal(0)


def splits(db: Session, project, clip: ProjectClip) -> bool:
    """An Omni talker's piece: its take's voice is separated from its room."""
    from app import omni_talker
    from app.take_watch import _shots

    return omni_talker.on(db, project) and any(s.get("line") for s in _shots(db, clip))


def queue(db: Session, job: Job, take: ClipTake, clip: ProjectClip) -> None:
    """After a talker piece's take is saved (in the worker): its voice separated, riding on
    the take's own price (clip_takes.take_credits)."""
    from app.models.projects import Project

    project = db.get(Project, clip.project_id)
    if not splits(db, project, clip):
        return
    data = {"step": STEP, "project_id": project.id, "take_id": take.id, "model": MODEL,
            "input": {"isolate_stem": "vocals", "format": "wav"},
            "files": {"audio": [take.file_id]}}  # fmt: skip
    db.add(Job(workspace_id=project.workspace_id, created_by_id=job.created_by_id, kind=STEP,
               provider="replicate", input=data, project_id=project.id, brand_id=project.brand_id,
               credits=price(db, project.workspace_id), status="queued",
               approved_by_id=job.approved_by_id))  # fmt: skip


def queue_safely(db: Session, job: Job, take: ClipTake, clip: ProjectClip) -> None:
    """A separation never stops a take from being saved: without one, the take's own sound."""
    try:
        with db.begin_nested():
            queue(db, job, take, clip)
    except Exception:
        log.exception("couldn't queue the voice separation of take %s", take.id)


def saved(db: Session, job: Job) -> None:
    """The separated voice is the take's sound in the cut from now on (Demucs names its
    files: `vocals`; a stand-in gives one)."""
    take = db.get(ClipTake, job.input["take_id"])
    out = job.output or {}
    files = out.get("file_ids") or []
    if take is None or not files:
        return
    named = [k for k, v in (out.get("fields") or {}).items() if isinstance(v, str)
             and v.startswith("http")]  # fmt: skip
    n = named.index("vocals") if "vocals" in named else 0
    take.made_with = {**(take.made_with or {}), KEY: files[min(n, len(files) - 1)]}


def given_up(job: Job) -> bool:
    """A separation no longer waited for: queued while paid generation is off (it would never
    run), or older than WAIT_FOR. The cut then plays the take's own sound (`even`); the
    separation may still land for the next cut. Its failure is never the director's (the
    fallback is automatic: director.py leaves it out)."""
    from app.db import utcnow
    from app.settings import get_settings

    settings = get_settings()
    off = not (settings.generation_enabled or settings.fake_providers)
    return (off and job.status == JobStatus.queued) or utcnow() - job.created_at > WAIT_FOR


def waiting(db: Session, project, rows: list[ProjectClip]) -> bool:
    """A picked talker take's voice is still being separated (`given_up` aside), or its
    measure still taken (MEASURE_FOR, and PER_PIECE for each piece, at most: then it plays
    as made)."""
    from app import item_checks
    from app.db import utcnow

    picked = [r.picked_take_id for r in rows if r.picked_take_id]
    jobs = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING),
                                        Job.input["step"].as_string() == STEP))  # fmt: skip
    if any(j.input.get("take_id") in picked and not given_up(j) for j in jobs):
        return True
    checks = item_checks.latest(db, "words", picked)
    talks = [(row, job) for row in checks.values()
             if (job := db.get(Job, row.job_id or 0)) and job.input.get("talker")]  # fmt: skip
    most = MEASURE_FOR + PER_PIECE * len(talks)
    return any(row.status == "checking" and job.status in WAITING
               and utcnow() - job.created_at <= most for row, job in talks)  # fmt: skip


# --- The cut's sound (cut_render.render) ---


def _ffmpeg(folder: Path, args: list[str]) -> bytes:
    from app.cut_render import _run

    return _run(folder, args)


def even(video: bytes, voice: bytes | None) -> bytes:
    """The take with its voice alone (the separated voice, else its own sound) brought to
    SPEECH by one fixed gain; the picture copied."""
    from app.cut_render import SAME, _loudness, _probe

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "in.mp4").write_bytes(video)
        name = "in.mp4"
        if voice is not None:
            (folder / "voice").write_bytes(voice)
            name = "voice"
        if not _probe(folder, name, "a:0", "index"):
            return video
        m = _loudness(folder, name)
        heard = m is not None and m["input_i"] not in ("-inf", "inf") and float(m["input_i"]) > -70
        gain = min(max(SPEECH - float(m["input_i"]), -30.0), 30.0) if heard else 0.0
        inputs = ["-i", "in.mp4", *(["-i", "voice"] if voice is not None else [])]
        return _ffmpeg(folder, [*inputs, "-map", "0:v", "-map", f"{len(inputs) // 2 - 1}:a:0",
                                "-c:v", "copy", "-af", f"{SAME},volume={gain:.2f}dB",
                                "-c:a", "aac", "-b:a", "192k"])  # fmt: skip


def finish(data: bytes) -> bytes:
    """The talker's whole cut: one room tone under it at BED_DB, SPEED times faster with its
    pitch kept, then one fixed gain to about AIM LUFS, its true peak under PEAK (and under the
    cut's ceiling after the encode). No loudnorm."""
    from app.cut_render import CEILING, SAME, _aac, _length, _loudness, _probe

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "in.mp4").write_bytes(data)
        total, has_sound = _length(folder, "in.mp4"), _probe(folder, "in.mp4", "a:0", "index")
        bed = f"{BED},atrim=duration={total + 0.5:.2f},volume={BED_DB}dB,{SAME}"
        graph = f"[0:v]setpts=PTS/{SPEED},fps=30[v]" + (
            f";[0:a]{SAME}[voice];{bed}[bed];"
            f"[voice][bed]amix=inputs=2:normalize=0:duration=first,atempo={SPEED}[a]"
            if has_sound else "")  # fmt: skip
        (folder / "fast.mp4").write_bytes(_ffmpeg(folder, [
            "-i", "in.mp4", "-filter_complex", graph, "-map", "[v]",
            *(["-map", "[a]", "-c:a", "pcm_s16le"] if has_sound else []),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-f", "mov"]))  # fmt: skip
        m = _loudness(folder, "fast.mp4") if has_sound else None
        if m is None or m["input_i"] in ("-inf", "inf") or float(m["input_i"]) < -70:
            if has_sound:  # silence (the stand-ins): AAC, as every cut's sound is
                return _aac(folder, "fast.mp4", "anull")
            return _ffmpeg(folder, ["-i", "fast.mp4", "-c", "copy", "-movflags", "+faststart"])
        gain = min(AIM - float(m["input_i"]), PEAK - float(m["input_tp"]))
        (folder / "loud.mp4").write_bytes(_aac(folder, "fast.mp4", f"volume={gain:.2f}dB"))
        after = _loudness(folder, "loud.mp4")
        over = float(after["input_tp"]) - CEILING if after else 0.0
        if over <= 0:
            return (folder / "loud.mp4").read_bytes()
        return _aac(folder, "loud.mp4", f"volume={-(over + 0.5):.2f}dB")
