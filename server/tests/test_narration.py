"""Narrated ads (flows N1): one voice reads the version's words, its pauses trimmed on real
silence, each sentence timed; all on the free stand-ins (no paid calls)."""

import json
from pathlib import Path

import pytest

from app import narration
from app.models.jobs import Job
from app.models.projects import Project
from app.prompts import check
from tests.conftest import make_cut
from tests.test_song_takes import _approve_plan, _work

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


def test_a_remakes_note_reaches_the_voice_as_a_short_tag_and_the_voice_is_one_of_ours():
    """F1 (video 261): v3 read "[A touch quicker and more animated, about 3.4 words a second,
    …]" aloud before the script. A note is a short delivery tag; a longer one, or one with a
    number, is refused before anything is paid for."""
    made = narration.job(WORDS, "Jane", note="warm, upbeat")
    assert made["input"] == {"prompt": f"[warm, upbeat] {check.narration_text(WORDS)}",
                             "voice": "Jane"}  # fmt: skip
    for note in ("A touch quicker and more animated", "quicker, 3.4 words a second",
                 "Say fomo as FOH-moh."):  # fmt: skip
        with pytest.raises(ValueError, match=r"short delivery tag .* read aloud"):
            narration.job(WORDS, "Jane", note=note)
    with pytest.raises(ValueError, match="voice"):
        narration.job(WORDS, "Morgan Freeman")


def test_a_remakes_pace_is_v3s_own_speed_within_its_recorded_range():
    """Replicate's elevenlabs/v3 schema (recorded) has `speed`, 0.7 to 1.2, default 1."""
    recorded = Path(__file__).parent / "fixtures/replicate/elevenlabs_v3.json"
    speed = json.loads(recorded.read_text())["Input"]["properties"]["speed"]
    assert (speed["minimum"], speed["maximum"], speed["default"]) == (*narration.V3_SPEED, 1)
    assert narration.job(WORDS, "Sarah", "warm", speed=1.1)["input"]["speed"] == 1.1
    assert narration.job(WORDS, "Sarah", speed=1.5)["input"]["speed"] == 1.2  # its fastest
    assert "speed" not in narration.job(WORDS, "Sarah", speed=1)["input"]  # v3's own pace


def test_the_male_voices_are_elevenlabs_own_names():
    """Austin and Roger are in Replicate's elevenlabs/v3 voice list (the recorded schema)."""
    recorded = Path(__file__).parent / "fixtures/replicate/elevenlabs_v3.json"
    schema = json.loads(recorded.read_text())
    assert set(narration.ELEVENLABS) <= set(schema["enums"]["voice"]["enum"])
    for voice in ("Austin", "Roger"):
        assert narration.job(WORDS, voice)["input"]["voice"] == voice


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


def test_the_trim_cuts_each_pause_to_its_quiet_middle_and_never_into_a_word(tmp_path):
    """Video 261 kept every 0.5-0.8 s pause (`trimmed: false`): its trim was refused because
    two Whisper reads of the same words differed. The trim now cuts only quiet (a breath
    above -40 dB included), leaving 0.1 s each side of a pause, and is heard once."""
    import subprocess

    from app import song_timing

    voice = "0.5*sin(2*PI*220*t)*(between(t,0.5,1.5)+between(t,2.3,3))"
    path = tmp_path / "voice.wav"  # two words with a breath (about -39 dBFS) under it all
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",  # noqa: S603, S607
                    f"aevalsrc='{voice}+0.015*sin(2*PI*90*t)':s=24000:d=3.5", str(path)],
                   check=True)  # fmt: skip
    asked = []

    def hear(file, text):
        asked.append(file.name)
        return [
            {"word": "Hi", "start": 0.5, "end": 1.5},
            {"word": "there.", "start": 2.3, "end": 3},
        ]

    timing, trimmed = narration.measure(path, "Hi there.", hear=hear)
    assert asked == ["voice.wav"] and timing["trimmed"] and trimmed is not None  # heard once
    assert abs(timing["seconds"] - 2.1) < 0.12  # 0.1 + 1.0 + 0.2 + 0.7 + 0.1 s
    assert [w["start"] for w in timing["words"]] == [0.1, 1.3]  # moved with the cuts
    loud = [x >= -30 for x in narration._levels(trimmed)]
    assert abs(sum(loud) - 170) <= 6  # every 10 ms of both words is still there
    gaps = "".join("x" if x else "." for x in loud).strip(".").split("x")
    assert max(len(g) for g in gaps) <= 25  # the pause between them: about 0.2 s of quiet
    assert song_timing.length(trimmed) == timing["seconds"]


def test_a_soft_word_whisper_heard_in_a_pause_is_never_cut(tmp_path):
    """QA on #1444: a whispered word under the quiet line ("psst") lasting over 0.2 s was cut.
    Only quiet outside every heard word is cut now."""
    import subprocess

    soft = "0.5*sin(2*PI*220*t)*(between(t,0.5,1.5)+between(t,3,3.5))"
    path = tmp_path / "voice.wav"  # the soft word, 2.0-2.4 s, is 32 dB under the voice
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",  # noqa: S603, S607
                    f"aevalsrc='{soft}+0.0126*sin(2*PI*300*t)*between(t,2,2.4)':s=24000:d=4",
                    str(path)], check=True)  # fmt: skip
    said = (("Hi", 0.5, 1.5), ("psst", 2.0, 2.4), ("listen.", 3.0, 3.5))
    heard = [{"word": w, "start": a, "end": b} for w, a, b in said]
    levels = narration._levels(path)
    found = narration.cuts(levels, narration.KEEP, heard)
    assert all(b <= 1.9 or a >= 2.5 for a, b in found)  # nothing from 0.1 s before it to after
    assert any(a < 2.0 < b for a, b in narration.cuts(levels))  # without the words, it was cut


def test_a_narration_that_says_more_than_the_script_is_never_used_on_its_own(
    app, db, owner, narrated, monkeypatch
):
    """F1: a note read aloud is words the script doesn't have (`extras`, as a song's). A word
    heard another way ("5000 dollars", "soft gels") isn't one."""
    from app.providers import fake_local

    said = "We hit $5,000 today. Two softgels a day."
    other_way = [
        {"word": w, "start": n * 0.4, "end": n * 0.4 + 0.3}
        for n, w in enumerate("We hit 5000 dollars today. Two soft gels a day.".split())
    ]
    assert narration.extras(said, other_way) == []
    note = "A touch quicker and more animated about 3.4 words a second".split()
    read = [{"word": w, "start": n * 0.3, "end": n * 0.3 + 0.2} for n, w in enumerate(note)]
    assert [x["text"] for x in narration.extras(said, read + other_way)] == [" ".join(note)]

    def stray(*words):  # the script heard, with words added where `words` says
        return [{"word": w, "start": n * 0.4, "end": n * 0.4 + 0.3} for n, w in enumerate(words)]

    script = said.split()
    assert narration.extras(said, stray(*script, "Thank", "you.")) == []  # Whisper's sign-off
    assert narration.extras(said, stray(*script[:3], "Hmm.", *script[3:])) == []  # a sound
    assert narration.extras(said, stray(*script[:3], "the", *script[3:])) == []  # one word
    assert [x["text"] for x in narration.extras(said, stray("Quickly", *script))] == ["Quickly"]

    heard = fake_local.hear_voice
    monkeypatch.setattr(
        fake_local,
        "hear_voice",
        lambda path, text: (
            [{"word": w, "start": 0.0, "end": 0.1} for w in ("Quickly", "warm")] + heard(path, text)
        ),
    )
    owner.post(f"{narrated}/songs", json={})
    _work(app, db)
    (take,) = owner.get(f"{narrated}/songs").json()["takes"]
    extra = narration.SAYS_MORE.format("Quickly warm")
    assert take["status"] == "ready" and not take["preferred"] and take["advice"] == [extra]
    assert owner.post(f"/songs/{take['id']}/preferred").status_code == 200  # a person may


def test_each_sentence_starts_on_its_first_word_with_whispers_junk_glued_on():
    """Video 261 (CRITIQUE-261 cause 2): Whisper glued junk onto each sentence's first word
    ("?ÿÿÿÿÿÿÿÿDay", ".שובDay", ".ManiaResilia"), `\\w` kept it, so every rung was timed from
    its second word and cut 0.2-0.7 s late. The words are the critic's local read of 261 with
    the site's glued tokens put in (job 1435; the other rungs glued the same way); the voice
    starts where the critic measured it, inside each glued word."""
    from app import song_timing

    heard = []
    for token in HEARD_261.split():
        word, at = token.rsplit("@", 1)
        start, end = at.split("-")
        heard.append({"word": word, "start": float(start), "end": float(end)})
    glued = [k for k, w in enumerate(heard) if w["word"].endswith(("Day", "Resilia"))]
    onsets = dict(zip(glued, (6.27, 10.38, 15.94, 19.91, 23.93, 29.27), strict=True))
    levels = [-70.0] * 3440  # 10 ms frames: the voice is on in each word, from its onset
    for n, w in enumerate(heard):
        for k in range(round(onsets.get(n, w["start"]) * 100), round(w["end"] * 100)):
            levels[k] = -15.0
    lines = song_timing.lines("\n".join(narration.sentences(SCRIPT_261)), heard, 34.4,
                              levels=levels)  # fmt: skip
    assert [ln["start"] for ln in lines] == [0.0, 6.27, 10.38, 15.94, 19.91, 23.93, 29.27, 32.68]
    assert all(ln["heard"] >= 0.6 for ln in lines)


def test_a_line_starts_at_its_first_sound_when_whisper_starts_the_word_late():
    """QA on #1444: "Actually" sounds from 1.92 s with a closure inside it (1.98-2.12 s);
    Whisper starting it anywhere up to 0.15 s late put the line at 2.12 s. A clean word now
    steps back to its sound; a junk one still walks on; only a junk word is read by its end."""
    from app import song_timing

    levels = [-70.0] * 300
    for a, b in ((100, 150), (192, 198), (212, 260)):  # "Say", then "A-ctually"
        levels[a:b] = [-15.0] * (b - a)
    for late in (1.95, 2.0, 2.05):
        heard = [{"word": "Say", "start": 1.0, "end": 1.6},
                 {"word": "Actually.", "start": late, "end": 2.6}]  # fmt: skip
        (_, line) = song_timing.lines("Say.\nActually.", heard, 3.0, levels=levels)
        assert line["start"] == 1.92, late
    heard[1] = {"word": "Actually.", "start": 2.1, "end": 2.6}
    assert song_timing.lines("Say.\nActually.", heard, 3.0, levels=levels)[1]["start"] == 2.1
    _, theirs, junk, _ = song_timing._matcher([{"words": ["Call", "one", "friend."]}], [
        {"word": w} for w in ("Call", "phone", ".ManiaFriend.")])  # fmt: skip
    assert theirs == ["call", "phone", "friend"] and junk == [False, False, True]
    for word in ("iPhone", "TikTok", "McDonald's", "U.S.", "e.g.", "$5,000", "days?"):
        assert not song_timing.glued(word), word  # names and abbreviations are words
    for word in ("?ÿÿÿÿÿÿÿÿDay", ".שובDay", ".ManiaResilia"):  # video 261's
        assert song_timing.glued(word), word


SCRIPT_261 = """What happens to your gut if you take two softgels of oil of oregano every morning for thirty days?
Day one, they go down easy, and you burp a little oregano.
Day three, the gas that's been trapped in there since Christmas finally finds the exit.
Day ten, your belly stops inflating after every meal.
Day twenty, your jeans close without lying down on the bed.
Day thirty, you're flat, light, and nobody at work can figure out what changed.
Resilia oil of oregano with black seed oil. Two softgels a day."""  # noqa: E501
HEARD_261 = """What@0-0.14 happens@0.14-0.44 to@0.44-0.66 your@0.66-0.76 gut@0.76-1 if@1-1.36
you@1.36-1.46 take@1.46-1.68 two@1.68-1.96 soft@1.96-2.32 gels@2.32-2.72 of@2.72-2.92 oil@2.92-3.14
of@3.14-3.38 oregano@3.38-3.86 every@3.86-4.14 morning@4.14-4.54 for@4.54-4.8 30@4.8-5.04
days?@5.04-5.4 ?ÿÿÿÿÿÿÿÿDay@5.48-6.42 one,@6.42-6.7 They@7.14-7.4 go@7.4-7.54 down@7.54-7.74
easy@7.74-7.94 and@7.94-8.48 you@8.48-8.66 burp@8.66-8.96 a@8.96-9.02 little@9.02-9.16
oregano.@9.16-9.76 .שובDay@9.74-10.54 three,@10.54-10.88 The@11.4-11.6 gas@11.6-11.84
that's@11.84-12.26 been@12.26-12.4 trapped@12.4-12.62 in@12.62-12.9 there@12.9-13.04
since@13.04-13.26 Christmas@13.26-13.72 finally@13.72-14.28 finds@14.28-14.7 the@14.7-14.92
exit.@14.92-15.12 .ÿÿDay@15.12-16.1 ten,@16.1-16.46 Your@16.9-17.12 belly@17.12-17.32
stops@17.32-17.68 inflating@17.68-18.28 after@18.28-18.56 every@18.56-18.9 meal.@18.9-19.14
?ÿÿDay@19.14-20.08 twenty,@20.08-20.4 Your@20.9-21.14 jeans@21.14-21.34 close@21.34-21.68
without@21.68-22.08 lying@22.08-22.5 down@22.5-22.76 on@22.76-22.92 the@22.92-23 bed.@23-23.16
.ÿÿDay@23.16-24.06 thirty,@24.06-24.44 Your@24.86-25.06 flat,@25.06-25.34 light,@25.7-25.84
and@26.18-26.28 nobody@26.28-26.6 at@26.6-26.96 work@26.96-27.12 can@27.12-27.36
figure@27.36-27.6 out@27.6-27.84 what@27.84-28.04 changed.@28.04-28.36 .ManiaResilia@28.6-29.76
oil@29.76-29.98 of@29.98-30.44 oregano@30.44-31 with@31-31.28 black@31.28-31.5 seed@31.5-31.82
oil.@31.82-32.12 Two@32.68-32.9 soft@32.9-33.24 gels@33.24-33.58 a@33.58-33.72 day.@33.72-33.94"""


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
    _work(app, db)  # its plan (flows 1b), then the shots from it
    _approve_plan(app, db, editor, video)
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

    from app import cut_render
    from tests.test_song_final_cut import _clip, _probe, _song

    silent = tmp_path / "silent.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",  # noqa: S603, S607
                    "testsrc=s=160x284:d=2:r=10", "-pix_fmt", "yuv420p", str(silent)],
                   check=True)  # fmt: skip
    clips, voice = [_clip(3, tmp_path), silent.read_bytes()], _song(4, tmp_path)
    for music in (_song(2, tmp_path), None):  # a short bed loops; no bed: voice and takes only
        got = _probe(cut_render.song_cut(clips, [3.0, 2.0], voice, True, music), tmp_path)
        assert abs(got["seconds"] - 5.0) < 0.2 and got["streams"] == ["audio", "video"]


def test_a_script_switches_between_dialogue_and_narrated_before_publishing(owner, narrated):
    from app.routes.script_library import SONG_STAYS

    base = narrated.rsplit("/drafts", 1)[0]
    assert owner.patch(base, json={"format": "dialogue"}).json()["kind"] == "story"
    assert owner.get(base).json()["versions"][0]["reads_narrated"]  # all one voice (ST0 Advice)
    assert owner.patch(base, json={"format": "narrated"}).json()["kind"] == "narrated"  # Undo
    brand = owner.get("/brands").json()[0]["id"]
    song = owner.post("/scripts", json={"brand_id": brand, "title": "S", "kind": "song"}).json()
    no = owner.patch(f"/scripts/{song['id']}", json={"format": "narrated"})
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
    _work(app, db)  # its plan (flows 1b), then the shots from it
    _approve_plan(app, db, editor, video)
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
    _work(app, db)  # its plan (flows 1b), then the shots from it
    _approve_plan(app, db, editor, video)
    _clips_made(app, db, editor, video)
    made = make_cut(app, db, editor, video)
    assert made.status_code == 200, made.text
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


def test_with_nothing_to_read_the_press_says_so_instead_of_a_price(owner, narrated):
    _words(owner, narrated, "SCENE 1\n★ Iron Paws")  # headings only: nothing to read aloud
    shown = owner.get(f"{narrated}/songs").json()
    assert (shown["songs_note"], shown["estimate_credits"]) == (narration.NO_WORDS, 0)
    _words(owner, narrated, WORDS)
    assert owner.get(f"{narrated}/songs").json()["songs_note"] is None


def test_whispers_read_has_time_for_a_long_take(tmp_path, monkeypatch):
    """The real-run audit: during a deploy's build, local Whisper ran past its fixed 180 s on
    a real UGC narration twice, and the run ended; a 23 s read later took 175 s. Its time now
    grows with the take (never under 300 s, at most 900 s), one try a job (the local lane is
    one shared worker: a failed read is read again as its own job), failing in plain words."""
    import subprocess

    from app import song_timing

    asked = []

    def run(args, timeout=song_timing.TIMEOUT):
        asked.append(timeout)
        return subprocess.CompletedProcess(args, 0, stdout=b'[{"word": "hi", "start": 0.1}]')

    monkeypatch.setattr(song_timing, "_run", run)
    monkeypatch.setattr(song_timing, "length", lambda path: 100.0)
    assert song_timing.words(tmp_path / "v.mp3", "Hi.") == [{"word": "hi", "start": 0.1}]
    assert asked == [600]  # 6 s a second of a 100 s take, one try
    monkeypatch.setattr(song_timing, "length", lambda path: 23.0)
    assert song_timing.read_timeout(tmp_path / "v.mp3") == 300  # the floor (175 s used of 180)
    monkeypatch.setattr(song_timing, "length", lambda path: 60.0)
    assert song_timing.read_timeout(tmp_path / "v.mp3") == 360  # 6 s a second above it
    monkeypatch.setattr(song_timing, "length", lambda path: 400.0)
    assert song_timing.read_timeout(tmp_path / "v.mp3") == song_timing.MOST  # the cap

    def slow(args, timeout=song_timing.TIMEOUT):
        asked.append(timeout)
        raise subprocess.TimeoutExpired(args, timeout)

    monkeypatch.setattr(song_timing, "_run", slow)
    with pytest.raises(RuntimeError, match=r"^Reading the sung words took too long\.$"):
        song_timing.words(tmp_path / "v.mp3", "Hi.")
    assert asked == [600, 900]  # never twice in one job


def test_a_plan_that_lost_its_narration_times_names_the_press_that_times_it(
    app, db, owner, editor, narrated
):
    """Video 240 (7 Nov): its plan had lost its narration times, so Make the video said
    "Rewrite the clip prompts" while the rewrite said no clip needed new prompts: the director
    stopped, "nothing I can press gets past them" (rule 22). The cut now says to make the
    shots again (timed as they're made), and a clip with no piece of the narration on a timed
    plan is one the rewrite is for."""
    from sqlalchemy.orm.attributes import flag_modified

    from app import clip_prompts, cut
    from app.models.breakdowns import BreakdownVersion
    from app.models.clips import ProjectClip
    from tests.test_song_final_cut import _clips_made

    owner.post(f"{narrated}/songs", json={})
    _work(app, db, ticks=8)
    owner.post(f"{narrated}/approve")
    owner.post(f"{narrated.rsplit('/drafts', 1)[0]}/publish")
    video = f"/projects/{editor.post(f'{narrated}/produce').json()['project_id']}"
    _work(app, db)
    _approve_plan(app, db, editor, video)
    _clips_made(app, db, editor, video)
    pid = int(video.rsplit("/", 1)[1])
    project = db.get(Project, pid)
    rows = db.query(ProjectClip).filter_by(project_id=pid).all()

    one = rows[0]  # a clip that lost its piece while the plan kept its times
    one.song_slice = None
    db.flush()  # (its row re-slices it on save: cleared after, as a damaged row left it)
    db.execute(ProjectClip.__table__.update().where(ProjectClip.id == one.id)
               .values(song_slice=None))  # fmt: skip
    db.commit()
    db.expire_all()
    assert make_cut(app, db, editor, video).json()["detail"] == cut.NOT_TIMED
    assert one.clip_id in clip_prompts.to_rewrite(db, project)  # the press it names works

    row = db.query(BreakdownVersion).filter_by(project_id=pid).order_by(
        BreakdownVersion.id.desc()).first()  # fmt: skip
    row.data = {k: v for k, v in row.data.items() if k != "song"}  # as complete_cast left it
    flag_modified(row, "data")
    db.commit()
    db.execute(ProjectClip.__table__.update().where(ProjectClip.project_id == pid)
               .values(song_slice=None))  # fmt: skip
    db.commit()
    db.expire_all()
    assert make_cut(app, db, editor, video).json()["detail"] == cut.UNTIMED_PLAN
    assert editor.post(f"{video}/breakdown").status_code == 201  # Make the shots again
    _work(app, db)
    db.expire_all()
    newest = db.query(BreakdownVersion).filter_by(project_id=pid).order_by(
        BreakdownVersion.id.desc()).first()  # fmt: skip
    assert newest.id != row.id and newest.data.get("song")  # timed to the narration again


def test_a_read_that_says_every_line_is_never_judged_missing_lines(tmp_path):
    """UGC video 281: the site's Whisper, prompted with the script, kept only the last line of
    takes 1 and 2 ("iPhDanny, you were right…"; locally reproduced: a retry at temperature 0.8
    continues the prompt and skips what it holds), so two paid remakes were made and the clean
    23.7 s take thrown away. A read missing most of the script is heard again without the
    prompt; a read with the script's words in order but for a few written another way ("10",
    "Everything's giving") has no lines missing; and "iPhDanny" is Danny with junk glued on."""
    import subprocess

    from app import director_song, song_timing
    from app.models.songs import SongTake

    path = tmp_path / "voice.wav"  # take 1's length; its words are the real reads' words
    tone = "aevalsrc='0.3*sin(2*PI*180*t)':s=24000:d=24.05"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", tone, str(path)],  # noqa: S603, S607
                   check=True)  # fmt: skip
    asked = []

    def hear(file, text, prompted=True):
        asked.append(prompted)
        return _read(SITE_281 if prompted else PLAIN_281)

    timing, _ = narration.measure(path, check.narration_text(SCRIPT_281), hear=hear)
    assert asked == [True, False]  # the site's read lost 9 of 11 lines: heard plainly too
    assert all(ln["heard"] >= 0.6 for ln in timing["lines"]) and timing["extras"] == []
    sentences = [{"text": t} for t in narration.sentences(check.narration_text(SCRIPT_281))]
    take = SongTake(kind=narration.KIND, lyrics=SCRIPT_281, timing={"words": _read(PLAIN_281)})
    assert narration.covered(check.narration_text(SCRIPT_281), _read(PLAIN_281)) >= 0.9
    assert director_song._missing(take, sentences) == []  # "10", "Everything's giving"
    take.timing = {"words": _read(SITE_281)}
    assert len(director_song._missing(take, sentences)) == 9  # what the site's read had
    danny = song_timing.lines("Danny, you were right.", _read(SITE_281), 23.18)[0]
    assert (danny["start"], danny["heard"]) == (19.38, 1.0)  # "iPhDanny," is Danny


def _read(words: str) -> list[dict]:
    out = []
    for token in words.split():
        word, at = token.rsplit("@", 1)
        start, end = at.split("-")
        out.append({"word": word, "start": float(start), "end": float(end)})
    return out


SCRIPT_281 = (
    "MARCUS: I owe my brother-in-law a public apology.\n"
    "MARCUS: Every Thanksgiving I laughed at him for staring at his phone at the table.\n"
    "MARCUS: Called him the crypto guy. In front of everybody.\n"
    "MARCUS: This year he finally showed me. Small trades on fomo, ten minutes a day.\n"
    "MARCUS: Then he showed me the balance.\n"
    "MARCUS: I didn't say a word for the rest of dinner.\n"
    "MARCUS: I downloaded it in the parking lot.\n"
    "MARCUS: Danny, you were right. Link's in my bio."
)
# Take 1 (job 1798) as the site heard it, and as faster-whisper small hears it unprompted
SITE_281 = (
    "iPhDanny,@19.38-19.82 you@21.06-21.28 were@21.28-21.42 right.@21.42-21.62 "
    "Link's@22.18-22.36 in@22.36-22.42 my@22.42-22.54 bio.@22.54-22.76"
)
PLAIN_281 = """I@0-0.26 owe@0.26-0.42
my@0.42-0.54 brother@0.54-0.74 -in@0.74-0.9 -law@0.9-1.04 a@1.04-1.46
public@1.46-1.68 apology.@1.68-2.16 Everything's@2.92-3.36 giving.@3.36-3.5 I@3.88-4.06
laughed@4.06-4.3 at@4.3-4.42 him@4.42-4.54 for@4.54-4.68 staring@4.68-4.9 at@4.9-5.08
his@5.08-5.18 phone@5.18-5.4 at@5.4-5.58 the@5.58-5.66 table.@5.66-5.9 Called@6.3-6.68
him@6.68-6.84 the@6.84-6.94 crypto@6.94-7.18 guy@7.18-7.48 in@7.48-8.22 front@8.22-8.38
of@8.38-8.5 everybody.@8.5-8.82 This@10-10.44 year@10.44-10.72 he@10.72-10.84
finally@10.84-11.12 showed@11.12-11.4 me@11.4-11.62 small@11.62-12.22 trades@12.22-12.58
on@12.58-12.82 FOMO@12.82-13.2 10@13.2-13.66 minutes@13.66-13.82 a@13.82-14 day.@14-14.26
Then@14.8-15.08 he@15.08-15.16 showed@15.16-15.32 me@15.32-15.42 the@15.42-15.52
balance.@15.52-15.78 I@16.5-16.86 didn't@16.86-17.04 say@17.04-17.16 a@17.16-17.26
word@17.26-17.42 for@17.42-17.56 the@17.56-17.64 rest@17.64-17.8 of@17.8-17.92
dinner.@17.92-18.08 I@18.62-18.82 downloaded@18.82-19.18 it@19.18-19.42 in@19.42-19.56
the@19.56-19.66 parking@19.66-19.82 lot.@19.82-20.12 Danny,@21.26-21.7 you@21.94-22.16
were@22.16-22.28 right.@22.28-22.5 Links@23.08-23.16 in@23.16-23.32 my@23.32-23.42
bio.@23.42-23.62"""
