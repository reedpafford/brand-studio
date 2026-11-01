"""Mute a span of a take in the final cut (take check, the hand fix for an unscripted line or
a gasp): the picked take's sound is silenced over each span when the video is put together.
Free (ffmpeg on our server); the take and its approval are untouched."""

import subprocess
import tempfile
from pathlib import Path

from app.models.clips import ClipTake, ProjectClip

MAX = 8  # spans a take may have muted
SHORTEST = 0.1  # seconds: a span shorter than this isn't one


def spans(take: ClipTake | None) -> list[list[float]]:
    return [list(s) for s in ((take.made_with or {}).get("mutes") or [])] if take else []


def add(take: ClipTake, start: float, end: float, longest: float) -> list[list[float]]:
    """Mute start–end (seconds in the take, kept inside it); spans that touch become one."""
    start, end = max(0.0, start), min(end, longest)
    if end - start < SHORTEST:
        raise ValueError("Pick a stretch of the take to mute.")
    merged: list[list[float]] = []
    for s, e in sorted([*spans(take), [round(start, 2), round(end, 2)]]):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    if len(merged) > MAX:
        raise ValueError(f"A take can have {MAX} muted stretches at most.")
    take.made_with = {**(take.made_with or {}), "mutes": merged}
    return merged


def remove(take: ClipTake, index: int) -> list[list[float]]:
    """Undo: unmute one span."""
    kept = spans(take)
    if not 0 <= index < len(kept):
        raise IndexError(index)
    del kept[index]
    take.made_with = {**(take.made_with or {}), "mutes": kept}
    return kept


def labels(clip: ProjectClip, take: ClipTake | None) -> list[str]:
    """How the final video remembers the mutes it was made with, so a new one shows as changes
    waiting (beside its cut-ins: "c2/mute:3.5-5.0")."""
    return [f"{clip.clip_id}/mute:{s}-{e}" for s, e in spans(take)]


def apply(video: bytes, muted: list[list[float]]) -> bytes:
    """The take with its sound silenced over each span (the picture copied as it is)."""
    if not muted:
        return video
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "in.mp4").write_bytes(video)
        probe = ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                 "stream=index", "-of", "csv=p=0", "in.mp4"]  # fmt: skip
        sound = subprocess.run(  # noqa: S603 - fixed arguments; file names are ours
            probe, cwd=folder, capture_output=True, text=True, timeout=60
        ).stdout.strip()
        if not sound:  # nothing to silence
            return video
        quiet = ",".join(f"volume=enable='between(t,{s},{e})':volume=0" for s, e in muted)
        command = ["ffmpeg", "-v", "error", "-y", "-i", "in.mp4", "-af", quiet, "-c:v", "copy",
                   "-c:a", "aac", "out.mp4"]  # fmt: skip
        done = subprocess.run(command, cwd=folder, capture_output=True, timeout=600)  # noqa: S603
        if done.returncode != 0:
            raise RuntimeError(done.stderr.decode(errors="replace")[-2000:])
        return (folder / "out.mp4").read_bytes()
