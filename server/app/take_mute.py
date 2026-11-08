"""Mute a span of a take in the final cut (take check, the hand fix for an unscripted line or
a gasp): the picked take's sound is silenced over each span when the video is put together.
Free (ffmpeg on our server); the take and its approval are untouched."""

import math
import re
import subprocess
import tempfile
from difflib import SequenceMatcher
from pathlib import Path

from app.models.clips import ClipTake, ProjectClip
from app.models.projects import Project

MAX = 8  # spans a take may have muted
SHORTEST = 0.1  # seconds: a span shorter than this isn't one


def spans(take: ClipTake | None) -> list[list[float]]:
    return [list(s) for s in ((take.made_with or {}).get("mutes") or [])] if take else []


def merged(muted: list[list[float]]) -> list[list[float]]:
    """The stretches as the cut silences them: ones that overlap or touch become one."""
    out: list[list[float]] = []
    for s, e in sorted(muted):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def add(take: ClipTake, start: float, end: float, longest: float) -> list[list[float]]:
    """Mute start–end (seconds in the take, kept inside it). Each stretch is kept as added, so
    Undo takes back exactly that one; overlaps are only joined in the cut."""
    if not (math.isfinite(start) and math.isfinite(end)):
        raise ValueError("Pick a stretch of the take to mute.")
    start, end = max(0.0, start), min(end, longest)
    if end - start < SHORTEST:
        raise ValueError("Pick a stretch of the take to mute.")
    kept = spans(take)
    if len(kept) >= MAX:
        raise ValueError(f"A take can have {MAX} muted stretches at most.")
    kept.append([round(start, 2), round(end, 2)])
    take.made_with = {**(take.made_with or {}), "mutes": kept}
    return kept


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
    return [f"{clip.clip_id}/mute:{s}-{e}" for s, e in merged(spans(take))]


def apply(video: bytes, muted: list[list[float]]) -> bytes:
    """The take with its sound silenced over each span (the picture copied as it is)."""
    muted = merged(muted)
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


HEARD = 0.8  # of a line's words heard, in order, for it to count as said
LOST_LINE = ("That would silence {who}“{line}”: it's the only time it's heard in the cut. Every "
             "scripted line stays; pick another take or remake the clip instead.")  # fmt: skip


def lost_line(db, row: ProjectClip, take: ClipTake, start: float, end: float) -> str:
    """Why muting start–end of the clip's picked take would leave one of its scripted lines
    heard nowhere in the cut, or "" (video 284: the words check heard "Two of these every
    morning." apart from the rest of its line, called it unscripted, and the mute silenced
    the line's only copy). Judged on the take's heard words that play in the cut, before and
    after the mute; with no words heard yet, it can't be told, so it's allowed."""
    from app import cut
    from app.word_splice import _heard

    heard = _heard(db, take)[0]
    lines = _lines(db, row)
    if not heard or not lines:
        return ""
    project = db.get(Project, row.project_id)
    pieces = [p for p in cut.timeline(db, project)[0]["pieces"] if p["take_id"] == take.id]
    plays = [(0.0, math.inf) if p["whole"] else (p["from"], p["from"] + p["end"] - p["start"])
             for p in pieces] or [(0.0, math.inf)]  # fmt: skip

    def kept(muted: list[list[float]]) -> list[str]:
        mid = [((w["start"] + w["end"]) / 2, w["word"]) for w in heard]
        return [bare for t, word in mid if any(a <= t <= b for a, b in plays)
                and not any(s <= t <= e for s, e in muted) for bare in _bare(word)]  # fmt: skip

    before, after = kept(spans(take)), kept([*spans(take), [start, end]])
    for who, line in lines:
        if _said(line, before) and not _said(line, after):
            return LOST_LINE.format(who=f"{who}'s " if who else "", line=line)
    return ""


def _bare(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _said(line: str, words: list[str]) -> bool:
    """Most of the line's words heard in order."""
    want = _bare(line)
    hit = sum(b.size for b in SequenceMatcher(None, want, words, autojunk=False)
              .get_matching_blocks())  # fmt: skip
    return bool(want) and hit >= HEARD * len(want)


def _lines(db, row: ProjectClip) -> list[tuple[str, str]]:
    """The clip's scripted spoken lines, (who, words), from the plan it was made from."""
    from app.models.breakdowns import BreakdownVersion

    plan = db.get(BreakdownVersion, row.breakdown_id) if row.breakdown_id else None
    data = plan.data if plan else {}
    ids = next((c["shot_ids"] for c in data.get("clips", []) if c["id"] == row.clip_id), [])
    return [((s.get("speaker") or "").strip(), s["line"].strip())
            for sc in data.get("scenes", []) for s in sc.get("shots", [])
            if s["id"] in ids and s.get("line")]  # fmt: skip
