"""Narrated ads (flows N1): one voice reads the version's words, its pauses trimmed on real
silence, each sentence timed; all on the free stand-ins (no paid calls)."""

import pytest

from app import narration
from app.models.jobs import Job
from app.models.projects import Project
from app.prompts import check
from tests.test_song_takes import _work

WORDS = "Your dog's gut is a mess. Iron Paws fixes it.\nLink in my bio!"


@pytest.fixture
def narrated(app, owner):
    app.state.settings.fake_providers = True
    brand = owner.get("/brands").json()[0]["id"]
    script = owner.post(
        "/scripts", json={"brand_id": brand, "title": "Gut", "kind": "narrated", "text": WORDS}
    ).json()
    assert script["kind"] == "narrated"
    return f"/scripts/{script['id']}/drafts/0"


def _words(client, url, text):
    assert client.put(url, json={"text": text}).status_code == 200


def test_the_narrator_reads_the_directors_narration_text():
    script = "[Hook]\nSCENE 1\nMIA: Your dog's gut is a mess.\n★ Iron Paws\nCTA: Link in bio"
    made = narration.job(script)
    assert made["input"]["prompt"] == check.narration_text(script) == "Your dog's gut is a mess."
    assert narration.sentences(WORDS) == [
        "Your dog's gut is a mess.", "Iron Paws fixes it.", "Link in my bio!"
    ]  # fmt: skip


def test_a_narration_is_made_trimmed_timed_and_used(app, db, owner, narrated):
    before = owner.get(f"{narrated}/songs").json()
    assert before["songs_on"] and before["estimate_credits"] > 0
    made = owner.post(f"{narrated}/songs", json={})
    assert made.status_code == 201, made.text
    assert [t["status"] for t in made.json()["takes"]] == ["making"]  # one voice call
    job = db.query(Job).filter(Job.kind == "speech").one()
    assert job.input["input"] == {"prompt": check.narration_text(WORDS), "voice": "Sarah"}
    _work(app, db)
    (take,) = owner.get(f"{narrated}/songs").json()["takes"]
    assert take["status"] == "ready" and take["preferred"] and take["kind"] == "narration"
    assert take["untrimmed_seconds"] > take["seconds"]  # the 0.8 s pauses shortened
    assert take["advice"] == []
    timing = db.query(Job).filter(Job.kind == "narration_timing").one().output["timing"]
    assert [ln["text"] for ln in timing["lines"]] == narration.sentences(WORDS)
    starts = [ln["start"] for ln in timing["lines"]]
    assert starts == sorted(starts) and timing["lines"][-1]["end"] <= take["seconds"]

    _words(owner, narrated, WORDS + " Today only.")  # new words: it reads older ones
    assert owner.get(f"{narrated}/songs").json()["takes"][0]["out_of_date"]


def test_a_trim_that_would_clip_a_word_keeps_the_pauses(app, db, owner, narrated):
    _words(owner, narrated, WORDS + " fake:clip-word")
    owner.post(f"{narrated}/songs", json={})
    _work(app, db)
    (take,) = owner.get(f"{narrated}/songs").json()["takes"]
    assert take["status"] == "ready" and take["advice"] == [narration.KEPT_PAUSES]
    assert take["untrimmed_seconds"] is None  # the untrimmed narration is the one kept


def test_a_failed_narration_says_so_and_costs_nothing(app, db, owner, narrated):
    _words(owner, narrated, "fake:fail. " + WORDS)
    owner.post(f"{narrated}/songs", json={})
    _work(app, db)
    (take,) = owner.get(f"{narrated}/songs").json()["takes"]
    assert (take["status"], take["failed_reason"]) == ("failed", narration.FAILED)
    assert take["retry_helps"] and take["retry_credits"] > 0


def test_publishing_needs_a_narration_and_a_video_starts_on_it(app, db, owner, editor, narrated):
    base = narrated.rsplit("/drafts", 1)[0]
    owner.post(f"{narrated}/approve")
    r = owner.post(f"{base}/publish")
    assert r.status_code == 409 and "Make the narration first" in r.json()["detail"]
    owner.delete(f"{narrated}/approve")
    owner.post(f"{narrated}/songs", json={})
    _work(app, db)
    owner.post(f"{narrated}/approve")
    assert owner.post(f"{base}/publish").status_code == 200
    made = editor.post(f"{narrated}/produce")
    assert made.status_code == 201, made.text
    take = owner.get(f"{narrated}/songs").json()["takes"][0]
    assert db.get(Project, made.json()["project_id"]).song_take_id == take["id"]


def test_a_narrated_videos_plan_is_timed_to_its_sentences(app, db, owner, editor, narrated):
    owner.post(f"{narrated}/songs", json={})
    _work(app, db)
    owner.post(f"{narrated}/approve")
    owner.post(f"{narrated.rsplit('/drafts', 1)[0]}/publish")
    video = f"/projects/{editor.post(f'{narrated}/produce').json()['project_id']}"
    _work(app, db)
    job = db.query(Job).filter(Job.input["step"].as_string() == "narrated_breakdown").one()
    assert "Iron Paws fixes it." in job.input["prompt"]  # the sentences are the clock
    plan = editor.get(f"{video}/breakdown").json()
    assert plan["song"] and not any(s["sung"] for s in plan["song"]["shots"].values())


def test_a_script_switches_between_dialogue_and_narrated_before_publishing(owner, narrated):
    from app.routes.script_library import SONG_STAYS

    base = narrated.rsplit("/drafts", 1)[0]
    assert owner.patch(base, json={"kind": "story"}).json()["kind"] == "story"
    assert owner.get(base).json()["versions"][0]["reads_narrated"]  # all one voice (ST0 Advice)
    assert owner.patch(base, json={"kind": "narrated"}).json()["kind"] == "narrated"  # Undo
    assert owner.patch(base, json={"kind": "song"}).status_code == 422  # never to a song
    brand = owner.get("/brands").json()[0]["id"]
    song = owner.post("/scripts", json={"brand_id": brand, "title": "S", "kind": "song"}).json()
    no = owner.patch(f"/scripts/{song['id']}", json={"kind": "narrated"})
    assert (no.status_code, no.json()["detail"]) == (409, SONG_STAYS)


def test_a_narrated_version_names_the_lines_spoken_on_camera(owner, narrated):
    _words(owner, narrated, "Your dog's gut is a mess.\nMIA: I fixed it with Iron Paws.")
    lines = owner.get(narrated.rsplit("/drafts", 1)[0]).json()["versions"][0]["dialogue_lines"]
    assert lines == [{"line": 2, "text": "MIA: I fixed it with Iron Paws."}]


def test_a_narration_shows_its_sentences_and_voice_and_only_one_is_made_at_a_time(
    app, db, owner, narrated
):
    assert owner.post(f"{narrated}/songs", json={}).status_code == 201
    again = owner.post(f"{narrated}/songs", json={})
    assert (again.status_code, again.json()["detail"]) == (409, narration.MAKING)
    assert db.query(Job).filter(Job.kind == "speech").count() == 1  # charged once
    _work(app, db)
    songs = owner.get(f"{narrated}/songs").json()
    assert songs["voice"] == "Sarah"
    (take,) = songs["takes"]
    assert [x["text"] for x in take["sentences"]] == narration.sentences(WORDS)
    assert take["sentences"][0]["start"] < take["sentences"][-1]["start"]


def test_a_narrated_videos_clips_keep_their_own_sound(app, db, owner, editor, narrated):
    from app import prompts

    owner.post(f"{narrated}/songs", json={})
    _work(app, db)
    owner.post(f"{narrated}/approve")
    owner.post(f"{narrated.rsplit('/drafts', 1)[0]}/publish")
    video = f"/projects/{editor.post(f'{narrated}/produce').json()['project_id']}"
    _work(app, db)
    editor.post(f"{video}/clips/prompts")
    job = db.query(Job).filter(Job.input["step"].as_string() == "clip_prompts").one()
    assert job.input["system"][0] == prompts.system("narrated_clip_prompts")
