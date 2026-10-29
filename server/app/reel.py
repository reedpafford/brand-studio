"""Reel import, the free local part (docs/design/reel-import-server.md §1–2): fetch a reel
link with yt-dlp, check the video with ffprobe, find the shot cuts with ffmpeg scene
detection, tile one frame per shot into a contact sheet, and transcribe with faster-whisper.
Everything runs as subprocesses with timeouts, so a stuck run fails the job, not the worker."""

import io
import json
import re
import subprocess  # noqa: S404 - fixed argument lists, never a shell
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

MAX_MB = 100
MAX_SECONDS = 90
SLACK = 0.5  # a "90 s" file often measures a little over (audio padding)
SCENE = 0.3  # ffmpeg scene score that counts as a cut
FETCH_TIMEOUT = 90
FETCH_PAUSE = 5  # seconds after each Instagram fetch
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
    args += ["--write-info-json"]  # reel.info.json: its caption names the script
    args += ["--max-filesize", f"{MAX_MB}M", "-f", "mp4/best[ext=mp4]/best", "-o", str(out), url]
    try:
        done = _run(args, FETCH_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise Refused("blocked", BLOCKED) from None
    finally:
        time.sleep(FETCH_PAUSE)  # several links in a row look less like a bot when spaced
    if done.returncode != 0 or not out.is_file():
        private = re.search(r"private|unavailable|removed|not exist", done.stderr, re.I)
        raise Refused("gone", GONE) if private else Refused("blocked", BLOCKED)
    return out


def probe(path: Path, max_seconds: int | None = None) -> float:
    """The video's length in seconds, once it passes the caps (size, length, sound, type);
    longer than `max_seconds` (default: a reel's MAX_SECONDS) is refused."""
    max_seconds = max_seconds or MAX_SECONDS
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
    if seconds > max_seconds + SLACK:
        long = f"{seconds / 60:.0f} minutes" if seconds >= 120 else f"{seconds:.0f} seconds"
        most = f"{max_seconds // 60} minutes" if max_seconds >= 120 else f"{max_seconds} seconds"
        raise Refused("too_long", f"This video is {long} long; reels up to {most} can be read.")
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


WATCH_KBPS = (160, 40)  # video, audio: a 90 s reel comes out near 2.3 MB
WATCH_MAX_MB = 6  # sent inline as a data: URL, so it must stay small


def watch_copy(path: Path, folder: Path) -> Path:
    """A small H.264/AAC copy that Gemini gets inline as a data: URL: short side 540 px,
    24 fps, bitrate capped. The original stays for everything else (cuts, contact sheet,
    transcript, download)."""
    out = folder / "watch.mp4"
    video, audio = WATCH_KBPS
    small = "scale='if(gt(iw,ih),-2,540)':'if(gt(iw,ih),540,-2)',fps=24"
    args = ["ffmpeg", "-v", "error", "-i", str(path), "-vf", small, "-c:v", "libx264"]
    args += ["-preset", "veryfast", "-b:v", f"{video}k", "-maxrate", f"{video}k"]
    args += ["-bufsize", f"{video * 2}k", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", f"{audio}k"]
    done = _run([*args, "-movflags", "+faststart", "-y", str(out)], 180)
    if done.returncode != 0 or not out.is_file():
        raise RuntimeError(f"Making the watch copy failed ({done.returncode}).")
    if out.stat().st_size > WATCH_MAX_MB * 1024 * 1024:  # the cap makes this very unlikely
        raise Refused(
            "bad_file", "This video can't be made small enough to read. Try a shorter one."
        )
    return out


def _grab(path: Path, t: float, frame: Path, width: int) -> Image.Image | None:
    args = ["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1"]
    _run([*args, "-vf", f"scale={width}:-2", "-y", str(frame)], 30)
    return Image.open(frame).convert("RGB") if frame.is_file() else None


def _tile(tiles: list[Image.Image], cols: int, out: Path) -> Path:
    w, h = tiles[0].size
    sheet = Image.new("RGB", (w * cols, h * -(-len(tiles) // cols)), (0, 0, 0))
    for n, tile in enumerate(tiles):
        sheet.paste(tile.resize((w, h)), ((n % cols) * w, (n // cols) * h))
    buf = io.BytesIO()
    sheet.save(buf, "JPEG", quality=80)
    out.write_bytes(buf.getvalue())
    return out


def _spans(cut_times: list[float], seconds: float) -> list[tuple[float, float]]:
    edges = [0.0, *cut_times, seconds]
    return [(a, b) for a, b in zip(edges, edges[1:], strict=False) if b > a]


def contact_sheet(path: Path, cut_times: list[float], seconds: float, folder: Path) -> Path:
    """One frame from the middle of each shot (up to 60), tiled six across into one JPEG."""
    middles = [(a + b) / 2 for a, b in _spans(cut_times, seconds)][:60]
    tiles = [
        t for n, m in enumerate(middles) if (t := _grab(path, m, folder / f"shot{n}.jpg", 180))
    ]
    if not tiles:
        raise Refused("bad_file", "That file isn't a video we can read. Use an MP4 or MOV.")
    return _tile(tiles, min(6, len(tiles)), folder / "contact.jpg")


GRIDS = 9  # with the contact sheet, the 10 images Gemini takes
ROWS = 12  # shots per grid at most; longer reels are sampled


def _label(frame: Image.Image, text: str) -> Image.Image:
    draw = ImageDraw.Draw(frame)
    box = draw.textbbox((4, 4), text)
    draw.rectangle((box[0] - 2, box[1] - 2, box[2] + 2, box[3] + 2), fill=(0, 0, 0))
    draw.text((4, 4), text, fill=(255, 255, 255))
    return frame


def frame_grids(path: Path, cut_times: list[float], seconds: float, folder: Path) -> list[Path]:
    """For watching from pictures when video won't go through: each shot as one row of three
    frames (near its start, middle and end), each marked with its shot number and time, in
    order, up to 12 shots per JPEG and 9 JPEGs."""
    spans = list(enumerate(_spans(cut_times, seconds), 1))
    if len(spans) > GRIDS * ROWS:  # sample evenly, keeping the order
        spans = [spans[i * len(spans) // (GRIDS * ROWS)] for i in range(GRIDS * ROWS)]
    per = ROWS  # as few pictures as possible
    grids = []
    for g in range(0, len(spans), per):
        tiles = []
        for shot, (a, b) in spans[g : g + per]:
            for k, f in enumerate((0.15, 0.5, 0.85)):
                t = a + (b - a) * f
                frame = _grab(path, t, folder / f"g{shot}-{k}.jpg", 240)
                if frame:
                    tiles.append(_label(frame, f"{shot} · {t:.2f}s"))
        if tiles:
            grids.append(_tile(tiles, 3, folder / f"grid{len(grids)}.jpg"))
    return grids


def warm() -> None:
    """Download and load the speech model once (at worker start)."""
    done = _run([sys.executable, "-m", "app.whisper", "--warm"], 900)
    if done.returncode != 0:
        raise RuntimeError(f"Loading the speech model failed ({done.returncode}).")


def caption(folder: Path) -> str:
    """The reel's caption as its page shows it (from yt-dlp's info file), or ""."""
    try:
        info = json.loads((folder / "reel.info.json").read_text())
    except (OSError, ValueError):
        return ""
    return str(info.get("description") or info.get("title") or "").strip()


def name_for(caption_text: str, transcript: list[dict], limit: int = 60) -> str:
    """A script's name from an imported reel: its caption's first line, else its first spoken
    line, without hashtags or mentions (QA-Live run 3: "Based on a True Story #business"), cut
    at a word to fit ("" if neither has words)."""
    lines = [caption_text, *(t.get("text", "") for t in transcript)]
    tags = re.compile(r"(?<!\w)[#@][\w.]+")
    bare = (" ".join(tags.sub(" ", x.strip().splitlines()[0]).split()) for x in lines if x.strip())
    first = next((line for line in bare if line), "")
    first = first.strip(" \"'“”")
    if len(first) <= limit:
        return first
    return first[:limit].rsplit(" ", 1)[0].rstrip(",.;:—-") + "…"


def transcribe(path: Path) -> list[dict]:
    """faster-whisper small (int8, CPU) in a subprocess: [{start, end, text, speaker}]."""
    try:
        done = _run([sys.executable, "-m", "app.whisper", str(path)], TRANSCRIBE_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Transcription took too long.") from None
    if done.returncode != 0:
        raise RuntimeError(f"Transcription failed ({done.returncode}).")
    return json.loads(done.stdout)
