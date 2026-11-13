"""The one-pass director on a Presenter video (app/one_pass.py, app/one_pass_timed.py): a host
in a corner over the B-roll, a talker cut between it (one HeyGen take of the narration), a
presenter who acts in the B-roll, and a UGC talker filmed on Omni saying the lines. On the
stand-ins."""

import pytest

from app import audition, cut, host, one_pass, one_pass_timed, voices
from app.models.checks import ItemCheck
from app.models.clips import ClipTake, HostPiece, ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from tests.test_one_pass_narrated import NARRATION, _delivered, _jobs, _run, _video

BODY = {"type": "presenter", "look": "house"}


@pytest.fixture(autouse=True)
def _one_pass_on(monkeypatch):
    from app.settings import get_settings

    monkeypatch.setattr(get_settings(), "one_pass", True)
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)  # as on the stand-ins


def _turns(db) -> list[str]:
    return [(j.output or {}).get("tool") for j in _jobs(db, "director")]


def test_a_corner_host_is_one_take_made_beside_the_b_roll_and_never_watched(app, owner, db):
    pid = _delivered(app, owner, db, type="presenter", look="dr-pickle")
    assert db.get(Project, pid).engine == one_pass.ENGINE
    (plan,) = _jobs(db, "one_pass")
    said = plan.input["prompt"]
    assert "<host>\nThe presenter presents this video from a bottom corner" in said
    assert not _jobs(db, audition.STEP)  # Dr. Pickle's own cloned voice: nobody auditions
    turns = _turns(db)
    assert turns.index("host") < turns.index("make_take")  # the long job starts first
    (piece,) = _jobs(db, host.PIECE)
    (take,) = _jobs(db, "clip_take")
    assert piece.provider == "heygen" and take.created_at <= piece.finished_at  # side by side
    assert host.TALK in piece.input["input"]["motion_prompt"]
    (clip,) = db.query(ProjectClip).all()
    assert one_pass_timed.FRAMING in clip.prompt and clip.prompt.startswith("Audio: no one speaks")
    assert not db.query(ItemCheck).filter_by(target="piece").count()  # the cut's watch has it
    assert db.query(HostPiece).filter(HostPiece.number > 0).one().watch is None
    tl = owner.get(f"/projects/{pid}/cut").json()["timeline"]
    assert tl["presenter"]["spans"][0]["side"] == "right" and tl["mode"] == "narrated"
    note = _jobs(db, "director")[-1].output["note"]
    assert "read in the cloned voice" in note["made"] and not [
        x for x in note["open"] if "host" in x.lower()]  # fmt: skip
    steps = [s["key"] for s in owner.get(f"/projects/{pid}/director/progress").json()["steps"]]
    assert steps[-3:] == ["takes", "host", "cut"] and "voice" in steps


def test_a_presenter_with_no_voice_is_auditioned_by_voices_chosen_in_code(app, owner, db):
    _delivered(app, owner, db, **BODY)
    reads = [j.input["voice"] for j in _jobs(db, audition.STEP)]
    sexes = [voices.TRAITS[k][0] for k in reads]
    assert len(reads) == audition.MOST and sexes.count("woman") == sexes.count("man") == 2
    assert all(j.provider == "server" for j in _jobs(db, "director"))  # no model named them
    asked = _jobs(db, "director")[0]
    assert asked.output["tool"] == "ask" and _turns(db)[1] == "wait"
    assert _jobs(db, "director")[1].input["result"].startswith("Waiting on your answer")
    (voice,) = _jobs(db, "song_take")
    assert voice.input["input"]["voice"] == reads[0]  # the one the person picked reads it


def test_a_talker_is_cut_from_one_heygen_take_between_the_b_roll(app, owner, db, heygen_talker):
    pid = _delivered(app, owner, db, type="presenter", look="ugc")
    (plan,) = _jobs(db, "one_pass")
    assert plan.input["audio"]["talks"] and "talking to camera in the one place" in plan.input[
        "prompt"]  # fmt: skip
    row = one_pass.shooting_plan(db, db.get(Project, pid))
    kinds = [c["kind"] for c in row["clips"]]
    assert kinds[0] == kinds[-1] == "host" and "broll" in kinds
    clips = db.query(ProjectClip).order_by(ProjectClip.id).all()
    mine = [c for c in clips if c.song_slice["sung_shots"]]
    assert [c.clip_id for c in mine] == [clips[0].clip_id, clips[-1].clip_id]
    assert len(_jobs(db, "clip_take")) == len(clips) - len(mine)  # theirs are never made
    (piece,) = _jobs(db, host.PIECE)
    for c in mine:  # each cut from the talker's one take
        assert db.get(ClipTake, c.picked_take_id).made_with["talker"] == db.query(
            HostPiece).filter(HostPiece.number > 0).one().file_id  # fmt: skip
    assert "The picture for the words heard at 0.00 s." in piece.input["input"]["motion_prompt"]
    assert [j.input["voice"] for j in _jobs(db, audition.STEP)][0].startswith("English_")
    tl = cut.base(db, db.get(Project, pid))
    assert [p["lipsync"] for p in tl["pieces"]] == [c in mine for c in clips]


def test_a_presenter_who_acts_is_in_the_b_roll_with_no_take_of_their_own(app, owner, db):
    fs = owner.post("/freestyles", json={"shape": "9:16", "text": NARRATION, "brand_id": 1,
                                         **BODY})  # fmt: skip
    pid = _video(db).id
    assert owner.post(f"/projects/{pid}/settings", json={"presenter": "acts"}).status_code == 200
    _run(app, db)
    assert owner.get(f"/freestyles/{fs.json()['id']}").json()["status"] == "delivered"
    (plan,) = _jobs(db, "one_pass")
    assert "presents this video by acting in it" in plan.input["prompt"]
    assert "host" not in _turns(db) and not _jobs(db, host.PIECE)
    shown = {p for c in one_pass.shooting_plan(db, db.get(Project, pid))["clips"]
             for s in c["shots"] for p in s["people"]}  # fmt: skip
    assert shown == {"The presenter"}
    assert all("[Image" in c.prompt and "No one speaks." in c.prompt
               for c in db.query(ProjectClip))  # fmt: skip


def test_a_ugc_talker_on_omni_says_the_lines_and_the_b_roll_is_laid_over(app, owner, db):
    pid = _delivered(app, owner, db, type="presenter", look="ugc")
    (plan,) = _jobs(db, "one_pass")
    assert plan.input["talker"] == "The presenter" and "audio" not in plan.input
    assert "<talker>\nThe presenter presents this video and says every spoken line" in plan.input[
        "prompt"]  # fmt: skip
    assert not _jobs(db, "song_take") and not _jobs(db, audition.STEP)  # Omni's own voice
    talks, shows = db.query(ProjectClip).order_by(ProjectClip.id).all()
    assert talks.prompt.count("The presenter (in English, plainly):") == 3  # every line theirs
    assert "[Image1] is the first frame." in talks.prompt and "No one speaks." in shows.prompt
    (still,) = _jobs(db, "frame")  # their ONE opening still, drawn before any take
    assert still.finished_at <= _jobs(db, "clip_take")[0].created_at
    frame = db.query(StoryboardFrame).one()
    assert frame.clip_id == talks.clip_id and "catch them at rest" in frame.prompt
    shots = owner.get(f"/projects/{pid}/breakdown").json()["breakdown"]["scenes"][0]["shots"]
    assert (shots[-1]["line"], shots[-1]["script_lines"]) == (None, [1])  # shows line 1, unsaid
    tl = cut.base(db, db.get(Project, pid))
    assert {p["clip_id"] for p in tl["pieces"]} == {talks.clip_id}  # the B-roll is over it
    assert tl["over"][0]["clip_id"] == shows.clip_id and tl["mode"] == "takes"
    assert len(_jobs(db, "voice_split")) == 1 and db.query(Job).filter_by(
        provider="heygen").count() == 0  # fmt: skip


def test_a_new_voice_is_read_after_make_it_and_the_presenter_follows(app, owner, db):
    """Reed, 13 Nov: "Let the director pick and we can swap if needed". The swap is his pick
    and one priced card: nothing is read before Make it."""
    from app.models.script_library import ScriptDraft
    from app.models.songs import SongTake

    pid = _delivered(app, owner, db, **BODY)
    was = db.get(SongTake, db.get(Project, pid).song_take_id)
    first, takes = was.voice, len(_jobs(db, "clip_take"))
    other = "Austin" if first != "Austin" else "Roger"
    assert owner.get(f"/projects/{pid}/host").json()["voice_pending"] is False

    def swap(voice):
        set_ = owner.post(f"/projects/{pid}/settings", json={"voice": f"stock:{voice}"})
        assert set_.status_code == 200, set_.text
        assert owner.post(f"/projects/{pid}/director/carry-on").status_code == 201
        db.expire_all()
        _run(app, db, ticks=3, start=False)
        video = db.get(Project, pid)
        return one_pass._work(db, db.get(ScriptDraft, video.script_draft_id), video)

    price = swap(other)  # the card's price: one read, and the presenter's still and take
    assert price["audio_most"] > 0 and price["host"] > 0 and not price["takes"]
    assert len(_jobs(db, "song_take")) == 1  # nothing is read before Make it
    assert owner.get(f"/projects/{pid}/host").json()["voice_pending"] is True
    steps = owner.get(f"/projects/{pid}/director/progress").json()["steps"]
    assert f"read in the {other} voice" in next(s["text"] for s in steps if s["key"] == "cast")
    (card,) = [c for c in owner.get(f"/projects/{pid}/asks").json() if c["state"] == "open"]
    assert card["kind"] == "start"
    _run(app, db)
    db.expire_all()
    now = db.get(SongTake, db.get(Project, pid).song_take_id)
    assert (now.voice, now.id != was.id) == (other, True)
    assert _turns(db)[-1] == "deliver" and len(_jobs(db, "clip_take")) == takes  # B-roll kept
    pieces = db.query(HostPiece).filter(HostPiece.number > 0).order_by(HostPiece.id)
    assert [p.take_id for p in pieces] == [was.id, now.id]  # the presenter says the new read
    shown = owner.get(f"/projects/{pid}/host").json()
    assert (shown["voice"], shown["voice_pending"]) == (other, False)
    price = swap(first)  # back to the first voice: its read is still there, so none is paid
    assert not price["audio_most"]
    _run(app, db)
    db.expire_all()
    assert db.get(Project, pid).song_take_id == was.id and len(_jobs(db, "song_take")) == 2
