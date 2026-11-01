"""Where a take check looks (Producer, 1 Nov): its FRAMES frames sit on the take's shot changes
and the starts of its spoken lines, not evenly spaced, so a quick cut, a swap or a 0.2 s
reveal is seen (FOMO-Producer: one frame a second missed them). Free: ffmpeg on our server."""

import re
import subprocess
from pathlib import Path

from sqlalchemy.orm import Session

AFTER = 0.15  # seconds after a boundary: the new shot or the speaker, settled
CUT = 0.3  # ffmpeg's scene score for a shot change


def moments(length: float, marks: list[float], count: int) -> list[float]:
    """`count` times to look at: the boundaries, the most spread out when there are too many,
    filled in evenly when too few. Always inside the take, in order."""
    last = max(length - 0.3, 0.0)
    marks = sorted({round(min(max(m + AFTER, 0.0), last), 2) for m in marks})
    grid = [round(last / 2 if count == 1 else last * n / (count - 1), 2) for n in range(count)]
    chosen: list[float] = []
    for pool in (marks, grid):  # boundaries first, then the even spacing fills the gaps
        pool = [p for p in pool if p not in chosen]
        while pool and len(chosen) < count:
            far = max(pool, key=lambda p: min((abs(p - c) for c in chosen), default=p + 1))
            chosen.append(far)
            pool.remove(far)
    return sorted(chosen)


def _ffmpeg(args: list[str]) -> str:
    """ffmpeg's log for a filter run (what the filters print goes to stderr)."""
    command = ["ffmpeg", "-hide_banner", "-nostats", *args, "-f", "null", "-"]
    return subprocess.run(  # noqa: S603 - fixed arguments; the file is ours
        command, capture_output=True, text=True, timeout=120
    ).stderr


def cuts(src: Path) -> list[float]:
    """The take's shot changes, in seconds."""
    log = _ffmpeg(["-i", str(src), "-vf", f"select='gt(scene,{CUT})',showinfo", "-an"])
    return [float(t) for t in re.findall(r"pts_time:([\d.]+)", log)]


def starts(db: Session, take_id: int | None, src: Path) -> list[float]:
    """Where its spoken lines start: from the take's words check when it has heard it, else
    where the sound comes back after a silence."""
    from app.item_checks import latest
    from app.models.jobs import Job

    row = latest(db, "words", [take_id]).get(take_id) if take_id else None
    job = db.get(Job, row.job_id) if row and row.status == "done" and row.job_id else None
    if job and (heard := (job.output or {}).get("heard")):
        return [h["start"] for h in heard]
    log = _ffmpeg(["-i", str(src), "-af", "silencedetect=noise=-30dB:d=0.3", "-vn"])
    return [float(t) for t in re.findall(r"silence_end: ([\d.]+)", log)]
