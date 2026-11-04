"""Narrated ads (flows N1, V6n): one voice reads the version's words. A narration is a song
take of kind "narration" (docs/next/data.md), so Use, out of date, Undo and the video's own
choice work as for a song; its lyrics are the words it reads and its style line is empty.

Made with one voice call (ElevenLabs v3, or MiniMax Speech 2.8 HD for its emotion and pause
control, through Replicate, priced from the catalogue per 1,000 characters); then, free on our
server: pauses are trimmed on real silence only, the trimmed narration is heard again and used
only if it says the same letters, and each sentence's start and end are measured (the
breakdown's clock, as a song's lines are). A UGC talker's narration then gets its room sound
(app/room.py)."""

import math
import re
import subprocess
from pathlib import Path

from app import song_timing
from app.prompts import check

KIND = "narration"
TIMED = ("song", "narrated")  # script kinds whose videos are timed to a take
MODEL = "elevenlabs-v3"
VOICE = "Sarah"
# Natural v3 voices (song-ad-workflow.md); the names are ElevenLabs v3's own (Replicate's enum).
# Austin (deep, ~81 Hz) and Roger (relaxed, ~115 Hz) are male, from the presenter-1 test.
# Words a second at our slowest voice (the paid test: 2.6; Reed's reference narrator reads 3.37)
SLOWEST = 2.6
ELEVENLABS = (VOICE, "Alexandra", "Hope", "Jane", "Austin", "Roger")
# MiniMax Speech 2.8 HD (replicate.com/minimax/speech-2.8-hd; platform.minimax.io's system
# voice list): two men, three women in natural English for someone talking to their phone
# (UGC, Reed 3 Nov: "emotion inflection from minimax"); English_Graceful_Lady is the older
# woman (th-20s: of 4 older-woman voices the lowest, 186 Hz, with the widest range). Its own
# controls: an emotion, pause marks <#0.4#> and sounds like (breath) in the text; no free-text
# note. Speed 1.1 with emotion auto read at 3.2-3.4 words a second in the batch-b test (the UGC
# references: 3.3-3.5).
MINIMAX, MINIMAX_SPEED = "minimax-speech-2.8-hd", 1.1
MINIMAX_VOICES = ("English_FriendlyPerson", "English_Trustworth_Man", "English_Upbeat_Woman",
                  "English_ConfidentWoman", "English_Graceful_Lady")  # fmt: skip
# An emotion slows MiniMax down, so its speed rises with it to keep the style's pace. Measured
# in th-20s (English_Graceful_Lady, the same lines): fearful read 2.4 words a second at 1.25 and
# 3.4-3.6 at 1.5; sad 1.6 at 1.1 and 2.0 at 1.3 (with its marked pauses). The other emotions
# aren't measured yet: they start at 1.1, and every narration's pace is measured once it's
# timed (`pace`), so a remake corrects its speed from what was heard (`retimed`).
SPEEDS = {"fearful": 1.5, "sad": 1.3}
FASTEST, SLOWEST_SPEED = 2.0, 0.5  # MiniMax's speed range
VOICES = ELEVENLABS + MINIMAX_VOICES
EMOTIONS = ("auto", "happy", "sad", "angry", "fearful", "disgusted", "surprised", "calm",
            "fluent", "neutral")  # Replicate's enum for speech-2.8-hd and -turbo  # fmt: skip
# platform.minimax.io T2A: interjections are "only supported when using speech-2.8-hd or
# speech-2.8-turbo"; a pause mark <#x#> goes between words, never two in a row
SOUNDS = ("laughs", "chuckle", "coughs", "clear-throat", "groans", "breath", "pant", "inhale",
          "exhale", "gasps", "sniffs", "sighs", "snorts", "burps", "lip-smacking", "humming",
          "hissing", "emm", "sneezes")  # fmt: skip
MARK = re.compile(r"<#(\d{1,2}(?:\.\d{1,2})?)#>|\((?:" + "|".join(SOUNDS) + r")\)")
LONGEST_PAUSE = 0.6  # a marked pause the trim keeps, at most (UGC: none past about 0.5 s)
# Silence only: a quiet stretch (below -40 dB) longer than this is shortened to it
PAUSE, QUIET = 0.25, "-40dB"


def video_script(db, project):
    """A video's script; None for a video with no script (the earlier New video form)."""
    from app.models.script_library import Script, ScriptDraft

    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    return db.get(Script, draft.script_id) if draft else None


def video_kind(db, project) -> str:
    """A video's type is its script's kind: story, song or narrated (the engine of its format).
    A video with no script is a story. Its look is a setting apart (Song in any look)."""
    script = video_script(db, project)
    return script.kind if script else "story"


def longest(db, draft, video=None) -> int:
    """A narrated version's length for a quote (rule 36: up to, never below): the narration
    made for it (the video's own, else the version's Preferred), else its words at our
    slowest narrator's pace (the dry run quoted 70 s for a script read in 104 s)."""
    from app import song_takes
    from app.models.songs import SongTake

    made = video is not None and video.song_take_id and db.get(SongTake, video.song_take_id)
    made = made or song_takes.preferred(db, draft)
    if made and made.seconds:
        return math.ceil(made.seconds)
    return math.ceil(len(check.narration_text(draft.text or "").split()) / SLOWEST)


NO_WORDS = "Write the words first: the narrator reads them as written."
FAILED = "The narration didn't finish. Nothing was charged."
MAKING = "A narration is being made. It's ready in a moment."
KEPT_PAUSES = "Kept the pauses: trimming would have clipped a word."
TIMING_FAILED = "We couldn't read this narration's timing. It's free to try again."
TIMING_UNREADABLE = "This narration's file can't be read. Make the narration again."


def sentences(text: str) -> list[str]:
    """One per line of the timing: each line split after . ! ? or …"""
    return [s for line in text.splitlines() for s in re.split(r"(?<=[.!?…])\s+", line) if s]


NOT_THE_WORDS = "The reading must say the script's words exactly, adding only pauses and sounds."
NO_NOTE = "A MiniMax voice takes no note: give it an emotion, or pause marks in its reading."


def job(script: str, voice: str = VOICE, note: str = "", emotion: str | None = None,
        reading: str = "", speed: float | None = None) -> dict:  # fmt: skip
    """The voice call. A remake's note ("Say fomo as FOH-moh.") goes in as a v3 delivery tag
    on this request only, never into the version's words; the voice is the Director's pick. A
    MiniMax voice reads `reading` when given (the words exactly, with pause marks and sounds
    added) in `emotion` (auto: its own choice), at `speed` (None: the emotion's own)."""
    text = check.narration_text(script)  # the Director's: what the narrator reads
    if not text:
        raise ValueError(NO_WORDS)
    if voice not in VOICES:
        raise ValueError(f"The narrator's voice is one of {', '.join(VOICES)}.")
    if voice in MINIMAX_VOICES:
        return _minimax(text, voice, note, emotion or "auto", (reading or "").strip(), speed)
    tag = re.sub(r"[\[\]\s]+", " ", note).strip()
    return {"model": MODEL, "input": {"prompt": f"[{tag}] {text}" if tag else text, "voice": voice}}


def speed_for(emotion: str | None) -> float:
    """The speed an emotion starts at (`SPEEDS`; else 1.1)."""
    return SPEEDS.get(emotion or "auto", MINIMAX_SPEED)


def _minimax(text: str, voice: str, note: str, emotion: str, reading: str,
             speed: float | None = None) -> dict:  # fmt: skip
    """minimax/speech-2.8-hd's own inputs, at the batch-b test's settings (44.1 kHz, 256k)."""
    if note.strip():
        raise ValueError(NO_NOTE)
    if emotion not in EMOTIONS:
        raise ValueError(f"The voice's emotion is one of {', '.join(EMOTIONS)}.")
    pauses = [float(s) for s in MARK.findall(reading) if s]
    if reading and (plain(MARK.sub(" ", reading)) != plain(text) or re.search(r"#>\s*<#", reading)
                    or any(not 0.01 <= s <= LONGEST_PAUSE for s in pauses)):  # fmt: skip
        raise ValueError(NOT_THE_WORDS)
    return {"model": MINIMAX, "input": {
        "text": reading or text, "voice_id": voice, "emotion": emotion,
        "speed": round(min(max(speed or speed_for(emotion), SLOWEST_SPEED), FASTEST), 2),
        "language_boost": "English", "english_normalization": True, "sample_rate": 44100,
        "bitrate": 256000, "audio_format": "mp3"}}  # fmt: skip


def characters(job_input: dict) -> int:
    said = job_input["input"]
    return len(said.get("prompt") or said.get("text") or "")


def delivery(job_input: dict) -> dict:
    """A MiniMax narration's emotion, reading and speed, to make it again the same way; else
    {}."""
    said = job_input.get("input") or {}
    if job_input.get("model") != MINIMAX:
        return {}
    return {"emotion": said.get("emotion"), "reading": said.get("text", ""),
            "speed": said.get("speed")}  # fmt: skip


def pace(heard: list[dict], gap: float = PAUSE) -> float | None:
    """Words a second while speaking, as the guides measure it: the words over the time they
    take, pauses longer than `gap` left out. None with too few words to say."""
    if len(heard) < 2:
        return None
    talking, start, end = 0.0, heard[0]["start"], heard[0]["end"]
    for w in heard[1:]:
        if w["start"] - end > gap:
            talking, start = talking + end - start, w["start"]
        end = max(end, w["end"])
    talking += end - start
    return round(len(heard) / talking, 2) if talking > 0 else None


def retimed(speed: float, heard: float, want: tuple[float, float]) -> float | None:
    """The speed that brings a narration read at `heard` words a second (at `speed`) to the
    middle of the style's range `want`, from the measurement, not a guess; None when it's
    inside the range already."""
    low, high = want
    if low <= heard <= high:
        return None
    scaled = speed * (low + high) / 2 / heard
    return round(min(max(scaled, SLOWEST_SPEED), FASTEST), 2)


def kept_pause(job_input: dict) -> float:
    """The longest silence the trim keeps: the longest pause the reading marks, else PAUSE."""
    said = (job_input.get("input") or {}).get("text") or ""
    return max([PAUSE, *(float(s) for s in MARK.findall(said) if s)])


def trim(path: Path, out: Path, longest: float = PAUSE) -> Path:
    """Every silence longer than `longest` shortened to it; nothing with sound is cut."""
    gate = f"threshold={QUIET}"
    keep = (f"silenceremove=start_periods=1:start_silence={PAUSE}:start_{gate}:stop_periods=-1:"
            f"stop_duration={longest}:stop_silence={longest}:stop_{gate}")  # fmt: skip
    command = ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-af", keep, str(out)]
    done = subprocess.run(command, capture_output=True, timeout=song_timing.TIMEOUT)  # noqa: S603
    if done.returncode:
        raise ValueError("The narration's file can't be read.")
    return out


def plain(text: str) -> str:
    """Letters and digits only, money and numbers one way however they're written: "$5,000"
    and "5000 dollars" both read "5000dollars"; "’" is "'"."""
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text.lower().replace("’", "'"))
    text = re.sub(r"\$\s*(\d+(?:\.\d+)?)", r"\1 dollars", text).replace("%", " percent")
    return re.sub(r"[^a-z0-9]", "", text)


def letters(heard: list[dict]) -> str:
    return plain(" ".join(w["word"] for w in heard))


def measure(path: Path, text: str, hear=song_timing.words,
            longest: float = PAUSE) -> tuple[dict, Path | None]:  # fmt: skip
    """The narration's timing, and the trimmed file (beside `path`) when it's the one to
    use (None: keep the original, because the trim would have clipped a word). A pause up to
    `longest` stays (the reading's own marks)."""
    before = song_timing.length(path)
    trimmed = trim(path, path.with_name("trimmed.mp3"), longest)
    after, heard = hear(trimmed, text), hear(path, text)
    same = letters(after) == letters(heard)
    use, heard = (trimmed, after) if same else (path, heard)
    seconds = song_timing.length(use)
    timing = {
        "seconds": seconds, "untrimmed_seconds": before, "trimmed": same, "bpm": None,
        "beats": [], "sections": [], "words": heard,
        "lines": song_timing.lines("\n".join(sentences(text)), heard, seconds),
        "pace": pace(heard),  # words a second while speaking
        "peaks": song_timing.peaks(song_timing._samples(use)),
    }  # fmt: skip
    return timing, trimmed if same else None
