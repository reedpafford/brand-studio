"""Reel import, the free part: upload or link, then `reel_prepare` (probe, caps, cuts, contact
sheet, transcript) on the local provider. Real ffmpeg; stand-in transcription and fetch."""

import subprocess
from pathlib import Path

import pytest
from PIL import Image

from app import reel
from app.models.files import StoredFile
from app.models.jobs import Job
from app.providers.fake_local import refuse_link, transcript
from app.providers.local import LocalProvider
from app.worker import run_once


def _clip(path: Path, *, sound: bool = True) -> Path:
    """3 s of testsrc, then 3 s of smptebars: one cut at 3 s."""
    scenes = ["-f", "lavfi", "-i", "testsrc=s=160x284:d=3:r=10"]
    scenes += ["-f", "lavfi", "-i", "smptebars=s=160x284:d=3:r=10"]
    audio = ["-f", "lavfi", "-i", "sine=d=6"] if sound else []
    joined = "[0:v][1:v]concat=n=2:v=1[v]"
    args = ["ffmpeg", "-v", "error", *scenes, *audio, "-filter_complex", joined, "-map", "[v]"]
    args += ["-map", "2:a", "-shortest"] if sound else []
    subprocess.run([*args, "-pix_fmt", "yuv420p", "-y", str(path)], check=True)  # noqa: S603
    return path


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


def test_wrong_file_type_and_deleting_the_script_removes_its_files(app, owner, db, clip):
    brand = owner.get("/brands").json()[0]["id"]
    files = {"file": ("a.png", b"\x89PNG\r\n\x1a\n", "image/png")}
    wrong = owner.post("/scripts/import/upload", data={"brand_id": brand}, files=files)
    assert wrong.status_code == 415
    sid = _upload(owner, clip).json()["script_id"]
    _work(app, db)
    assert owner.delete(f"/scripts/{sid}").status_code == 204
    db.expire_all()
    assert db.query(StoredFile).count() == 0


@pytest.mark.whisper
def test_the_real_speech_model_runs(clip):  # opt in: uv run pytest -m whisper
    lines = reel.transcribe(clip)
    assert isinstance(lines, list) and all({"start", "end", "text"} <= set(x) for x in lines)
