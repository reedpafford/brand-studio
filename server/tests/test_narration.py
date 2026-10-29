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
def narrated(app, owner, monkeypatch):
    app.state.settings.fake_providers = True
    monkeypatch.setattr("app.narration_music.on", lambda db: True)  # as on the stand-ins
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


def test_the_music_bed_follows_the_narration_and_a_failed_one_keeps_it(app, db, owner, narrated):
    from app import narration_music

    owner.post(f"{narrated}/songs", json={})
    _work(app, db, ticks=8)
    (take,) = owner.get(f"{narrated}/songs").json()["takes"]
    assert take["status"] == "ready" and take["music_status"] == "ready" and take["music_file_id"]
    bed = db.query(Job).filter(Job.kind == "music_bed").one()
    assert bed.input["input"]["duration"] >= int(take["seconds"])  # the narration's length
    assert bed.input["input"]["prompt"].endswith(
        "Instrumental only: no vocals, no choir, no spoken word."
    )

    bed.status, bed.error = "failed", narration_music.FAILED  # as if the music model failed
    from app.models.songs import SongTake

    row = db.get(SongTake, take["id"])
    row.music_file_id = None
    db.commit()
    failed = owner.get(f"{narrated}/songs").json()["takes"][0]
    assert failed["status"] == "ready" and failed["music_status"] == "failed"  # narration kept
    # The prompt was written and charged (a Claude call); the music alone is made again
    assert failed["music_reason"] == narration_music.BED_FAILED.format("3 credits")
    assert failed["music_credits"] == float(narration_music._bed_price(db, 1))
    prompts = db.query(Job).filter(Job.kind == "write-claude").count()
    assert owner.post(f"/songs/{take['id']}/music-again").json()["music_status"] == "making"
    db.expire_all()  # the route changed the take in its own session
    _work(app, db, ticks=8)
    assert owner.get(f"{narrated}/songs").json()["takes"][0]["music_status"] == "ready"
    assert db.query(Job).filter(Job.kind == "write-claude").count() == prompts  # not again


def test_a_music_prompt_asking_for_vocals_is_written_again_once(app, db, owner, narrated):
    from app.models.script_library import ScriptDraft

    owner.post(f"{narrated}/songs", json={})
    _work(app, db, ticks=3)  # the narration and its timing
    job = db.query(Job).filter(Job.input["step"].as_string() == "narration_music").one()
    job.input = {**job.input, "prompt": job.input["prompt"] + "\n<note>fake:vocals</note>"}
    db.commit()
    _work(app, db, ticks=4)
    db.refresh(job)
    assert job.status == "succeeded" and "choir sings" not in str(job.output)
    assert db.query(ScriptDraft).count() >= 1


def test_a_narrated_cut_keeps_each_takes_sound_under_the_voice_and_the_music(tmp_path):
    import subprocess

    from app import clip_takes
    from tests.test_song_final_cut import _clip, _probe, _song

    silent = tmp_path / "silent.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",  # noqa: S603, S607
                    "testsrc=s=160x284:d=2:r=10", "-pix_fmt", "yuv420p", str(silent)],
                   check=True)  # fmt: skip
    clips, voice = [_clip(3, tmp_path), silent.read_bytes()], _song(4, tmp_path)
    for music in (_song(2, tmp_path), None):  # a short bed loops; no bed: voice and takes only
        got = _probe(clip_takes.song_cut(clips, [3.0, 2.0], voice, True, music), tmp_path)
        assert abs(got["seconds"] - 5.0) < 0.2 and got["streams"] == ["audio", "video"]


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


def test_a_narrated_video_is_cut_with_its_narration_and_music(app, db, owner, editor, narrated):
    from tests.test_song_final_cut import _clips_made

    owner.post(f"{narrated}/songs", json={})
    _work(app, db, ticks=8)
    owner.post(f"{narrated}/approve")
    owner.post(f"{narrated.rsplit('/drafts', 1)[0]}/publish")
    video = f"/projects/{editor.post(f'{narrated}/produce').json()['project_id']}"
    _work(app, db)
    _clips_made(app, db, editor, video)
    made = editor.post(f"{video}/video")
    assert made.status_code == 201, made.text
    assert made.json()["narration"] == {"voice": "Sarah", "music": True}


def test_the_music_is_off_unless_switched_on_and_stops_at_its_budget(db, monkeypatch):
    from app import narration_music
    from app.models.jobs import Job
    from app.settings import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "fake_providers", False)
    assert not narration_music.on(db) and narration_music.price(db, 1) == 0  # off: no music
    sent = db.query(Job).filter(Job.input["step"].as_string() == narration_music.BED).count()
    monkeypatch.setattr(settings, "narration_music_paid", True)
    monkeypatch.setattr(settings, "narration_music_budget_usd", (sent + 2) * 0.25)  # 2 runs left
    assert narration_music.on(db)
    for _ in range(2):
        db.add(Job(workspace_id=1, kind="music_bed", provider="replicate", credits=1,
                   input={"step": narration_music.BED}))  # fmt: skip
    db.commit()
    assert not narration_music.on(db)  # the next run would pass the budget
    monkeypatch.setattr(settings, "fake_providers", True)
    assert narration_music.on(db)  # the stand-ins are free
