"""Deep watch (the lead's kit, .context/avtools/deepwatch.py, as server code): how a take or a
cut moves and sounds, measured, and filmstrips dense enough to read motion and lips. Free:
ffmpeg and Pillow on our server, light enough for the worker. Left out of the kit: optical
flow (OpenCV) and the demucs stems (torch, about 2 GB); the camera move and music under a
voice are read from the strips and the spectrogram instead, with the loudness between words."""

import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TILE = 256  # a strip's frame width: a face and its mouth still read
DENSE_FPS, DENSE_SECONDS = 10, 0.8  # a dense window: frames sampled 10 a second round a moment
JUMP, JUMP_X = 12.0, 4.0  # a jump: a frame change this big and this many times its neighbours'
STILL = 0.05  # a frame identical to the one before (a freeze)
SILENT = -45  # dB: below this, nothing is heard
CUT = 0.3  # ffmpeg's scene score for a shot change
FONT = Path(__file__).parent / "fonts" / "Inter-SemiBold.otf"


def _log(args: list[str]) -> str:
    """ffmpeg's log for a filter run (what the filters print goes to stderr)."""
    command = ["ffmpeg", "-hide_banner", "-nostats", *args, "-f", "null", "-"]
    return subprocess.run(  # noqa: S603 - fixed arguments; the file is ours
        command, capture_output=True, text=True, timeout=300
    ).stderr


def probe(src: Path) -> dict:
    """{length, width, height, audio}: the file's own facts."""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,width,height",
        "-of",
        "default=nw=1",
        str(src),
    ]
    out = subprocess.run(command, capture_output=True, text=True, timeout=60).stdout  # noqa: S603
    num = {k: float(v) for k, v in re.findall(r"^(duration|width|height)=([\d.]+)$", out, re.M)}
    return {"length": round(num.get("duration", 0.0), 2), "width": int(num.get("width", 9)),
            "height": int(num.get("height", 16)), "audio": "codec_type=audio" in out}  # fmt: skip


def cuts(src: Path) -> list[float]:
    """Its shot changes, in seconds (ffmpeg's scene score)."""
    log = _log(["-i", str(src), "-vf", f"select='gt(scene,{CUT})',showinfo", "-an"])
    return [round(float(t), 2) for t in re.findall(r"pts_time:([\d.]+)", log)]


def motion(src: Path, cuts: list[float]) -> dict:
    """Frame-to-frame change (the mean pixel difference, 0-255, on a small grey copy): how much
    moves each second, jumps away from any cut (a glitch, a pop, a morph), and freezes."""
    log = _log(["-i", str(src), "-an", "-vf", "scale=160:-2,format=gray,tblend=all_mode="
                "difference,signalstats,metadata=print:key=lavfi.signalstats.YAVG"])  # fmt: skip
    times = [float(t) for t in re.findall(r"pts_time:([\d.]+)", log)]
    diffs = [float(d) for d in re.findall(r"signalstats\.YAVG=([\d.]+)", log)]
    seen = list(zip(times, diffs, strict=False))
    jumps, frozen, run = [], [], None
    for n, (t, d) in enumerate(seen):
        near = sorted(x for _, x in seen[max(0, n - 6) : n] + seen[n + 1 : n + 7])
        usual = near[len(near) // 2] if near else 0.0
        away = all(abs(t - c) > 0.1 for c in [*cuts, *jumps])  # a pop in and out is one jump
        if d > max(JUMP, JUMP_X * usual) and away:
            jumps.append(round(t, 2))
        if d < STILL:
            run = run if run is not None else t
        elif run is not None:
            frozen += [[round(run, 2), round(t, 2)]] if t - run >= 0.4 else []
            run = None
    if run is not None and seen and seen[-1][0] - run >= 0.4:
        frozen.append([round(run, 2), round(seen[-1][0], 2)])
    seconds: dict[int, list[float]] = {}
    for t, d in seen:
        seconds.setdefault(int(t), []).append(d)
    return {"per_second": [round(sum(v) / len(v), 1) for _, v in sorted(seconds.items())],
            "jumps": jumps[:6], "frozen": frozen[:4]}  # fmt: skip


def sound(src: Path, words: list[dict]) -> dict:
    """What it sounds like: loudness (LUFS) as a whole and each half second, the peak, clipped
    samples, the silences, and how loud it is while nobody speaks (music or noise under it)."""
    log = _log(["-i", str(src), "-vn", "-af", "ebur128=metadata=1,ametadata=print:key=lavfi."
                f"r128.M,volumedetect,silencedetect=noise={SILENT}dB:d=0.3"])  # fmt: skip
    steps = [float(x) for x in re.findall(r"lavfi\.r128\.M=(-?[\d.]+)", log)]  # every 0.1 s
    whole = re.search(r"I:\s+(-?[\d.]+) LUFS", log)
    peak = re.search(r"max_volume: (-?[\d.]+) dB", log)
    clipped = re.search(r"histogram_0db: (\d+)", log)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    halves = [round(max(steps[i : i + 5]), 1) for i in range(0, len(steps), 5)]
    spoken = [(w["start"], w["end"]) for w in words]
    gaps = [m for i, m in enumerate(steps)
            if not any(a - 0.1 <= i / 10 <= b + 0.1 for a, b in spoken)]  # fmt: skip
    gaps = sorted(gaps)
    return {
        "lufs": float(whole[1]) if whole else None,
        "peak_db": float(peak[1]) if peak else None,
        "clipped_samples": int(clipped[1]) if clipped else 0,
        "silences": [
            [round(max(a, 0), 2), round(b, 2)] for a, b in zip(starts, ends, strict=False)
        ],  # fmt: skip
        "loudness_per_half_second": [max(x, -70.0) for x in halves],
        "between_words_lufs": round(gaps[len(gaps) // 2], 1) if spoken and gaps else None,
    }


def spectrogram(src: Path, dst: Path, width: int = 1000) -> bool:
    """The sound as a picture (time across, pitch up): a voice's harmonics, a music bed's
    steady lines, hits and silences show. False when the file has no sound."""
    done = subprocess.run(  # noqa: S603 - fixed arguments; the file is ours
        ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-lavfi",  # noqa: S607
         f"showspectrumpic=s={width}x160:legend=1:scale=log:fscale=log", str(dst)],
        capture_output=True, timeout=120)  # fmt: skip
    return done.returncode == 0 and dst.exists()


def windows(length: float, moments: list[float], most: int) -> list[float]:
    """Where dense windows start: one on each moment (in the order given: the most important
    first), never overlapping, `most` at most, inside the video."""
    out: list[float] = []
    for m in moments:
        start = round(min(max(m - DENSE_SECONDS / 2, 0.0), max(length - DENSE_SECONDS, 0.0)), 2)
        if all(abs(start - s) >= DENSE_SECONDS for s in out):
            out.append(start)
        if len(out) == most:
            break
    return sorted(out)


def _frames(src: Path, start: float, seconds: float, fps: float, folder: Path,
            name: str) -> list[tuple[float, Path]]:  # fmt: skip
    """Frames from `start` for `seconds` at `fps`, each with its time."""
    command = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-t", f"{seconds:.2f}",
               "-i", str(src), "-vf", f"fps={fps:.4f},scale={TILE}:-2", "-q:v", "4",
               str(folder / f"{name}-%03d.jpg")]  # fmt: skip
    subprocess.run(command, timeout=120, check=True)  # noqa: S603
    made = sorted(folder.glob(f"{name}-*.jpg"))
    return [(round(start + n / fps, 2), p) for n, p in enumerate(made)]


def said_at(words: list[dict], t: float) -> str:
    """The word being said at `t` seconds, for a frame's label ("" between words)."""
    return next((w["word"].strip() for w in words if w["start"] <= t < w["end"]), "")


def strip(frames: list[tuple[float, Path]], dst: Path, words: list[dict], cols: int = 4) -> None:
    """Frames in a grid, each labelled with its time and the word said then."""
    tiles = [Image.open(p).convert("RGB") for _, p in frames]
    w, h = tiles[0].size
    rows = -(-len(tiles) // cols)
    sheet = Image.new("RGB", (w * min(cols, len(tiles)), h * rows))
    draw, font = ImageDraw.Draw(sheet), ImageFont.truetype(str(FONT), 15)
    for n, ((t, _), tile) in enumerate(zip(frames, tiles, strict=True)):
        x, y = (n % cols) * w, (n // cols) * h
        sheet.paste(tile, (x, y))
        word = said_at(words, t)
        draw.rectangle((x, y, x + w, y + 20), fill=(0, 0, 0))
        draw.text((x + 4, y + 2), f"{t:.2f}s" + (f"  “{word}”" if word else ""), font=font,
                  fill=(255, 255, 255))  # fmt: skip
    sheet.save(dst, quality=80)


def per_strip(width: int, height: int) -> int:
    """Frames a strip holds at four across within about 1024 px high: 8 upright, 16 at most."""
    tall = TILE * height / max(width, 1)
    return max(4, min(16, 4 * int(1024 // max(tall, 1))))


def strips(src: Path, facts: dict, folder: Path, words: list[dict], overview: int,
           moments: list[float], dense: int) -> list[dict]:  # fmt: skip
    """The filmstrips to look at, [{path, what, start, end}]: `overview` frames spread over
    the whole video, then dense windows (10 a second) on the `moments` (jumps, cuts, the first
    word: most important first), `dense` at most."""
    length, size = facts["length"], per_strip(facts["width"], facts["height"])
    out = []
    every = _frames(src, 0.0, length, overview / max(length, 0.1), folder, "all")
    rate = f"{overview / max(length, 0.1):.1f}".removesuffix(".0")
    for n in range(0, len(every), size):
        part = every[n : n + size]
        dst = folder / f"strip-all-{n // size}.jpg"
        strip(part, dst, words)
        out.append({"path": dst, "what": f"sampled frames over the whole ({rate} a second)",
                    "start": part[0][0], "end": part[-1][0]})  # fmt: skip
    for k, start in enumerate(windows(length, moments, dense)):
        frames = _frames(src, start, DENSE_SECONDS, DENSE_FPS, folder, f"near{k}")
        if frames:
            dst = folder / f"strip-near-{k}.jpg"
            strip(frames, dst, words)
            out.append({"path": dst, "what": f"sampled frames round a key moment "
                        f"({DENSE_FPS} a second)",
                        "start": frames[0][0], "end": frames[-1][0]})  # fmt: skip
    for f in folder.glob("*-[0-9][0-9][0-9].jpg"):
        f.unlink()  # the single frames: only the strips stay
    return out


def told(m: dict) -> str:
    """The measurements as plain lines for a watch's <measured>."""
    lines = [f"Length {m['length']} s, {m['width']}x{m['height']}."]
    if (moved := m.get("motion")) is not None:
        lines.append(f"Picture change each second (0-255): {moved['per_second']}.")
        lines.append(
            f"Jumps away from any cut (a glitch, a pop or a morph?): "
            f"{moved['jumps'] or 'none'}. Frozen stretches: {moved['frozen'] or 'none'}."
        )
    if m.get("cuts") is not None:
        lines.append(f"Shot changes at: {m['cuts'] or 'none'} s.")
    heard = m.get("sound")
    if not m.get("audio") or heard is None:
        lines.append("No sound track.")
    else:
        lines.append(f"Loudness {heard['lufs']} LUFS, peak {heard['peak_db']} dB, "
                     f"{heard['clipped_samples']} clipped samples. Each half second (LUFS): "
                     f"{heard['loudness_per_half_second']}.")  # fmt: skip
        lines.append(f"Silences: {heard['silences'] or 'none'}. Between the transcript's words: "
                     f"{heard['between_words_lufs'] if heard['between_words_lufs'] is not None else 'n/a'} LUFS.")  # fmt: skip  # noqa: E501
    return "\n".join(lines)


def look(src: Path, folder: Path, words: list[dict], count: int, dense: int,
         wide: int = 1000, ending: bool = False) -> tuple[dict, list[dict]]:  # fmt: skip
    """Everything a watch looks at, free: the facts (`told` says them), and its pictures
    ({path, what, start, end}): `count` frames sampled over the whole, `dense` windows
    sampled at 10 a second on its jumps, then its shot changes, then the first word, and its
    spectrogram when it has sound. `ending`: a cut's, whose first dense window is its last
    moment (what it ends on: the director's trim says what that should be), one more than
    `dense`, so its glitches and clip joins keep theirs.
    `words` ({word, start, end}) label the frames and split the loudness."""
    facts = probe(src)
    facts["cuts"] = cuts(src)
    facts["motion"] = motion(src, facts["cuts"])
    facts["sound"] = sound(src, words) if facts["audio"] else None
    first = [words[0]["start"]] if words else []
    last = [facts["length"]] if ending else []
    moments = [*last, *facts["motion"]["jumps"], *facts["cuts"], *first]
    made = strips(src, facts, folder, words, count, moments, dense + len(last))
    spec = folder / "spectrogram.png"
    if facts["audio"] and spectrogram(src, spec, wide):
        made.append({"path": spec, "what": "the sound as a spectrogram (time across, pitch up)",
                     "start": 0.0, "end": facts["length"]})  # fmt: skip
    return facts, made


def named(made: list[dict]) -> list[str]:
    """What each picture is, as a watch's <strips> lists it."""
    return [f"{m['start']:.1f}–{m['end']:.1f} s: {m['what']}" for m in made]
