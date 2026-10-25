"""Reading an imported reel: one price for watch + write + cast read, all or none against an
editor's allowance, the chain queued step by step (prepaid), a failed step retried from
itself. Stand-in providers only."""

import pytest

from app.models.jobs import Job, JobStatus
from app.models.script_library import Script
from app.prompts import check
from app.providers import get_providers
from app.providers.fake_local import refuse_link, transcript
from app.providers.local import LocalProvider
from app.worker import run_once
from tests.test_reel_import import _clip, _upload


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    return _clip(tmp_path_factory.mktemp("reel") / "two.mp4")


def _drain(app, db):
    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings, app.state.storage)
    providers["local"] = LocalProvider(app.state.storage, transcript, refuse_link)
    for _ in range(8):
        run_once(db, providers, app.state.storage)


def _ready(app, client, db, clip) -> str:
    sid = _upload(client, clip).json()["script_id"]
    _drain(app, db)
    return f"/scripts/{sid}"


def test_one_price_then_watch_write_and_cast_in_turn(app, owner, db, clip):
    url = _ready(app, owner, db, clip)
    ready = owner.get(f"{url}/import").json()
    assert ready["status"] == "ready" and ready["estimate"] == {
        "credits": 7,
        "credits_left": None,
        "tries": 0,
    }
    started = owner.post(f"{url}/import/read")
    assert started.status_code == 201 and started.json()["status"] == "reading"
    _drain(app, db)
    done = owner.get(f"{url}/import").json()
    assert (done["status"], done["steps_done"]) == ("done", ["watch", "write", "cast"])
    steps = [j.input.get("reel_step") for j in db.query(Job).order_by(Job.id)][1:]
    assert steps == ["watch", "write", "cast"]
    watch = db.query(Job).filter(Job.kind == "watch-gemini").one()
    assert watch.input["uploads"] == {"videos": [ready["video_file_id"]]}
    script = owner.get(url).json()
    assert script["reel_imported"] and script["versions"][0]["text"]
    assert script["description"].startswith("A proposal goes wrong")
    assert {s["role"] for s in script["cast"]}
    assert watch.status == JobStatus.succeeded
    shots = db.get(Script, script["id"]).reference_breakdown["shots"]
    assert [(s["speaker"], s["line"]) for s in shots] == [
        ("groom", "Will you marry me?"),
        ("bride", "No."),
    ]
    assert owner.post(f"{url}/import/read").status_code == 409  # nothing left to read


def test_an_editor_past_the_allowance_runs_nothing(app, owner, editor, db, clip):
    owner.put(
        "/credits/limits", json={"weekly_quick_clip_credits": 5, "per_video_max_credits": 729}
    )
    url = _ready(app, editor, db, clip)
    assert editor.get(f"{url}/import").json()["estimate"] == {
        "credits": 7,
        "credits_left": 5,
        "tries": 0,
    }
    declined = editor.post(f"{url}/import/read")
    assert declined.status_code == 409
    assert declined.json()["detail"] == "This reel needs 7 credits; you have 5 left this week."
    assert db.query(Job).count() == 1  # only the free prep


def test_later_steps_are_prepaid(app, owner, editor, db, clip):
    owner.put(
        "/credits/limits", json={"weekly_quick_clip_credits": 7, "per_video_max_credits": 729}
    )
    url = _ready(app, editor, db, clip)
    assert editor.post(f"{url}/import/read").status_code == 201
    owner.put(
        "/credits/limits", json={"weekly_quick_clip_credits": 1, "per_video_max_credits": 729}
    )
    _drain(app, db)  # the allowance shrank after the press: the steps still run
    assert editor.get(f"{url}/import").json()["status"] == "done"


def test_a_failed_watch_stops_and_a_new_press_retries_from_it(app, owner, db, clip, monkeypatch):
    url = _ready(app, owner, db, clip)
    monkeypatch.setattr(check, "reel_watch", lambda w, c, t: ["shot 2 is missing"])
    owner.post(f"{url}/import/read")
    _drain(app, db)
    failed = owner.get(f"{url}/import").json()
    assert (failed["status"], failed["failed_step"]) == ("failed", "watch")
    assert failed["problem"].startswith("Finding the shots didn't finish")
    assert failed["estimate"]["credits"] == 7 and db.query(Job).count() == 2  # no write queued
    assert failed["estimate"]["tries"] == 1  # the screen warns a retry is charged again
    monkeypatch.setattr(check, "reel_watch", lambda w, c, t: [])
    assert owner.post(f"{url}/import/read").status_code == 201
    _drain(app, db)
    assert owner.get(f"{url}/import").json()["status"] == "done"


def test_reading_needs_generation_on(app, owner, db, clip):
    url = _ready(app, owner, db, clip)
    app.state.settings.fake_providers = False
    app.state.settings.generation_enabled = False
    assert owner.post(f"{url}/import/read").status_code == 503


def _write_job(db) -> Job:
    return next(j for j in db.query(Job) if j.input.get("step") == "script_draft")


def test_version_a_keeps_the_reels_lines_by_its_speakers(app, owner, db, clip):
    url = _ready(app, owner, db, clip)
    owner.post(f"{url}/import/read")
    _drain(app, db)
    job = _write_job(db)
    assert job.input["reel_lines"] == ["Will you marry me?", "No."]
    assert "<new_lines>" not in job.input["prompt"] and "</reference>" in job.input["prompt"]
    version = owner.get(url).json()["versions"][0]
    assert "GROOM: Will you marry me?\nBRIDE: No." in version["text"]
    assert (version["changed_lines"], version["problems"]) == ([], [])  # nothing lost


def test_new_lines_tells_the_writer_and_skips_the_word_check(app, owner, db, clip):
    sid = _upload(owner, clip, new_lines="true").json()["script_id"]
    _drain(app, db)
    owner.post(f"/scripts/{sid}/import/read")
    _drain(app, db)
    assert "<new_lines>true</new_lines>" in _write_job(db).input["prompt"]
    problems = owner.get(f"/scripts/{sid}").json()["versions"][0]["problems"]
    assert not any("changed or missing" in p for p in problems)


def test_the_whole_read_is_held_against_the_allowance_until_it_runs(app, owner, editor, db, clip):
    """QA on #292: pressing Read holds all 7 credits, so nothing else can spend them first."""
    owner.put(
        "/credits/limits", json={"weekly_quick_clip_credits": 7, "per_video_max_credits": 729}
    )
    url = _ready(app, editor, db, clip)
    other = _upload(editor, clip).json()["script_id"]
    _drain(app, db)
    assert editor.post(f"{url}/import/read").status_code == 201  # only its watch is queued
    assert editor.get(f"/scripts/{other}/import").json()["estimate"]["credits_left"] == 0
    over = editor.post(f"/scripts/{other}/write")
    assert over.status_code == 409 and "credits" in over.json()["detail"]
    _drain(app, db)
    assert editor.get(f"{url}/import").json()["status"] == "done"  # its steps all ran


def test_a_stopped_read_holds_nothing(app, owner, editor, db, clip, monkeypatch):
    owner.put(
        "/credits/limits", json={"weekly_quick_clip_credits": 10, "per_video_max_credits": 729}
    )
    url = _ready(app, editor, db, clip)
    monkeypatch.setattr(check, "reel_watch", lambda w, c, t: ["shot 2 is missing"])
    editor.post(f"{url}/import/read")
    _drain(app, db)
    status = editor.get(f"{url}/import").json()
    assert status["failed_step"] == "watch"
    assert status["estimate"]["credits_left"] == 9  # only the watch that ran is spent


def test_getting_a_reel_is_free_even_past_the_allowance(app, owner, editor, db, clip):
    """Designer: only the paid Read (and Write all) stop at the allowance, so the editor sees
    the price and the reason in context."""
    plain = editor.post(
        "/scripts", json={"brand_id": editor.get("/brands").json()[0]["id"], "title": "Spent"}
    ).json()["id"]
    assert editor.post(f"/scripts/{plain}/write").status_code == 201  # 3 credits used
    owner.put(
        "/credits/limits", json={"weekly_quick_clip_credits": 1, "per_video_max_credits": 729}
    )
    made = _upload(editor, clip)  # past the allowance (3 of 1), getting a reel is still free
    assert made.status_code == 201, made.text
    _drain(app, db)
    ready = editor.get(f"/scripts/{made.json()['script_id']}/import").json()
    assert ready["status"] == "ready" and ready["estimate"]["credits_left"] == 0
    declined = editor.post(f"/scripts/{made.json()['script_id']}/import/read")
    assert declined.status_code == 409 and "7 credits" in declined.json()["detail"]
