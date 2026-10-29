"""Song ads' music: the service interface, its price, the stand-in song and the free timing
step (no real or paid calls)."""

import re

import pytest

from app import music, song_timing
from app.models.accounts import User
from app.models.files import StoredFile
from app.models.jobs import JobStatus
from app.providers import get_providers
from app.providers.fake_local import SONG, hear_song, song
from app.routes.jobs import enqueue
from app.settings import Settings
from app.worker import run_once

LYRICS = """[Verse 1]
Wake up hungry, bowl is bright
Iron Paws, it feels so right
[Chorus]
Gut so happy, tail so high
Iron Paws, my best ally
[Drop]"""


def test_lyrics_are_sent_word_for_word_never_suno_s_own():
    job = music.job(LYRICS, " pop, female lead, 120 BPM ")
    assert job == {"input": {"lyrics": LYRICS, "style": "pop, female lead, 120 BPM",
                             "instrumental": False}}  # fmt: skip


@pytest.mark.parametrize(
    ("lyrics", "style", "said"),
    [
        ("", "pop", music.NO_LYRICS),
        ("[Verse]\n[Chorus]", "pop", music.NO_LYRICS),
        ("la " * 1700, "pop", music.TOO_LONG),
        ("la la", "x" * 1001, music.STYLE_TOO_LONG),
    ],
)
def test_a_song_that_cant_be_made_says_why(lyrics, style, said):
    with pytest.raises(music.NotReady, match=re.escape(said)):
        music.job(lyrics, style)


def test_suno_stays_off_until_reed_has_access(app):
    """No public Suno API yet: only the stand-ins make songs."""
    assert music.PROVIDER not in get_providers(Settings())


def test_a_refused_song_says_so_plainly_and_quotes_little():
    assert music.failure("Input flagged as sensitive (E005)") == music.REFUSED
    assert music.failure("Internal error") == music.FAILED
    said = music.failure("Copyrighted artist", "warm pop " * 200)
    assert len(said) < 300 and "…" in said


@pytest.fixture(scope="module")
def timing(tmp_path_factory):
    path = tmp_path_factory.mktemp("song") / "song.mp3"
    path.write_bytes(song())
    return song_timing.measure(path, LYRICS, hear=hear_song)


def test_the_stand_in_songs_beats_are_found(timing):
    assert timing["bpm"] == SONG["bpm"]
    assert timing["beats"][:3] == [0.25, 0.75, 1.25]
    assert abs(timing["seconds"] - SONG["seconds"]) < 0.2
    assert len(timing["peaks"]) == 200 and max(timing["peaks"]) == 1


def test_every_line_keeps_its_words_and_gets_its_time(timing):
    assert [(ln["section"], ln["text"], ln["start"]) for ln in timing["lines"]] == [
        ("Verse 1", "Wake up hungry, bowl is bright", 2.25),
        ("Verse 1", "Iron Paws, it feels so right", 5.25),
        ("Chorus", "Gut so happy, tail so high", 8.25),
        ("Chorus", "Iron Paws, my best ally", 11.25),
    ]
    assert all((ln["heard"], ln["times_sung"]) == (1, 1) for ln in timing["lines"])


def test_sections_start_on_bars_and_never_cut_a_word(timing):
    parts = timing["sections"]
    assert [(p["name"], p["start"], p["end"]) for p in parts] == [
        ("Intro", 0, 2.25), ("Verse 1", 2.25, 8.25), ("Chorus", 8.25, 14.25),
        ("Outro", 14.25, timing["seconds"]),
    ]  # fmt: skip
    cuts = [c for p in parts for c in (p["start"], *p["cuts"])]
    assert not [c for c in cuts for w in timing["words"] if w["start"] < c < w["end"]]
    assert set(cuts) <= set(timing["beats"][::4]) | {0}


def test_lines_whisper_missed_sit_between_the_ones_it_heard():
    heard = [{"word": w, "start": 1 + k * 0.5, "end": 1.3 + k * 0.5}
             for k, w in enumerate("Wake up hungry bowl is bright".split())]  # fmt: skip
    heard += [{"word": "ally", "start": 9.0, "end": 9.5}]
    sung = song_timing.lines(LYRICS, heard, seconds=12)
    assert [ln["heard"] for ln in sung] == [1, 0, 0, 0.2]
    assert [(ln["start"], ln["end"]) for ln in sung[1:3]] == [(3.8, 6.4), (6.4, 9.0)]


def test_a_chorus_written_twice_and_sung_twice_is_no_repeat():
    twice = LYRICS + "\n[Chorus]\nGut so happy, tail so high\nIron Paws, my best ally"
    words = [w for line in music.sung(twice) for w in line.split()]
    heard = [{"word": w, "start": k, "end": k + 0.5} for k, w in enumerate(words)]
    assert [ln["times_sung"] for ln in song_timing.lines(twice, heard, 30)] == [1] * 6
    heard += [{"word": w, "start": 30 + k, "end": 30.5 + k}
              for k, w in enumerate("Iron Paws, my best ally".split())]  # fmt: skip
    assert [ln["times_sung"] for ln in song_timing.lines(twice, heard, 40)][-1] == 2


def test_a_request_gives_two_songs_and_its_timing_runs_free(app, db, owner):
    take, timed = _run(app, db, "pop")
    assert take.status == JobStatus.succeeded and take.credits == 1  # A4: assumed price
    songs = [db.get(StoredFile, f) for f in take.output["file_ids"]]
    assert len(songs) == music.TAKES
    assert all(s.content_type == "audio/mpeg" and s.filename.endswith(".mp3") for s in songs)
    assert timed.status == JobStatus.succeeded and timed.credits == 0
    assert timed.output["timing"]["bpm"] == SONG["bpm"]


def _run(app, db, style):
    """One take on the stand-ins, then its timing (if it was made)."""
    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings, app.state.storage)
    user = db.query(User).first()
    take = enqueue(db, user, "music", music.job(LYRICS, style), provider=music.PROVIDER)
    for _ in range(2):  # handed over, then collected
        run_once(db, providers, app.state.storage)
    db.refresh(take)
    if take.status != JobStatus.succeeded:
        return take, None
    mp3 = db.get(StoredFile, take.output["file_ids"][0])
    timed = enqueue(db, user, "song_timing", {"song_key": mp3.key, "lyrics": LYRICS},
                    units=0, provider="local")  # fmt: skip
    run_once(db, providers, app.state.storage)
    db.refresh(timed)
    return take, timed


@pytest.mark.parametrize(
    ("marker", "said"),
    [
        ("fake:fail", music.FAILED),
        ("fake:refuse", music.REFUSED),
        ("fake:copyright", music.COPYRIGHT.format("pop fake:copyright")),
    ],
)
def test_a_failed_take_says_why_in_plain_words(app, db, owner, marker, said):
    take, _ = _run(app, db, f"pop {marker}")
    assert (take.status, take.error) == (JobStatus.failed, said)
    assert take.error_detail  # the raw reason stays owner-only


def test_stand_in_takes_can_drop_or_repeat_a_line_or_run_long(app, db, owner):
    _, dropped = _run(app, db, "pop fake:drop-line")
    assert [ln["heard"] for ln in dropped.output["timing"]["lines"]] == [1, 1, 1, 0]
    _, repeated = _run(app, db, "pop fake:repeat-line")
    assert [ln["times_sung"] for ln in repeated.output["timing"]["lines"]] == [1, 1, 1, 2]
    _, long = _run(app, db, "pop fake:long=400")
    assert long.output["timing"]["seconds"] > 399


def test_a_failed_timing_says_whether_trying_again_can_help(app, db, owner, monkeypatch):
    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings, app.state.storage)
    user = db.query(User).first()
    app.state.storage.put("junk", b"not a song")
    jobs = [enqueue(db, user, "song_timing", {"song_key": "junk", "lyrics": LYRICS}, units=0,
                    provider="local")]  # fmt: skip
    run_once(db, providers, app.state.storage)

    def slow(path, lyrics):
        raise RuntimeError("Reading the sung words took too long.")

    monkeypatch.setattr(providers["local"], "hear_song", slow)
    app.state.storage.put("song", song())
    jobs.append(enqueue(db, user, "song_timing", {"song_key": "song", "lyrics": LYRICS},
                        units=0, provider="local"))  # fmt: skip
    run_once(db, providers, app.state.storage)
    for job in jobs:
        db.refresh(job)
    assert [(j.status, j.error) for j in jobs] == [
        (JobStatus.failed, music.TIMING_UNREADABLE),
        (JobStatus.failed, music.TIMING_FAILED),
    ]


def test_a_take_longer_than_any_ad_says_so(app, db, owner, monkeypatch):
    def too_long(path):
        raise song_timing.TooLong("Song length 950 s is over 900 s.")

    monkeypatch.setattr(song_timing, "length", too_long)
    _, timed = _run(app, db, "pop")
    assert (timed.status, timed.error) == (JobStatus.failed, music.TIMING_TOO_LONG)


def test_lip_sync_marks_are_never_sung_or_sent():
    marked = "[Chorus] [Lip-sync]\nGut so happy, tail so high [Lip-sync]\n[Lip-sync]\n\nIron Paws"
    assert music.sung(marked) == ["Gut so happy, tail so high", "Iron Paws"]
    assert music.job(marked, "pop")["input"]["lyrics"] == (
        "[Chorus]\nGut so happy, tail so high\n\nIron Paws"
    )
    sung = song_timing.lines(marked, [], 10)
    assert [(ln["section"], ln["text"]) for ln in sung] == [
        ("Chorus", "Gut so happy, tail so high"), ("Chorus", "Iron Paws")
    ]  # fmt: skip
