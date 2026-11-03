"""The presenter's host layer (the Dr. Pickle and UGC composite specs, 2026-11-03): one host,
filmed on a green screen, stands in a bottom corner over the full-frame B-roll cut and is
never cut. His clips are joined end to end into one continuous layer that runs straight
across the B-roll's cuts; he switches side at the times given so he never covers the action.
The sound is the cut's own (the narration) or a narration track given; the host clips' own
sound is never used. Free: ffmpeg only. Nothing calls it yet: the presenter format wires it
in after the narrated cut (routes/project_clips.make_video).

From the paid P-Video test (.context/tests/presenter-1, 2026-11-03): the host is made in
pieces of about 10-12 s, cut at sentence ends (P-Video takes 20 s of sound at most and cuts
the rest without saying so, and its lip-sync weakens after about 10 s), each piece from the
same still; each piece's video runs about 0.5 s past its sound, so it's trimmed to it; the
key below took its generated green (measured #07A548) cleanly."""

import re
import subprocess
import tempfile
from pathlib import Path

KEY = "#00B140"  # chroma-key green
HEIGHT = 0.38  # of the frame's height (spec: 35-45 %, at the bottom edge; the test's pick)
SIMILARITY, BLEND = 0.13, 0.06  # how near the key a colour is keyed, and how soft its edge
SIDES = ("left", "right")
PIECE, MOST = 12.0, 20.0  # seconds of narration a host piece aims under, and P-Video's cap


def pieces(breaks: list[float], longest: float = PIECE) -> list[tuple[float, float]]:
    """The narration split into host pieces: `breaks` are where a piece may end (its
    sentence ends, in order; the last is the narration's end). Each piece runs up to
    `longest` seconds where the sentences allow; one past P-Video's 20 s can't be made."""
    spans, start, last = [], 0.0, 0.0
    for end in breaks:
        if end - start > longest and last > start:
            spans.append((start, last))
            start = last
        last = end
    spans.append((start, last))
    if any(b - a > MOST for a, b in spans):
        raise ValueError(f"A sentence runs past {MOST:.0f} s: split it to make the host.")
    return spans


def _x(sides: list[tuple[float, str]]) -> str:
    """The layer's left edge over time: flush with the frame's left or right side."""
    if not sides or sides[0][0] != 0 or any(s not in SIDES for _, s in sides):
        raise ValueError("Sides start at 0 s, each 'left' or 'right'.")
    if any(b <= a for (a, _), (b, _) in zip(sides, sides[1:], strict=False)):
        raise ValueError("Side changes go in time order.")
    x = "0" if sides[-1][1] == "left" else "W-w"
    for (_, side), (until, _) in reversed(list(zip(sides, sides[1:], strict=False))):
        x = f"if(lt(t,{until}),{'0' if side == 'left' else 'W-w'},{x})"
    return x


def command(cut: str, hosts: list[str], sides: list[tuple[float, str]],
            frame: tuple[int, int], key: str = KEY, height: float = HEIGHT,
            narration: str | None = None, lengths: list[float | None] | None = None,
            out: str = "out.mp4") -> list[str]:  # fmt: skip
    """The ffmpeg command that lays the host clips (`hosts`, in order, each cut to its
    `lengths` entry when given) over the B-roll `cut` (`frame` is its width and height):
    keyed on `key` (#RRGGBB) with its spill taken off, `height` of the frame tall, at the
    bottom, on the side `sides` says from each time ([(0, "right"), (6.2, "left"), ...])."""
    if not hosts:
        raise ValueError("No host clips.")
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", key):
        raise ValueError("The key colour is #RRGGBB.")
    green, blue = int(key[3:5], 16), int(key[5:7], 16)
    tall = max(2, round(frame[1] * height / 2) * 2)
    lengths = lengths or [None] * len(hosts)
    clips = [f"[{n + 1}:v]{f'trim=duration={d},setpts=PTS-STARTPTS,' if d else ''}"
             f"fps=30,scale=-2:{tall},setsar=1[h{n}]" for n, d in enumerate(lengths)]  # fmt: skip
    joined = "".join(f"[h{n}]" for n in range(len(hosts)))
    graph = [*clips,
             f"{joined}concat=n={len(hosts)}:v=1:a=0,"
             f"chromakey=0x{key[1:]}:{SIMILARITY}:{BLEND},"
             f"despill=type={'blue' if blue > green else 'green'}[host]",
             f"[0:v][host]overlay=x='{_x(sides)}':y=H-h:eval=frame:eof_action=pass,"
             "format=yuv420p[v]"]  # fmt: skip
    inputs = [arg for name in (cut, *hosts, *([narration] if narration else [])) for arg in
              ("-i", name)]  # fmt: skip
    sound = f"{len(hosts) + 1}:a" if narration else "0:a?"
    return ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(graph),
            "-map", "[v]", "-map", sound, "-c:v", "libx264", "-c:a", "aac",
            "-movflags", "+faststart", out]  # fmt: skip


def lay_over(cut: bytes, hosts: list[bytes], sides: list[tuple[float, str]], key: str = KEY,
             height: float = HEIGHT, narration: bytes | None = None) -> bytes:  # fmt: skip
    """The B-roll cut with the host layer over it, as an MP4. Each host clip is cut to its
    own sound (the narration piece it lip-syncs), so the pieces stay in time with the voice."""
    from app.clip_takes import _probe

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "cut.mp4").write_bytes(cut)
        names = [f"host{n}.mp4" for n in range(len(hosts))]
        for name, data in zip(names, hosts, strict=True):
            (folder / name).write_bytes(data)
        if narration:
            (folder / "narration").write_bytes(narration)
        w, h = (int(n) for n in _probe(folder, "cut.mp4", "v:0", "width,height").split("x"))
        heard = [_probe(folder, name, "a:0", "duration") for name in names]
        lengths = [float(s) if re.fullmatch(r"[\d.]+", s) else None for s in heard]
        args = command("cut.mp4", names, sides, (w, h), key, height,
                       "narration" if narration else None, lengths)  # fmt: skip
        done = subprocess.run(args, cwd=folder, capture_output=True, timeout=600)  # noqa: S603
        if done.returncode:
            raise RuntimeError(done.stderr.decode(errors="replace")[-2000:])
        return (folder / "out.mp4").read_bytes()
