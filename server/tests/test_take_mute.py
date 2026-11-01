"""Mute a span of a take in the final cut: free (ffmpeg), the take and its approval untouched."""

import re
import subprocess
import tempfile
from pathlib import Path

import pytest

from app import take_mute
from app.models.clips import ClipTake, ProjectClip
from app.models.projects import Project
from app.take_words import compare
from tests.test_clip_takes import FakeSeedance, _mp4, _work, clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture


def test_stretches_are_kept_as_added_inside_the_take_and_joined_only_in_the_cut():
    take = ClipTake(made_with={})
    take_mute.add(take, 1.0, 2.0, longest=8)
    take_mute.add(take, 1.5, 3.0, longest=8)  # overlaps: kept as its own, for Undo
    take_mute.add(take, -1, 0.5, longest=8)  # before the start: from 0
    assert take_mute.add(take, 7.5, 12, longest=8) == [[1.0, 2.0], [1.5, 3.0], [0.0, 0.5],
                                                       [7.5, 8]]  # fmt: skip
    clip_row = ProjectClip(clip_id="c2")
    assert take_mute.labels(clip_row, take) == ["c2/mute:0.0-0.5", "c2/mute:1.0-3.0",
                                                "c2/mute:7.5-8"]  # fmt: skip
    with pytest.raises(ValueError, match="Pick a stretch"):
        take_mute.add(take, 9, 10, longest=8)  # past the end: nothing left
    with pytest.raises(ValueError, match="Pick a stretch"):
        take_mute.add(take, 0.5, float("nan"), longest=8)
    assert take_mute.remove(take, 1) == [[1.0, 2.0], [0.0, 0.5], [7.5, 8]]  # Undo: just that one
    for i in range(5):
        take_mute.add(take, 3.5 + i * 0.7, 3.7 + i * 0.7, longest=8)
    with pytest.raises(ValueError, match="8 muted stretches at most"):
        take_mute.add(take, 6.9, 7.1, longest=8)


def _loudness(video: bytes, start: float, seconds: float) -> float:
    """The loudest sample's level, in dB, over start–start+seconds."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "v.mp4"
        path.write_bytes(video)
        args = ["-ss", str(start), "-t", str(seconds), "-i", str(path), "-af", "volumedetect",
                "-f", "null", "-"]  # fmt: skip
        out = subprocess.run(["ffmpeg", *args], capture_output=True, text=True, check=True)  # noqa: S603, S607
    out = out.stderr
    found = re.search(r"max_volume: (-?[\d.]+|-inf) dB", out)
    return float("-inf") if found[1] == "-inf" else float(found[1])


def test_the_take_is_silent_over_the_span_and_heard_elsewhere():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "tone.mp4"
        args = ["-v", "error", "-f", "lavfi", "-i", "color=c=red:s=64x64:d=3", "-f", "lavfi",
                "-i", "sine=frequency=440:duration=3", "-shortest", "-c:v", "libx264", "-c:a",
                "aac", str(path)]  # fmt: skip
        subprocess.run(["ffmpeg", *args], check=True)  # noqa: S603, S607
        video = path.read_bytes()
    muted = take_mute.apply(video, [[1.0, 2.0]])
    assert _loudness(muted, 1.2, 0.6) < -60  # silent over the span
    assert _loudness(muted, 0.1, 0.6) > -30 and _loudness(muted, 2.3, 0.5) > -30  # heard around
    assert take_mute.apply(video, []) is video  # nothing to mute: the take as it is


def test_an_unscripted_line_offers_its_stretch_to_mute():
    lines = [{"who": "MIA", "text": "Fomo made me rich!"}]
    heard = [{"start": 0.5, "end": 1.8, "text": "Fomo made me rich!"},
             {"start": 2.5, "end": 3.8, "text": "Let's go home."}]  # fmt: skip
    (extra,) = compare(lines, heard, "fomo", "FOH-moh", ["Mia waves."])
    assert extra["span"] == [2.5, 3.8]


def test_mute_and_undo_from_the_clip_keep_its_approval(app, db, editor, setup, clip):  # noqa: F811
    clips = f"/projects/{setup['project']}/clips"
    assert editor.post(f"{clips}/{clip['id']}/mute", json={"start": 1, "end": 2}).status_code == 409
    editor.post(f"{clips}/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    editor.post(f"{clips}/{clip['id']}/approve")
    shown = editor.post(f"{clips}/{clip['id']}/mute", json={"start": 1.0, "end": 2.0}).json()
    assert shown["takes"][0]["mutes"] == [[1.0, 2.0]] and shown["approved"] is True
    bad = editor.post(f"{clips}/{clip['id']}/mute", json={"start": 99, "end": 100})
    assert bad.status_code == 422  # past the clip's end
    nan = editor.post(f"{clips}/{clip['id']}/mute", content='{"start": 0.5, "end": NaN}',
                      headers={"content-type": "application/json"})  # fmt: skip
    assert nan.status_code == 422
    back = editor.delete(f"{clips}/{clip['id']}/mute/0").json()
    assert back["takes"][0]["mutes"] == []
    assert editor.delete(f"{clips}/{clip['id']}/mute/0").status_code == 404
    db.get(Project, setup["project"]).archived_at = db.get(ProjectClip, clip["id"]).created_at
    db.commit()
    archived = editor.post(f"{clips}/{clip['id']}/mute", json={"start": 1, "end": 2})
    assert archived.status_code == 409
