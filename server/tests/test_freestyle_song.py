"""Freestyle Song and Narrated (the Producer; the Director's prompt side): the director makes
the song or the narration right after the treatment, uses its best timed take, and the shots
follow it. Stand-ins only."""

import pytest

from app import director_song
from app.models.freestyles import Freestyle
from app.models.jobs import Job
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.routes.estimate import run_price
from tests.conftest import first_brand
from tests.test_freestyle_dialogue import _run
from tests.test_music import LYRICS

NARRATION = ("Every morning starts the same. The bowl, the wait, the wag. Iron Paws makes the "
             "bowl worth waiting for.")  # fmt: skip


@pytest.fixture(autouse=True)
def songs_on(monkeypatch):  # as on the test site's stand-ins (get_settings there)
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)


def _sent(owner, type_, text):
    body = {"type": type_, "look": "house", "shape": "9:16", "text": text,
            "brand_id": first_brand(owner)}  # fmt: skip
    r = owner.post("/freestyles", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_a_song_freestyle_makes_the_song_first_then_the_video_to_it(app, db, owner):
    fs = _sent(owner, "song", LYRICS)
    _run(app, db, ticks=120)
    out = owner.get(f"/freestyles/{fs['id']}").json()
    moves = [t["text"] for t in out["thread"] if t.get("kind") == "move"]
    assert out["status"] == "delivered", moves
    assert moves[0].startswith("Writing the treatment") or "treatment" in moves[0].lower()
    song = next(i for i, m in enumerate(moves) if m.startswith("Making the song"))
    plan = next(i for i, m in enumerate(moves) if m.startswith("Making the plan"))
    assert song < plan  # the audio is the clock: first (its first timed take is used)
    video = db.get(Project, db.get(Freestyle, fs["id"]).project_id,
                   execution_options={"see_hidden": True})  # fmt: skip
    assert video.song_take_id
    state = director_song.state(db, video)
    (picked,) = [t for t in state["takes"] if t["used"]]
    assert picked["timed"] and picked["hook_at"] is not None and picked["missing"] == []


def test_a_narrated_freestyle_makes_the_narration_first(app, db, owner):
    fs = _sent(owner, "narrated", NARRATION)
    _run(app, db, ticks=120)
    out = owner.get(f"/freestyles/{fs['id']}").json()
    moves = [t["text"] for t in out["thread"] if t.get("kind") == "move"]
    assert out["status"] == "delivered", moves
    assert any(m.startswith("Making the narration") for m in moves)


def test_a_song_runs_price_holds_its_song_and_one_remake(app, db, owner):
    fs = _sent(owner, "song", LYRICS)
    video = db.get(Project, db.get(Freestyle, fs["id"]).project_id,
                   execution_options={"see_hidden": True})  # fmt: skip
    draft = db.get(ScriptDraft, video.script_draft_id)
    assert director_song.price(db, draft) > 0
    assert fs["up_to"] == float(run_price(db, draft, video))


def test_a_song_is_made_again_once_a_run_and_never_in_another_kind(app, db, owner):
    from app import director_tools
    from app.models.accounts import User

    fs = _sent(owner, "song", LYRICS)
    _run(app, db, ticks=120)
    video = db.get(Project, db.get(Freestyle, fs["id"]).project_id,
                   execution_options={"see_hidden": True})  # fmt: skip
    me = db.query(User).filter_by(email="reed@example.com").one()

    def tool(name, note="", made=0):
        decision = {"tool": name, "note": note}
        return director_tools.run(db, me, video, decision, app.state.storage, {"songs": made})

    assert tool("narration") == director_song.NO_NARRATOR
    assert tool("song", "warmer, female vocal", made=1) == director_song.AGAIN.format(what="song")
    assert tool("song", "warmer, female vocal") == "Making the song (warmer, female vocal)."
    job = max(db.query(Job).filter(Job.project_id == video.id, Job.kind == "music"),
              key=lambda j: j.id)  # fmt: skip
    assert "warmer, female vocal" in str(job.input)  # the note rides this request only
    assert "warmer" not in db.get(ScriptDraft, video.script_draft_id).style_line
