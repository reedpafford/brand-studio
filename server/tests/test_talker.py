"""The UGC talker (Reed, 3 Nov: "Heygen for still imaged UGC talking, yes."): a MiniMax voice
in a room, one HeyGen Avatar IV take of it from one still, and the cut alternating the talker
and B-roll cut-ins. Stand-ins and a mocked HeyGen only: no paid calls."""

import base64
import json
import re
import subprocess
from pathlib import Path

import httpx2 as httpx
import pytest

from app import (
    director,
    director_song,
    director_tools,
    guides,
    host,
    model_map,
    narration,
    prompts,
    room,
    talker,
)
from app.catalogue import get_model
from app.models.accounts import User
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.freestyles import Freestyle
from app.models.jobs import Job
from app.models.projects import Project
from app.models.songs import SongTake
from app.providers import NoKey, NotStarted
from app.providers.heygen import HeyGenProvider
from tests.conftest import first_brand
from tests.test_freestyle_dialogue import _run

LINES = ("Every morning starts the same.\nThe bowl, the wait, the wag.\nIron Paws makes the bowl "
         "worth waiting for.")  # fmt: skip


@pytest.fixture(autouse=True)
def songs_on(monkeypatch):
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)


def _steps(db, video, step):
    return [j for j in db.query(Job).filter(Job.project_id == video.id).order_by(Job.id)
            if j.input.get("step") == step]  # fmt: skip


def test_a_ugc_presenter_talks_on_heygen_in_one_take_cut_between_b_roll(app, db, owner):
    body = {"type": "presenter", "look": "ugc", "shape": "9:16", "text": LINES,
            "brand_id": first_brand(owner)}  # fmt: skip
    fs = owner.post("/freestyles", json=body).json()
    _run(app, db, ticks=200)
    out = owner.get(f"/freestyles/{fs['id']}").json()
    assert out["status"] == "delivered", [t["text"] for t in out["thread"]][-4:]
    video = db.get(Project, db.get(Freestyle, fs["id"]).project_id,
                   execution_options={"see_hidden": True})  # fmt: skip
    (voice,) = [j for j in _steps(db, video, "song_take") if j.kind == "speech"]
    assert (voice.input["model"], voice.input["input"]["voice_id"]) == (
        narration.MINIMAX, talker.VOICE)  # a MiniMax voice by default  # fmt: skip
    (timing,) = db.query(Job).filter(Job.kind == "narration_timing").all()
    assert timing.input["room"] == talker.place(db, video) in room.PLACES  # its room's sound
    (still,) = _steps(db, video, host.STILL)
    said = still.input["input"]["prompt"]  # where their clip's still has them (video 281)
    assert "where [Image1] (the opening still of their clip) shows them" in said
    assert talker.frame(db, video) in still.input["files"]["image_input"] and "alone" in said
    assert "green" not in still.input["input"]["prompt"]
    (piece,) = _steps(db, video, host.PIECE)  # ONE take, the whole narration
    (row,) = host.rows(db, video)[1:]
    assert (piece.provider, piece.input["model"], row.start) == ("heygen", talker.MODEL, 0.0)
    assert row.end == pytest.approx(db.get(SongTake, video.song_take_id).seconds)
    sent = piece.input["input"]
    assert (sent["expressiveness"], sent["resolution"]) == ("high", "720p")  # th-20s: high
    assert sent["motion_prompt"] == f"{talker.MOTION} {talker.ALONE}"  # the plain one, no hands
    assert "hand" not in talker.MOTION
    assert piece.input["files"] == {"image": [host.rows(db, video)[0].file_id],
                                    "audio": [row.audio_file_id]}  # fmt: skip
    assert piece.credits == sent["duration"] * get_model(talker.MODEL).credits_per_unit("720p")
    said = talker.clips(db, video)
    rows = {r.clip_id: r for r in db.query(ProjectClip).filter_by(project_id=video.id)}
    assert said and set(rows) - said  # the cut alternates talker and B-roll
    takes = {j.input["project_clip_id"] for j in _steps(db, video, "clip_take")}
    assert not takes & {rows[c].id for c in said}  # no paid take of a talker clip
    for c in said:  # each cut from the talker's take, free
        assert db.get(ClipTake, rows[c].picked_take_id).job_id == piece.id
    timed = db.get(SongTake, video.song_take_id).timing
    assert timed["pace"] == narration.pace(timed["words"])  # its pace, measured
    final = db.query(FinalVideo).filter_by(project_id=video.id).order_by(FinalVideo.id).all()[-1]
    assert len(final.take_ids) == len(rows)
    from app import cut, cut_render

    tl, _ = cut.timeline(db, video)  # the B-roll's own sound far under the talker (293)
    assert set(cut_render.recipe(db, video, tl)["takes"]) == {cut_render.UNDER_TALKER}
    director = prompts.system("director")
    assert "where its guide measures its own talker rhythm" in director  # the style's swaps first


def test_the_directors_motion_note_makes_the_talker_and_a_remake_keeps_it(app, db, owner):
    body = {"type": "presenter", "look": "ugc", "shape": "9:16", "text": LINES,
            "brand_id": first_brand(owner)}  # fmt: skip
    fs = owner.post("/freestyles", json=body).json()
    _run(app, db, ticks=200)
    video = db.get(Project, db.get(Freestyle, fs["id"]).project_id,
                   execution_options={"see_hidden": True})  # fmt: skip
    note = "Close to tears, fighting it: chin trembles. Both hands stay on the steering wheel."
    user, storage = db.get(User, video.created_by_id), app.state.storage
    said = director_tools.run(db, user, video, {"tool": "host", "note": note}, storage)
    assert said == "Refused: " + host.MADE + director_tools.REDRAW  # made: redraw its still
    host.make(db, user, video, storage, number=1, motion=note)
    assert _steps(db, video, host.PIECE)[-1].input["input"]["motion_prompt"] == (
        f"{note} {talker.ALONE}"
    )  # nobody else in it, whatever the note (video 281)
    _run(app, db, ticks=5)
    host.make(db, user, video, storage, number=1)  # again with none: the last one stays
    assert _steps(db, video, host.PIECE)[-1].input["input"]["motion_prompt"] == (
        f"{note} {talker.ALONE}"
    )  # nobody else in it, whatever the note (video 281)
    assert talker.motion(" ") == talker.MOTION and len(talker.motion("x" * 900)) == 600
    for said in (talker.ALONE, talker.MOTION):  # said as what's there (#1392: no negatives)
        assert not re.search(r"\b(?:no|nobody|never|not)\b", said, re.I), said
    heard = db.get(SongTake, video.song_take_id).timing["pace"]  # measured, then set from it
    want = director_song.target(db, video)
    assert want == (3.3, 3.5) and director_song.state(db, video)["pace_wanted"] == want
    first = narration.speed_for("auto", talker.VOICE)  # the talker's voice's own start
    speed = narration.retimed(first, heard, want) or first
    said = director_song.run(db, user, video, {"tool": "narration", "emotion": "auto"}, {})
    assert said.startswith("Making the narration"), said
    (voice, *_) = sorted((j for j in _steps(db, video, "song_take") if j.kind == "speech"),
                         key=lambda j: -j.id)  # fmt: skip
    assert voice.input["input"]["speed"] == speed


def test_an_emotion_speeds_minimax_up_and_a_remake_is_set_from_the_measured_pace():
    words = "Two of them get out and walk right at her."
    speed = {e: narration.job(words, "English_Graceful_Lady", emotion=e)["input"]["speed"]
             for e in ("fearful", "sad", "auto", "calm")}  # fmt: skip
    assert speed == {"fearful": 1.5, "sad": 1.3, "auto": 1.1, "calm": 1.1}  # th-20s, measured
    friendly = narration.job(words, "English_FriendlyPerson", emotion="calm")["input"]["speed"]
    assert friendly == 0.85  # 281 and 293: 4.9, 3.7 and 2.9 words a second at 1.1, 0.9, 0.76
    scared = narration.job(words, "English_FriendlyPerson", emotion="fearful")["input"]["speed"]
    assert scared == round(0.85 * 1.5 / 1.1, 2)  # the emotion's rise, from the voice's own start
    assert narration.job(words, "English_Graceful_Lady", speed=2.6)["input"]["speed"] == 2.0
    heard = [{"word": "a", "start": 0.0, "end": 0.4}, {"word": "b", "start": 0.45, "end": 1.0},
             {"word": "c", "start": 2.0, "end": 2.5}]  # a 1 s pause, left out  # fmt: skip
    assert narration.pace(heard) == round(3 / 1.5, 2) and narration.pace(heard[:1]) is None
    assert narration.retimed(0.76, 2.88, (3.3, 3.5)) == 0.85  # 293's take 1, to the middle
    assert narration.retimed(1.1, 4.9, (3.3, 3.5)) == 0.85  # 281's take 1: the same 0.85
    assert narration.retimed(1.5, 3.4, (3.3, 3.5)) is None  # inside the style's range
    assert guides.pace("ugc", "presenter") == (3.3, 3.5)  # "3.3–3.5 words a second"
    assert guides.pace("dr-pickle", "presenter") == (3.1, 4.3)
    assert "English_Graceful_Lady" in narration.VOICES  # the older woman (th-20s)
    assert director_song.REMAKES >= 1


def test_photoreal_seedance_b_roll_describes_people_instead_of_attaching_them():
    people, nobody = [{"character_ids": ["char:1"]}], [{"character_ids": []}]
    assert model_map.unsent("ugc", "seedance-2.0", people) == ("char:", "frame:")
    assert model_map.unsent("ugc", "seedance-1-lite", nobody) == ("char:",)
    assert model_map.unsent("house", "seedance-2.0", people) == ()  # a drawn look sends them
    assert model_map.unsent("ugc", "p-video", people) == ()


def test_a_minimax_reading_keeps_the_words_and_its_pauses_survive_the_trim(tmp_path):
    words = "Your dog's gut is a mess. Iron Paws fixes it."
    marked = "Your dog's gut is a mess. <#0.4#> (breath) Iron Paws fixes it."
    made = narration.job(words, "English_ConfidentWoman", emotion="calm", reading=marked)
    assert made["model"] == narration.MINIMAX and made["input"]["text"] == marked
    assert (made["input"]["emotion"], made["input"]["speed"]) == ("calm", 1.1)
    assert narration.kept_pause(made) == narration.MARKED_KEEP  # kept, at most 0.3 s (281)
    assert narration.kept_pause({"input": {"text": "One. <#0.2#> Two."}}) == 0.2
    for wrong in ("Your cat's gut is a mess. <#0.4#> Iron Paws fixes it.",
                  "Your dog's gut is a mess. <#0.4#><#0.3#> Iron Paws fixes it."):  # fmt: skip
        with pytest.raises(ValueError, match="words exactly"):
            narration.job(words, "English_ConfidentWoman", reading=wrong)
    with pytest.raises(ValueError, match="no note"):
        narration.job(words, "English_ConfidentWoman", note="slower and warmer")
    recorded = json.loads(
        (Path(__file__).parent / "fixtures/replicate/minimax_speech-2.8-hd.json").read_text()
    )
    assert set(narration.EMOTIONS) == set(recorded["enums"]["emotion"]["enum"])
    gap = _tone(tmp_path / "gap.mp3", "between(t,0,1)+between(t,2,3)", 3)  # a 1 s silence
    kept = narration.trim(gap, tmp_path / "kept.mp3", 0.5)  # a marked 0.5 s pause stays 0.5
    assert _length(kept) > _length(narration.trim(gap, tmp_path / "cut.mp3")) + 0.15


def _ff(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True).stderr  # noqa: S603


def _tone(path: Path, when: str, seconds: int) -> Path:
    _ff("ffmpeg", "-v", "error", "-f", "lavfi", "-i",
        f"aevalsrc='0.3*sin(2*PI*180*t)*({when})':d={seconds}", str(path))  # fmt: skip
    return path


def _length(path: Path) -> float:
    probe = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0"]
    return float(subprocess.run([*probe, str(path)], capture_output=True, text=True).stdout)  # noqa: S603


@pytest.mark.parametrize("place", ["room", "car"])
def test_the_room_keeps_the_voices_length_fills_its_gaps_and_sets_its_loudness(tmp_path, place):
    dry = _tone(tmp_path / "dry.mp3", "between(t,0,1.5)+between(t,2,3.5)", 4)  # dead gaps
    wet = room.finish(dry, tmp_path / "wet.mp3", place)
    assert room.graph("car") != room.graph() and talker.CAR.search("his parked car, seatbelt on")
    assert not talker.CAR.search("at her kitchen table, cards on the counter")  # a room
    assert abs(_length(wet) - _length(dry)) < 0.06
    gaps = _ff("ffmpeg", "-i", str(wet), "-af", "silencedetect=n=-70dB:d=0.2", "-f", "null", "-")
    assert "silence_start" not in gaps  # room tone under every gap
    tone = _ff("ffmpeg", "-i", str(wet), "-af", "atrim=1.65:1.85,highpass=f=200,astats",
               "-f", "null", "-")  # fmt: skip
    level = float(re.findall(r"RMS level dB:\s+(-?[\d.]+)", tone)[-1])
    assert -64 < level < -45  # heard on a phone's speaker, well under the voice (281's: -68)
    loud = _ff("ffmpeg", "-i", str(wet), "-af", "ebur128", "-f", "null", "-")
    assert abs(float(re.findall(r"I:\s+(-?[\d.]+) LUFS", loud)[-1]) - room.LUFS) < 1.5


PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nstill").decode()
MP3 = base64.b64encode(b"ID3voice").decode()
JOB = {"model": talker.MODEL, "input": {
    "image": f"data:image/png;base64,{PNG}", "audio": f"data:audio/mpeg;base64,{MP3}",
    "aspect_ratio": "9:16", "resolution": "720p", "expressiveness": "high",
    "motion_prompt": talker.MOTION, "title": "t", "duration": 25}}  # fmt: skip


def test_heygen_uploads_the_voice_animates_the_still_and_prices_the_seconds():
    seen, states = [], iter(["processing", "completed"])

    def api(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/v3/assets":
            return httpx.Response(200, json={"data": {"asset_id": "a1"}})
        if request.url.path == "/v3/videos":
            return httpx.Response(200, json={"data": {"video_id": "v1", "status": "waiting"}})
        if request.url.path == "/v3/videos/v1":
            return httpx.Response(200, json={"data": {
                "id": "v1", "status": next(states), "duration": 25.07,
                "video_url": "https://files2.heygen.ai/v1.mp4?Signature=x"}})  # fmt: skip
        return httpx.Response(200, content=b"\0\0\0\x18ftypmp42")  # the file host

    client = httpx.Client(transport=httpx.MockTransport(api))
    heygen = HeyGenProvider("https://api.heygen.com", "test-key", client)
    assert heygen.submit("video", JOB) == "v1"
    upload, create = seen
    assert b'filename="voice.mp3"' in upload.content and b"ID3voice" in upload.content
    body = json.loads(create.content)
    assert body == {"type": "image", "audio_asset_id": "a1",
                    "image": {"type": "base64", "media_type": "image/png", "data": PNG},
                    "aspect_ratio": "9:16", "resolution": "720p", "expressiveness": "high",
                    "motion_prompt": talker.MOTION, "title": "t"}  # fmt: skip
    assert heygen.poll("v1").state == "running"
    done = heygen.poll("v1")
    assert done.files == ["https://files2.heygen.ai/v1.mp4?Signature=x"]
    assert float(done.usage[0].cost_usd) == pytest.approx(25.07 * 0.039)
    data, kind = heygen.fetch(done.files[0])
    assert kind == "video/mp4" and "x-api-key" not in seen[-1].headers  # the key: API only
    assert all(r.headers["x-api-key"] == "test-key" for r in seen[:-1])
    with pytest.raises(RuntimeError, match="Refusing"):
        heygen.fetch("https://example.com/v1.mp4")
    busy = HeyGenProvider("https://api.heygen.com", "k", httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(429))))  # fmt: skip
    with pytest.raises(NotStarted):
        busy.submit("video", JOB)
    with pytest.raises(NoKey):
        HeyGenProvider("https://api.heygen.com", "", client).submit("video", JOB)


def _talker(app, db, owner) -> Project:
    """A UGC presenter video, made: its talker's still and one HeyGen take."""
    body = {"type": "presenter", "look": "ugc", "shape": "9:16", "text": LINES,
            "brand_id": first_brand(owner)}  # fmt: skip
    fs = owner.post("/freestyles", json=body).json()
    _run(app, db, ticks=200)
    return db.get(Project, db.get(Freestyle, fs["id"]).project_id,
                  execution_options={"see_hidden": True})  # fmt: skip


def test_a_talker_with_the_wrong_picture_is_redrawn_with_a_note_and_its_take_follows(
    app, db, owner
):
    """Video 281: all three HeyGen tries came from one still in the wrong room, and nothing
    could draw it again (redraw_still, host and make_take each refused, pointing at another).
    redraw_still on a talker shot draws the still again with the note and the take is made
    from the new still; every refusal points there. A talker clip's take says HeyGen and
    costs the talker's take."""
    from app.clip_prompts import newest
    from app.clip_takes import take_credits
    from app.routes.jobs import DIRECTOR_TOOL

    video = _talker(app, db, owner)
    user, storage = db.get(User, video.created_by_id), app.state.storage
    said = director_tools.run(db, user, video, {"tool": "host"}, storage)
    assert "redraw_still" in said  # made: the way to change it, never "Make it again"
    mine = sorted(talker.clips(db, video))
    row = db.query(ProjectClip).filter_by(project_id=video.id, clip_id=mine[0]).one()
    taken = director_tools.run(db, user, video, {"tool": "make_take", "clip_id": mine[0]},
                               storage)  # fmt: skip
    assert taken.startswith("Refused") and "redraw_still" in taken, taken  # points there too
    picked = db.get(ClipTake, row.picked_take_id)
    assert picked.made_with["model"] == talker.MODEL  # "Made on HeyGen", never Omni
    assert take_credits(db, video, row) == host.price(db, video, 1)  # the talker's take
    from app.clip_takes import takes_price

    every = db.query(ProjectClip).filter_by(project_id=video.id).all()
    broll = sum(take_credits(db, video, c) for c in every if c.clip_id not in mine)
    assert takes_price(db, video, every) == broll + host.price(db, video, 1)  # once, together
    shot = next(c["shot_ids"][0] for c in newest(db, video).data["clips"] if c["id"] == mine[0])
    note = "Alone in the driver's seat of his parked car, nobody behind him."
    marked = DIRECTOR_TOOL.set(True)
    try:
        said = director_tools.run(db, user, video, {"tool": "redraw_still", "shot_id": shot,
                                                    "note": note}, storage)  # fmt: skip
    finally:
        DIRECTOR_TOOL.reset(marked)
    assert said.startswith("Drawing the host's still again"), said
    redrawn = _steps(db, video, host.STILL)[-1]
    assert f"Change from the last still: {note}" in redrawn.input["input"]["prompt"]
    plan = newest(db, video).data  # QA on #1457: each redraw makes a whole HeyGen take again,
    talks = [s for c in plan["clips"] if c["id"] in mine for s in c["shot_ids"]]  # so all
    broll = next(s for c in plan["clips"] if c["id"] not in mine for s in c["shot_ids"])
    keys = {director._still_key(db, video, {"shot_id": s}) for s in talks}  # their shots
    assert keys == {director.TALKER} and director._still_key(db, video, {"shot_id": broll}) == (
        broll)  # share one count (twice a run); a B-roll still keeps its own  # fmt: skip
    _run(app, db, ticks=20)
    db.expire_all()
    still = host.rows(db, video)[0]
    assert still.file_id in redrawn.output["file_ids"]  # the new still
    piece = _steps(db, video, host.PIECE)[-1]
    assert piece.id > redrawn.id and piece.input["files"]["image"] == [still.file_id]


def test_a_talker_still_in_the_wrong_place_is_redrawn_before_any_take(app, db, owner,
                                                                      monkeypatch):  # fmt: skip
    """Its still is looked at for who and where before HeyGen makes anything: wrong, it's
    drawn again once with the check's note (and looked at no more), and the take is made only
    from that one."""
    from app.providers.fake_local import FakeWriter

    real = FakeWriter._item_check
    asked = []

    def wrong_room(self, prompt):
        if "<place>" in prompt:
            asked.append(prompt)
            if len(asked) == 1:
                return {
                    "findings": [
                        {
                            "kind": "place",
                            "who": "",
                            "says": "A home office",
                            "note": "In the driver's seat of his parked car.",
                        }
                    ]
                }
            return {"findings": []}
        return real(self, prompt)

    monkeypatch.setattr(FakeWriter, "_item_check", wrong_room)
    from app.settings import get_settings

    monkeypatch.setattr(get_settings(), "item_checks_paid", True)  # looks on, as on the site
    video = _talker(app, db, owner)
    assert len(asked) == 1 and "<place>where the plan puts them" in asked[0]  # before any take
    first, again = _steps(db, video, host.STILL)
    assert "In the driver's seat of his parked car." in again.input["input"]["prompt"]
    (piece,) = _steps(db, video, host.PIECE)  # one take, from the redrawn still only
    assert piece.id > again.id and piece.input["files"]["image"] == again.output["file_ids"]


def test_a_watch_that_finds_someone_else_in_the_talker_redraws_its_still_first(app, db, owner):
    """Video 281: the watch remade the talker's take twice from the same still, strangers in
    each. A fault in what the still shows draws the still again with the fix, then the take."""
    from app import host_watch

    video = _talker(app, db, owner)
    piece = host.rows(db, video)[1]
    note = "Only Marcus in the frame: nobody behind him."
    did, action, _, credits = host_watch.act(db, piece, note, picture=True)
    assert did.startswith("Drawing its still again") and action == "redo", did
    assert credits == host.price(db, video, 0)  # the still and its take again
    redrawn = _steps(db, video, host.STILL)[-1]
    assert note in redrawn.input["input"]["prompt"]
    assert redrawn.input["mark"] == {host_watch.REDO: piece.id, host_watch.NOTE: note}
    _run(app, db, ticks=20)
    db.expire_all()
    remade = _steps(db, video, host.PIECE)[-1]
    assert remade.input.get(host_watch.REDO) == piece.id  # one of the piece's two remakes
    assert remade.input["files"]["image"] == redrawn.output["file_ids"]
