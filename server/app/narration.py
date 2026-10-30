"""Narrated ads (flows N1, V6n): one voice reads the version's words. A narration is a song
take of kind "narration" (docs/next/data.md), so Use, out of date, Undo and the video's own
choice work as for a song; its lyrics are the words it reads and its style line is empty.

Made with one voice call (ElevenLabs v3 through Replicate, priced from the catalogue per
1,000 characters); then, free on our server: pauses are trimmed on real silence only, the
trimmed narration is heard again and used only if it says the same letters, and each
sentence's start and end are measured (the breakdown's clock, as a song's lines are)."""

import re
import subprocess
from pathlib import Path

from app import song_timing
from app.prompts import check

KIND = "narration"
TIMED = ("song", "narrated")  # script kinds whose videos are timed to a take
MODEL = "elevenlabs-v3"
VOICE = "Sarah"
# Silence only: a quiet stretch (below -40 dB) longer than this is shortened to it
PAUSE, QUIET = 0.25, "-40dB"


def video_kind(db, project) -> str:
    """A video's type is its script's kind: story, song or narrated. A video with no script
    (the earlier New video form) is a story. Its look is a setting apart (Song in any look)."""
    from app.models.script_library import Script, ScriptDraft

    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    return db.get(Script, draft.script_id).kind if draft else "story"


NO_WORDS = "Write the words first: the narrator reads them as written."
FAILED = "The narration didn't finish. Nothing was charged."
MAKING = "A narration is being made. It's ready in a moment."
KEPT_PAUSES = "Kept the pauses: trimming would have clipped a word."
TIMING_FAILED = "We couldn't read this narration's timing. It's free to try again."
TIMING_UNREADABLE = "This narration's file can't be read. Make the narration again."


def sentences(text: str) -> list[str]:
    """One per line of the timing: each line split after . ! ? or …"""
    return [s for line in text.splitlines() for s in re.split(r"(?<=[.!?…])\s+", line) if s]


def job(script: str, voice: str = VOICE) -> dict:
    text = check.narration_text(script)  # the Director's: what the narrator reads
    if not text:
        raise ValueError(NO_WORDS)
    return {"model": MODEL, "input": {"prompt": text, "voice": voice}}


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


def _letters(heard: list[dict]) -> str:
    return "".join(re.sub(r"[^a-z]", "", w["word"].lower()) for w in heard)


def measure(path: Path, text: str, hear=song_timing.words) -> tuple[dict, Path | None]:
    """The narration's timing, and the trimmed file (beside `path`) when it's the one to
    use (None: keep the original, because the trim would have clipped a word)."""
    before = song_timing.length(path)
    trimmed = trim(path, path.with_name("trimmed.mp3"))
    after, heard = hear(trimmed, text), hear(path, text)
    same = _letters(after) == _letters(heard)
    use, heard = (trimmed, after) if same else (path, heard)
    seconds = song_timing.length(use)
    timing = {
        "seconds": seconds, "untrimmed_seconds": before, "trimmed": same, "bpm": None,
        "beats": [], "sections": [], "words": heard,
        "lines": song_timing.lines("\n".join(sentences(text)), heard, seconds),
        "peaks": song_timing.peaks(song_timing._samples(use)),
    }  # fmt: skip
    return timing, trimmed if same else None
