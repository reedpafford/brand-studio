"""Several reel links in bulk create, and Write all over reel scripts (one total, all or none,
refused while a reel isn't ready). Stand-in providers; real ffmpeg on a generated clip."""

import shutil
from pathlib import Path

import pytest

from app.models.jobs import Job
from app.providers import get_providers
from app.providers.fake_local import transcript
from app.providers.local import LocalProvider
from app.reel import BLOCKED, Refused
from app.worker import run_once
from tests.test_reel_import import _clip

LINKS = [f"https://www.instagram.com/reel/Reel{n}abc/" for n in range(3)]


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    return _clip(tmp_path_factory.mktemp("reel") / "two.mp4")


def _drain(app, db, clip: Path, refused: str = ""):
    def fetch(url: str, folder: Path) -> Path:
        if url == refused:
            raise Refused("blocked", BLOCKED)
        return Path(shutil.copy(clip, folder / "reel.mp4"))

    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings, app.state.storage)
    providers["local"] = LocalProvider(app.state.storage, transcript, fetch)
    for _ in range(10):
        run_once(db, providers, app.state.storage)


def _bulk(client, rows: list[dict]):
    brand = client.get("/brands").json()[0]["id"]
    return client.post("/scripts/bulk", json={"scripts": [{"brand_id": brand, **r} for r in rows]})


def test_each_link_becomes_a_draft_with_its_own_prep(owner, db):
    made = _bulk(owner, [{"reel_url": u} for u in LINKS] + [{"title": "Plain"}])
    assert made.status_code == 201, made.text
    titles = [s["title"] for s in made.json()]
    assert titles == ["Untitled reel"] * 3 + ["Plain"]
    jobs = db.query(Job).filter(Job.kind == "reel_prepare").all()
    assert sorted(j.input["url"] for j in jobs) == sorted(LINKS)


def test_a_bad_link_or_a_row_with_nothing_refuses_the_whole_request(owner, db):
    bad = _bulk(owner, [{"reel_url": LINKS[0]}, {"reel_url": "https://x.com/r"}])
    assert bad.status_code == 422
    assert bad.json()["detail"] == "Row 2: That isn't an Instagram reel link."
    empty = _bulk(owner, [{"description": "no title, no reel"}])
    assert empty.json()["detail"] == "Row 1: Give it a title."
    assert owner.get("/scripts").json() == [] and db.query(Job).count() == 0


def test_write_all_reads_reels_and_writes_the_rest_at_one_price(app, owner, db, clip):
    ids = [s["id"] for s in _bulk(owner, [{"reel_url": LINKS[0]}, {"reel_url": LINKS[1]},
                                          {"title": "Plain"}]).json()]  # fmt: skip
    waiting = owner.post("/scripts/write", json={"script_ids": ids})
    assert waiting.status_code == 409
    assert waiting.json()["detail"] == "2 reels are still being prepared. Try again shortly."
    est = owner.post("/scripts/write/estimate", json={"script_ids": ids}).json()
    assert est["waiting"] == ids[:2]
    _drain(app, db, clip, refused=LINKS[1])
    est = owner.post("/scripts/write/estimate", json={"script_ids": ids}).json()
    assert (est["reading"], est["writing"], est["failed"]) == (1, 1, [ids[1]])
    assert est["credits"] == 7 + 3  # a reel's read (watch, write, cast) plus one write
    failed = owner.post("/scripts/write", json={"script_ids": ids})
    assert failed.status_code == 409 and "couldn't be fetched" in failed.json()["detail"]
    started = owner.post("/scripts/write", json={"script_ids": [ids[0], ids[2]]})
    assert started.status_code == 201, started.text
    _drain(app, db, clip)
    assert owner.get(f"/scripts/{ids[0]}/import").json()["status"] == "done"
    assert all(owner.get(f"/scripts/{i}").json()["versions"][0]["text"] for i in (ids[0], ids[2]))


def test_write_all_is_all_or_none_over_reading_too(app, owner, editor, db, clip):
    owner.put(
        "/credits/limits", json={"weekly_quick_clip_credits": 9, "per_video_max_credits": 729}
    )
    ids = [s["id"] for s in _bulk(editor, [{"reel_url": LINKS[0]}, {"title": "Plain"}]).json()]
    _drain(app, db, clip)
    declined = editor.post("/scripts/write", json={"script_ids": ids})
    assert declined.status_code == 409 and "10 credits" in declined.json()["detail"]
    assert db.query(Job).filter(Job.kind != "reel_prepare").count() == 0


def test_write_all_holds_every_reels_read(app, owner, editor, db, clip):
    """QA on #292: each reel's later steps are held from the press, so nothing else spends
    them first."""
    owner.put(
        "/credits/limits", json={"weekly_quick_clip_credits": 14, "per_video_max_credits": 729}
    )
    ids = [s["id"] for s in _bulk(editor, [{"reel_url": u} for u in LINKS[:2]]).json()]
    plain = _bulk(editor, [{"title": "Plain"}]).json()[0]["id"]
    _drain(app, db, clip)
    assert editor.post("/scripts/write", json={"script_ids": ids}).status_code == 201
    over = editor.post(f"/scripts/{plain}/write")  # 2 x 7 held, though only 2 watches queued
    assert over.status_code == 409 and "credits" in over.json()["detail"]
    _drain(app, db, clip)
    assert all(editor.get(f"/scripts/{i}/import").json()["status"] == "done" for i in ids)
