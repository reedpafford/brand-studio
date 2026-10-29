"""Song ads, the final cut (flows V6): each picked take cut to its piece of the song, the
song the only sound, the end faded. Free, on the stand-ins (no paid calls)."""

import json
import subprocess

from sqlalchemy import select

from app import clip_takes
from app.models.clips import ProjectClip
from tests.test_song_takes import _video, _work, song  # noqa: F401 - fixture


def _probe(data: bytes, tmp_path) -> dict:
    path = tmp_path / "out.mp4"
    path.write_bytes(data)
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",  # noqa: S603, S607
                          "format=duration:stream=codec_type", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout  # fmt: skip
    info = json.loads(out)
    return {"seconds": float(info["format"]["duration"]),
            "streams": sorted(s["codec_type"] for s in info["streams"])}  # fmt: skip


def _clip(seconds: float, tmp_path) -> bytes:
    path = tmp_path / f"clip{seconds}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",  # noqa: S603, S607
                    f"testsrc=s=160x284:d={seconds}:r=10", "-f", "lavfi", "-i",
                    f"sine=d={seconds}", "-pix_fmt", "yuv420p", "-shortest", str(path)],
                   check=True)  # fmt: skip
    return path.read_bytes()


def _song(seconds: float, tmp_path) -> bytes:
    path = tmp_path / "song.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",  # noqa: S603, S607
                    f"sine=f=440:d={seconds}", str(path)], check=True)  # fmt: skip
    return path.read_bytes()


def test_each_take_is_cut_to_its_slice_and_a_short_one_holds(tmp_path):
    long, short = _clip(4, tmp_path), _clip(1, tmp_path)
    data = clip_takes.song_cut([long, short], [2.5, 3.0], _song(8, tmp_path))
    got = _probe(data, tmp_path)
    assert abs(got["seconds"] - 5.5) < 0.2  # 2.5 s cut + 1 s held to 3 s; never the song's 8
    assert got["streams"] == ["audio", "video"]


def _clips_made(app, db, editor, video):
    editor.post(f"{video}/clips/prompts")
    _work(app, db)
    for c in editor.get(f"{video}/clips").json():
        assert editor.post(f"{video}/clips/{c['id']}/generate").status_code == 201
    _work(app, db)
    for c in editor.get(f"{video}/clips").json():
        editor.post(f"{video}/clips/{c['id']}/prompt-ok")
        r = editor.post(f"{video}/clips/{c['id']}/approve")
        assert r.status_code == 200, r.text


def test_a_song_video_is_cut_to_the_song(app, db, owner, editor, song, tmp_path):  # noqa: F811
    video = _video(app, db, owner, editor, song)
    _clips_made(app, db, editor, video)
    rows = db.scalars(select(ProjectClip).order_by(ProjectClip.id)).all()
    assert all(r.song_slice for r in rows)
    assert rows[0].song_slice["start"] == 0
    songs = editor.get(f"{video}/songs").json()
    made = editor.post(f"{video}/video")
    assert made.status_code == 201, made.text
    assert made.json()["song_take_id"] == songs["song_take_id"] and not made.json()["out_of_date"]
    got = _probe(editor.get(f"/files/{made.json()['file_id']}").content, tmp_path)
    end = max(r.song_slice["end"] for r in rows)
    assert abs(got["seconds"] - end) < 0.3 and got["streams"] == ["audio", "video"]
    other = songs["takes"][1]["id"]
    editor.put(f"{video}/song", json={"take_id": other})  # a new song: make it again
    assert editor.get(f"{video}/video").json()["out_of_date"] is True
