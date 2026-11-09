"""The voice audition (Reed, 9 Nov: "Let's implement a voice discovery stage"): a presenter's
voice is picked by ear from the director's candidates, each reading the script's opening,
before anything is timed to it; the pick is saved on the presenter. All on the stand-ins."""

import pytest

from app import asks, audition, director, director_tools, narration
from app.models.accounts import User
from app.models.asks import Ask
from app.models.freestyles import Freestyle
from app.models.jobs import Job
from app.models.projects import Project
from app.providers import get_providers
from app.worker import run_once
from tests.conftest import first_brand
from tests.helpers import make_it
from tests.test_freestyle_dialogue import _run

OPENING = ("Okay so I owe my brother-in-law a public apology. Every Thanksgiving I'd make fun of "
           "Danny on his phone the whole dinner.")  # fmt: skip  # 22 words: about 7 s
LINES = f"{OPENING}\nAnd this year he finally shows me what he's doing, and I'm like, oh."


@pytest.fixture(autouse=True)
def songs_on(monkeypatch):
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)


def _video(app, db, owner) -> Project:
    """A UGC presenter video, run until it waits on its audition (nobody picks a voice)."""
    body = {"type": "presenter", "look": "ugc", "shape": "9:16", "text": LINES,
            "brand_id": first_brand(owner)}  # fmt: skip
    fs = owner.post("/freestyles", json=body).json()
    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings, app.state.storage)
    for _ in range(40):
        run_once(db, providers, app.state.storage)
        db.expire_all()
        make_it(db)
    return db.get(Project, db.get(Freestyle, fs["id"]).project_id,
                  execution_options={"see_hidden": True})  # fmt: skip


def _samples(db, video) -> list[Job]:
    return [j for j in db.query(Job).filter_by(project_id=video.id).order_by(Job.id)
            if j.input.get("step") == audition.STEP]  # fmt: skip


def test_nothing_is_timed_to_a_presenters_voice_until_the_person_picks_it(app, db, owner):
    """Each of the director's candidates reads the script's opening (about 8 s, the words as
    written) on the cast card; the narration, looks, stills, takes and host wait; the pick is
    the voice the narration is read in."""
    video = _video(app, db, owner)
    reads = _samples(db, video)
    assert [j.input["voice"] for j in reads] == list(director.STAND_IN_VOICES)
    assert {j.input["input"]["text"] for j in reads} == {OPENING}  # whole sentences to ~8 s
    assert all(j.kind == "speech" and j.input["model"] == narration.MINIMAX for j in reads)
    assert not [
        j
        for j in db.query(Job).filter_by(project_id=video.id)
        if j.input.get("step") in ("song_take", "sheet", "frame", "host_still")
    ]
    user = db.get(User, video.created_by_id)
    for tool in audition.HELD:
        said = director_tools.run(db, user, video, {"tool": tool}, app.state.storage)
        assert said.startswith("Refused: ") and "being auditioned" in said, tool
    ask = audition.card(db, video)
    card = owner.get(f"/projects/{video.id}/asks").json()
    shown = next(c for c in card if c["id"] == ask.id)
    assert [a["name"] for a in shown["audition"]] == ["Decent Young Man", "Jovial Man",
                                                      "Trustworthy Man"]  # fmt: skip
    assert all(a["sample_file_id"] for a in shown["audition"]) and "voice" in shown["can"]
    url = f"/asks/{ask.id}/answer"
    assert owner.post(url, json={"how": "voice", "option": "stock:Roger"}).status_code == 422
    picked = owner.post(url, json={"how": "voice", "option": "stock:English_Jovialman"})
    assert picked.status_code == 200 and picked.json()["voice"] == "stock:English_Jovialman"
    _run(app, db, ticks=200)
    db.expire_all()
    (read,) = [j for j in db.query(Job).filter_by(project_id=video.id, kind="speech")
               if j.input.get("step") == "song_take"]  # fmt: skip
    assert read.input["input"]["voice_id"] == "English_Jovialman"
    assert len(_samples(db, video)) == 3  # no new audition on the way, nor after delivery
    assert audition.status(db, video) is None


def test_the_pick_is_saved_on_the_presenter_so_their_next_video_has_no_audition(
    app, db, owner, monkeypatch
):
    """Reed: "it might be easier to maintain consistency". A presenter with a saved voice is
    never auditioned again, and a voice they already had is never overwritten."""
    from app import host
    from app.models.library import Kind, LibraryItem

    video = _video(app, db, owner)
    marcus = LibraryItem(workspace_id=video.workspace_id, kind=Kind.character, name="Marcus")
    db.add(marcus)
    db.flush()
    monkeypatch.setattr(host, "host_look", lambda db, p: marcus)
    ask = audition.card(db, video)
    asks.answer(db, db.get(User, video.created_by_id), ask,
                {"how": "voice", "option": "stock:English_DecentYoungMan"})  # fmt: skip
    assert marcus.voice_stock_key == "English_DecentYoungMan"
    video.voice = None  # their next video: nothing picked for it yet
    assert not audition.needed(db, video)
    assert audition.start(db, db.get(User, video.created_by_id), video, ask,
                          ["English_Jovialman"] * 3, before=False) == ""  # fmt: skip
    marcus.voice_stock_key, video.voice = "Roger", "stock:English_Jovialman"
    audition.keep(db, video)
    assert marcus.voice_stock_key == "Roger"  # their own voice stays


def test_the_director_names_three_or_four_app_voices_on_the_card_that_casts_them(app, db, owner):
    """The audition rides on the cast card (no new step, no extra turn); a wrong list is
    refused in plain words and no card is made."""
    video = _video(app, db, owner)
    for card in db.query(Ask).filter_by(project_id=video.id):
        card.state = "not_needed"  # the stand-in's own card gone: this video asks again
    db.commit()
    move = {"kind": "presenter", "subject": "Marcus", "question": "Who plays Marcus?"}
    cards = db.query(Ask).count()
    for wrong in (
        ["English_Jovialman", "English_DecentYoungMan"],
        ["Roger"] * 3,
        ["Roger", "Austin", "Narrator Bob"],
        list(narration.MINIMAX_VOICES[:5]),
    ):
        assert asks.asked(db, video, None, {**move, "voices": wrong}) == audition.TOO_FEW
    assert db.query(Ask).count() == cards
    said = asks.asked(
        db,
        video,
        None,
        {**move, "voices": ["Roger", "English_Jovialman", "English_Trustworth_Man"]},
    )
    assert said == ("Asked: Who plays Marcus? Roger, Jovial Man, Trustworthy Man each read the "
                    "opening for the person to pick from.")  # fmt: skip
    ask = db.query(Ask).order_by(Ask.id.desc()).first()
    assert (ask.kind, [j.input["voice"] for j in audition.jobs(db, ask)]) == (
        "presenter", ["Roger", "English_Jovialman", "English_Trustworth_Man"])  # fmt: skip
