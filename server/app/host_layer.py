"""The presenter's host layer (the Dr. Pickle and UGC composite specs, 2026-11-03): one host,
filmed on a green screen, stands in a bottom corner over the full-frame B-roll cut and is
never cut. His clips are joined end to end into one continuous layer that runs straight
across the B-roll's cuts; he switches side at the times given so he never covers the action.
The sound is the cut's own (the narration) or a narration track given; the host clips' own
sound is never used. Free: ffmpeg only. Nothing calls it yet: the presenter format wires it
in after the narrated cut (routes/project_clips.make_video)."""

import re
import subprocess
import tempfile
from pathlib import Path

KEY = "#00B140"  # chroma-key green
HEIGHT = 0.45  # of the frame's height (Dr. Pickle: 35-45 %, at the bottom edge)
SIMILARITY, BLEND = 0.12, 0.08  # how near the key a colour is keyed, and how soft its edge
SIDES = ("left", "right")


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
            narration: str | None = None, out: str = "out.mp4") -> list[str]:  # fmt: skip
    """The ffmpeg command that lays the host clips (`hosts`, in order) over the B-roll `cut`
    (`frame` is its width and height): keyed on `key` (#RRGGBB) with its spill taken off,
    `height` of the frame tall, at the bottom, on the side `sides` says from each time
    ([(0, "right"), (6.2, "left"), ...] in seconds)."""
    if not hosts:
        raise ValueError("No host clips.")
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", key):
        raise ValueError("The key colour is #RRGGBB.")
    green, blue = int(key[3:5], 16), int(key[5:7], 16)
    tall = max(2, round(frame[1] * height / 2) * 2)
    clips = [f"[{n + 1}:v]fps=30,scale=-2:{tall},setsar=1[h{n}]" for n in range(len(hosts))]
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
    """The B-roll cut with the host layer over it, as an MP4."""
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
        args = command("cut.mp4", names, sides, (w, h), key, height,
                       "narration" if narration else None)  # fmt: skip
        done = subprocess.run(args, cwd=folder, capture_output=True, timeout=600)  # noqa: S603
        if done.returncode:
            raise RuntimeError(done.stderr.decode(errors="replace")[-2000:])
        return (folder / "out.mp4").read_bytes()
