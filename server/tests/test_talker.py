"""The UGC talker (Reed, 3 Nov: "Heygen for still imaged UGC talking, yes."): a MiniMax voice
in a room, one HeyGen Avatar IV take of it from one still, and the cut alternating the talker
and B-roll cut-ins. Stand-ins and a mocked HeyGen only: no paid calls."""

import base64
import json
import re
import subprocess
from pathlib import Path

import httpx2 as httpx
import pytest

from app import host, narration, prompts, room, talker
from app.catalogue import get_model
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.freestyles import Freestyle
from app.models.jobs import Job
from app.models.projects import Project
from app.models.songs import SongTake
from app.providers import NoKey, NotStarted
from app.providers.heygen import HeyGenProvider
from tests.conftest import first_brand
from tests.test_freestyle_dialogue import _run

LINES = ("Every morning starts the same.\nThe bowl, the wait, the wag.\nIron Paws makes the bowl "
         "worth waiting for.")  # fmt: skip


@pytest.fixture(autouse=True)
def songs_on(monkeypatch):
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)


def _steps(db, video, step):
    return [j for j in db.query(Job).filter(Job.project_id == video.id).order_by(Job.id)
            if j.input.get("step") == step]  # fmt: skip


def test_a_ugc_presenter_talks_on_heygen_in_one_take_cut_between_b_roll(app, db, owner):
    body = {"type": "presenter", "look": "ugc", "shape": "9:16", "text": LINES,
            "brand_id": first_brand(owner)}  # fmt: skip
    fs = owner.post("/freestyles", json=body).json()
    _run(app, db, ticks=200)
    out = owner.get(f"/freestyles/{fs['id']}").json()
    assert out["status"] == "delivered", [t["text"] for t in out["thread"]][-4:]
    video = db.get(Project, db.get(Freestyle, fs["id"]).project_id,
                   execution_options={"see_hidden": True})  # fmt: skip
    (voice,) = [j for j in _steps(db, video, "song_take") if j.kind == "speech"]
    assert (voice.input["model"], voice.input["input"]["voice_id"]) == (
        narration.MINIMAX, talker.VOICE)  # a MiniMax voice by default  # fmt: skip
    (timing,) = db.query(Job).filter(Job.kind == "narration_timing").all()
    assert timing.input["room"] is True  # in a room
    (still,) = _steps(db, video, host.STILL)
    assert "own real, lived-in room" in still.input["input"]["prompt"]
    assert "green" not in still.input["input"]["prompt"]
    (piece,) = _steps(db, video, host.PIECE)  # ONE take, the whole narration
    (row,) = host.rows(db, video)[1:]
    assert (piece.provider, piece.input["model"], row.start) == ("heygen", talker.MODEL, 0.0)
    assert row.end == pytest.approx(db.get(SongTake, video.song_take_id).seconds)
    sent = piece.input["input"]
    assert (sent["expressiveness"], sent["resolution"]) == ("medium", "720p")
    assert piece.input["files"] == {"image": [host.rows(db, video)[0].file_id],
                                    "audio": [row.audio_file_id]}  # fmt: skip
    assert piece.credits == sent["duration"] * get_model(talker.MODEL).credits_per_unit("720p")
    said = talker.clips(db, video)
    rows = {r.clip_id: r for r in db.query(ProjectClip).filter_by(project_id=video.id)}
    assert said and set(rows) - said  # the cut alternates talker and B-roll
    takes = {j.input["project_clip_id"] for j in _steps(db, video, "clip_take")}
    assert not takes & {rows[c].id for c in said}  # no paid take of a talker clip
    for c in said:  # each cut from the talker's take, free
        assert db.get(ClipTake, rows[c].picked_take_id).job_id == piece.id
    final = db.query(FinalVideo).filter_by(project_id=video.id).order_by(FinalVideo.id).all()[-1]
    assert len(final.take_ids) == len(rows)
    director = prompts.system("director")
    assert "never more than about 6 s without a swap" in director  # the director's B-roll swaps


def test_a_minimax_reading_keeps_the_words_and_its_pauses_survive_the_trim(tmp_path):
    words = "Your dog's gut is a mess. Iron Paws fixes it."
    marked = "Your dog's gut is a mess. <#0.4#> (breath) Iron Paws fixes it."
    made = narration.job(words, "English_ConfidentWoman", emotion="calm", reading=marked)
    assert made["model"] == narration.MINIMAX and made["input"]["text"] == marked
    assert (made["input"]["emotion"], made["input"]["speed"]) == ("calm", 1.1)
    assert narration.kept_pause(made) == 0.4  # the trim keeps the marked pause
    for wrong in ("Your cat's gut is a mess. <#0.4#> Iron Paws fixes it.",
                  "Your dog's gut is a mess. <#0.4#><#0.3#> Iron Paws fixes it."):  # fmt: skip
        with pytest.raises(ValueError, match="words exactly"):
            narration.job(words, "English_ConfidentWoman", reading=wrong)
    with pytest.raises(ValueError, match="no note"):
        narration.job(words, "English_ConfidentWoman", note="slower and warmer")
    recorded = json.loads(
        (Path(__file__).parent / "fixtures/replicate/minimax_speech-2.8-hd.json").read_text()
    )
    assert set(narration.EMOTIONS) == set(recorded["enums"]["emotion"]["enum"])
    gap = _tone(tmp_path / "gap.mp3", "between(t,0,1)+between(t,2,3)", 3)  # a 1 s silence
    kept = narration.trim(gap, tmp_path / "kept.mp3", 0.5)  # a marked 0.5 s pause stays 0.5
    assert _length(kept) > _length(narration.trim(gap, tmp_path / "cut.mp3")) + 0.15


def _ff(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True).stderr  # noqa: S603


def _tone(path: Path, when: str, seconds: int) -> Path:
    _ff("ffmpeg", "-v", "error", "-f", "lavfi", "-i",
        f"aevalsrc='0.3*sin(2*PI*180*t)*({when})':d={seconds}", str(path))  # fmt: skip
    return path


def _length(path: Path) -> float:
    probe = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0"]
    return float(subprocess.run([*probe, str(path)], capture_output=True, text=True).stdout)  # noqa: S603


def test_the_room_keeps_the_voices_length_fills_its_gaps_and_sets_its_loudness(tmp_path):
    dry = _tone(tmp_path / "dry.mp3", "between(t,0,1.5)+between(t,2,3.5)", 4)  # dead gaps
    wet = room.finish(dry, tmp_path / "wet.mp3")
    assert abs(_length(wet) - _length(dry)) < 0.06
    gaps = _ff("ffmpeg", "-i", str(wet), "-af", "silencedetect=n=-70dB:d=0.2", "-f", "null", "-")
    assert "silence_start" not in gaps  # room tone under every gap
    loud = _ff("ffmpeg", "-i", str(wet), "-af", "ebur128", "-f", "null", "-")
    assert abs(float(re.findall(r"I:\s+(-?[\d.]+) LUFS", loud)[-1]) - room.LUFS) < 1.5


PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nstill").decode()
MP3 = base64.b64encode(b"ID3voice").decode()
JOB = {"model": talker.MODEL, "input": {
    "image": f"data:image/png;base64,{PNG}", "audio": f"data:audio/mpeg;base64,{MP3}",
    "aspect_ratio": "9:16", "resolution": "720p", "expressiveness": "medium",
    "motion_prompt": talker.MOTION, "title": "t", "duration": 25}}  # fmt: skip


def test_heygen_uploads_the_voice_animates_the_still_and_prices_the_seconds():
    seen, states = [], iter(["processing", "completed"])

    def api(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/v3/assets":
            return httpx.Response(200, json={"data": {"asset_id": "a1"}})
        if request.url.path == "/v3/videos":
            return httpx.Response(200, json={"data": {"video_id": "v1", "status": "waiting"}})
        if request.url.path == "/v3/videos/v1":
            return httpx.Response(200, json={"data": {
                "id": "v1", "status": next(states), "duration": 25.07,
                "video_url": "https://files2.heygen.ai/v1.mp4?Signature=x"}})  # fmt: skip
        return httpx.Response(200, content=b"\0\0\0\x18ftypmp42")  # the file host

    client = httpx.Client(transport=httpx.MockTransport(api))
    heygen = HeyGenProvider("https://api.heygen.com", "test-key", client)
    assert heygen.submit("video", JOB) == "v1"
    upload, create = seen
    assert b'filename="voice.mp3"' in upload.content and b"ID3voice" in upload.content
    body = json.loads(create.content)
    assert body == {"type": "image", "audio_asset_id": "a1",
                    "image": {"type": "base64", "media_type": "image/png", "data": PNG},
                    "aspect_ratio": "9:16", "resolution": "720p", "expressiveness": "medium",
                    "motion_prompt": talker.MOTION, "title": "t"}  # fmt: skip
    assert heygen.poll("v1").state == "running"
    done = heygen.poll("v1")
    assert done.files == ["https://files2.heygen.ai/v1.mp4?Signature=x"]
    assert float(done.usage[0].cost_usd) == pytest.approx(25.07 * 0.039)
    data, kind = heygen.fetch(done.files[0])
    assert kind == "video/mp4" and "x-api-key" not in seen[-1].headers  # the key: API only
    assert all(r.headers["x-api-key"] == "test-key" for r in seen[:-1])
    with pytest.raises(RuntimeError, match="Refusing"):
        heygen.fetch("https://example.com/v1.mp4")
    busy = HeyGenProvider("https://api.heygen.com", "k", httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(429))))  # fmt: skip
    with pytest.raises(NotStarted):
        busy.submit("video", JOB)
    with pytest.raises(NoKey):
        HeyGenProvider("https://api.heygen.com", "", client).submit("video", JOB)
