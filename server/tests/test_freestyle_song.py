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


def test_the_brands_name_heard_wrong_in_a_narration_is_found_once_timed():
    words = [{"word": w, "start": float(n)} for n, w in enumerate(["Get", "Foma.", "fomo", "now"])]
    assert director_song.misheard(None, "fomo") is None  # not timed yet
    assert director_song.misheard({"words": words}, "fomo") == [
        {"word": "fomo", "heard": "Foma.", "at": 1.0}
    ]


def test_a_narration_sentence_with_one_word_lost_is_missing():
    from app.models.songs import SongTake

    said = "Packed with probiotics and greens. Get it today."
    heard = [{"word": w, "start": 0.0} for w in "Packed with and greens. Get it today.".split()]
    take = SongTake(kind="narration", timing={"words": heard})
    lines = [{"text": "Packed with probiotics and greens.", "heard": 0.8},
             {"text": "Get it today.", "heard": 1.0}]  # fmt: skip
    assert director_song._missing(take, lines) == ["Packed with probiotics and greens."]
    take.timing = {"words": [{"word": w, "start": 0.0} for w in said.split()]}
    assert director_song._missing(take, lines) == []
    song = SongTake(kind="song", timing={"words": heard})  # a song keeps its 60 %
    assert director_song._missing(song, lines) == []


def test_a_narration_with_the_brand_said_wrong_is_read_again_before_the_plan(app, db, owner):
    from app.models.songs import SongTake

    fs = _sent(owner, "narrated", "Every morning starts the same. Get fake:misheard fomo today.")
    _run(app, db, ticks=120)
    out = owner.get(f"/freestyles/{fs['id']}").json()
    moves = [t["text"] for t in out["thread"] if t.get("kind") == "move"]
    assert out["status"] == "delivered", moves
    again = next(i for i, m in enumerate(moves) if m.startswith("Making the narration (Say"))
    plan = next(i for i, m in enumerate(moves) if m.startswith("Making the plan"))
    assert again < plan, moves
    video = db.get(Project, db.get(Freestyle, fs["id"]).project_id,
                   execution_options={"see_hidden": True})  # fmt: skip
    state = director_song.state(db, video)
    first, second = state["takes"]
    assert first["misheard"] and first["misheard"][0]["word"] == "fomo"
    assert second["used"] and second["misheard"] == []  # the plan follows the good one
    draft = db.get(ScriptDraft, video.script_draft_id)
    assert "[" not in draft.text  # the note went to the voice, never into the version's words
    redo = db.get(Job, db.get(SongTake, second["id"]).job_id)
    assert redo.input["input"]["prompt"].startswith("[Say ")
    assert db.get(SongTake, second["id"]).voice == "Sarah"  # no voice picked: the default


def test_the_director_picks_the_narrators_voice_from_ours(app, db, owner):
    from app import director_tools
    from app.models.accounts import User
    from app.models.songs import SongTake

    fs = _sent(owner, "narrated", NARRATION)
    _run(app, db, ticks=120)
    video = db.get(Project, db.get(Freestyle, fs["id"]).project_id,
                   execution_options={"see_hidden": True})  # fmt: skip
    me = db.query(User).filter_by(email="reed@example.com").one()

    def tool(voice):
        decision = {"tool": "narration", "note": "warmer", "voice": voice}
        return director_tools.run(db, me, video, decision, app.state.storage, {})

    assert tool("Morgan").startswith("Refused: the narrator's voice is one of Sarah")
    assert tool("Jane") == "Making the narration (warmer)."
    newest = max(director_song.state(db, video)["takes"], key=lambda t: t["id"])
    assert db.get(SongTake, newest["id"]).voice == "Jane"


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
    full = director_song.REMAKES
    assert tool("song", "warmer, female vocal", made=full) == director_song.AGAIN.format(
        what="song"
    )
    other = next(t for t in director_song.state(db, video)["takes"] if not t["used"])
    picked = director_tools.run(db, me, video, {"tool": "song", "take_id": other["id"]},
                                app.state.storage, {})  # fmt: skip
    assert picked == f"Using take {other['number']} for the song."
    assert (
        db.get(Project, video.id, execution_options={"see_hidden": True}).song_take_id
        == other["id"]
    )
    assert other["longest_gap"] is not None and other["tail"] is not None
    assert tool("song", "warmer, female vocal") == "Making the song (warmer, female vocal)."
    job = max(db.query(Job).filter(Job.project_id == video.id, Job.kind == "music"),
              key=lambda j: j.id)  # fmt: skip
    assert "warmer, female vocal" in str(job.input)  # the note rides this request only
    assert "warmer" not in db.get(ScriptDraft, video.script_draft_id).style_line


def test_a_song_the_service_failed_is_tried_again_free_once_and_a_refusal_says_so(app, db, owner):
    """Song-Producer: a KIE internal error gets a plain free retry, not a remake."""
    from app import director_tools
    from app.models.accounts import User
    from app.providers import get_providers
    from app.worker import run_once

    fs = _sent(owner, "song", LYRICS)
    video = db.get(Project, db.get(Freestyle, fs["id"]).project_id,
                   execution_options={"see_hidden": True})  # fmt: skip
    me = db.query(User).filter_by(email="reed@example.com").one()
    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings, app.state.storage)

    def songs():  # the music service and the timing only: the director waits
        for _ in range(3):
            run_once(db, providers, app.state.storage, only={"suno", "local"})
        db.expire_all()

    run = {}

    def tool(note=""):
        return director_tools.run(db, me, video, {"tool": "song", "note": note},
                                  app.state.storage, run)  # fmt: skip

    assert tool("pop, fake:fail") == "Making the song (pop, fake:fail)."  # its style line
    songs()
    assert director_song.state(db, video)["state"] == "failed"
    assert tool() == "Trying the song again: the service failed, nothing was charged."
    assert run["song_retries"] == 1 and "songs" not in run  # not a remake
    songs()  # the same request again, its style line too: it fails again here
    assert tool().startswith("Refused: the song didn't come out")  # once; then a note
    job = max(db.query(Job).filter(Job.kind == "music"), key=lambda j: j.id)
    assert "fake:fail" in str(job.input)
