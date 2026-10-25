"""Reel import, the free local part (docs/design/reel-import-server.md §1–2): fetch a reel
link with yt-dlp, check the video with ffprobe, find the shot cuts with ffmpeg scene
detection, tile one frame per shot into a contact sheet, and transcribe with faster-whisper.
Everything runs as subprocesses with timeouts, so a stuck run fails the job, not the worker."""

import io
import json
import re
import subprocess  # noqa: S404 - fixed argument lists, never a shell
import sys
from pathlib import Path

from PIL import Image

MAX_MB = 100
MAX_SECONDS = 90
SCENE = 0.3  # ffmpeg scene score that counts as a cut
FETCH_TIMEOUT = 90
TRANSCRIBE_TIMEOUT = 180
LINK = re.compile(
    r"https://(?:www\.)?instagram\.com/(?:reels?|p)/([A-Za-z0-9_-]{5,40})/?(?:\?\S*)?"
)
BLOCKED = "Instagram didn't let us download this reel. Upload the video instead."
GONE = "That reel is private or was removed. Upload the video instead."


class Refused(Exception):
    """A plain reason the reel can't be read, with a code the screens can branch on:
    blocked, gone, bad_file or too_long."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def reel_link(url: str) -> str | None:
    """The canonical reel URL, or None if it isn't an Instagram reel (or post) link."""
    found = LINK.fullmatch(url.strip())
    return f"https://www.instagram.com/reel/{found.group(1)}/" if found else None


def _run(args: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)  # noqa: S603


def fetch(url: str, folder: Path) -> Path:
    """Download a reel with yt-dlp: no cookies, no login, capped in size. Any failure is a
    plain Refused; the raw output is never logged (it holds nothing secret, but no need)."""
    out = folder / "reel.mp4"
    args = [sys.executable, "-m", "yt_dlp", "--no-playlist", "--no-cookies", "--quiet"]
    args += ["--max-filesize", f"{MAX_MB}M", "-f", "mp4/best[ext=mp4]/best", "-o", str(out), url]
    try:
        done = _run(args, FETCH_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise Refused("blocked", BLOCKED) from None
    if done.returncode != 0 or not out.is_file():
        private = re.search(r"private|unavailable|removed|not exist", done.stderr, re.I)
        raise Refused("gone", GONE) if private else Refused("blocked", BLOCKED)
    return out


def probe(path: Path) -> float:
    """The video's length in seconds, once it passes the caps (size, length, sound, type)."""
    if path.stat().st_size > MAX_MB * 1024 * 1024:
        raise Refused("bad_file", f"This video is over {MAX_MB} MB. Upload a smaller copy.")
    args = ["ffprobe", "-v", "error", "-show_entries", "format=duration,format_name"]
    done = _run([*args, "-show_entries", "stream=codec_type", "-of", "json", str(path)], 30)
    info = json.loads(done.stdout or "{}") if done.returncode == 0 else {}
    fmt = info.get("format", {})
    kinds = {s.get("codec_type") for s in info.get("streams", [])}
    if "mp4" not in fmt.get("format_name", "") or "video" not in kinds:
        raise Refused("bad_file", "That file isn't a video we can read. Use an MP4 or MOV.")
    seconds = float(fmt.get("duration") or 0)
    if seconds > MAX_SECONDS:
        long = f"{seconds / 60:.0f} minutes" if seconds >= 120 else f"{seconds:.0f} seconds"
        raise Refused(
            "too_long", f"This video is {long} long; reels up to {MAX_SECONDS} seconds can be read."
        )
    if "audio" not in kinds:
        raise Refused("bad_file", "This video has no sound, so there's no dialogue to read.")
    return round(seconds, 2)


def cuts(path: Path) -> list[float]:
    """Times (s) where a new shot starts, from ffmpeg's scene score."""
    vf = f"select='gt(scene,{SCENE})',showinfo"
    done = _run(["ffmpeg", "-hide_banner", "-i", str(path), "-vf", vf, "-f", "null", "-"], 120)
    return [round(float(t), 2) for t in re.findall(r"pts_time:([\d.]+)", done.stderr)]


def stats(cut_times: list[float], seconds: float) -> dict:
    """Shot count, median and shortest shot: measured here, never guessed by a model."""
    edges = [0.0, *cut_times, seconds]
    lengths = sorted(b - a for a, b in zip(edges, edges[1:], strict=False) if b > a)
    if not lengths:
        return {"shots": 0, "median_shot": 0, "shortest_shot": 0}
    return {
        "shots": len(lengths),
        "median_shot": round(lengths[len(lengths) // 2], 2),
        "shortest_shot": round(lengths[0], 2),
    }


def contact_sheet(path: Path, cut_times: list[float], seconds: float, folder: Path) -> Path:
    """One frame from the middle of each shot (up to 60), tiled six across into one JPEG."""
    edges = [0.0, *cut_times, seconds]
    middles = [(a + b) / 2 for a, b in zip(edges, edges[1:], strict=False) if b > a][:60]
    tiles = []
    for n, t in enumerate(middles):
        frame = folder / f"shot{n}.jpg"
        args = ["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1"]
        _run([*args, "-vf", "scale=180:-2", "-y", str(frame)], 30)
        if frame.is_file():
            tiles.append(Image.open(frame).convert("RGB"))
    if not tiles:
        raise Refused("bad_file", "That file isn't a video we can read. Use an MP4 or MOV.")
    w, h = tiles[0].size
    cols = min(6, len(tiles))
    sheet = Image.new("RGB", (w * cols, h * -(-len(tiles) // cols)), (0, 0, 0))
    for n, tile in enumerate(tiles):
        sheet.paste(tile.resize((w, h)), ((n % cols) * w, (n // cols) * h))
    out = folder / "contact.jpg"
    buf = io.BytesIO()
    sheet.save(buf, "JPEG", quality=80)
    out.write_bytes(buf.getvalue())
    return out


def transcribe(path: Path) -> list[dict]:
    """faster-whisper small (int8, CPU) in a subprocess: [{start, end, text, speaker}]."""
    try:
        done = _run([sys.executable, "-m", "app.whisper", str(path)], TRANSCRIBE_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Transcription took too long.") from None
    if done.returncode != 0:
        raise RuntimeError(f"Transcription failed ({done.returncode}).")
    return json.loads(done.stdout)
