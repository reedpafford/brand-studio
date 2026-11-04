"""Song ads, the final cut (flows V6): each picked take cut to its piece of the song, the
song the only sound, the end faded. Free, on the stand-ins (no paid calls)."""

import json
import subprocess

from sqlalchemy import select

from app import clip_takes
from app.models.clips import ProjectClip
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.models.songs import SongTake
from app.routes.project_clips import SONG_CHANGED
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
    from app.routes.project_clips import song_end

    take = db.get(SongTake, songs["song_take_id"])
    end = min(max(r.song_slice["end"] for r in rows), song_end(take))  # a breath after the
    assert abs(got["seconds"] - end) < 0.3 and got["streams"] == ["audio", "video"]  # last line
    other = songs["takes"][1]["id"]
    editor.put(f"{video}/song", json={"take_id": other})  # a new song: make it again
    assert editor.get(f"{video}/video").json()["out_of_date"] is True


def test_after_a_song_change_the_old_clips_are_never_cut_to_it(app, db, owner, editor, song):  # noqa: F811
    video = _video(app, db, owner, editor, song)
    _clips_made(app, db, editor, video)
    project = db.get(Project, int(video.rsplit("/", 1)[1]))
    draft = db.get(ScriptDraft, project.script_draft_id)
    draft.style_line = "pop fake:long=40"  # a longer take, standing in for another take
    db.commit()
    editor.post(f"{video}/songs", json={})
    _work(app, db)
    draft.style_line = "pop"
    longer = db.query(SongTake).order_by(SongTake.id.desc()).first()
    longer.style_line = "pop"
    db.commit()
    assert editor.put(f"{video}/song", json={"take_id": longer.id}).status_code == 200
    made = editor.post(f"{video}/video")
    count = len(editor.get(f"{video}/clips").json())
    assert (made.status_code, made.json()["detail"]) == (409, SONG_CHANGED.format(count))


def test_a_song_video_ends_a_breath_after_its_last_line():
    """Song-Producer: the cut ends about 1 s after the last sung line, then fades."""
    from app.clip_takes import ends_at

    assert ends_at([5, 5, 5], 11.0) == [5, 5, 1.0]  # the third clip shortened to the end
    assert ends_at([5, 5, 5], 9.5) == [5, 4.5]  # a clip wholly after it drops
    assert ends_at([5, 5], 30.0) == [5, 5] and ends_at([5, 5], None) == [5, 5]


def test_a_short_take_is_slowed_to_fill_its_piece_never_sped_up(tmp_path):
    import subprocess

    from app.clip_takes import _length, song_cut

    def clip(name, seconds):
        path = tmp_path / name
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",  # noqa: S603, S607
                        f"testsrc=s=64x64:r=24:d={seconds}", "-c:v", "libx264", str(path)],
                       check=True)  # fmt: skip
        return path.read_bytes()

    track = tmp_path / "song.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",  # noqa: S603, S607
                    "sine=frequency=440:duration=8", str(track)], check=True)  # fmt: skip
    out = song_cut([clip("a.mp4", 2), clip("b.mp4", 6)], [4.0, 3.0], track.read_bytes())
    (tmp_path / "out.mp4").write_bytes(out)
    assert abs(_length(tmp_path, "out.mp4") - 7.0) < 0.2  # the 2 s take filled its 4 s
