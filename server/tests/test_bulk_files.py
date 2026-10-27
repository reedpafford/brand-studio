"""Bulk create with video files (reel-import.md §8): uploads stored and checked for free, then
made into drafts with links in one ordered, all-or-none batch. Real ffmpeg on generated clips."""

from datetime import timedelta
from pathlib import Path

import pytest

from app import reel
from app.db import utcnow
from app.models.files import StoredFile, VideoUpload
from app.models.jobs import Job
from app.models.script_library import Script
from app.providers.fake_local import two_scenes
from app.purge import purge_uploads

LINK = "https://www.instagram.com/reel/Bulk1abc/"


@pytest.fixture(scope="module")
def clip(tmp_path_factory) -> Path:
    return two_scenes(tmp_path_factory.mktemp("reel") / "two.mp4")


def _send(client, clip: Path, name="bo-tries-salmon.mp4"):
    brand = client.get("/brands").json()[0]["id"]
    with clip.open("rb") as f:
        files = {"file": (name, f, "video/mp4")}
        return client.post("/uploads/video", data={"brand_id": brand}, files=files)


def _bulk(client, rows: list[dict]):
    brand = client.get("/brands").json()[0]["id"]
    return client.post("/scripts/bulk", json={"scripts": [{"brand_id": brand, **r} for r in rows]})


def test_an_upload_is_checked_and_kept_for_free_and_remove_drops_it(owner, editor, db, clip):
    sent = _send(owner, clip)
    assert sent.status_code == 201, sent.text
    got = sent.json()
    assert got["upload_id"] and got["file_name"] == "bo-tries-salmon.mp4" and got["problem"] == ""
    assert 0 < got["seconds"] <= 90 and got["size"] == clip.stat().st_size
    assert db.query(Job).count() == 0  # nothing is read
    url = f"/uploads/{got['upload_id']}"
    assert editor.delete(url).status_code == 404  # only its own person removes it
    assert owner.delete(url).status_code == 204
    assert owner.delete(url).status_code == 404
    assert db.query(VideoUpload).count() == 0 and db.query(StoredFile).count() == 0


def test_a_video_too_long_or_without_sound_is_refused_on_its_row(
    owner, db, clip, tmp_path, monkeypatch
):  # noqa: E501
    files = db.query(StoredFile).count()
    mute = _send(owner, two_scenes(tmp_path / "mute.mp4", sound=False)).json()
    assert (mute["upload_id"], mute["problem_code"]) == (None, "bad_file") and mute["problem"]
    monkeypatch.setattr(reel, "MAX_SECONDS", 1)
    long = _send(owner, clip).json()
    assert (long["upload_id"], long["problem_code"]) == (None, "too_long")
    assert db.query(StoredFile).count() == files  # nothing kept


def test_links_and_videos_become_drafts_in_the_order_given(owner, db, clip):
    video = _send(owner, clip).json()
    made = _bulk(owner, [{"reel_url": LINK}, {"upload_id": video["upload_id"]}, {"title": "Plain"}])
    assert made.status_code == 201, made.text
    reels = [s["reel"] for s in made.json()]
    assert [r and r["source"] for r in reels] == ["link", "file", None]
    assert (
        reels[1]["file_name"] == "bo-tries-salmon.mp4" and reels[1]["seconds"] == video["seconds"]
    )
    assert reels[0]["url"] == LINK and reels[1]["url"] is None
    jobs = db.query(Job).filter(Job.kind == "reel_prepare").order_by(Job.id).all()
    assert [("url" in j.input, "video_key" in j.input) for j in jobs] == [
        (True, False),
        (False, True),
    ]
    assert db.get(VideoUpload, video["upload_id"]).used is True

    estimate = owner.post(
        "/scripts/write/estimate", json={"script_ids": [s["id"] for s in made.json()]}
    )
    assert estimate.json()["reels"] == {"links": 1, "videos": 1}


def test_a_used_or_removed_upload_refuses_the_whole_batch_naming_the_file(owner, db, clip):
    video = _send(owner, clip).json()
    owner.delete(f"/uploads/{video['upload_id']}")
    bad = _bulk(owner, [{"title": "Fine"}, {"upload_id": video["upload_id"]}])
    assert bad.status_code == 404
    assert bad.json()["detail"] == "Row 2: That upload was removed. Add the file again."
    both = _bulk(owner, [{"reel_url": LINK, "upload_id": _send(owner, clip).json()["upload_id"]}])
    assert (
        both.json()["detail"]
        == "Row 1 (bo-tries-salmon.mp4): Give it a reel link or a video, not both."
    )
    twice = _send(owner, clip).json()["upload_id"]
    again = _bulk(owner, [{"upload_id": twice}, {"upload_id": twice}])  # QA: one file, two drafts
    assert again.status_code == 422
    assert again.json()["detail"] == "Row 2 (bo-tries-salmon.mp4): That video is already in row 1."
    assert db.query(Script).count() == 0  # all or none
    many = _bulk(owner, [{"reel_url": f"https://www.instagram.com/reel/R{n}x/"} for n in range(21)])
    assert (many.status_code, many.json()["detail"]) == (422, "Up to 20 reels at once.")


def test_uploads_never_used_go_after_a_day(app, owner, db, clip):
    old, kept = (_send(owner, clip).json()["upload_id"] for _ in range(2))
    _bulk(owner, [{"upload_id": kept}])
    for upload in db.query(VideoUpload).all():
        upload.created_at = utcnow() - timedelta(days=2)
    db.commit()
    assert purge_uploads(db, app.state.storage) == 1
    assert db.get(VideoUpload, old) is None and db.get(VideoUpload, kept) is not None
