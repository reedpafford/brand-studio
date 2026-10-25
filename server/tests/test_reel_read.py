"""Reading an imported reel: one price for watch + write + cast read, all or none against an
editor's allowance, the chain queued step by step (prepaid), a failed step retried from
itself. Stand-in providers only."""

import pytest
from pydantic import BaseModel, ConfigDict

from app import prompts
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


@pytest.fixture(autouse=True)
def director_stand_ins(monkeypatch):
    """Until the Director's reel_watch prompt, schema and check land (then delete this)."""

    class ReelWatch(BaseModel):
        model_config = ConfigDict(extra="allow")
        logline: str

    system = prompts.system
    monkeypatch.setattr(prompts, "system", lambda s: "watch" if s == "reel_watch" else system(s))
    monkeypatch.setitem(prompts.SCHEMAS, "reel_watch", ReelWatch)
    monkeypatch.setattr(check, "reel_watch", lambda w, c, t: [], raising=False)


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
    assert ready["status"] == "ready" and ready["estimate"] == {"credits": 7, "credits_left": None}
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
    assert editor.get(f"{url}/import").json()["estimate"] == {"credits": 7, "credits_left": 5}
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
    monkeypatch.setattr(check, "reel_watch", lambda w, c, t: [])
    assert owner.post(f"{url}/import/read").status_code == 201
    _drain(app, db)
    assert owner.get(f"{url}/import").json()["status"] == "done"


def test_reading_needs_generation_on(app, owner, db, clip):
    url = _ready(app, owner, db, clip)
    app.state.settings.fake_providers = False
    app.state.settings.generation_enabled = False
    assert owner.post(f"{url}/import/read").status_code == 503
