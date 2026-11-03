"""The presenter's host layer (app/host_layer.py) on tiny generated clips: free, ffmpeg only."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from app import host_layer

W, H = 180, 320  # the B-roll; the host is keyed to 45 % of its height: 72 x 144
BOX = "0xFF00FF"  # the "host" standing on the green screen, in magenta


def _ffmpeg(*args: str, cwd: str | None = None) -> bytes:
    command = ["ffmpeg", "-v", "error", *args]
    return subprocess.run(command, cwd=cwd, capture_output=True, check=True).stdout  # noqa: S603, S607


def _make(source: str, seconds: float, sound: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        tone = f"sine=f={sound}:d={seconds}"
        _ffmpeg("-f", "lavfi", "-i", source, "-f", "lavfi", "-i", tone, "-t", str(seconds),
                "-pix_fmt", "yuv420p", "clip.mp4", cwd=tmp)  # fmt: skip
        return (Path(tmp) / "clip.mp4").read_bytes()


def _pixel(video: bytes, at: float, x: int, y: int) -> tuple[int, ...]:
    """The colour at (x, y) at `at` seconds, averaged over a 3 x 3 patch."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "v.mp4").write_bytes(video)
        frame = _ffmpeg("-ss", str(at), "-i", "v.mp4", "-frames:v", "1", "-f", "rawvideo",
                        "-pix_fmt", "rgb24", "-", cwd=tmp)  # fmt: skip
    patch = [frame[((y + j) * W + x + i) * 3 :][:3] for i in (-1, 0, 1) for j in (-1, 0, 1)]
    return tuple(sum(p[c] for p in patch) // 9 for c in range(3))


def _near(a, b, by=40) -> bool:
    return all(abs(p - q) <= by for p, q in zip(a, b, strict=True))


def test_the_host_is_keyed_over_the_b_roll_and_switches_side():
    broll = _make(f"testsrc=s={W}x{H}:r=30:d=2", 2, 440)
    host = f"color=c=0x00B140:s=100x200:r=30:d=1,drawbox=x=30:y=60:w=40:h=120:color={BOX}:t=fill"
    hosts = [_make(host, 1, 1000), _make(host, 1, 1000)]  # two clips, one layer
    cut = host_layer.lay_over(broll, hosts, [(0, "right"), (1, "left")])
    for at, right in ((0.5, True), (1.5, False)):
        left = W - 72 if right else 0  # the layer's left edge
        assert _near(_pixel(cut, at, left + 36, H - 58), (255, 0, 255))  # the host shows
        for x, y in ((left + 5, H - 139), (left + 66, H - 5)):  # his green screen doesn't:
            assert _near(_pixel(cut, at, x, y), _pixel(broll, at, x, y))  # the B-roll does
        other = 36 if right else W - 36  # and the far corner is all B-roll
        assert _near(_pixel(cut, at, other, H - 58), _pixel(broll, at, other, H - 58))


def test_the_sound_is_the_narration_never_the_hosts():
    args = host_layer.command("cut.mp4", ["a.mp4", "b.mp4"], [(0, "left")], (720, 1280))
    assert args[args.index("[v]") + 2] == "0:a?"  # the cut's own sound
    args = host_layer.command("cut.mp4", ["a.mp4"], [(0, "left")], (720, 1280),
                              key="#0047BB", narration="voice.mp3")  # fmt: skip
    assert args[args.index("[v]") + 2] == "2:a"
    graph = args[args.index("-filter_complex") + 1]
    assert "chromakey=0x0047BB" in graph and "despill=type=blue" in graph
    assert "scale=-2:576" in graph  # 45 % of the frame's height


@pytest.mark.parametrize("sides", [[], [(1, "left")], [(0, "up")], [(0, "left"), (0, "right")]])
def test_sides_start_at_zero_and_go_in_order(sides):
    with pytest.raises(ValueError):
        host_layer.command("cut.mp4", ["a.mp4"], sides, (720, 1280))
