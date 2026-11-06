"""Voices (v6 S8-04): every app voice and a brand's own voices with free samples, a voice
cloned from a sample (priced first, held for the owner when an editor asks), remove with
Undo, and Dr. Pickle's clone as that style's narrator, with its 7-day expiry said plainly.
Stand-ins and a mocked Replicate only: no paid calls."""

import subprocess
from datetime import timedelta
from decimal import Decimal

import httpx2 as httpx
import pytest
from fastapi import HTTPException

from app import director_song, narration, usage, voices
from app.catalogue import get_model
from app.db import utcnow
from app.models.accounts import Workspace
from app.models.files import StoredFile
from app.models.freestyles import Freestyle
from app.models.jobs import Job, JobStatus
from app.models.library import Kind, LibraryItem
from app.models.projects import Project
from app.models.voices import Voice
from app.providers.replicate import ReplicateProvider
from tests.conftest import first_brand, upload
from tests.test_freestyle_dialogue import _run

WORDS = "Your gut is a mess. Resilia fixes it."


def _audio(seconds: float) -> bytes:
    command = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"sine=f=200:d={seconds}",
               "-c:a", "libmp3lame", "-b:a", "64k", "-f", "mp3", "-"]  # fmt: skip
    return subprocess.run(command, capture_output=True, check=True).stdout  # noqa: S603


def _sample(client, seconds: float = 12) -> int:
    return upload(client, "me.mp3", _audio(seconds), "audio/mpeg")


def _list(client, brand, **params):
    r = client.get(f"/brands/{brand}/voices", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _ws(db) -> int:
    return db.query(Workspace).one().id


def _pickle(db, workspace_id: int) -> Voice:
    voices.ensure_style_voices(db, workspace_id)
    return db.query(Voice).filter_by(workspace_id=workspace_id, look="dr-pickle").one()


def _saved(client, brand) -> list[dict]:
    return [v for v in _list(client, brand)["voices"] if v["id"] is not None]


def test_the_brands_voices_list_dr_pickles_clone_with_its_sample_and_expiry(db, owner):
    brand = first_brand(owner)
    body = _list(owner, brand)
    (pickle,) = _saved(owner, brand)
    assert (pickle["name"], pickle["kind"], pickle["look"], pickle["brand_id"]) == (
        "Dr. Pickle", "cloned", "dr-pickle", None)  # fmt: skip
    assert pickle["sample_url"] == "/voices/samples/dr-pickle.mp3"  # the web adds /api
    assert owner.get(pickle["sample_url"]).headers["content-type"] == "audio/mpeg"
    row = db.get(Voice, pickle["id"])
    assert (row.provider_voice_id, row.speech_model) == ("R8_CJRWYITM", "minimax-speech-02-hd")
    assert voices.expires_at(row) == row.last_used_at + timedelta(days=7)
    assert body["clone_credits"] == 29.18 and body["clone_usd"] == 3.0  # $3 once
    assert len(_saved(owner, brand)) == 1  # made once per workspace


def test_every_app_voice_is_listed_with_a_free_sample_where_a_test_made_one(owner, editor):
    """Reed, 4 Nov: the app's voices are always offered; a brand saves only its own."""
    brand = first_brand(owner)
    listed = {v["stock_key"]: v for v in _list(editor, brand)["voices"] if v["id"] is None}
    assert list(listed) == voices.stock_keys() and "Roger" in listed
    assert {v["kind"] for v in listed.values()} == {"stock"}
    assert listed["Roger"]["provider"] == "elevenlabs"
    assert listed["Roger"]["sample_url"] == "/voices/samples/Roger.mp3"
    assert listed["English_FriendlyPerson"]["provider"] == "minimax"
    assert all(v["sample_url"] for v in listed.values())  # every app voice has its free sample
    assert _list(editor, brand, all=True)["voices"] == _list(editor, brand)["voices"]
    assert _list(editor, brand)["clone_usd"] is None  # editors never see dollars
    assert editor.get("/voices/samples/..%2Fvoices.mp3").status_code == 404
    assert editor.post(f"/brands/{brand}/voices", json={"stock_key": "Roger"}).status_code == 405


def test_a_brands_voice_lists_who_uses_it_and_is_removed_with_undo(db, owner, editor):
    brand = first_brand(owner)
    ws = _ws(db)
    mark = Voice(workspace_id=ws, brand_id=brand, name="Mark", kind="cloned",
                 provider="minimax", provider_voice_id="R8_MARK", speech_model=voices.SPEAKS,
                 cloned_at=utcnow(), last_used_at=utcnow())  # fmt: skip
    db.add(mark)
    db.flush()
    item = LibraryItem(workspace_id=ws, kind=Kind.character, name="Mark", voice_id=mark.id)
    db.add(item)
    db.commit()
    assert next(v for v in _saved(editor, brand) if v["id"] == mark.id)["used_by"] == [item.id]
    assert editor.delete(f"/voices/{mark.id}").status_code == 204
    assert mark.id not in [v["id"] for v in _saved(editor, brand)]
    assert editor.post(f"/voices/{mark.id}/restore").json()["id"] == mark.id
    assert editor.post(f"/voices/{mark.id}/restore").status_code == 409
    assert db.query(Job).count() == 0  # free


def test_a_styles_own_voice_is_removed_by_the_owner_only(owner, editor):
    brand = first_brand(owner)
    pickle = _saved(owner, brand)[0]["id"]
    assert editor.delete(f"/voices/{pickle}").status_code == 403
    assert owner.delete(f"/voices/{pickle}").status_code == 204
    assert _saved(owner, brand) == []  # stays removed, never made again
    assert owner.post(f"/voices/{pickle}/restore").status_code == 200


def test_a_voice_is_cloned_from_a_sample_through_the_cloning_model(app, db, owner):
    app.state.settings.fake_providers = True
    brand = first_brand(owner)
    body = {"name": "Mark", "description": "Relaxed, warm", "sample_file_id": _sample(owner)}
    made = owner.post(f"/brands/{brand}/voices/clone", json=body)
    assert made.status_code == 201, made.text
    assert (made.json()["state"], made.json()["kind"]) == ("cloning", "cloned")
    job = db.query(Job).filter_by(kind="voice").one()
    assert (job.input["model"], job.input["step"]) == (voices.CLONER, voices.STEP)
    assert job.input["input"] == {"model": "speech-02-hd", "need_volume_normalization": True,
                                  "need_noise_reduction": False}  # fmt: skip
    assert job.input["files"] == {"voice_file": [body["sample_file_id"]]}
    assert job.credits == get_model(voices.CLONER).credits_per_unit()  # one clone
    _run(app, db, ticks=3)
    mark = next(v for v in _saved(owner, brand) if v["name"] == "Mark")
    assert mark["state"] == "ready" and mark["preview_file_id"] and mark["cloned_at"]
    row = db.get(Voice, mark["id"])
    assert row.provider_voice_id.startswith("stand-in-voice") and row.speech_model == voices.SPEAKS


def test_a_sample_outside_the_cloning_models_limits_is_refused_before_any_spend(db, owner):
    brand = first_brand(owner)
    for seconds, said in ((5, "at least 10 seconds"),):
        body = {"name": "Short", "sample_file_id": _sample(owner, seconds)}
        r = owner.post(f"/brands/{brand}/voices/clone", json=body)
        assert r.status_code == 422 and said in r.json()["detail"]
    picture = upload(owner)
    r = owner.post(f"/brands/{brand}/voices/clone", json={"name": "P", "sample_file_id": picture})
    assert r.status_code == 422
    r = owner.post(f"/brands/{brand}/voices/clone",
                   json={"name": " ", "sample_file_id": _sample(owner)})  # fmt: skip
    assert r.status_code == 422
    assert db.query(Job).count() == 0


def test_an_editors_clone_waits_for_the_owner_and_a_failed_one_says_so(app, db, owner, editor):
    brand = first_brand(owner)
    body = {"name": "Ed", "sample_file_id": _sample(editor)}
    made = editor.post(f"/brands/{brand}/voices/clone", json=body).json()
    job = db.query(Job).filter_by(kind="voice").one()
    assert job.status == JobStatus.needs_owner_approval
    assert (made["state"], made["error"]) == ("cloning", voices.HELD)
    assert usage.what(db, job) == "Voice clone · Ed"  # Usage and My requests, not "Quick clip"
    job.status, job.error = JobStatus.failed, "The voice service failed."
    db.commit()
    ed = next(v for v in _saved(editor, brand) if v["name"] == "Ed")
    assert (ed["state"], ed["error"]) == ("failed", "The voice service failed.")


def test_a_clone_unused_for_7_days_is_shown_and_refused_plainly_never_swapped(db, owner):
    brand = first_brand(owner)
    pickle = _pickle(db, _ws(db))
    pickle.last_used_at = utcnow() - timedelta(days=6)
    db.commit()
    assert voices.state(db, pickle)[0] == "may_expire"
    pickle.last_used_at = utcnow() - timedelta(days=8)
    db.commit()
    status, why = voices.state(db, pickle)
    assert status == "expired" and why == voices.GONE.format(name="Dr. Pickle", credits="29.18")
    with pytest.raises(HTTPException) as no:
        voices.narration_job(db, pickle.workspace_id, None, WORDS, f"voice:{pickle.id}")
    assert no.value.status_code == 409 and "Clone it again" in no.value.detail
    listed = next(v for v in _saved(owner, brand) if v["id"] == pickle.id)
    assert listed["state"] == "expired" and "7 days" in listed["error"]


def test_dr_pickles_narration_is_read_by_its_clone_on_speech_02_hd(db, owner):
    ws = _ws(db)
    pickle = _pickle(db, ws)
    pickle.last_used_at = utcnow()
    db.commit()
    made = voices.narration_job(
        db,
        ws,
        None,
        WORDS,
        f"voice:{pickle.id}",
        emotion="angry",
        reading="Your gut is a mess. <#0.3#> Resilia fixes it.",
    )
    assert made["model"] == "minimax-speech-02-hd" and made["saved_voice"] == pickle.id
    sent = made["input"]
    assert (sent["voice_id"], sent["emotion"]) == ("R8_CJRWYITM", "angry")
    assert sent["text"] == "Your gut is a mess. <#0.3#> Resilia fixes it."
    assert narration.characters(made) == len(sent["text"])  # priced on what's read
    again = narration.delivery(made)  # a remake or retry keeps its delivery (QA on #1314)
    assert again == {"emotion": "angry", "reading": sent["text"], "speed": sent["speed"]}
    faster = voices.narration_job(
        db,
        ws,
        None,
        WORDS,
        f"voice:{pickle.id}",
        speed=1.4,
        **{k: v for k, v in again.items() if k != "speed"},
    )  # the measured pace's speed
    assert faster["input"]["speed"] == 1.4
    with pytest.raises(HTTPException, match="sounds"):  # 02 reads no (breath)
        voices.narration_job(
            db,
            ws,
            None,
            WORDS,
            f"voice:{pickle.id}",
            reading="(breath) Your gut is a mess. Resilia fixes it.",
        )
    with pytest.raises(HTTPException):
        voices.narration_job(db, ws + 99, None, WORDS, f"voice:{pickle.id}")  # another workspace's


def test_minimax_saying_the_clone_is_gone_marks_it_lost(db, owner):
    ws = _ws(db)
    pickle = _pickle(db, ws)
    job = Job(workspace_id=ws, kind="speech", provider="replicate", status=JobStatus.failed,
              input={"step": "song_take", "saved_voice": pickle.id},
              error_detail="voice id not exist (2054)")  # fmt: skip
    db.add(job)
    db.flush()
    voices.failed(db, job)
    assert pickle.lost_at and "no longer has Dr. Pickle's cloned voice" in job.error
    assert voices.state(db, pickle)[0] == "expired"


def test_a_dr_pickle_presenter_is_narrated_in_its_clone(app, db, owner, monkeypatch):
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)
    body = {"type": "presenter", "look": "dr-pickle", "shape": "9:16", "text": WORDS,
            "brand_id": first_brand(owner)}  # fmt: skip
    fs = owner.post("/freestyles", json=body)
    assert fs.status_code in (200, 201), fs.text
    _run(app, db, ticks=40)
    video = db.get(Project, db.get(Freestyle, fs.json()["id"]).project_id,
                   execution_options={"see_hidden": True})  # fmt: skip
    speech = [j for j in db.query(Job).filter(Job.project_id == video.id, Job.kind == "speech")]
    assert speech, "no narration was made"
    pickle = db.query(Voice).filter_by(look="dr-pickle").one()
    assert speech[0].input["model"] == "minimax-speech-02-hd"
    assert speech[0].input["input"]["voice_id"] == "R8_CJRWYITM"
    assert director_song._voice(db, video) == f"voice:{pickle.id}"
    shown = director_song.state(db, video)["voice"]
    assert shown["name"] == "Dr. Pickle" and shown["expires_at"]


def test_replicate_keeps_a_clones_named_output_and_downloads_its_preview():
    done = {"id": "c1", "status": "succeeded", "version": get_model(voices.CLONER).provider_version,
            "input": {"model": "speech-02-hd"}, "metrics": {"predict_time": 10.9},
            "output": {"voice_id": "R8_TEST", "model": "speech-02-hd",
                       "preview": "https://replicate.delivery/p.mp3"}}  # fmt: skip
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=done)))
    got = ReplicateProvider("https://replicate.test/v1", client=client, token="t").poll("c1")
    assert got.output == {"fields": done["output"]}
    assert got.files == ["https://replicate.delivery/p.mp3"]
    (used,) = got.usage
    assert used.cost_usd == Decimal("3")  # one clone, $3


def test_a_character_has_one_voice_saved_or_from_the_app_and_its_host_speaks_in_it(
    db, owner, monkeypatch
):
    ws = _ws(db)
    pickle = _pickle(db, ws)
    db.commit()
    mark = owner.post("/library/character", json={"name": "Mark", "voice_stock_key": "Roger"})
    assert mark.status_code == 201, mark.text
    mark = mark.json()
    assert (mark["voice_stock_key"], mark["voice_id"]) == ("Roger", None)
    url = f"/library/character/{mark['id']}"
    both = owner.patch(url, json={"voice_id": pickle.id})
    assert both.status_code == 422 and "one voice" in both.json()["detail"]
    moved = owner.patch(url, json={"voice_id": pickle.id, "voice_stock_key": None}).json()
    assert (moved["voice_id"], moved["voice_stock_key"]) == (pickle.id, None)
    assert owner.patch(url, json={"voice_id": None}).json()["voice_id"] is None  # neither
    assert owner.patch(url, json={"voice_stock_key": "Morgan"}).status_code == 422
    assert owner.patch(url, json={"voice_id": 9999}).status_code == 404
    place = owner.post("/library/place", json={"name": "Kitchen", "voice_stock_key": "Roger"})
    assert place.status_code == 422

    item = db.get(LibraryItem, mark["id"])
    video = Project(workspace_id=ws, look="ugc")
    monkeypatch.setattr("app.host.presents", lambda db, project: True)
    monkeypatch.setattr("app.host.host_look", lambda db, project: item)
    item.voice_stock_key, item.voice_id = "Roger", None
    assert voices.default_for(db, video) == "Roger"
    item.voice_stock_key, item.voice_id = None, pickle.id
    assert voices.default_for(db, video) == f"voice:{pickle.id}"


def _wav(seconds: float) -> bytes:
    command = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"sine=f=200:d={seconds}",
               "-ar", "8000", "-ac", "1", "-f", "wav", "-"]  # fmt: skip
    return subprocess.run(command, capture_output=True, check=True).stdout  # noqa: S603


def _m4a(seconds: float) -> bytes:
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "s.m4a"
        command = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"sine=f=200:d={seconds}",
                   "-c:a", "aac", "-b:a", "32k", str(out)]  # fmt: skip
        subprocess.run(command, check=True)  # noqa: S603
        return out.read_bytes()


def test_the_sample_limits_and_its_three_kinds(app, db, owner, monkeypatch):
    """MiniMax's docs: MP3, M4A or WAV, 10 s to 5 min, under 20 MB; checked before any spend."""
    brand = first_brand(owner)
    url = f"/brands/{brand}/voices/clone"
    for name, data, kind in (("w.wav", _wav(12), "audio/wav"), ("m.m4a", _m4a(12), "audio/mp4")):
        sample = upload(owner, name, data, kind)
        assert owner.post(url, json={"name": name, "sample_file_id": sample}).status_code == 201
    long = upload(owner, "long.mp3", _audio(301), "audio/mpeg")
    r = owner.post(url, json={"name": "Long", "sample_file_id": long})
    assert r.status_code == 422 and "5 minutes at most" in r.json()["detail"]
    big = db.get(StoredFile, _sample(owner))
    big.size = 20 * 1024 * 1024  # the file's recorded size, as uploaded
    db.commit()
    r = owner.post(url, json={"name": "Big", "sample_file_id": big.id})
    assert r.status_code == 422 and "under 20 MB" in r.json()["detail"]

    hung = _sample(owner)

    def hangs(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 60)

    monkeypatch.setattr("app.voices.subprocess.run", hangs)
    r = owner.post(url, json={"name": "Hung", "sample_file_id": hung})
    assert (r.status_code, r.json()["detail"]) == (422, voices.SAMPLE_UNREADABLE)
    assert db.query(Job).filter_by(kind="voice").count() == 2  # only the WAV and the M4A


def test_a_brands_voice_is_that_brands_own_and_a_styles_voice_is_everyones(db, owner):
    a = first_brand(owner)
    b = owner.post("/brands", json={"name": "Other Brand"}).json()["id"]
    ws = _ws(db)
    pickle = _pickle(db, ws)
    mark = Voice(workspace_id=ws, brand_id=a, name="Mark", kind="cloned", provider="minimax",
                 provider_voice_id="R8_MARK", speech_model=voices.SPEAKS, cloned_at=utcnow(),
                 last_used_at=utcnow())  # fmt: skip
    db.add(mark)
    db.commit()
    assert voices.named(db, ws, f"voice:{mark.id}", a) is mark
    assert voices.named(db, ws, f"voice:{mark.id}", b) is None
    assert voices.named(db, ws, f"voice:{pickle.id}", b) is pickle
    with pytest.raises(HTTPException):
        voices.narration_job(db, ws, b, WORDS, f"voice:{mark.id}")
    assert voices.narration_job(db, ws, a, WORDS, f"voice:{mark.id}")["input"]["voice_id"] == (
        "R8_MARK")  # fmt: skip
    other = owner.post("/library/character",
                       json={"name": "Bo", "brand_ids": [b], "voice_id": mark.id})  # fmt: skip
    assert other.status_code == 422 and "another brand" in other.json()["detail"]
    own = owner.post("/library/character",
                     json={"name": "Mo", "brand_ids": [a], "voice_id": mark.id})  # fmt: skip
    assert own.status_code == 201, own.text
    styled = owner.post("/library/character",
                        json={"name": "Jo", "brand_ids": [b], "voice_id": pickle.id})  # fmt: skip
    assert styled.status_code == 201, styled.text


def test_a_removed_voice_never_stops_its_presenter_and_says_what_to_do(db, owner, monkeypatch):
    brand = first_brand(owner)
    ws = _ws(db)
    pickle = _pickle(db, ws)
    pickle.last_used_at = utcnow()
    mark = Voice(workspace_id=ws, brand_id=brand, name="Mark's clone", kind="cloned",
                 provider="minimax", provider_voice_id="R8_MARK", speech_model=voices.SPEAKS,
                 cloned_at=utcnow(), last_used_at=utcnow(), archived_at=utcnow())  # fmt: skip
    db.add(mark)
    db.flush()
    item = LibraryItem(workspace_id=ws, kind=Kind.character, name="Mark", voice_id=mark.id)
    db.add(item)
    db.commit()
    monkeypatch.setattr("app.host.presents", lambda db, project: True)
    monkeypatch.setattr("app.host.host_look", lambda db, project: item)
    video = Project(workspace_id=ws, brand_id=brand, look="dr-pickle")
    assert voices.default_for(db, video) == f"voice:{pickle.id}"  # the style's voice instead
    note = voices.host_note(db, video)
    assert "Mark's voice, Mark's clone" in note and "Pick another voice for Mark in Cast" in note
    with pytest.raises(HTTPException) as no:
        voices.narration_job(db, ws, brand, WORDS, f"voice:{mark.id}")
    assert no.value.status_code == 422 and "was removed" in no.value.detail
    mark.archived_at = None
    assert voices.default_for(db, video) == f"voice:{mark.id}" and voices.host_note(db, video) == ""


def test_a_clone_on_02_hd_refuses_sounds_in_the_scripts_own_words_too(db, owner):
    ws = _ws(db)
    pickle = _pickle(db, ws)
    pickle.last_used_at = utcnow()
    db.commit()
    with pytest.raises(HTTPException, match="sounds"):
        voices.narration_job(db, ws, None, "Your gut is a mess. (breath) Resilia fixes it.",
                             f"voice:{pickle.id}")  # fmt: skip


def test_a_description_picks_the_nearest_app_voice_the_same_way_every_time():
    """Reed, 6 Nov: "Describe it" makes no voice; the words pick the nearest app voice by its
    own descriptors (gender, age, tone), with no model call."""
    picks = {
        "late 40s, tired, warm": "English_Graceful_Lady",  # older, warm
        "late 30s, dry, quick": "English_Upbeat_Woman",  # quick: upbeat
        "deep male voice": "Austin",
        "tired dad in his 50s": "Roger",  # a man, relaxed; no older man to prefer
        "calm man, serious": "English_Trustworth_Man",
        "young guy, chatty": "English_FriendlyPerson",
        "confident woman": "English_ConfidentWoman",
        "a 25 year old woman, warm": "Sarah",  # young: never the older lady
        "British accent": "Sarah",  # nothing it knows: the narrator's default
    }
    assert {said: voices.closest(said) for said in picks} == picks
    assert all(voices.closest("late 40s, tired, warm") == picks["late 40s, tired, warm"]
               for _ in range(3))  # fmt: skip


def test_a_described_voice_is_the_brands_and_is_read_in_its_app_voice(db, owner):
    """A described voice is saved to the brand with its words, played with its app voice's
    free sample, usable for a video, and narrated as that app voice: never cloned, nothing
    paid."""
    from app.models.accounts import User

    brand = first_brand(owner)
    user = db.query(User).order_by(User.id).first()  # the owner
    dana = voices.describe(db, user, brand, "  late 30s,  dry, quick ", "Dana")
    db.commit()
    assert (dana.kind, dana.description, dana.provider_voice_id) == (
        "described", "late 30s, dry, quick", "English_Upbeat_Woman")  # fmt: skip
    assert voices.describe(db, user, brand, "Late 30s, dry, quick").id == dana.id  # the same
    plain = voices.describe(db, user, brand, "deep male voice")
    assert plain.name == "Described voice" and plain.provider_voice_id == "Austin"
    db.commit()
    (row,) = [v for v in _saved(owner, brand) if v["id"] == dana.id]
    assert (row["kind"], row["stock_key"], row["uses"], row["state"]) == (
        "described", "English_Upbeat_Woman", "Upbeat Woman", "ready")  # fmt: skip
    assert row["sample_url"] == "/voices/samples/English_Upbeat_Woman.mp3"
    said = f"voice:{dana.id}"
    assert voices.usable(db, user.workspace_id, brand, said)
    made = voices.narration_job(db, user.workspace_id, brand, WORDS, said, emotion="calm")
    expected = narration.job(WORDS, "English_Upbeat_Woman", "", "calm")
    assert made == {**expected, "saved_voice": dana.id}
    sarah = voices.describe(db, user, brand, "warm narrator")
    assert voices.narration_job(db, user.workspace_id, brand, WORDS, f"voice:{sarah.id}") == {
        **narration.job(WORDS, "Sarah"),
        "saved_voice": sarah.id,
    }  # an ElevenLabs voice too
    assert db.query(Job).count() == 0  # nothing made, nothing charged
    with pytest.raises(HTTPException):
        voices.describe(db, user, brand, "   ")
