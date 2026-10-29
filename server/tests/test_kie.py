"""Suno through KIE (app/providers/kie.py), against a mock of KIE's API: no paid call."""

import json

import httpx2 as httpx
import pytest

from app import music
from app.providers import NotStarted, get_providers, kie_on
from app.providers.kie import KieSuno
from app.settings import Settings

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
    third = owner.post(f"{url}/songs", json={})
    assert (third.status_code, third.json()["detail"]) == (409, song_takes.BUDGET_USED)
    assert "$" not in third.json()["detail"]
    from app.models.jobs import Job

    assert all(j.input["kie"] for j in db.query(Job).filter(Job.kind == "music"))
