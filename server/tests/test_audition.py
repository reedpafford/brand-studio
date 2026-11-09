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
    """Each of the director's candidates reads the script's opening (about 8 s, run together
    as a talker says it) on the cast card; the narration, looks, stills, takes and host wait;
    the pick is the voice the narration is read in."""
    video = _video(app, db, owner)
    reads = _samples(db, video)
    assert [j.input["voice"] for j in reads] == list(director.STAND_IN_VOICES)
    run_together = OPENING.replace("apology.", "apology,")  # whole sentences to ~8 s
    assert {j.input["input"]["text"] for j in reads} == {run_together}
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
    pressed = owner.post(f"/projects/{video.id}/songs")  # a person's own narration press too
    assert pressed.status_code == 409 and pressed.json()["detail"].startswith("Pick ")
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


def test_the_audition_reads_the_words_the_narration_will_say(app, db, owner, monkeypatch):
    """The lead, 9 Nov: the voices read exactly what the narration will (the approved words,
    from the narration's own source, song_takes.words: #1484's spoken version once it lands),
    run together as the talker says them, so the pick is judged on the real read."""
    spoken = ("So I owe my brother-in-law an apology. Every Thanksgiving I'd tease Danny about "
              "his phone. And this year he showed me what he's doing.")  # fmt: skip
    monkeypatch.setattr("app.song_takes.words", lambda db, draft, project: spoken)
    video = _video(app, db, owner)
    (said,) = {j.input["input"]["text"] for j in _samples(db, video)}
    assert said == spoken.replace("apology.", "apology,").replace("phone.", "phone,")
    _run(app, db, ticks=200)  # the voice picked, the narration made
    db.expire_all()
    (read,) = [j for j in db.query(Job).filter_by(project_id=video.id, kind="speech")
               if j.input.get("step") == "song_take"]  # fmt: skip
    assert narration.plain(read.input["input"]["text"]) == narration.plain(said)


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


def test_an_empty_voices_list_is_no_audition_and_an_open_one_is_never_paid_twice(app, db, owner):
    """QA on #1486: the model sends every field, `voices: []` when it has none. Another cast
    question goes on as asked; voices sent on another card while an audition is open read
    nothing again and leave the audition where it is."""
    video = _video(app, db, owner)
    open_, reads = audition.card(db, video), len(_samples(db, video))
    danny = {"kind": "cast", "subject": "Danny", "question": "Who plays Danny?", "voices": []}
    assert asks.asked(db, video, None, danny) == "Asked: Who plays Danny?"
    again = {**danny, "question": "Who plays Danny now?", "voices": list(director.STAND_IN_VOICES)}
    said = asks.asked(db, video, None, again)
    assert said == f"Asked: Who plays Danny now? The audition is already on question {open_.id}."
    assert len(_samples(db, video)) == reads and audition.card(db, video).id == open_.id


def test_when_every_voice_fails_to_read_the_card_never_leaves_the_video_stuck(app, db, owner):
    """Rule 22 (QA on #1486): every read failed, nothing charged. The card offers Read them
    again and any voice the brand may use, unheard; the director may audition again."""
    from app.models.jobs import JobStatus

    video = _video(app, db, owner)
    ask = audition.card(db, video)
    for job in _samples(db, video):
        job.status = JobStatus.failed
    db.commit()
    assert audition.status(db, video)["state"] == "none"  # the director may ask again
    url = f"/asks/{ask.id}/answer"
    card = next(c for c in owner.get(f"/projects/{video.id}/asks").json() if c["id"] == ask.id)
    assert card["audition_failed"] and {"again", "voice"} <= set(card["can"])
    assert "stock:Roger" in {o["id"] for o in card["saved"]}  # a voice card: the brand's voices
    assert owner.post(url, json={"how": "again"}).status_code == 200
    assert len(_samples(db, video)) == 6 and audition.card(db, video).id == ask.id
    for job in _samples(db, video):
        job.status = JobStatus.failed
    db.commit()
    picked = owner.post(url, json={"how": "voice", "option": "stock:Roger"})  # unheard
    assert picked.status_code == 200 and picked.json()["voice_name"] == "Roger"
    db.expire_all()
    assert db.get(Project, video.id, execution_options={"see_hidden": True}).voice == "stock:Roger"


def test_a_failed_cards_read_again_gives_way_to_the_directors_new_audition(app, db, owner):
    """QA on #1486: once the director auditions again on a new card, the failed card can't
    read again (one audition at a time, never paid twice) and drops its button."""
    from app.models.jobs import JobStatus

    video = _video(app, db, owner)
    old = audition.card(db, video)
    for job in _samples(db, video):
        job.status = JobStatus.failed
    db.commit()
    move = {"kind": "voice", "subject": "Marcus", "question": "Which voice now?",
            "voices": ["Roger", "English_Jovialman", "English_Diligent_Man"]}  # fmt: skip
    assert asks.asked(db, video, None, move).startswith("Asked: Which voice now? Roger")
    new, reads = audition.card(db, video), len(_samples(db, video))
    assert new.id != old.id
    card = next(c for c in owner.get(f"/projects/{video.id}/asks").json() if c["id"] == old.id)
    assert card["audition_failed"] and "again" not in card["can"]
    refused = owner.post(f"/asks/{old.id}/answer", json={"how": "again"})
    assert refused.status_code == 409 and f"question {new.id}" in refused.json()["detail"]
    assert len(_samples(db, video)) == reads


def test_more_narration_takes_read_in_the_voice_the_narration_is_in(app, db, owner):
    """QA on #1486: a person's "more takes" press reads in the voice of the narration in use
    (the director chose Roger), never the narrator's default."""
    from app.models.songs import SongTake

    body = {"type": "narrated", "look": "house", "shape": "9:16", "text": LINES,
            "brand_id": first_brand(owner)}  # fmt: skip
    fs = owner.post("/freestyles", json=body).json()
    _run(app, db, ticks=200)
    video = db.get(Project, db.get(Freestyle, fs["id"]).project_id,
                   execution_options={"see_hidden": True})  # fmt: skip
    db.get(SongTake, video.song_take_id).voice = "Roger"  # the director's pick for it
    db.commit()
    assert owner.post(f"/projects/{video.id}/songs").status_code == 201
    newest = db.query(Job).filter_by(project_id=video.id, kind="speech").order_by(Job.id.desc())
    assert newest.first().input["input"]["voice"] == "Roger"
