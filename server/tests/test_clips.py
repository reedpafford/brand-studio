import base64
import io
import json
from datetime import timedelta

import httpx2 as httpx
import pytest
from PIL import Image

from app.models.accounts import Role, User
from app.models.jobs import Job
from app.providers.replicate import ReplicateProvider
from app.routes.jobs import enqueue
from app.worker import run_once
from tests.conftest import PNG, png, upload
from tests.helpers import MP3, MP4, assert_hidden, assert_no_dollars, mp4, with_sheet
from tests.test_replicate import BASE, FakeReplicate


@pytest.fixture
def fomo(owner, editor, db):
    """fomo with one trading screen, plus a character with a sheet image."""
    brand = owner.get("/brands").json()[0]["id"]
    screen = editor.post(
        f"/brands/{brand}/screens",
        json={"name": "Buy", "file_id": upload(editor), "default_for": ["trading", "buy-the-dip"]},
    ).json()["id"]
    sheet = upload(editor)
    max_ = editor.post("/library/character", json={"name": "Max", "image_file_ids": [sheet]}).json()
    with_sheet(db, max_["id"])
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


def test_estimate_says_when_the_weekly_allowance_is_used(editor, fomo, db):
    ed = db.query(User).filter_by(role=Role.editor).one()
    enqueue(db, ed, "video-480p", {}, units=143)
    r = editor.post("/clips/estimate", json=_clip(fomo))
    assert r.status_code == 409 and r.json()["detail"].startswith("You've used this week's 145")
    assert editor.post("/clips", json=_clip(fomo)).status_code == 409  # declined, not held


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


def test_screen_from_another_brand_is_refused(owner, editor, fomo):
    other = owner.post("/brands", json={"name": "Other"}).json()["id"]
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
    assert sent["prompt"].endswith("\nA cat starts trading at sunrise")
    assert sent["reference_images"][0] == f"data:image/png;base64,{base64.b64encode(PNG).decode()}"
    assert sent["reference_videos"][0].startswith("data:video/mp4;base64,")
    assert "files" not in sent
    assert db.get(Job, r.json()["id"]).status == "succeeded"


def _sent(app, db) -> dict:
    fake = FakeReplicate()
    client = httpx.Client(transport=httpx.MockTransport(fake))
    run_once(db, {"replicate": ReplicateProvider(BASE, client)}, app.state.storage)
    return json.loads(next(q for q in fake.requests if q.method == "POST").content)["input"]


def test_prompt_says_which_picture_is_which(app, editor, fomo, db):
    kitchen = editor.post(
        "/library/place", json={"name": "kitchen", "image_file_ids": [upload(editor)]}
    ).json()["id"]
    with_sheet(db, kitchen)
    prompt = "@max starts trading in the @Kitchen, emailing max@fomo.app"
    body = _clip(fomo, prompt=prompt, character_ids=[fomo["character"]], place_ids=[kitchen])
    assert editor.post("/clips", json=body).status_code == 201
    assert _sent(app, db)["prompt"] == (
        "[Image1] is Max. [Image2] is the kitchen. "
        '[Image3] is the fomo "Buy" screen, logo and layout exact.\n'
        "[Image1] starts trading in the [Image2], emailing max@fomo.app"
    )
    job = db.query(Job).one().id
    assert editor.get(f"/clips/{job}/request").json()["prompt"] == prompt  # for Try again
    assert editor.get(f"/jobs/{job}").json()["prompt_summary"] == prompt


def test_reference_images_are_shrunk_to_the_video_size(app, editor, fomo, db):
    big, clear = (
        upload(editor, data=png(3000, 1000)),
        upload(editor, data=png(10, 10, (0, 0, 0, 0))),
    )
    body = _clip(fomo, prompt="A quiet beach at dawn", file_ids=[big, clear], resolution="720p")
    assert editor.post("/clips", json=body).status_code == 201
    images = _sent(app, db)["reference_images"]
    assert [_decoded(u) for u in images] == [
        ("image/jpeg", (1280, 427)),
        ("image/png", (10, 10)),
    ]  # never scaled up


def _decoded(url: str) -> tuple[str, tuple[int, int]]:
    kind, data = url.removeprefix("data:").split(";base64,")
    return kind, Image.open(io.BytesIO(base64.b64decode(data))).size


def test_brand_screens_and_products_stay_lossless(app, editor, fomo, db):
    big_screen = editor.post(
        f"/brands/{fomo['brand']}/screens",
        json={"name": "Chart", "file_id": upload(editor, data=png(2000, 1000))},
    ).json()["id"]
    bag = editor.post(
        "/library/prop",
        json={"name": "bag", "image_file_ids": [upload(editor, data=png(900, 900))]},
    ).json()["id"]
    body = _clip(fomo, prompt="A quiet beach at dawn", screen_ids=[big_screen], prop_ids=[bag])
    assert editor.post("/clips", json=body).status_code == 201
    images = _sent(app, db)["reference_images"]
    assert [_decoded(u) for u in images] == [("image/png", (854, 854)), ("image/png", (854, 427))]


def test_huge_images_fail_before_any_paid_call(app, editor, fomo, db, monkeypatch):
    big = upload(editor, data=png(20, 20))
    monkeypatch.setattr("app.references.MAX_PIXELS", 100)  # e.g. the limit was lowered since
    body = _clip(fomo, prompt="A quiet beach at dawn", file_ids=[big])
    job = editor.post("/clips", json=body).json()["id"]
    fake = FakeReplicate()
    client = httpx.Client(transport=httpx.MockTransport(fake))
    run_once(db, {"replicate": ReplicateProvider(BASE, client)}, app.state.storage)
    assert db.get(Job, job).status == "failed" and not fake.requests


def test_reference_media_is_limited_per_type(editor, fomo):
    long = [upload(editor, f"{n}.mp4", mp4(20), "video/mp4") for n in range(2)]
    r = editor.post("/clips/estimate", json=_clip(fomo, file_ids=long))
    assert r.json()["detail"] == "Reference videos add up to 40 s; Seedance 2.5 takes 30 s."
    broken = upload(editor, "b.mp4", b"\0\0\0\x18ftypmp42" + b"0" * 32, "video/mp4")
    r = editor.post("/clips/estimate", json=_clip(fomo, file_ids=[broken]))
    assert r.status_code == 422 and "couldn't tell how long b.mp4" in r.json()["detail"]
    ok = editor.post("/clips/estimate", json=_clip(fomo, file_ids=[long[0]]))
    assert ok.status_code == 200


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


def test_skipped_screens_are_not_re_added(editor, fomo):
    body = _clip(fomo, skip_screen_ids=[fomo["screen"]])
    assert editor.post("/clips/estimate", json=body).json()["auto_screen_ids"] == []
    job = editor.post("/clips", json=body).json()
    assert editor.get(f"/clips/{job['id']}/request").json()["skip_screen_ids"] == [fomo["screen"]]


def test_full_request_for_try_again(editor, outsider, fomo, db):
    body = _clip(fomo, character_ids=[fomo["character"]], generate_audio=False, duration=7)
    job = editor.post("/clips", json=body).json()
    again = editor.get(f"/clips/{job['id']}/request").json()
    assert again["prompt"] == body["prompt"] and again["generate_audio"] is False
    assert (again["duration"], again["character_ids"]) == (7, [fomo["character"]])
    assert editor.post("/clips", json=again).status_code == 409  # a double press is refused
    db.get(Job, job["id"]).created_at -= timedelta(minutes=1)
    db.commit()
    assert editor.post("/clips", json=again).status_code == 201  # "Try again" later, as is
    assert_hidden(outsider, [("GET", f"/clips/{job['id']}/request")])


def test_generation_switch_off_refuses_and_worker_holds_paid_jobs(app, editor, fomo, db):
    app.state.settings.generation_enabled = False
    assert editor.post("/clips/estimate", json=_clip(fomo)).status_code == 200  # still works
    r = editor.post("/clips", json=_clip(fomo))
    assert r.status_code == 503 and "switched off" in r.json()["detail"]
    assert db.query(Job).count() == 0
    queued = enqueue(
        db,
        db.query(User).first(),
        "video",
        {"model": "seedance-2.5", "input": {}},
        provider="replicate",
    )
    fake = FakeReplicate()
    client = httpx.Client(transport=httpx.MockTransport(fake))
    run_once(
        db, {"replicate": ReplicateProvider(BASE, client)}, app.state.storage, allow_paid=False
    )
    db.refresh(queued)
    assert queued.status == "queued" and fake.requests == []  # nothing was sent


def test_references_have_a_total_size_cap(editor, fomo, monkeypatch):
    monkeypatch.setattr("app.routes.clips.MAX_REFERENCE_BYTES", 10)
    r = editor.post("/clips/estimate", json=_clip(fomo))
    assert r.status_code == 422 and "too big together" in r.json()["detail"]


def test_a_quick_clip_is_removed_from_the_history_and_brought_back(owner, editor, fomo, db):
    """Gaps #14: search the history; remove a finished clip with Undo. Its credits still count."""
    from app.credits import quick_clip_used

    cat = editor.post("/clips", json=_clip(fomo)).json()["id"]
    dog = editor.post("/clips", json=_clip(fomo, prompt="A dog naps by the pool")).json()["id"]
    assert [j["id"] for j in editor.get("/jobs", params={"q": "DOG naps"}).json()] == [dog]
    assert editor.delete(f"/jobs/{cat}").status_code == 409  # still going
    db.query(Job).update({"status": "succeeded"})
    db.commit()
    me = db.query(User).filter_by(role="editor").one()
    spent = quick_clip_used(db, me)
    assert owner.delete(f"/jobs/{cat}").status_code == 204  # the owner may too
    assert [j["id"] for j in editor.get("/jobs").json()] == [dog]
    assert [j["id"] for j in editor.get("/jobs", params={"removed": True}).json()] == [cat]
    assert quick_clip_used(db, me) == spent  # removing never gives credits back
    assert editor.post(f"/jobs/{cat}/restore").json()["id"] == cat  # Undo
    assert editor.post(f"/jobs/{cat}/restore").status_code == 404  # not removed
    assert {j["id"] for j in editor.get("/jobs").json()} == {cat, dog}
