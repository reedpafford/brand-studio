"""Narrated ads (flows N1, V6n): one voice reads the version's words. A narration is a song
take of kind "narration" (docs/next/data.md), so Use, out of date, Undo and the video's own
choice work as for a song; its lyrics are the words it reads and its style line is empty.

Made with one voice call (ElevenLabs v3 through Replicate, priced from the catalogue per
1,000 characters); then, free on our server: pauses are trimmed on real silence only, the
trimmed narration is heard again and used only if it says the same letters, and each
sentence's start and end are measured (the breakdown's clock, as a song's lines are)."""

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
VOICES = (VOICE, "Alexandra", "Hope", "Jane", "Austin", "Roger")
# Words a second at our slowest voice (the paid test: 2.6; Reed's reference narrator reads 3.37)
SLOWEST = 2.6
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


def job(script: str, voice: str = VOICE, note: str = "") -> dict:
    """The voice call. A remake's note ("Say fomo as FOH-moh.") goes in as a v3 delivery tag
    on this request only, never into the version's words; the voice is the Director's pick."""
    text = check.narration_text(script)  # the Director's: what the narrator reads
    if not text:
        raise ValueError(NO_WORDS)
    if voice not in VOICES:
        raise ValueError(f"The narrator's voice is one of {', '.join(VOICES)}.")
    tag = re.sub(r"[\[\]\s]+", " ", note).strip()
    return {"model": MODEL, "input": {"prompt": f"[{tag}] {text}" if tag else text, "voice": voice}}


def characters(job_input: dict) -> int:
    return len(job_input["input"]["prompt"])


def trim(path: Path, out: Path) -> Path:
    """Every silence longer than PAUSE shortened to PAUSE; nothing with sound is cut."""
    gate = f"threshold={QUIET}"
    keep = (f"silenceremove=start_periods=1:start_silence={PAUSE}:start_{gate}:"
            f"stop_periods=-1:stop_duration={PAUSE}:stop_silence={PAUSE}:stop_{gate}")  # fmt: skip
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


def measure(path: Path, text: str, hear=song_timing.words) -> tuple[dict, Path | None]:
    """The narration's timing, and the trimmed file (beside `path`) when it's the one to
    use (None: keep the original, because the trim would have clipped a word)."""
    before = song_timing.length(path)
    trimmed = trim(path, path.with_name("trimmed.mp3"))
    after, heard = hear(trimmed, text), hear(path, text)
    same = letters(after) == letters(heard)
    use, heard = (trimmed, after) if same else (path, heard)
    seconds = song_timing.length(use)
    timing = {
        "seconds": seconds, "untrimmed_seconds": before, "trimmed": same, "bpm": None,
        "beats": [], "sections": [], "words": heard,
        "lines": song_timing.lines("\n".join(sentences(text)), heard, seconds),
        "peaks": song_timing.peaks(song_timing._samples(use)),
    }  # fmt: skip
    return timing, trimmed if same else None
