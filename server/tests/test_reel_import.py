"""Reel import, the free part: upload or link, then `reel_prepare` (probe, caps, cuts, contact
sheet, transcript) on the local provider. Real ffmpeg; stand-in transcription and fetch."""

import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from app import reel
from app.models.accounts import User
from app.models.files import StoredFile
from app.models.jobs import Job
from app.providers.fake_local import refuse_link, transcript
from app.providers.fake_local import two_scenes as _clip
from app.providers.local import LocalProvider
from app.routes.jobs import enqueue
from app.worker import run_once


@pytest.fixture(scope="module")
def clip(tmp_path_factory) -> Path:
    return _clip(tmp_path_factory.mktemp("reel") / "two.mp4")


def _work(app, db) -> LocalProvider:
    local = LocalProvider(app.state.storage, transcribe=transcript, fetch_link=refuse_link)
    run_once(db, {"local": local}, app.state.storage, allow_paid=False)  # free: runs with it off
    return local


def _upload(client, clip: Path, url="/scripts/import/upload", **form):
    brand = client.get("/brands").json()[0]["id"]
    with clip.open("rb") as f:
        files = {"file": ("reel.mp4", f, "video/mp4")}
        return client.post(url, data={"brand_id": brand, **form}, files=files)


def test_cuts_stats_and_contact_sheet(clip, tmp_path):
    seconds = reel.probe(clip)
    cuts = reel.cuts(clip)
    assert seconds == pytest.approx(6, abs=0.2) and cuts == [pytest.approx(3, abs=0.2)]
    assert reel.stats(cuts, seconds)["shots"] == 2
    sheet = Image.open(reel.contact_sheet(clip, cuts, seconds, tmp_path))
    assert sheet.width == 2 * 180  # two tiles, one a shot


def test_caps_refuse_in_plain_words(clip, tmp_path, monkeypatch):
    with pytest.raises(reel.Refused) as no:
        reel.probe(_clip(tmp_path / "mute.mp4", sound=False))
    assert "no sound" in no.value.message and no.value.code == "bad_file"
    monkeypatch.setattr(reel, "MAX_SECONDS", 5)
    with pytest.raises(reel.Refused) as no:
        reel.probe(clip)
    assert no.value.code == "too_long" and "6 seconds long" in no.value.message
    (tmp_path / "x.mp4").write_bytes(b"\0\0\0\x18ftypmp42" + b"0" * 64)
    with pytest.raises(reel.Refused, match="isn't a video"):
        reel.probe(tmp_path / "x.mp4")


def test_only_instagram_reel_links():
    assert reel.reel_link("https://instagram.com/reels/DehudnaAmce?igsh=x") == (
        "https://www.instagram.com/reel/DehudnaAmce/"
    )
    assert reel.reel_link("https://www.instagram.com/p/DehudnaAmce/")
    for bad in ("https://evil.com/reel/DehudnaAmce/", "http://instagram.com/reel/abcdef/", "x"):
        assert reel.reel_link(bad) is None


def test_upload_prepares_the_reel_for_free(app, editor, db, clip):
    made = _upload(editor, clip, new_lines="true")
    assert made.status_code == 201, made.text
    assert made.json()["status"] == "preparing"
    sid = made.json()["script_id"]
    script = editor.get(f"/scripts/{sid}").json()
    assert (script["title"], script["new_lines"]) == ("Untitled reel", True)
    job = db.query(Job).one()
    assert (job.provider, float(job.credits), job.brand_id) == ("local", 0, script["brand_id"])
    local = _work(app, db)
    ready = editor.get(f"/scripts/{sid}/import").json()
    assert (ready["status"], ready["shots"], len(ready["transcript"])) == ("ready", 2, 2)
    sheet = editor.get(f"/files/{ready['contact_file_id']}")
    assert sheet.headers["content-type"] == "image/jpeg"
    assert editor.get(f"/files/{ready['video_file_id']}").status_code == 200
    assert not any(local.root.iterdir())  # its working files are gone


def test_a_refused_link_says_upload_instead_and_an_upload_fixes_it(app, owner, db, clip):
    brand = owner.get("/brands").json()[0]["id"]
    bad = owner.post("/scripts/import/link", json={"brand_id": brand, "url": "https://x.com/a"})
    assert bad.status_code == 422 and bad.json()["detail"] == "That isn't an Instagram reel link."
    link = {"brand_id": brand, "url": "https://www.instagram.com/reel/DehudnaAmce/"}
    sid = owner.post("/scripts/import/link", json=link).json()["script_id"]
    _work(app, db)
    failed = owner.get(f"/scripts/{sid}/import").json()
    assert (failed["status"], failed["problem_code"]) == ("failed", "blocked")
    assert failed["problem"].endswith("Upload the video instead.")
    again = _upload(owner, clip, url=f"/scripts/{sid}/import/upload")
    assert again.status_code == 200 and again.json()["status"] == "preparing"
    assert _upload(owner, clip, url=f"/scripts/{sid}/import/upload").status_code == 409
    _work(app, db)
    ready = owner.get(f"/scripts/{sid}/import").json()
    assert ready["status"] == "ready" and ready["problem"] == ""
    assert ready["url"] == link["url"]


def test_wrong_file_type_and_a_deleted_reel_keeps_its_files_to_restore(app, owner, db, clip):
    brand = owner.get("/brands").json()[0]["id"]
    files = {"file": ("a.png", b"\x89PNG\r\n\x1a\n", "image/png")}
    wrong = owner.post("/scripts/import/upload", data={"brand_id": brand}, files=files)
    assert wrong.status_code == 415
    sid = _upload(owner, clip).json()["script_id"]
    _work(app, db)
    assert owner.delete(f"/scripts/{sid}").status_code == 204  # undoable: nothing removed
    assert owner.post(f"/scripts/{sid}/restore").status_code == 200
    assert owner.get(f"/scripts/{sid}/import").json()["status"] == "ready"


@pytest.mark.whisper
def test_the_real_speech_model_runs(clip):  # opt in: uv run pytest -m whisper
    reel.warm()  # what the reel worker does at start
    lines = reel.transcribe(clip)
    assert isinstance(lines, list) and all({"start", "end", "text"} <= set(x) for x in lines)


def test_one_reel_prepared_at_a_time_per_person(owner, editor, clip):
    assert _upload(editor, clip).status_code == 201
    again = _upload(editor, clip)
    assert again.status_code == 409 and "being prepared" in again.json()["detail"]
    assert _upload(owner, clip).status_code == 201  # someone else's is fine


def test_replaced_and_unreadable_uploads_leave_no_files(app, owner, db, clip, tmp_path):
    sid = _upload(owner, clip).json()["script_id"]
    _work(app, db)
    old = owner.get(f"/scripts/{sid}/import").json()
    assert _upload(owner, clip, url=f"/scripts/{sid}/import/upload").status_code == 200
    db.expire_all()
    assert db.get(StoredFile, old["video_file_id"]) is None
    assert db.get(StoredFile, old["contact_file_id"]) is None
    _work(app, db)
    mute = _clip(tmp_path / "mute.mp4", sound=False)
    bad = _upload(owner, mute).json()["script_id"]
    _work(app, db)
    assert owner.get(f"/scripts/{bad}/import").json()["video_file_id"] is None
    db.expire_all()
    assert db.query(StoredFile).count() == 3  # only the replacement's video, sheet, watch copy
    assert len([p for p in Path(app.state.settings.storage_dir).rglob("*") if p.is_file()]) == 3


def test_a_worker_can_take_only_some_providers(app, owner, db, clip):
    _upload(owner, clip)
    user = db.get(User, 1)
    other = enqueue(db, user, "image", {"input": {}}, provider="fake")
    local = LocalProvider(app.state.storage, transcribe=transcript, fetch_link=refuse_link)
    run_once(db, {"local": local}, app.state.storage, only={"local"})
    db.expire_all()
    assert db.get(Job, other.id).status == "queued"  # left for the other worker, not failed
    assert db.query(Job).filter(Job.provider == "local").one().status == "succeeded"


def test_a_refused_replacement_keeps_the_old_reel_whole(app, owner, db, clip):
    """QA on #288: a replacement that's refused (415) leaves the old video's row and bytes."""
    sid = _upload(owner, clip).json()["script_id"]
    _work(app, db)
    old = owner.get(f"/scripts/{sid}/import").json()
    files = {"file": ("notes.txt", b"not a video", "text/plain")}
    refused = owner.post(f"/scripts/{sid}/import/upload", files=files)
    assert refused.status_code == 415
    assert owner.get(f"/files/{old['video_file_id']}").content == clip.read_bytes()
    assert owner.get(f"/scripts/{sid}/import").json()["status"] == "ready"


def test_the_deployed_workers_cover_every_provider():
    """Release on #288: the workers' lists are allowlists, so a new provider must be in one."""
    import json
    import re

    from app.providers import get_providers
    from app.settings import REPO_ROOT, Settings

    compose = (REPO_ROOT / "deploy/docker-compose.yml").read_text()
    lists = re.findall(r"BS_WORKER_PROVIDERS: '(\[.*?\])'", compose)
    covered = {name for found in lists for name in json.loads(found)}
    assert covered == set(get_providers(Settings()))


def test_gemini_gets_a_small_watch_copy(app, owner, db, clip, tmp_path):
    """Gemini's Replicate file URLs fail on and off (E001); a data: URL works, so prep makes
    a small H.264 copy that fits one and keeps the original for everything else."""
    budget = sum(reel.WATCH_KBPS) * 1000 / 8 * reel.MAX_SECONDS  # bytes at the cap, 90 s
    assert budget < 3_000_000
    copy = reel.watch_copy(clip, tmp_path)
    probe = ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name", "-of", "csv=p=0"]
    streams = subprocess.run([*probe, str(copy)], capture_output=True, text=True).stdout.split()  # noqa: S603
    assert "h264" in streams[0] and "aac" in streams[1]
    sid = _upload(owner, clip).json()["script_id"]
    _work(app, db)
    ready = owner.get(f"/scripts/{sid}/import").json()
    from app.models.script_library import Script
    from app.reel_read import watch_input

    watch_id = db.get(Script, sid).reel["watch_file_id"]
    assert watch_id not in (None, ready["video_file_id"])
    sent = watch_input(db.get(Script, sid))
    assert sent["files"]["videos"] == [watch_id] and "uploads" not in sent  # a data: URL


def test_a_reel_a_little_over_the_limit_still_counts(clip, monkeypatch):
    """A "90 s" file often measures 90.02 s (audio padding): half a second of slack."""
    monkeypatch.setattr(reel, "MAX_SECONDS", 5.7)  # the clip measures about 6.0 s
    assert reel.probe(clip) == pytest.approx(6, abs=0.2)


def test_transcription_keeps_lines_spoken_over_music(monkeypatch, capsys):
    """The altar reel has music under every line; with VAD on, 6 of 11 lines were lost."""
    import sys
    import types

    from app import whisper

    asked = {}

    class Model:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, path, **kwargs):
            asked.update(kwargs)
            said = dict(no_speech_prob=0.1, avg_logprob=-0.3)
            invented = dict(no_speech_prob=0.9, avg_logprob=-1.4)  # over the music bed
            unsure = dict(no_speech_prob=0.7, avg_logprob=-0.4)  # quiet but confident: kept
            return [
                types.SimpleNamespace(start=0.0, end=0.5, text=" I do.", **said),
                types.SimpleNamespace(start=1.0, end=3.0, text=" Thanks for watching!", **invented),
                types.SimpleNamespace(start=3.0, end=3.4, text=" Huh?!", **unsure),
            ], None

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=Model))
    whisper.main("reel.mp4")
    said = [x["text"] for x in json.loads(capsys.readouterr().out)]
    assert asked["vad_filter"] is False and said == ["I do.", "Huh?!"]  # the invented one dropped
