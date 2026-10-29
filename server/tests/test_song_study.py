"""Study a song ad (flows S3a): free, on the stand-ins; its sections, BPM, words and frames;
Use as a guide, Remove and Undo; it never touches the lyrics or the style line (rule 19)."""

from pathlib import Path

import pytest

from app import song_study
from app.models.files import StoredFile
from app.models.jobs import Job
from app.models.script_library import ScriptDraft
from app.providers.fake_local import STUDY, hear_study, refuse_link, transcript
from app.providers.fake_local import two_scenes as _clip
from app.providers.local import LocalProvider
from app.worker import run_once
from tests.test_music import LYRICS


@pytest.fixture(scope="module")
def clip(tmp_path_factory) -> Path:
    return _clip(tmp_path_factory.mktemp("ad") / "two.mp4")


@pytest.fixture
def song(owner):
    brand = owner.get("/brands").json()[0]["id"]
    made = owner.post("/scripts", json={"brand_id": brand, "title": "Paws", "kind": "song",
                                         "text": LYRICS})  # fmt: skip
    sid = made.json()["id"]
    owner.put(f"/scripts/{sid}/drafts/0", json={"text": LYRICS, "style_line": "pop"})
    return sid


def _work(app, db):
    local = LocalProvider(app.state.storage, transcribe=transcript, fetch_link=refuse_link,
                          hear_study=hear_study)  # fmt: skip
    run_once(db, {"local": local}, app.state.storage, allow_paid=False)  # free: runs with it off


def _upload(client, sid, clip: Path):
    with clip.open("rb") as f:
        files = {"file": ("ad.mp4", f, "video/mp4")}
        return client.post(f"/scripts/{sid}/drafts/0/song-study", files=files)


def _study(client, sid):
    return client.get(f"/scripts/{sid}").json()["versions"][0]["song_study"]


def _line(text, start, end):
    return {"text": text, "start": start, "end": end}


def test_sections_are_found_from_pauses_and_repeated_lines():
    beats = [round(k * 0.5, 2) for k in range(120)]  # 120 BPM: a bar every 2 s
    gut = "that's my gut breaking down"
    lines = [_line("we walk the dog at dawn", 2.1, 4), _line("he will not eat a thing", 4.1, 6),
             _line(gut, 8.1, 10), _line(gut, 10.1, 12), _line("then we found the scoop", 14.1, 16),
             _line(gut, 18.1, 20), _line("brand new pup", 22.1, 24),
             _line(gut, 26.1, 28)]  # fmt: skip
    found = song_study.sections(lines, beats, 120, 32)
    assert [(p["name"], p["start"], p["end"], p["guessed"]) for p in found] == [
        ("Intro", 0, 2, False), ("Verse", 2, 8, False), ("Chorus", 8, 14, False),
        ("Verse", 14, 18, False), ("Chorus", 18, 22, False), ("Bridge", 22, 26, True),
        ("Chorus", 26, 28, False), ("Outro", 28, 32, False),
    ]  # fmt: skip
    assert found[2]["lines"] == [gut, gut]

    plain = song_study.sections(lines[:2], beats, 120, 6)  # nothing repeats: the name's a guess
    assert [(p["name"], p["guessed"]) for p in plain] == [("Intro", False), ("Verse", True)]
    assert song_study.sections([], beats, 120, 6) == []


def test_an_uploaded_song_ad_is_studied_for_free(app, db, owner, song, clip):
    made = _upload(owner, song, clip)
    assert made.status_code == 201, made.text
    assert made.json()["credits"] == 0
    studying = _study(owner, song)
    assert studying["status"] == "studying" and studying["job"]["id"] == made.json()["id"]
    assert studying["job"]["status"] == "queued"
    again = _upload(owner, song, clip)  # one at a time on a version
    assert (again.status_code, again.json()["detail"]) == (409, song_study.BUSY)
    upload_id = db.get(Job, made.json()["id"]).input["video_file_id"]
    assert db.get(StoredFile, upload_id) is not None

    _work(app, db)  # with generation off: it's free
    study = _study(owner, song)
    assert study["status"] == "done" and study["source"] == "upload" and study["use_as_guide"]
    assert study["seconds"] == pytest.approx(6, abs=0.2)
    assert [x["text"] for x in study["lines"]] == STUDY
    assert len(study["words"]) == sum(len(t.split()) for t in STUDY)
    assert [p["name"] for p in study["sections"]][:4] == ["Verse", "Chorus", "Verse", "Chorus"]
    assert [round(f["t"]) for f in study["frames"]] == [2, 4]  # one from each shot's middle
    assert owner.get(f"/files/{study['frames'][0]['file_id']}").status_code == 200
    db.expire_all()
    assert db.get(StoredFile, upload_id) is None  # only the study and its frames are kept
    version = owner.get(f"/scripts/{song}").json()["versions"][0]
    assert (version["text"], version["style_line"]) == (LYRICS.strip(), "pop")  # rule 19

    old_frames = [f["file_id"] for f in study["frames"]]  # a new study replaces it once saved
    assert _upload(owner, song, clip).status_code == 201
    assert _study(owner, song)["attempt"]["status"] == "studying"
    _work(app, db)
    db.expire_all()
    newer = _study(owner, song)
    assert newer["attempt"] is None and newer["frames"][0]["file_id"] not in old_frames
    assert all(db.get(StoredFile, i) for i in old_frames)  # the next press deletes them
    assert _upload(owner, song, clip).status_code == 201
    db.expire_all()
    assert all(db.get(StoredFile, i) is None for i in old_frames)


def test_use_as_guide_remove_and_undo(app, db, owner, song, clip):
    _upload(owner, song, clip)
    _work(app, db)
    draft_id = db.query(ScriptDraft).filter_by(script_id=song, slot=0).one().id
    url = f"/scripts/{song}/drafts/0/song-study"
    assert song_study.guide(db.get(ScriptDraft, draft_id))["seconds"]

    assert owner.patch(url, json={"use_as_guide": False}).status_code == 204
    db.expire_all()
    assert song_study.guide(db.get(ScriptDraft, draft_id)) is None
    assert _study(owner, song)["use_as_guide"] is False
    owner.patch(url, json={"use_as_guide": True})

    assert owner.delete(url).status_code == 204
    assert _study(owner, song) is None
    db.expire_all()
    assert song_study.guide(db.get(ScriptDraft, draft_id)) is None
    assert owner.post(f"{url}/restore").status_code == 204  # Undo
    assert _study(owner, song)["status"] == "done"


def test_a_link_that_cant_be_fetched_says_why(app, db, owner, song):
    url = f"/scripts/{song}/drafts/0/song-study"
    made = owner.post(url, data={"url": "https://www.instagram.com/reel/DehudnaAmce/"})
    assert made.status_code == 201, made.text
    _work(app, db)
    study = _study(owner, song)
    assert study["status"] == "failed" and study["problem_code"] == "blocked"
    assert study["problem"] == song_study.PROBLEMS["blocked"] and study["job"] is None
    assert study["link"] == "https://www.instagram.com/reel/DehudnaAmce/"
    assert owner.patch(url, json={"use_as_guide": True}).status_code == 409  # nothing to use


def test_wrong_input_is_refused_in_plain_words(app, db, owner, song, clip, tmp_path):
    url = f"/scripts/{song}/drafts/0/song-study"
    bad = owner.post(url, data={"url": "https://example.com/ad"})
    assert (bad.status_code, bad.json()["detail"]) == (422, song_study_routes().NOT_A_LINK)
    assert owner.post(url, data={}).status_code == 422
    brand = owner.get("/brands").json()[0]["id"]
    story = owner.post("/scripts", json={"brand_id": brand, "title": "Story"}).json()["id"]
    assert _upload(owner, story, clip).status_code == 409

    _upload(owner, song, _clip(tmp_path / "mute.mp4", sound=False))
    _work(app, db)
    study = _study(owner, song)
    assert study["status"] == "failed" and study["problem_code"] == "bad_file"


def test_a_failed_job_shows_as_failed_and_a_silent_ad_has_no_shape(app, db, owner, song, clip):
    _upload(owner, song, clip)
    local = LocalProvider(app.state.storage, hear_study=lambda path, watch: [])
    run_once(db, {"local": local}, app.state.storage, allow_paid=False)
    study = _study(owner, song)
    assert (study["status"], study["problem"]) == ("failed", song_study.PROBLEMS["no_words"])

    def broken(path, watch):
        raise RuntimeError("Reading the song ad's words failed (1).")

    _upload(owner, song, clip)
    local = LocalProvider(app.state.storage, hear_study=broken)
    run_once(db, {"local": local}, app.state.storage, allow_paid=False)
    study = _study(owner, song)
    assert (study["status"], study["problem"]) == ("failed", song_study.FAILED)
    assert study["job"]["status"] == "failed"


def song_study_routes():
    from app.routes import song_study as routes

    return routes


def test_whisper_keeps_each_lines_words_for_a_study(monkeypatch, capsys):
    import json
    import sys
    import types

    from app import whisper

    def seg(text, start, end, **sure):
        words = [types.SimpleNamespace(word=f" {w}", start=start, end=end) for w in text.split()]
        return types.SimpleNamespace(text=f" {text}", start=start, end=end, words=words, **sure)

    class Model:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, path, **kwargs):
            said = dict(no_speech_prob=0.1, avg_logprob=-0.3)
            invented = dict(no_speech_prob=0.9, avg_logprob=-1.4)  # over the music bed
            return [seg("my gut", 0.5, 1.0, **said), seg("thanks", 2.0, 3.0, **invented)], None

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=Model))
    whisper.main("ad.mp4", study=True)
    assert json.loads(capsys.readouterr().out) == [
        {"start": 0.5, "end": 1.0, "text": "my gut", "speaker": None,
         "words": [{"word": "my", "start": 0.5, "end": 1.0},
                   {"word": "gut", "start": 0.5, "end": 1.0}]}
    ]  # fmt: skip


@pytest.mark.whisper
def test_the_real_speech_model_studies(clip):  # opt in: uv run pytest -m whisper
    heard = song_study.hear(clip, song_study.Watch())
    assert isinstance(heard, list) and all("words" in x for x in heard)


def test_a_failed_studys_upload_is_tidied_when_replaced(app, db, owner, song, clip):
    made = _upload(owner, song, clip).json()
    local = LocalProvider(app.state.storage, hear_study=lambda path, watch: 1 / 0)  # the job fails
    run_once(db, {"local": local}, app.state.storage, allow_paid=False)
    upload_id = db.get(Job, made["id"]).input["video_file_id"]
    assert db.get(StoredFile, upload_id) is not None  # its bytes are gone, its row isn't
    assert _upload(owner, song, clip).status_code == 201
    db.expire_all()
    assert db.get(StoredFile, upload_id) is None


def test_a_failed_or_cancelled_restudy_keeps_the_good_study(app, db, owner, song, clip):
    _upload(owner, song, clip)
    _work(app, db)
    good = _study(owner, song)
    draft_id = db.query(ScriptDraft).filter_by(script_id=song, slot=0).one().id
    url = f"/scripts/{song}/drafts/0/song-study"

    owner.post(url, data={"url": "https://www.instagram.com/reel/DehudnaAmce/"})  # can't fetch
    _work(app, db)
    db.expire_all()
    study = _study(owner, song)
    assert study["status"] == "done" and study["frames"] == good["frames"]  # A still shows
    assert study["attempt"]["status"] == "failed"
    assert study["attempt"]["problem"] == song_study.PROBLEMS["blocked"]
    assert song_study.guide(db.get(ScriptDraft, draft_id))["seconds"] == good["seconds"]
    assert all(owner.get(f"/files/{f['file_id']}").status_code == 200 for f in good["frames"])

    job = _upload(owner, song, clip).json()  # a cancelled try is as if never pressed
    assert owner.post(f"/jobs/{job['id']}/cancel").status_code in (200, 204)
    study = _study(owner, song)
    assert study["status"] == "done" and study["attempt"] is None
    assert owner.delete(url).status_code == 204  # nothing running now


def test_reading_the_words_stops_at_stop_or_the_time_limit():
    import sys
    import time

    from app import reel

    slow = [sys.executable, "-c", "import time; time.sleep(30)"]
    began = time.monotonic()
    with pytest.raises(song_study.Stopped):
        song_study.wait(slow, song_study.Watch(stopped=lambda: True))
    with pytest.raises(reel.Refused) as no:
        song_study.wait(slow, song_study.Watch(until=time.monotonic()))
    assert no.value.code == "too_slow" and time.monotonic() - began < 5  # killed, not waited
    assert song_study.wait([sys.executable, "-c", "print(1)"], song_study.Watch()) == b"1\n"


def test_stop_ends_a_running_study_and_keeps_the_finished_one(app, db, owner, song, clip):
    _upload(owner, song, clip)
    _work(app, db)
    good = _study(owner, song)
    url = f"/scripts/{song}/drafts/0/song-study"
    assert owner.post(f"{url}/stop").status_code == 409  # nothing is being studied

    job = _upload(owner, song, clip).json()
    marker = song_study.stop_key(job["id"])

    def pressed_while_reading(path, watch):
        assert owner.post(f"{url}/stop").status_code == 204  # Stop, mid-read
        assert app.state.storage.exists(marker)
        watch.check()  # what the real reader does every half second
        raise AssertionError("not stopped")

    local = LocalProvider(app.state.storage, hear_study=pressed_while_reading)
    run_once(db, {"local": local}, app.state.storage, allow_paid=False)
    db.expire_all()
    assert db.get(Job, job["id"]).status == "cancelled" and db.get(Job, job["id"]).credits == 0
    assert not app.state.storage.exists(marker)
    study = _study(owner, song)
    assert study["status"] == "done" and study["frames"] == good["frames"]
    assert study["attempt"] is None  # as if never pressed

    job = _upload(owner, song, clip).json()  # Stop before it starts: cancelled, no marker
    assert owner.post(f"{url}/stop").status_code == 204
    assert db.get(Job, job["id"]).status == "cancelled"
    assert not app.state.storage.exists(song_study.stop_key(job["id"]))
    assert _upload(owner, song, clip).status_code == 201  # a new study can start at once


def test_a_study_past_the_time_limit_says_so(app, db, owner, song, clip, monkeypatch):
    monkeypatch.setattr(song_study, "LIMIT", -1)
    _upload(owner, song, clip)
    _work(app, db)
    study = _study(owner, song)
    assert (study["status"], study["problem"]) == ("failed", song_study.PROBLEMS["too_slow"])
    assert study["problem_code"] == "too_slow"


def test_stop_as_the_worker_finishes_says_it_finished(app, db, owner, song, clip, monkeypatch):
    job = _upload(owner, song, clip).json()
    original = song_study.update

    def worker_saves_first(*args, **kwargs):  # its save lands between Stop's read and update
        db.query(Job).filter_by(id=job["id"]).update({"status": "succeeded"})
        db.commit()
        return original(*args, **kwargs)

    monkeypatch.setattr(song_study, "update", worker_saves_first)
    no = owner.post(f"/scripts/{song}/drafts/0/song-study/stop")
    assert (no.status_code, no.json()["detail"]) == (409, song_study.JUST_DONE)
    db.expire_all()
    assert db.get(Job, job["id"]).status == "succeeded"  # Stop never claims it stopped it
    assert not app.state.storage.exists(song_study.stop_key(job["id"]))
