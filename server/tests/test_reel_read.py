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
    assert watch.input["files"]["videos"] != [ready["video_file_id"]]  # the small copy, inline
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


def test_reading_a_reel_is_never_refused_for_the_week(app, owner, editor, db, clip):
    """One allowance (Reed, 30 Oct): reading a reel is a brand's work, never the week's, so
    an editor with nothing left still reads it and reads it again; no "left" is shown."""
    owner.put(
        "/credits/limits", json={"weekly_quick_clip_credits": 0, "per_video_max_credits": 729}
    )
    url = _ready(app, editor, db, clip)
    assert editor.get(f"{url}/import").json()["estimate"] == {
        "credits": 7,
        "credits_left": None,
        "tries": 0,
    }
    assert editor.post(f"{url}/import/read").status_code == 201
    _drain(app, db)
    assert editor.get(f"{url}/import").json()["status"] == "done"
    assert editor.post(f"{url}/import/read-again", json={}).status_code == 201


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


def test_a_reel_prepared_before_watch_copies_asks_for_a_new_upload(app, owner, db, clip):
    url = _ready(app, owner, db, clip)
    script = db.get(Script, int(url.rsplit("/", 1)[1]))
    script.reel = {k: v for k, v in script.reel.items() if k != "watch_file_id"}
    db.commit()
    refused = owner.post(f"{url}/import/read")
    assert refused.status_code == 409 and "Upload the video again" in refused.json()["detail"]
    all_of_them = owner.post("/scripts/write", json={"script_ids": [script.id]})
    assert all_of_them.json()["detail"] == (
        "1 reel needs the video uploaded again. Upload it or untick it."
    )
    assert db.query(Job).count() == 1  # nothing paid queued


def test_write_refuses_a_script_whose_reel_isnt_read(app, owner, db, clip):
    url = _ready(app, owner, db, clip)
    refused = owner.post(f"{url}/write")
    assert refused.status_code == 409 and refused.json()["detail"] == "Read the reel first."
    owner.post(f"{url}/import/read")
    _drain(app, db)
    assert owner.post(f"{url}/write").status_code == 201  # read: Write redoes the words


def test_a_failing_video_watch_retries_then_watches_from_frames_charged_once(
    app, owner, editor, db, clip, monkeypatch
):
    """The Producer's real read: Gemini's video upload kept failing (E001), images worked."""
    from app.providers.fake_local import FakeMedia

    url = _ready(app, editor, db, clip)
    monkeypatch.setattr(FakeMedia, "video_failures", 2)  # the video and its one retry
    assert editor.post(f"{url}/import/read").status_code == 201
    _drain(app, db)
    done = editor.get(f"{url}/import").json()
    assert (done["status"], done["watched_from"]) == ("done", "frames")
    watches = db.query(Job).filter(Job.kind == "watch-gemini").order_by(Job.id).all()
    assert [(j.status, j.input["watch_mode"]) for j in watches] == [
        ("failed", "video"), ("failed", "video"), ("succeeded", "frames")
    ]  # fmt: skip
    frames = watches[-1].input
    assert "videos" not in frames["files"] and len(frames["files"]["images"]) >= 2
    assert frames["input"]["prompt"].startswith("<watched_from>frames</watched_from>")
    paid = [j for j in db.query(Job).all() if j.status == "succeeded" and j.kind != "reel_prepare"]
    assert sum(j.credits for j in paid) == 7  # one watch, one write, one cast read: failures free


def test_a_video_watch_that_works_on_retry_stays_video(app, owner, db, clip, monkeypatch):
    from app.providers.fake_local import FakeMedia

    url = _ready(app, owner, db, clip)
    monkeypatch.setattr(FakeMedia, "video_failures", 1)
    owner.post(f"{url}/import/read")
    _drain(app, db)
    assert owner.get(f"{url}/import").json()["watched_from"] == "video"


def _read(app, client, db, clip) -> str:
    url = _ready(app, client, db, clip)
    client.post(f"{url}/import/read")
    _drain(app, db)
    return url


def test_read_it_again_redoes_the_breakdown_and_script_with_the_note(app, owner, db, clip):
    """reel-import.md §5: priced first; the note goes to the watch; the download, transcript
    and cast are kept; an unedited script is filled again."""
    url = _read(app, owner, db, clip)
    done = owner.get(f"{url}/import").json()
    assert done["read_again_credits"] > 0 and done["edited_since_fill"] is False
    jobs = db.query(Job).count()
    said = owner.post(f"{url}/import/read-again", json={"note": "Change the line to “Yes.”"})
    assert (said.status_code, said.json()["detail"]) == (422, check.READ_AGAIN)
    quoted = owner.post(f"{url}/import/read-again", json={"note": 'She says "Maybe."'})
    assert quoted.status_code == 422  # words nobody says in the reel
    assert db.query(Job).count() == jobs  # nothing charged
    again = owner.post(f"{url}/import/read-again", json={"note": "Shot 2 is the bride."})
    assert again.status_code == 201 and again.json()["status"] == "reading"
    watch = db.query(Job).filter(Job.kind == "watch-gemini").order_by(Job.id.desc()).first()
    prompt = watch.input["input"]["prompt"]
    assert "Shot 2 is the bride." in prompt
    assert "<last_reading>" in prompt and "logline" in prompt  # the last reading, to keep
    _drain(app, db)
    steps = [j.input.get("reel_step") for j in db.query(Job).order_by(Job.id)][jobs:]
    assert steps == ["watch", "write"]  # not the prep, not the cast
    after = owner.get(f"{url}/import").json()
    assert (after["status"], after["edited_since_fill"], after["new_fill_ready"]) == (
        "done", False, False
    )  # fmt: skip


def test_read_it_again_keeps_your_edits_until_you_fill_again(app, owner, db, clip):
    url = _read(app, owner, db, clip)
    owner.put(f"{url}/drafts/0", json={"text": "GROOM: My own words."})
    assert owner.get(f"{url}/import").json()["edited_since_fill"] is True
    owner.post(f"{url}/import/read-again", json={})
    _drain(app, db)
    kept = owner.get(f"{url}/import").json()
    assert (kept["edited_since_fill"], kept["new_fill_ready"]) == (True, True)
    assert owner.get(url).json()["versions"][0]["text"] == "GROOM: My own words."
    filled = owner.post(f"{url}/fill-from-reel")
    assert filled.status_code == 200
    assert (filled.json()["edited_since_fill"], filled.json()["new_fill_ready"]) == (False, False)
    assert owner.get(url).json()["versions"][0]["text"] != "GROOM: My own words."
    assert owner.post(f"{url}/fill-from-reel").status_code == 409  # nothing new now


def test_a_worse_reading_can_be_swapped_back_for_free(app, owner, db, clip):
    """QA on #452: Read it again keeps the reading before it; putting it back is free, and
    pressing again swaps the newer one back."""
    url = _read(app, owner, db, clip)
    sid = int(url.rsplit("/", 1)[1])
    assert owner.post(f"{url}/import/previous-reading").status_code == 409  # none yet
    db.expire_all()
    first = db.get(Script, sid).reference_breakdown
    owner.post(f"{url}/import/read-again", json={"note": "Shot 2 is the bride."})
    _drain(app, db)
    db.expire_all()
    second = {**db.get(Script, sid).reference_breakdown, "logline": "A worse reading."}
    db.get(Script, sid).reference_breakdown = second
    db.commit()
    assert owner.get(f"{url}/import").json()["has_previous_reading"] is True
    jobs = db.query(Job).count()
    back = owner.post(f"{url}/import/previous-reading")
    assert back.status_code == 200 and db.query(Job).count() == jobs  # free
    db.expire_all()
    assert db.get(Script, sid).reference_breakdown == first
    owner.post(f"{url}/import/previous-reading")
    db.expire_all()
    assert db.get(Script, sid).reference_breakdown["logline"] == "A worse reading."


def test_fill_from_reel_brings_the_new_scripts_own_was_marks(app, owner, db, clip):
    """QA on #452 + #455: after Fill the script again, the "Was:" marks are the new script's,
    never the old ones left on the wrong lines."""
    from app.models.script_library import ScriptDraft

    url = _read(app, owner, db, clip)
    sid = int(url.rsplit("/", 1)[1])
    draft = db.query(ScriptDraft).filter_by(script_id=sid, slot=0).one()
    draft.rewritten = [{"line_index": 0, "was": "an old mark"}]  # left from an earlier write
    db.commit()
    owner.put(f"{url}/drafts/0", json={"text": "GROOM: My own words."})
    db.expire_all()  # the worker here shares this session: let it see the edit
    again = owner.post(f"{url}/import/read-again", json={})
    assert again.status_code == 201, again.text
    _drain(app, db)
    db.expire_all()
    pending = db.get(Job, db.get(Script, sid).reel["pending_fill_job_id"])
    new = "SCENE 1\nGROOM: Will you buy me a coin?\nBRIDE: No."  # the reel's line, rewritten
    pending.output = {"drafts": [{**pending.output["drafts"][0], "script": new,
                                  "changed_lines": ["Will you buy me a coin?"]}]}  # fmt: skip
    db.commit()
    marks = owner.post(f"{url}/fill-from-reel").json()
    version = owner.get(url).json()["versions"][0]
    assert version["rewritten"] == [
        {"line_index": 1, "was": "Will you marry me?", "text": "GROOM: Will you buy me a coin?"}
    ]
    assert version["changed_lines"] == ["Will you buy me a coin?"]
    assert marks["edited_since_fill"] is False
