"""An Omni talker's cut, sound and checks (the outside editor's UGC playbook, adopted by Reed on
9 Nov: app/talker_sound.py). Synthetic sound and pictures made with ffmpeg here; stand-ins
only, no paid calls."""

import json
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest

from app import cut, cut_render, director, reel, song_timing, spend, talker_sound, watch_report
from app.catalogue import get_model
from app.db import utcnow
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.settings import get_settings
from tests.test_omni_talker import SAYS, _clips, _jobs, _made

DEMUCS = Path(__file__).parent / "fixtures/replicate/ryan5453_demucs.json"

TONE = 0.3  # a "word": a 220 Hz tone at about -13.5 dBFS
STILL = "color=c=gray:s=180x320:r=30:d={d}"
MOVING = f"{STILL},geq=lum='random(1)*255':cb=128:cr=128"  # a picture that never stays still


@pytest.fixture(autouse=True)
def songs_on(monkeypatch):
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)


def _piece(path: Path, words: list[tuple[float, float]], seconds: float, room: float = 0.002,
           picture: str = STILL, hiss: tuple[float, float] = (0, 0)) -> Path:  # fmt: skip
    """A take: a still picture, and a room's pink noise (`room` its amplitude) with a tone
    for each word and a soft "s" (`hiss`, about -51 dBFS); PCM, so its edges are exact."""
    on = "+".join(f"between(t,{a},{b})" for a, b in words) or "0"
    on = f"{TONE}*sin(2*PI*220*t)*({on})+0.004*sin(2*PI*3000*t)*between(t,{hiss[0]},{hiss[1]})"
    command = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", picture.format(d=seconds),
               "-f", "lavfi", "-i", f"aevalsrc='{on}':s=48000:d={seconds}",
               "-f", "lavfi", "-i", f"anoisesrc=c=pink:a={room}:r=48000:seed=1:d={seconds}",
               "-filter_complex", "[1:a][2:a]amix=inputs=2:normalize=0[a]", "-map", "0:v",
               "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le",
               "-f", "mov", str(path)]  # fmt: skip
    subprocess.run(command, check=True, timeout=60)  # noqa: S603
    return path


def _levels(path: Path) -> list[float]:
    return song_timing.levels(song_timing._samples(path, song_timing.CLEAR), song_timing.CLEAR)


def _db(levels: list[float], t: float) -> float:
    return levels[min(round(t / song_timing.HOP), len(levels) - 1)]


def test_speech_is_found_from_the_pieces_own_sound_and_noise_floor(tmp_path):
    words = [(0.6, 1.4), (2.2, 3.1)]
    quiet = talker_sound.measure(_piece(tmp_path / "a.mov", words, 4.0), [{"text": "Hi."}])
    assert quiet["speech"] == pytest.approx([0.6, 3.1], abs=0.02)
    assert quiet["floor"] < -50 and quiet["quiet"] == talker_sound.QUIET
    loud = talker_sound.measure(_piece(tmp_path / "b.mov", words, 4.0, room=0.1), [])
    assert loud["floor"] > -52 and loud["quiet"] == pytest.approx(loud["floor"] + 10, abs=0.15)
    assert loud["speech"] == pytest.approx([0.6, 3.1], abs=0.02)  # a loud room: still the words
    bump = talker_sound.measure(_piece(tmp_path / "c.mov", [(0.1, 0.15), *words], 4.0), [],
                                vad=lambda path: [[0.55, 3.2]])  # fmt: skip
    assert bump["speech"] == pytest.approx([0.6, 3.1], abs=0.02)  # a knock isn't the voice
    soft = talker_sound.measure(_piece(tmp_path / "d.mov", words, 4.0, hiss=(0.45, 0.6)), [])
    assert soft["speech"][0] == pytest.approx(0.45, abs=0.02)  # its soft "s" is the word's


def test_a_piece_is_trimmed_by_numbers_every_cut_quiet_on_the_frame_grid(tmp_path):
    words = [(0.7, 1.5), (1.6, 2.4), (3.0, 4.2)]  # a 0.1 s gap kept, a 0.6 s one cut to a beat
    path = _piece(tmp_path / "a.mov", words, 5.0)
    m, levels = talker_sound.measure(path, [{"text": "I told him."}]), _levels(path)
    (a, x), (y, b) = talker_sound.keep(m, last=False)
    assert -1 / 30 - 0.02 < a - (0.7 - talker_sound.HEAD) <= 0.02  # just before it
    assert -0.02 <= b - (4.2 + talker_sound.SENTENCE) < 1 / 30 + 0.02  # just after it
    assert (x - 2.4) + (3.0 - y) == pytest.approx(talker_sound.BEAT, abs=0.04)
    for t in (a, x, y, b):  # never inside a word: quiet at every cut, on the grid
        assert _db(levels, t) < talker_sound.QUIET
        assert t * 30 == pytest.approx(round(t * 30), abs=0.02)
    comma = {**m, "comma": True}
    assert talker_sound.keep(comma, False)[-1][1] < 4.2 + talker_sound.COMMA + 1 / 30
    assert talker_sound.measure(path, [{"text": "When I told him,"}])["comma"]
    first, *_, last = talker_sound.keep(m, last=True)  # the ending as made; the opening on its word
    assert (first[0], last[1]) == (a, 5.0)
    # video 390: a sentence made up after the line, muted: the piece ends on the line itself
    *_, (_, end) = talker_sound.keep(m, False, muted=[[2.9, 4.3]])
    assert 2.4 <= end < 2.4 + talker_sound.SENTENCE + 1 / 30 + 0.02
    assert talker_sound.keep(m, False, muted=[[1.55, 2.45]])[-1][1] == b  # mid-piece: no
    # video 399: the transcript ended the muted words 0.3 s before their sound did, and the
    # piece ran on through them, the presenter mouthing in silence
    assert talker_sound.keep(m, False, muted=[[2.9, 3.9]])[-1][1] == end


def test_the_talkers_pieces_play_their_kept_stretches_back_to_back(app, db, owner, monkeypatch):
    video = _made(app, db, owner)
    m = {"length": 15.0, "comma": False, "sounds": [[0.9, 2.0], [2.6, 3.4]],
         "speech": [0.9, 3.4]}  # fmt: skip
    monkeypatch.setattr("app.talker_sound.measured", lambda db, take: m)
    tl = cut.base(db, video)
    rows = [r.clip_id for r in _clips(db, video) if SAYS in r.prompt]
    for n, clip in enumerate(rows):
        mine = [p for p in tl["pieces"] if p["clip_id"] == clip]
        kept = talker_sound.keep(m, n == len(rows) - 1)
        assert [(p["from"], round(p["from"] + p["end"] - p["start"], 3)) for p in mine] == [
            (round(a, 3), round(b, 3)) for a, b in kept]  # fmt: skip
    # Reed, 12 Nov: "start on the FIRST WORD": the 0.9 s before the voice isn't played
    assert tl["pieces"][0]["start"] == 0.0 and 0.8 < tl["pieces"][0]["from"] < 0.9
    assert tl["pieces"][-1]["end"] == tl["length"]
    ends = [p["end"] for p in tl["pieces"]]
    assert [p["start"] for p in tl["pieces"][1:]] == ends[:-1]  # back to back
    assert tl["speed"] == talker_sound.SPEED


def test_back_to_back_b_roll_never_flashes_the_talker_and_no_take_is_used_twice():
    tl = {
        "length": 30.0,
        "pieces": [{"clip_id": "c1", "start": 0.0, "end": 30.0, "from": 0.0}],
        "over": [
            {"take_id": 1, "piece": "c1", "at": 2.0, "seconds": 3.0},
            {"take_id": 2, "piece": "c1", "at": 6.0, "seconds": 3.0},  # 1 s after
            {"take_id": 3, "piece": "c1", "at": 12.0, "seconds": 3.0},  # 3 s after
            {"take_id": 2, "piece": "c1", "at": 20.0, "seconds": 3.0},
        ],
    }  # used again
    laid = cut.laid_over(tl)
    assert [(o["take_id"], o["start"], o["length"]) for o in laid] == [
        (1, 2.0, 3.0), (2, 5.0, 3.0), (3, 12.0, 3.0)]  # fmt: skip


def _take(path: Path, level: float, seconds: float = 3.0) -> bytes:
    """An MP4 take: a tone at `level` (amplitude), as Omni's AAC sound."""
    out = path.with_suffix(".mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",  # noqa: S603, S607
                    f"color=c=gray:s=180x320:r=30:d={seconds}", "-f", "lavfi", "-i",
                    f"aevalsrc='{level}*sin(2*PI*220*t)*between(t,0.5,2.5)':s=48000:d={seconds}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)],
                   check=True, timeout=60)  # fmt: skip
    return out.read_bytes()


def _loudness(tmp: Path, data: bytes) -> dict:
    (tmp / "m.mp4").write_bytes(data)
    return cut_render._loudness(tmp, "m.mp4")


def test_every_take_is_brought_to_one_speech_loudness_by_one_fixed_gain(tmp_path):
    quiet, loud = _take(tmp_path / "q", 0.02), _take(tmp_path / "l", 0.5)
    ones = [float(_loudness(tmp_path, talker_sound.even(v, None))["input_i"])
            for v in (quiet, loud)]  # fmt: skip
    assert ones == pytest.approx([talker_sound.SPEECH] * 2, abs=0.5)  # 28 dB apart before
    voice = _take(tmp_path / "v", 0.1)  # the separated voice replaces the take's own sound
    (tmp_path / "s.mp4").write_bytes(talker_sound.even(quiet, voice))
    assert cut_render.seconds(tmp_path.joinpath("s.mp4").read_bytes()) == pytest.approx(3, abs=0.1)


def _crossings(path: Path, a: float, b: float) -> float:
    """Zero crossings a second between a and b: twice a tone's pitch."""
    s = song_timing._samples(path, song_timing.CLEAR)[int(a * 24000) : int(b * 24000)]
    return sum((x < 0) != (y < 0) for x, y in zip(s, s[1:], strict=False)) / (b - a)


def test_the_talkers_cut_is_faster_on_one_room_at_one_fixed_gain(tmp_path):
    words = [(0.5, 2.0), (4.0, 5.5)]
    data = (_piece(tmp_path / "a.mov", words, 7.0, room=0.0)).read_bytes()
    made = tmp_path / "made.mp4"
    made.write_bytes(talker_sound.finish(data))
    assert cut_render.seconds(made.read_bytes()) == pytest.approx(7.0 / talker_sound.SPEED, abs=0.1)
    k = talker_sound.SPEED
    assert _crossings(made, 0.6 / k, 1.9 / k) == pytest.approx(440, rel=0.03)  # pitch kept
    levels = _levels(made)
    room = [_db(levels, t / k) for t in (2.3, 3.0, 3.7, 5.9, 6.5)]  # in every pause
    speech = _db(levels, 1.0 / k)
    assert max(room) - min(room) < 2.0  # one steady room, never pumped up in a pause
    assert speech - max(room) == pytest.approx(37, abs=4)  # where room.py's room sits
    loud = _loudness(tmp_path, made.read_bytes())
    assert float(loud["input_i"]) == pytest.approx(talker_sound.AIM, abs=1.0)
    assert float(loud["input_tp"]) <= cut_render.CEILING


def test_each_piece_is_checked_before_the_cut_for_drags_fillers_doubles_and_moving(tmp_path):
    heard = [{"words": [{"word": " I", "start": 0.5, "end": 0.6},
                        {"word": " um,", "start": 0.7, "end": 0.9},
                        {"word": " done", "start": 1.0, "end": 1.2},
                        {"word": " done.", "start": 1.25, "end": 1.4},
                        {"word": " So", "start": 2.0, "end": 2.8}]}]  # fmt: skip
    lines = [{"text": "I done. So."}]
    m = {"length": 4.0, "speech": [0.5, 2.8], "sounds": [[0.5, 1.4], [2.0, 2.3]],
         "motion": [0.5, 0.4, 0.6, 0.5]}  # fmt: skip
    found = talker_sound.findings(m, heard, lines)
    assert [f["kind"] for f in found] == ["filler", "stutter"]  # "So" sounds only 0.3 s
    m["sounds"] = [[0.5, 1.4], [2.0, 2.8]]
    found = talker_sound.findings(m, heard, [{"text": "I done done. So."}])  # its own double
    assert [f["kind"] for f in found] == ["filler", "held"]
    moving = talker_sound.measure(_piece(tmp_path / "m.mov", [(0.5, 2.5)], 3.0, picture=MOVING),
                                  [])  # fmt: skip
    (f,) = talker_sound.findings(moving, [], [])
    assert f["kind"] == "motion" and "seated" in f["change_note"]
    known = talker_sound.facts(moving, [], [])
    assert watch_report.confirmed("motion", "measured", known)  # the watch's note, measured
    assert not watch_report.confirmed("timing", "measured", known)  # nothing held here


def test_a_talker_piece_is_heard_with_its_fillers(monkeypatch, tmp_path):
    ran = []
    monkeypatch.setattr(reel, "_run", lambda args, timeout: ran.append(args) or
                        subprocess.CompletedProcess(args, 0, b"[]", b""))  # fmt: skip
    reel.transcribe(tmp_path / "t.mp4", True, fillers=True)
    assert ran[0][-2:] == ["--sounds", "--fillers"]


def test_each_talker_piece_has_its_voice_separated_and_the_cut_plays_faster(app, db, owner):
    video = _made(app, db, owner)
    split = _jobs(db, video, talker_sound.STEP)
    talks = [r for r in _clips(db, video) if SAYS in r.prompt]
    assert {j.input["take_id"] for j in split} == {
        t.id for r in talks for t in db.query(ClipTake).filter_by(clip_id=r.id)}  # fmt: skip
    schema = json.loads(DEMUCS.read_text())
    for job in split:  # Demucs on Replicate, priced from the catalogue, as its schema reads
        assert (job.provider, job.input["model"]) == ("replicate", talker_sound.MODEL)
        assert get_model(talker_sound.MODEL).provider_version == schema["version"]
        assert {*job.input["input"], *job.input["files"]} <= set(schema["Input"]["properties"])
        assert "vocals" in schema["Output"]["properties"]
        assert job.credits == talker_sound.price(db, video.workspace_id) > 0
        assert spend.kind_name(job.provider, job.kind) == "Voice"  # never "Sound effects"
        take = db.get(ClipTake, job.input["take_id"])
        assert take.made_with[talker_sound.KEY] == job.output["file_ids"][0]
    broll = [r for r in _clips(db, video) if SAYS not in r.prompt]
    assert not {j.input["take_id"] for j in split} & {r.picked_take_id for r in broll}
    made = db.query(FinalVideo).filter_by(project_id=video.id).order_by(FinalVideo.id).all()[-1]
    assert made.timeline["speed"] == talker_sound.SPEED
    assert made.seconds == pytest.approx(made.timeline["length"] / talker_sound.SPEED, abs=0.15)
    rows = list(db.query(ProjectClip).filter_by(project_id=video.id))
    assert not talker_sound.waiting(db, video, rows)
    job = next(j for j in split if j.input["take_id"] in {r.picked_take_id for r in rows})
    job.status = "running"  # a voice still being separated: the cut waits for it
    db.commit()
    assert talker_sound.waiting(db, video, rows)
    assert job in director._waiting(db, video)  # and the director with it


def test_a_separation_is_waited_for_three_minutes_at_most_and_never_with_paid_work_off(
    app, db, owner, monkeypatch
):
    video = _made(app, db, owner)
    rows = list(db.query(ProjectClip).filter_by(project_id=video.id))
    job = next(j for j in _jobs(db, video, talker_sound.STEP)
               if j.input["take_id"] in {r.picked_take_id for r in rows})  # fmt: skip
    job.status, job.created_at = "running", utcnow() - talker_sound.WAIT_FOR - timedelta(seconds=1)
    db.commit()
    assert not talker_sound.waiting(db, video, rows)  # the take's own sound, and on
    assert job not in director._waiting(db, video)
    job.status, job.created_at = "queued", utcnow()
    db.commit()
    monkeypatch.setattr(get_settings(), "fake_providers", False)
    monkeypatch.setattr(get_settings(), "generation_enabled", True)
    assert talker_sound.waiting(db, video, rows)
    monkeypatch.setattr(get_settings(), "generation_enabled", False)  # paid work is off: it
    assert not talker_sound.waiting(db, video, rows)  # would never run, so never waited for


def test_a_separation_that_cant_be_queued_never_stops_the_take(db, monkeypatch, caplog):
    def broken(*args):
        raise RuntimeError("no catalogue")

    monkeypatch.setattr(talker_sound, "queue", broken)
    take = ClipTake(id=1, clip_id=1, number=1, job_id=1, file_id=1)
    talker_sound.queue_safely(db, None, take, None)  # logged, nothing raised
    assert "voice separation of take 1" in caplog.text


def test_a_trimmed_pieces_words_are_all_kept(monkeypatch):
    tl = {"mode": "takes", "speed": talker_sound.SPEED, "pieces": [
        {"take_id": 5, "start": 0.0, "end": 1.467, "from": 0.633},
        {"take_id": 5, "start": 1.467, "end": 2.5, "from": 2.5}]}  # fmt: skip
    heard = [{"word": "I", "start": 0.0, "end": 0.9},  # its silence before glued on
             {"word": "said", "start": 1.0, "end": 1.9},
             {"word": "so", "start": 2.0, "end": 2.9},  # mostly after the cut pause
             {"word": "hour.", "start": 3.2, "end": 4.2}]  # run past the tail  # fmt: skip
    monkeypatch.setattr(cut, "_heard", lambda db, take: heard)
    words = cut._cut_words(type("Db", (), {"get": lambda self, kind, i: object()})(), tl)
    said = [("I", 0.0, 0.27), ("said", 0.37, 1.27), ("so", 1.47, 1.87), ("hour.", 2.17, 2.5)]
    assert [(w["word"], w["start"], w["end"]) for w in words] == said
