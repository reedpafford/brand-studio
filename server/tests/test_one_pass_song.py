"""The one-pass director on a Song video (app/one_pass.py, app/one_pass_timed.py): the song is
made and timed first (in the style the person gives when the lyrics have none), every clip is
B-roll on the song's own times, and the cut ends with the song. On the stand-ins."""

import pytest

from app import cut, one_pass, song_takes
from app.models.asks import Ask
from app.models.clips import ClipTake, ProjectClip
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.models.songs import SongTake
from tests.test_one_pass_narrated import _jobs, _run, _video

LYRICS = ("[Verse]\nWoke up late and the bowl was bare\nShook the bag, there was nothing there\n"
          "[Chorus] [Lip-sync]\nIron Paws, fill it up again\nIron Paws, for my four-legged friend\n"
          "[Verse]\nNow he waits by the kitchen door\nTail goes thump on the wooden "
          "floor")  # fmt: skip
BODY = {"type": "song", "look": "house", "shape": "9:16", "text": LYRICS, "brand_id": 1}
STYLE = "bright pop, warm female vocal, 110 bpm"


@pytest.fixture(autouse=True)
def _one_pass_on(monkeypatch, app):
    from app.settings import get_settings

    monkeypatch.setattr(get_settings(), "one_pass", True)
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)  # as on the stand-ins
    monkeypatch.setattr(app.state.settings, "kie_suno", True)


def _sent(app, owner, db, **change) -> int:
    """A song sent and run until it stops for its style; its video."""
    fs = owner.post("/freestyles", json={**BODY, **change})
    assert fs.status_code == 201, fs.text
    _run(app, db, ticks=6)
    return _video(db).id


def test_a_song_with_no_style_asks_for_it_once_then_is_made_before_the_plan(
    app, owner, db, monkeypatch
):
    from app import music

    # a brand with long style lines (video 377: the card's why passed 500 characters, was
    # refused, and the run stopped at every Carry on)
    monkeypatch.setattr(music, "recent_styles", lambda *a, **k: ["dark country " * 30] * 3)
    pid = _sent(app, owner, db, mode="auto")  # "make without asking": this card still waits
    (card,) = db.query(Ask).filter_by(project_id=pid, state="open").all()
    assert (card.kind, card.topic, card.question) == ("question", one_pass.STYLE_TOPIC,
                                                      one_pass.STYLE_ASK)  # fmt: skip
    assert "like “bright pop, warm female vocal, 110 bpm”" in card.why
    turns = [(j.output["tool"], j.input.get("result")) for j in _jobs(db, "director")]
    assert [t for t, _ in turns] == ["ask", "wait"] and turns[1][1].startswith("Waiting on your")
    assert not _jobs(db, "song_take") and not _jobs(db, "one_pass")  # nothing made on a guess
    said = owner.post(f"/asks/{card.id}/answer", json={"how": "reply", "text": STYLE})
    assert said.status_code == 200, said.text
    _run(app, db)
    out = owner.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    (song,) = _jobs(db, "song_take")
    (plan,) = _jobs(db, "one_pass")
    assert song.input["input"]["style"].startswith(STYLE) and song.finished_at <= plan.created_at
    assert "This script is a song" in plan.input["system"][0] and "Sections:" in plan.input[
        "prompt"]  # fmt: skip
    assert db.query(Ask).filter_by(project_id=pid, topic=one_pass.STYLE_TOPIC).count() == 1


def test_every_clip_is_b_roll_and_lip_sync_lines_are_said_in_the_note(app, owner, db):
    pid = _sent(app, owner, db)
    card = db.query(Ask).filter_by(project_id=pid, state="open").one()
    owner.post(f"/asks/{card.id}/answer", json={"how": "reply", "text": STYLE})
    _run(app, db)
    project = db.get(Project, pid)
    plan = one_pass.shooting_plan(db, project)
    assert {c["kind"] for c in plan["clips"]} == {"broll"} and plan["voices"] == []
    clips = db.query(ProjectClip).all()
    assert all(c.song_slice["sung_shots"] == [] and c.prompt.startswith("Audio: no one speaks")
               for c in clips)  # fmt: skip
    assert db.query(ClipTake).count() == len(clips)  # each made once: nobody can miss a line
    note = _jobs(db, "director")[-1].output["note"]
    assert (
        "It runs to take 1 of the song. Lines 5, 6 ask for lip-sync: every clip is B-roll"
        in (note["made"])
    )
    take = db.get(SongTake, project.song_take_id)
    tl = cut.base(db, project)
    assert tl["mode"] == "song" and tl["length"] == cut.song_end(take) < take.seconds
    draft = db.get(ScriptDraft, project.script_draft_id)
    assert song_takes.song_video_cost(db, draft, take.seconds) == one_pass.expected(db, draft)


def test_a_clip_planned_as_sung_is_made_as_b_roll():
    from tests.test_one_pass_narrated import TRACK, _plan

    asked = {"script": LYRICS, "cast": [], "assets": [], "timing": {"fast": 4.8, "pause": 0.2},
             "limits": {"min": 4, "max": 15, "people": 6},
             "audio": {**TRACK, "hold": 0.0}}  # fmt: skip
    plan, fixes = one_pass.checked(asked, _plan([0.0, 1.4, 2.8], kind="sung"))
    assert fixes == [] and plan["clips"][0]["kind"] == "broll"
