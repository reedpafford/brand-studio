import json

import httpx2 as httpx
import pytest

from app.models.accounts import Role, User
from app.models.jobs import Job
from app.providers.replicate import ReplicateProvider
from app.routes.jobs import enqueue
from app.worker import run_once
from tests.conftest import upload
from tests.helpers import MP3, MP4, assert_hidden, assert_no_dollars
from tests.test_replicate import BASE, FakeReplicate


@pytest.fixture
def fomo(owner, editor):
    """fomo with one trading screen, plus a character with a sheet image."""
    brand = owner.get("/brands").json()[0]["id"]
    screen = editor.post(
        f"/brands/{brand}/screens",
        json={"name": "Buy", "file_id": upload(editor), "default_for": ["trading", "buy-the-dip"]},
    ).json()["id"]
    sheet = upload(editor)
    max_ = editor.post("/library/character", json={"name": "Max", "image_file_ids": [sheet]}).json()
    return {"brand": brand, "screen": screen, "character": max_["id"], "sheet": sheet}


def _clip(fomo, **extra):
    return {"brand_id": fomo["brand"], "prompt": "A cat starts trading at sunrise", **extra}


def test_estimate_auto_attaches_moment_screens(editor, fomo):
    r = editor.post("/clips/estimate", json=_clip(fomo, character_ids=[fomo["character"]]))
    body = r.json()
    assert body["credits"] == 5 and body["needs_owner_approval"] is False
    assert body["auto_screen_ids"] == [fomo["screen"]]
    assert body["reference_images"] == 2  # character sheet + trading screen
    other = editor.post("/clips/estimate", json=_clip(fomo, prompt="A quiet beach at dawn"))
    assert other.json()["auto_screen_ids"] == []
    dip = editor.post("/clips/estimate", json=_clip(fomo, prompt="Time to buy the dip, Max!"))
    assert dip.json()["auto_screen_ids"] == [fomo["screen"]]


def test_estimate_warns_when_owner_must_approve(editor, fomo, db):
    ed = db.query(User).filter_by(role=Role.editor).one()
    enqueue(db, ed, "video-480p", {}, units=148)
    body = editor.post("/clips/estimate", json=_clip(fomo)).json()
    assert body["needs_owner_approval"] is True and "approve" in body["reason"]


def test_create_returns_job_with_safe_summary(editor, fomo, db):
    prompt = "A cat starts trading at sunrise. " * 10
    r = editor.post("/clips", json=_clip(fomo, prompt=prompt, character_ids=[fomo["character"]]))
    assert r.status_code == 201, r.text
    job = r.json()
    assert (job["status"], job["model_id"], job["brand_id"]) == (
        "queued",
        "seedance-2.5",
        fomo["brand"],
    )
    assert (job["duration"], job["aspect_ratio"], job["resolution"]) == (5, "9:16", "480p")
    assert len(job["prompt_summary"]) == 140 and job["prompt_summary"].endswith("…")
    assert editor.get("/jobs").json()[0]["prompt_summary"] == job["prompt_summary"]
    stored = db.get(Job, job["id"])
    assert stored.provider == "replicate"
    assert sorted(stored.input["files"]["reference_images"]) == sorted(
        [fomo["sheet"], editor.get(f"/brands/{fomo['brand']}/screens").json()[0]["file_id"]]
    )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"resolution": "1080p"}, "offers 480p, 720p"),
        ({"duration": 31}, "from 4 to 30 seconds"),
        ({"duration": 3}, "from 4 to 30 seconds"),
        ({"aspect_ratio": "2:1"}, "doesn't do 2:1"),
        ({"model_id": "nano-banana-pro"}, "Pick a video model"),
        ({"prompt": "short"}, None),
    ],
)
def test_limits_give_plain_errors(editor, fomo, change, message):
    r = editor.post("/clips", json=_clip(fomo, **change))
    assert r.status_code == 422
    if message:
        assert message in r.json()["detail"]


def test_too_many_references_and_audio_alone_are_refused(editor, fomo):
    images = [upload(editor) for _ in range(9)]  # + the auto trading screen = 10 > 9
    r = editor.post("/clips", json=_clip(fomo, model_id="seedance-2.0", file_ids=images))
    assert r.status_code == 422 and "up to 9 reference images" in r.json()["detail"]
    song = upload(editor, "a.mp3", MP3, "audio/mpeg")
    beach = _clip(fomo, prompt="A quiet beach at dawn", file_ids=[song])
    assert "Audio references need" in editor.post("/clips", json=beach).json()["detail"]


def test_screen_from_another_brand_is_refused(editor, fomo):
    other = editor.post("/brands", json={"name": "Other"}).json()["id"]
    r = editor.post("/clips", json=_clip(fomo, brand_id=other, screen_ids=[fomo["screen"]]))
    assert r.status_code == 404


def test_worker_sends_references_as_data_urls(app, editor, fomo, db):
    video = upload(editor, "v.mp4", MP4, "video/mp4")
    r = editor.post("/clips", json=_clip(fomo, file_ids=[video]))
    fake = FakeReplicate()
    client = httpx.Client(transport=httpx.MockTransport(fake))
    for _ in range(3):
        run_once(db, {"replicate": ReplicateProvider(BASE, client)}, app.state.storage)
    sent = json.loads(next(q for q in fake.requests if q.method == "POST").content)["input"]
    assert sent["prompt"].startswith("A cat starts trading")
    assert sent["reference_images"][0].startswith("data:image/png;base64,")
    assert sent["reference_videos"][0].startswith("data:video/mp4;base64,")
    assert "files" not in sent
    assert db.get(Job, r.json()["id"]).status == "succeeded"


def test_other_workspace_is_shut_out(outsider, fomo):
    assert_hidden(
        outsider, [("POST", "/clips", _clip(fomo)), ("POST", "/clips/estimate", _clip(fomo))]
    )
    mine = outsider.post("/brands", json={"name": "Mine"}).json()["id"]
    theirs = {"brand_id": mine, "prompt": "A cat at sunrise", "character_ids": [fomo["character"]]}
    assert outsider.post("/clips", json=theirs).status_code == 404


def test_editor_sees_no_dollars(editor, fomo):
    editor.post("/clips", json=_clip(fomo))
    assert_no_dollars(editor, ["/jobs"])
    assert "usd" not in editor.post("/clips/estimate", json=_clip(fomo)).text.lower()
