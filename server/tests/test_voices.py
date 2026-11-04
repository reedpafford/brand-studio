"""Voices (v6 S8-04): a brand's voices with free samples, an app voice saved to a brand, a
voice cloned from a sample (priced first, held for the owner when an editor asks), remove with
Undo, and Dr. Pickle's clone as that style's narrator, with its 7-day expiry said plainly.
Stand-ins and a mocked Replicate only: no paid calls."""

import subprocess
from datetime import timedelta
from decimal import Decimal

import httpx2 as httpx
import pytest
from fastapi import HTTPException

from app import director_song, narration, voices
from app.catalogue import get_model
from app.db import utcnow
from app.models.accounts import Workspace
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


def test_the_brands_voices_list_dr_pickles_clone_with_its_sample_and_expiry(db, owner):
    brand = first_brand(owner)
    body = _list(owner, brand)
    (pickle,) = body["voices"]
    assert (pickle["name"], pickle["kind"], pickle["look"], pickle["brand_id"]) == (
        "Dr. Pickle", "cloned", "dr-pickle", None)  # fmt: skip
    assert pickle["sample_url"].endswith("/voices/samples/dr-pickle.mp3")
    assert owner.get(pickle["sample_url"]).headers["content-type"] == "audio/mpeg"
    row = db.get(Voice, pickle["id"])
    assert (row.provider_voice_id, row.speech_model) == ("R8_CJRWYITM", "minimax-speech-02-hd")
    assert voices.expires_at(row) == row.last_used_at + timedelta(days=7)
    assert body["clone_credits"] == 29.18 and body["clone_usd"] == 3.0  # $3 once
    assert len(_list(owner, brand)["voices"]) == 1  # made once per workspace


def test_every_app_voice_is_offered_with_a_free_sample_where_a_test_made_one(owner, editor):
    brand = first_brand(owner)
    listed = {
        v["stock_key"]: v for v in _list(editor, brand, all=True)["voices"] if v["id"] is None
    }
    assert list(listed) == voices.stock_keys() and "Roger" in listed
    assert listed["Roger"]["provider"] == "elevenlabs" and listed["Roger"]["sample_url"]
    assert listed["English_FriendlyPerson"]["provider"] == "minimax"
    assert listed["Sarah"]["sample_url"] is None  # no paid test made one yet
    assert _list(editor, brand)["clone_usd"] is None  # editors never see dollars
    assert editor.get("/voices/samples/..%2Fvoices.mp3").status_code == 404


def test_an_app_voice_is_saved_to_a_brand_free_once_and_removed_with_undo(db, owner, editor):
    brand = first_brand(owner)
    saved = editor.post(f"/brands/{brand}/voices", json={"stock_key": "Roger"})
    assert saved.status_code == 201, saved.text
    assert (saved.json()["kind"], saved.json()["brand_id"]) == ("stock", brand)
    again = editor.post(f"/brands/{brand}/voices", json={"stock_key": "Roger"})
    assert again.status_code == 409
    assert editor.post(f"/brands/{brand}/voices", json={"stock_key": "Morgan"}).status_code == 422
    rows = _list(editor, brand, all=True)["voices"]
    assert [v["id"] is None for v in rows if v["stock_key"] == "Roger"] == [False]
    assert db.query(Job).count() == 0  # free

    roger = saved.json()["id"]
    item = LibraryItem(workspace_id=db.get(Voice, roger).workspace_id, kind=Kind.character,
                       name="Mark", voice_id=roger)  # fmt: skip
    db.add(item)
    db.commit()
    assert next(v for v in _list(editor, brand)["voices"] if v["id"] == roger)["used_by"] == [
        item.id]  # fmt: skip

    assert editor.delete(f"/voices/{roger}").status_code == 204
    assert roger not in [v["id"] for v in _list(editor, brand)["voices"]]
    assert editor.post(f"/voices/{roger}/restore").json()["id"] == roger
    assert editor.post(f"/voices/{roger}/restore").status_code == 409


def test_a_styles_own_voice_is_removed_by_the_owner_only(owner, editor):
    brand = first_brand(owner)
    pickle = _list(owner, brand)["voices"][0]["id"]
    assert editor.delete(f"/voices/{pickle}").status_code == 403
    assert owner.delete(f"/voices/{pickle}").status_code == 204
    assert _list(owner, brand)["voices"] == []  # stays removed, never made again
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
    mark = next(v for v in _list(owner, brand)["voices"] if v["name"] == "Mark")
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
    job.status, job.error = JobStatus.failed, "The voice service failed."
    db.commit()
    ed = next(v for v in _list(editor, brand)["voices"] if v["name"] == "Ed")
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
        voices.narration_job(db, pickle.workspace_id, WORDS, f"voice:{pickle.id}")
    assert no.value.status_code == 409 and "Clone it again" in no.value.detail
    listed = next(v for v in _list(owner, brand)["voices"] if v["id"] == pickle.id)
    assert listed["state"] == "expired" and "7 days" in listed["error"]


def test_dr_pickles_narration_is_read_by_its_clone_on_speech_02_hd(db, owner):
    ws = _ws(db)
    pickle = _pickle(db, ws)
    pickle.last_used_at = utcnow()
    db.commit()
    made = voices.narration_job(
        db,
        ws,
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
    with pytest.raises(HTTPException, match="sounds"):  # 02 reads no (breath)
        voices.narration_job(
            db,
            ws,
            WORDS,
            f"voice:{pickle.id}",
            reading="(breath) Your gut is a mess. Resilia fixes it.",
        )
    with pytest.raises(HTTPException):
        voices.narration_job(db, ws + 99, WORDS, f"voice:{pickle.id}")  # another workspace's


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
