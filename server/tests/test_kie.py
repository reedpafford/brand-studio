"""Suno, Seedream and Seedance through KIE (app/providers/kie.py), against a mock of KIE's API
as its docs describe it: no paid call."""

import base64
import json
from decimal import Decimal

import httpx2 as httpx
import pytest

from app import music
from app.providers import NoKey, NotStarted, get_providers, kie_on
from app.providers.kie import AGAIN, KieMedia, KieSuno
from app.routes.jobs import enqueue
from app.settings import Settings
from tests.conftest import png, upload
from tests.helpers import MP4

BASE = "https://api.kie.ai/api/v1"
SONG = "https://files.example-cdn.com/song1.mp3"


def _kie(handler) -> tuple[KieSuno, list[httpx.Request]]:
    seen = []

    def record(request):
        seen.append(request)
        return handler(request)

    client = httpx.Client(transport=httpx.MockTransport(record))
    return KieSuno(BASE, "test-key", ("example-cdn.com",), client=client), seen


def _real(job: dict) -> dict:
    return {**job, "kie": True}  # made while real songs were on (song_takes.real_songs)


def _ok(data):
    return httpx.Response(200, json={"code": 200, "msg": "success", "data": data})


def test_one_request_is_suno_v6_custom_mode_with_our_words():
    kie, seen = _kie(lambda r: _ok({"taskId": "t1"}))
    job = _real(music.job("[Verse 1]\nIron Paws, bowl is bright\nLink in my bio", "breezy pop"))
    assert kie.submit("music", job) == "t1"
    sent = json.loads(seen[0].content)
    assert seen[0].url == f"{BASE}/jobs/createTask"
    assert seen[0].headers["authorization"] == "Bearer test-key"
    assert sent["input"]["custom_mode"] and not sent["input"]["instrumental"]
    assert sent["input"]["model"] == "V6" and sent["input"]["title"] == "Iron Paws, bowl is bright"
    assert sent["input"]["lyrics"] == job["input"]["lyrics"]  # word for word
    assert sent["input"]["style"] == job["input"]["style"]
    assert sent["input"]["negative_tags"] == job["input"]["exclude_styles"]


@pytest.mark.parametrize("gender", ["f", "m", ""])
def test_the_style_lines_voice_goes_to_kie_only_when_set(gender):
    kie, seen = _kie(lambda r: _ok({"taskId": "t1"}))
    job = _real(music.job("Iron Paws, bowl is bright", "breezy pop, warm vocal"))
    job["input"]["vocal_gender"] = gender  # prompts.song_request reads it from the style line
    kie.submit("music", job)
    sent = json.loads(seen[0].content)["input"]
    assert sent.get("vocal_gender") == (gender or None) and "vocalGender" not in sent


def test_a_female_vocal_in_the_style_line_reaches_kie():
    kie, seen = _kie(lambda r: _ok({"taskId": "t1"}))
    kie.submit("music", _real(music.job("Iron Paws, bowl is bright", "pop, warm female vocal")))
    assert json.loads(seen[0].content)["input"]["vocal_gender"] == "f"


def test_poll_waits_then_gives_both_songs():
    states = iter(
        [
            {"state": "generating"},
            {
                "state": "success",
                "response": {
                    "data": [
                        {"audio_url": SONG, "duration": 31.2},
                        {"audio_url": SONG.replace("1", "2")},
                    ]
                },
            },
        ]
    )
    kie, seen = _kie(lambda r: _ok(next(states)))
    assert kie.poll("t1").state == "running"
    done = kie.poll("t1")
    assert done.state == "succeeded" and len(done.files) == 2
    assert seen[0].url.params["taskId"] == "t1"


def test_a_failed_song_says_why_plainly():
    kie, _ = _kie(lambda r: _ok({"state": "fail", "failCode": "400",
                                 "failMsg": "Prompt contains artist name"}))  # fmt: skip
    failed = kie.poll("t1")
    assert failed.state == "failed"
    assert music.failure(failed.error, "pop") == music.COPYRIGHT.format("pop")


def test_kie_errors_come_back_as_http_200_with_their_own_code():
    kie, _ = _kie(lambda r: httpx.Response(200, json={"code": 402, "msg": "Insufficient credits"}))
    with pytest.raises(RuntimeError, match="402"):
        kie.submit("music", _real(music.job("Iron Paws", "pop")))
    kie, _ = _kie(lambda r: httpx.Response(200, json={"code": 429, "msg": "slow down"}))
    with pytest.raises(NotStarted):
        kie.submit("music", _real(music.job("Iron Paws", "pop")))


def test_songs_download_only_from_the_delivery_hosts_and_never_get_the_key():
    kie, seen = _kie(lambda r: httpx.Response(200, content=b"ID3", headers={
        "content-type": "audio/mpeg"}))  # fmt: skip
    assert kie.fetch(SONG) == (b"ID3", "audio/mpeg")
    assert "authorization" not in seen[0].headers
    for url in ("https://169.254.169.254/x.mp3", "http://files.example-cdn.com/a.mp3", BASE):
        with pytest.raises(RuntimeError, match="Refusing"):
            kie.fetch(url)


def test_it_stays_off_until_switched_on_with_a_key(monkeypatch):
    monkeypatch.delenv("KIE_API_KEY", raising=False)
    off = Settings(fake_providers=False)
    assert not kie_on(off) and "suno" not in get_providers(off)
    assert not kie_on(Settings(kie_suno=True))  # no key: still off
    monkeypatch.setenv("KIE_API_KEY", "test-key")
    assert not kie_on(Settings())  # a key alone never switches it on
    on = Settings(kie_suno=True)
    assert kie_on(on) and isinstance(get_providers(on)["suno"], KieSuno)
    test_site = Settings(kie_suno=True, fake_providers=True)  # every other service a stand-in
    providers = get_providers(test_site)
    assert isinstance(providers["suno"], KieSuno) and not providers["replicate"].paid


def test_a_request_queued_before_real_songs_is_never_sung_for_real():
    kie, seen = _kie(lambda r: _ok({"taskId": "t1"}))
    with pytest.raises(RuntimeError, match="Not a real-song request"):
        kie.submit("music", music.job("Iron Paws", "pop"))
    assert seen == []  # nothing reached KIE


def test_real_songs_stop_at_the_test_budget(app, db, owner):
    from app import song_takes
    from tests.test_song_takes import _style

    settings = app.state.settings
    settings.fake_providers, settings.kie_suno = True, True
    settings.kie_budget_usd, settings.kie_usd_per_request = 0.25, 0.1
    brand = owner.get("/brands").json()[0]["id"]
    words = "[Verse 1]\nIron Paws\nLink in my bio"
    body = {"brand_id": brand, "title": "Paws", "kind": "song", "text": words}
    script = owner.post("/scripts", json=body)
    url = f"/scripts/{script.json()['id']}/drafts/0"
    _style(owner, url, "pop")
    assert owner.get(f"{url}/songs").json()["songs_on"]
    for _ in range(2):
        assert owner.post(f"{url}/songs", json={}).status_code == 201
    third = owner.post(f"{url}/songs", json={})  # past the budget: free stand-in songs, one press
    assert third.status_code == 201 and third.json()["songs_note"] == song_takes.BUDGET_USED
    assert "$" not in third.json()["songs_note"] and "Producer" not in third.json()["songs_note"]
    from app.models.jobs import Job

    real = [j.input.get("kie", False) for j in db.query(Job).filter(Job.kind == "music")]
    assert real == [True, True, False]  # the third is never sent to KIE


def test_a_real_song_sent_to_kie_counts_even_if_its_video_is_put_away(app, db, owner):
    from app import song_takes
    from app.models.jobs import Job, JobStatus

    settings = app.state.settings
    settings.kie_suno, settings.kie_budget_usd, settings.kie_usd_per_request = True, 0.25, 0.1
    settings.fake_providers = True  # the test site: past the budget, stand-ins
    sent = Job(
        workspace_id=1,
        kind="music",
        provider="suno",
        input={"kie": True},
        credits=1,
        status=JobStatus.cancelled,
        provider_ref="t1",
    )  # put away mid-song: still paid
    never = Job(
        workspace_id=1,
        kind="music",
        provider="suno",
        input={"kie": True},
        credits=1,
        status=JobStatus.cancelled,
    )  # cancelled before it was sent: costs nothing
    db.add_all([sent, never])
    db.commit()
    assert song_takes.real_songs(db, settings) == 0.1  # one left: 1 counted, not 2 or 0
    db.add(Job(workspace_id=1, kind="music", provider="suno", input={"kie": True}, credits=1))
    db.commit()
    assert song_takes.real_songs(db, settings) == 0.0 and song_takes.budget_used(db, settings)


def test_past_the_budget_a_stand_in_sings_and_kie_hears_nothing():
    from app.providers.fake_local import FakeSuno

    kie, seen = _kie(lambda r: _ok({"taskId": "t1"}))
    kie.stand_in = FakeSuno()
    ref = kie.submit("music", music.job("Iron Paws", "pop"))
    done = kie.poll(ref)
    assert done.state == "succeeded" and len(done.files) == 2
    assert kie.fetch(done.files[0])[1] == "audio/mpeg" and seen == []


def test_off_the_test_site_real_songs_past_the_budget_stop_plainly(db):
    from fastapi import HTTPException

    from app import song_takes

    settings = Settings(kie_suno=True, kie_budget_usd=0.05)
    with pytest.raises(HTTPException) as no:
        song_takes.real_songs(db, settings)
    assert no.value.detail == song_takes.NO_MORE_REAL


def test_poll_reports_what_kie_took_for_the_request():
    done = {"state": "success", "creditsConsumed": 12, "response": {"data": [{"audio_url": SONG}]}}
    kie, _ = _kie(lambda r: _ok(done))
    (cost,) = kie.poll("t1").usage
    assert (cost.cost_usd, cost.estimated) == (Decimal("0.06"), False)  # 12 credits at $0.005
    kie, _ = _kie(lambda r: _ok({**done, "creditsConsumed": None}))
    (cost,) = kie.poll("t1").usage  # not said: its usual price, marked estimated
    assert (cost.cost_usd, cost.estimated) == (Decimal("0.06"), True)
    kie, _ = _kie(lambda r: _ok({"state": "fail", "failCode": "500", "failMsg": "internal"}))
    assert kie.poll("t1").usage == []  # a failure KIE didn't charge costs nothing
    kie, seen = _kie(lambda r: _ok(done))
    again = kie.submit("music", {**_real(music.job("Iron Paws", "pop")), AGAIN: "t1"})
    assert again == "again:t1" and seen == []  # no new request
    read = kie.poll(again)
    assert read.files == [SONG] and read.usage == []  # paid once, by the first request
    assert seen[0].url.params["taskId"] == "t1"


def test_songs_made_but_not_saved_are_fetched_again_free_never_paid_twice(app, db, owner):
    from app import song_takes
    from app.models.jobs import Job, Usage
    from app.models.songs import SongTake
    from app.providers.fake_local import FakeSuno
    from app.worker import run_once
    from tests.test_song_takes import _style

    settings = app.state.settings
    settings.fake_providers, settings.kie_suno, settings.kie_budget_usd = True, True, 1.0
    calls = []

    def kie_api(r):
        calls.append(r)
        if r.url.path.endswith("/jobs/createTask"):
            return _ok({"taskId": "t1"})
        if r.url.path.endswith("/jobs/recordInfo"):
            return _ok(
                {
                    "state": "success",
                    "creditsConsumed": 12,
                    "response": {"data": [{"audio_url": SONG}, {"audio_url": SONG}]},
                }
            )
        return httpx.Response(200, content=b"ID3" + bytes(64), headers={
            "content-type": "audio/mpeg"})  # fmt: skip

    client = httpx.Client(transport=httpx.MockTransport(kie_api))
    kie = KieSuno(BASE, "test-key", (), client=client, stand_in=FakeSuno())  # no hosts yet
    providers = {**get_providers(settings, app.state.storage), "suno": kie}
    brand = owner.get("/brands").json()[0]["id"]
    body = {"brand_id": brand, "title": "Paws", "kind": "song", "text": "Iron Paws\nLink below"}
    url = f"/scripts/{owner.post('/scripts', json=body).json()['id']}/drafts/0"
    _style(owner, url, "pop")
    owner.post(f"{url}/songs", json={})
    for _ in range(2):
        run_once(db, providers, app.state.storage)
    first = db.query(Job).filter_by(kind="music").one()
    assert first.status == "failed" and first.output.get("unsaved")  # made, not saved
    (paid,) = db.query(Usage).filter_by(job_id=first.id).all()  # KIE was paid: listed
    assert (paid.cost_usd, paid.estimated) == (Decimal("0.06"), False)
    take = db.query(SongTake).order_by(SongTake.id).first()
    assert song_takes.retry_credits(db, take) == 0

    assert owner.post(f"/songs/{take.id}/try-again").status_code == 200
    kie.delivery_hosts = ("example-cdn.com",)
    for _ in range(2):
        run_once(db, providers, app.state.storage)
    again = db.query(Job).filter(Job.kind == "music", Job.id != first.id).one()
    assert again.input[AGAIN] == "t1" and again.credits == 0 and again.status == "succeeded"
    assert db.query(Usage).filter_by(job_id=again.id).count() == 0  # nothing paid again
    assert sum(r.url.path.endswith("/createTask") for r in calls) == 1  # one KIE request
    assert len(song_takes._real_jobs(db)) == 1  # the read again isn't a request
    assert all(t.file_id for t in db.query(SongTake).all())


# --- Pictures and takes (Reed, 12 Nov: real-looking people on Seedream and Seedance) ---------

UPLOADS = "https://kieai.redpandaai.test"
MADE = "https://tempfile.aiquickdraw.com/p/t1_1.mp4"
SHEET = png(1600, 900)  # wider than a 480p take's 854 px: scaled, were it sent any other way
KIE_TAKE = "seedance-2.5-kie"
TAKE = {
    "prompt": "[Image1] is Mia. [Image1] waves at the camera.",
    "duration": 5,
    "resolution": "480p",
    "aspect_ratio": "9:16",
    "generate_audio": True,
}


def _data(raw: bytes, kind: str = "image/png") -> str:
    return f"data:{kind};base64,{base64.b64encode(raw).decode()}"


def _param(input: dict) -> str:
    return json.dumps({"model": "bytedance/seedance-2-5", "input": json.dumps(input)})


def _media(answer=None, key: str = "test-key") -> tuple[KieMedia, list[httpx.Request]]:
    """KIE as its docs describe it: an upload answers with its file's address, a new task
    with its id, a check with `answer` (a made take by default), a download with a video."""
    seen = []

    def api(request):
        seen.append(request)
        if request.url.path.endswith("/api/file-stream-upload"):
            return _ok({"downloadUrl": f"https://tempfile.redpandaai.test/u{len(seen)}.png"})
        if request.url.path.endswith("/jobs/createTask"):
            return _ok({"taskId": "t1"})
        if request.url.path.endswith("/jobs/recordInfo"):
            return _ok(
                answer
                or {
                    "state": "success",
                    "model": "bytedance/seedance-2-5",
                    "creditsConsumed": 140,
                    "param": _param(TAKE),
                    "resultJson": json.dumps({"resultUrls": [MADE]}),
                }
            )
        return httpx.Response(200, content=MP4, headers={"content-type": "binary/octet-stream"})

    client = httpx.Client(transport=httpx.MockTransport(api))
    return KieMedia(BASE, key, ("aiquickdraw.com",), client=client, upload_url=UPLOADS), seen


def test_a_seedream_sheet_is_asked_from_words_alone_as_kies_docs_say():
    kie, seen = _media()
    sheet = {"prompt": "A character reference sheet.", "aspect_ratio": "16:9", "resolution": "2K"}
    assert kie.submit("image", {"model": "seedream-5.5", "input": sheet}) == "t1"
    assert seen[0].url == f"{BASE}/jobs/createTask"
    assert json.loads(seen[0].content) == {
        "model": "seedream/5-5-text-to-image",
        "input": {
            "prompt": "A character reference sheet.",
            "aspect_ratio": "16:9",
            "size": "2K",
            "output_format": "png",
            "background": "opaque",
            "nsfw_checker": True,
        },
    }
    with pytest.raises(RuntimeError, match="words only"):  # never a picture drawn from one
        kie.submit("image", {"model": "seedream-5.5", "input": {**sheet, "image_input": ["x"]}})
    with pytest.raises(RuntimeError, match="isn't made through KIE"):
        kie.submit("video", {"model": "seedance-2.5", "input": TAKE})
    assert len(seen) == 1


def test_a_take_uploads_each_file_untouched_and_names_its_pictures_kies_way():
    kie, seen = _media()
    job = {
        "model": KIE_TAKE,
        "input": {
            **TAKE,
            "reference_images": [_data(SHEET)],
            "reference_audios": [_data(b"ID3song", "audio/mpeg")],
        },
    }
    assert kie.submit("video", job) == "t1"
    sheet, song, task = seen
    assert sheet.url == f"{UPLOADS}/api/file-stream-upload" and SHEET in sheet.content
    assert sheet.headers["authorization"] == "Bearer test-key"
    assert b"ID3song" in song.content and b".mp3" in song.content
    sent = json.loads(task.content)
    assert sent["model"] == "bytedance/seedance-2-5"
    assert sent["input"] == {
        "prompt": "@Image1 is Mia. @Image1 waves at the camera.",
        "duration": 5,
        "resolution": "480p",
        "aspect_ratio": "9:16",
        "generate_audio": True,
        "output_format": "mp4",
        "web_search": False,
        "draft": False,
        "nsfw_checker": True,
        "reference_image_urls": ["https://tempfile.redpandaai.test/u1.png"],
        "reference_audio_urls": ["https://tempfile.redpandaai.test/u2.png"],
        "omni_reference_task_type": "auto",
    }
    kie, seen = _media()  # words alone, then a start frame: no task type (KIE refuses it there)
    kie.submit("video", {"model": KIE_TAKE, "input": TAKE})
    kie.submit("video", {"model": KIE_TAKE, "input": {**TAKE, "image": _data(SHEET)}})
    kie.submit("video", {"model": KIE_TAKE, "input": {**TAKE, "reference_videos": [_data(MP4)]}})
    assert json.loads(seen[4].content)["input"]["omni_reference_task_type"] == "reference"
    plain, framed = json.loads(seen[0].content)["input"], json.loads(seen[2].content)["input"]
    assert "omni_reference_task_type" not in plain and "omni_reference_task_type" not in framed
    assert framed["first_frame_url"] == "https://tempfile.redpandaai.test/u2.png"


def test_an_upload_that_fails_or_no_key_starts_nothing_paid():
    seen = []

    def down(request):
        seen.append(request)
        return httpx.Response(200, json={"code": 500, "msg": "Internal server error"})

    client = httpx.Client(transport=httpx.MockTransport(down))
    kie = KieMedia(BASE, "test-key", (), client=client, upload_url=UPLOADS)
    job = {"model": KIE_TAKE, "input": {**TAKE, "reference_images": [_data(SHEET)]}}
    with pytest.raises(NotStarted):  # tried again later: no task was asked for
        kie.submit("video", job)
    assert [r.url.path for r in seen] == ["/api/file-stream-upload"]
    kie, seen = _media(key="")
    with pytest.raises(NoKey):
        kie.submit("video", job)
    assert seen == []


def test_checking_reads_running_made_and_failed_and_the_cost_is_the_credits_kie_took():
    assert _media({"state": "queuing"})[0].poll("t1").state == "running"
    made = _media()[0].poll("t1")
    assert (made.state, made.files) == ("succeeded", [MADE])
    (cost,) = made.usage  # 5 s at 480p: 140 KIE credits at $0.005
    assert (cost.units, cost.unit, cost.cost_usd, cost.estimated) == (
        5,
        "second",
        Decimal("0.7"),
        False,
    )
    drawn = _media(
        {
            "state": "success",
            "model": "seedream/5-5-text-to-image",
            "creditsConsumed": 6.3,
            "response": {"resultUrls": [MADE]},
        }
    )[0].poll("t1")
    assert [(u.units, u.unit, u.cost_usd) for u in drawn.usage] == [(1, "image", Decimal("0.0315"))]
    unsaid = _media({"state": "success", "resultJson": json.dumps({"resultUrls": [MADE]})})
    assert unsaid[0].poll("t1").usage == []  # the worker records the job's own price instead
    refused = _media(
        {
            "state": "fail",
            "failCode": "400",
            "creditsConsumed": 0,
            "failMsg": "input image may contain real person",
        }
    )[0].poll("t1")
    assert refused.state == "failed"
    assert [u.cost_usd for u in refused.usage] == [0]  # KIE said it took nothing: $0, listed
    assert refused.error == "400: input image may contain real person"
    assert _media({"state": "success", "resultJson": ""})[0].poll("t1").state == "failed"


def test_what_kie_made_downloads_only_from_its_file_host_and_never_gets_the_key():
    kie, seen = _media()
    assert kie.fetch(MADE) == (MP4, "video/mp4")  # named by its ending, whatever the host says
    assert "authorization" not in seen[0].headers
    for url in (
        "https://169.254.169.254/x.mp4",
        MADE.replace("https", "http"),
        "https://aiquickdraw.com.evil.test/x.mp4",
        f"{UPLOADS}/x.mp4",
    ):
        with pytest.raises(RuntimeError, match="Refusing"):
            kie.fetch(url)


def test_the_kie_models_go_to_kie_at_its_price_and_replicates_seedance_stays(app, owner, db):
    from app.catalogue import get_model, provider_for
    from app.models.accounts import User

    assert provider_for(KIE_TAKE, "replicate") == provider_for("seedream-5.5", "replicate") == "kie"
    assert provider_for("seedance-2.5", "replicate") == "replicate"
    assert provider_for(KIE_TAKE, "fake") == "fake"  # a test's own lane
    assert get_model("seedance-2.5").usd_per_unit("480p") == Decimal("0.1028")  # as it was
    assert get_model("seedream-5.5").usd_per_unit("2K") == Decimal("0.0315")
    kinds = {m["id"]: m["kind"] for m in owner.get("/models").json()}
    assert kinds[KIE_TAKE] == "video" and "seedream-5.5" not in kinds  # it draws sheets only
    user = db.query(User).first()
    job = enqueue(
        db, user, "video", {"model": KIE_TAKE, "input": TAKE}, units=5, provider="replicate"
    )
    assert (job.provider, job.credits) == ("kie", Decimal("6.80"))  # 5 s at $0.14: 1.36 credits


def test_a_kie_clip_gets_its_sheet_as_stored_and_is_charged_what_kie_took(app, owner, db):
    from app.models.jobs import Job, Usage
    from app.worker import run_once
    from tests.helpers import with_sheet

    brand = owner.get("/brands").json()[0]["id"]
    made = owner.post(
        "/library/character", json={"name": "Mia", "image_file_ids": [upload(owner, data=SHEET)]}
    )
    with_sheet(db, made.json()["id"])
    clip = {
        "brand_id": brand,
        "model_id": KIE_TAKE,
        "prompt": "@Mia waves at the camera",
        "character_ids": [made.json()["id"]],
    }
    assert owner.post("/clips/estimate", json=clip).json()["credits"] == 6.8
    job = db.get(Job, owner.post("/clips", json=clip).json()["id"])
    assert (job.provider, job.input["fit_images_to"]) == ("kie", 854)
    kie, seen = _media()
    for _ in range(3):
        run_once(db, {"kie": kie}, app.state.storage)
    db.refresh(job)
    assert job.status == "succeeded" and SHEET in seen[0].content  # byte for byte, never scaled
    assert json.loads(seen[1].content)["input"]["prompt"] == (
        "@Image1 is Mia.\n@Image1 waves at the camera"
    )
    assert owner.get(f"/files/{job.output['file_ids'][0]}").content == MP4
    usage = db.query(Usage).one()
    assert (usage.provider, usage.units, usage.cost_usd, usage.estimated) == (
        "kie",
        5,
        Decimal("0.7000"),
        False,
    )


def test_the_stand_ins_answer_for_both_kie_models_and_no_key_sends_nothing(
    app, owner, db, monkeypatch
):
    from app.models.accounts import User
    from app.worker import run_once

    monkeypatch.delenv("KIE_API_KEY", raising=False)
    providers = get_providers(Settings(fake_providers=True), app.state.storage)
    assert type(providers["kie"]) is type(providers["replicate"])  # the same free stand-in
    user = db.query(User).first()
    sheet = {"prompt": "A character reference sheet.", "aspect_ratio": "16:9", "resolution": "2K"}
    made = [
        enqueue(
            db, user, "video", {"model": KIE_TAKE, "input": TAKE}, units=5, provider="replicate"
        ),
        enqueue(db, user, "image", {"model": "seedream-5.5", "input": sheet}, provider="replicate"),
    ]
    for _ in range(3):
        run_once(db, providers, app.state.storage)
    for job in made:
        db.refresh(job)
    assert [(j.provider, j.status) for j in made] == [("kie", "succeeded")] * 2
    real = get_providers(Settings(), app.state.storage)["kie"]
    assert isinstance(real, KieMedia)
    with pytest.raises(NoKey):  # a worker with no KIE key: unsent, so never charged
        real.submit("video", {"model": KIE_TAKE, "input": TAKE})
