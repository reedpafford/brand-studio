"""The presenter's host layer (the Dr. Pickle and UGC composite specs, 2026-11-03): one host,
filmed on a green screen, stands in a bottom corner over the full-frame B-roll cut and is
never cut. His clips are joined end to end into one continuous layer that runs straight
across the B-roll's cuts; over each span of the cut he stands on its side at its height, or
is hidden there (app/cut.py: the cut editor's presenter track).
The sound is the cut's own (the narration) or a narration track given; the host clips' own
sound is never used. Free: ffmpeg only, after the narrated cut (app/cut_render.py). The host
is one HeyGen take of the whole narration (app/host.py); a list of clips still joins end to end.

From the paid P-Video test (.context/tests/presenter-1, 2026-11-03): each clip's video can run
past its sound, so it's trimmed to it; the key below took a generated green (measured #07A548)
cleanly."""

import re
import subprocess
import tempfile
from pathlib import Path

KEY = "#00B140"  # chroma-key green
HEIGHT = 0.38  # of the frame's height (spec: 35-45 %, at the bottom edge; the test's pick)
SIMILARITY, BLEND = 0.13, 0.06  # how near the key a colour is keyed, and how soft its edge
SIDES = ("left", "right")


def _spans(spans: list[dict]) -> list[dict]:
    """Where the host shows: each span's start and end, side, height (of the frame) and
    whether it's hidden there (the cut editor's presenter spans)."""
    if any(s["side"] not in SIDES or s["end"] <= s["start"] for s in spans):
        raise ValueError("Each span runs forward, on the 'left' or the 'right'.")
    if any(b["start"] < a["end"] - 0.01 for a, b in zip(spans, spans[1:], strict=False)):
        raise ValueError("Spans go in time order.")
    return [s for s in spans if not s.get("hidden")]


def command(cut: str, hosts: list[str], spans: list[dict], frame: tuple[int, int],
            key: str = KEY, narration: str | None = None,
            lengths: list[float | None] | None = None,
            out: str = "out.mp4") -> list[str]:  # fmt: skip
    """The ffmpeg command that lays the host clips (`hosts`, in order, each cut to its
    `lengths` entry when given) over the B-roll `cut` (`frame` is its width and height):
    keyed on `key` (#RRGGBB) with its spill taken off, at the bottom, over each span not
    hidden at its side and height ([{start, end, side, height, hidden}, ...])."""
    if not hosts:
        raise ValueError("No host clips.")
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", key):
        raise ValueError("The key colour is #RRGGBB.")
    shown = _spans(spans)
    if not shown:
        raise ValueError("The host is hidden everywhere.")
    green, blue = int(key[3:5], 16), int(key[5:7], 16)
    lengths = lengths or [None] * len(hosts)
    clips = [f"[{n + 1}:v]{f'trim=duration={d},setpts=PTS-STARTPTS,' if d else ''}"
             f"fps=30,setsar=1[h{n}]" for n, d in enumerate(lengths)]  # fmt: skip
    joined = "".join(f"[h{n}]" for n in range(len(hosts)))
    outs = "".join(f"[k{i}]" for i in range(len(shown)))
    graph = [*clips,
             f"{joined}concat=n={len(hosts)}:v=1:a=0,"
             f"chromakey=0x{key[1:]}:{SIMILARITY}:{BLEND},"
             f"despill=type={'blue' if blue > green else 'green'},"
             f"split={len(shown)}{outs}"]  # fmt: skip
    under = "0:v"
    for i, s in enumerate(shown):
        tall = max(2, round(frame[1] * s.get("height", HEIGHT) / 2) * 2)
        a, b = s["start"], s["end"]
        x = "0" if s["side"] == "left" else "W-w"
        last = i == len(shown) - 1
        graph += [f"[k{i}]trim=start={a}:end={b},scale=-2:{tall},setsar=1[p{i}]",
                  f"[{under}][p{i}]overlay=x={x}:y=H-h:eof_action=pass:"
                  f"enable='between(t,{a},{b})'{',format=yuv420p' if last else ''}"
                  f"[{'v' if last else f'o{i}'}]"]  # fmt: skip
        under = f"o{i}"
    inputs = [arg for name in (cut, *hosts, *([narration] if narration else [])) for arg in
              ("-i", name)]  # fmt: skip
    sound = f"{len(hosts) + 1}:a" if narration else "0:a?"
    return ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(graph),
            "-map", "[v]", "-map", sound, "-c:v", "libx264", "-c:a", "aac",
            "-movflags", "+faststart", out]  # fmt: skip


def lay_over(cut: bytes, hosts: list[bytes], spans: list[dict], key: str = KEY,
             narration: bytes | None = None) -> bytes:  # fmt: skip
    """The B-roll cut with the host layer over it, as an MP4. Each host clip is cut to its
    own sound (the narration piece it lip-syncs), so the pieces stay in time with the voice.
    Hidden everywhere: the cut as it is."""
    from app.cut_render import _probe

    if not _spans(spans):
        return cut

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
        args = command("cut.mp4", names, spans, (w, h), key,
                       "narration" if narration else None, lengths)  # fmt: skip
        done = subprocess.run(args, cwd=folder, capture_output=True, timeout=600)  # noqa: S603
        if done.returncode:
            raise RuntimeError(done.stderr.decode(errors="replace")[-2000:])
        return (folder / "out.mp4").read_bytes()
