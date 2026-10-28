"""Song takes on a song script's version: make 2, their states, Try again, Preferred and
remove, all on the free stand-ins (no paid calls)."""

import pytest

from app import music, song_takes
from app.providers import get_providers
from app.worker import run_once
from tests.helpers import assert_no_dollars
from tests.test_music import LYRICS


@pytest.fixture
def song(app, owner):
    app.state.settings.fake_providers = True
    brand = owner.get("/brands").json()[0]["id"]
    script = owner.post(
        "/scripts", json={"brand_id": brand, "title": "Paws", "kind": "song", "text": LYRICS}
    ).json()
    assert script["kind"] == "song"
    return f"/scripts/{script['id']}/drafts/0"


def _style(client, url, style):
    lyrics = client.get(url.rsplit("/drafts", 1)[0]).json()["versions"][0]["text"]
    r = client.put(url, json={"text": lyrics, "style_line": style})
    assert r.status_code == 200, r.text


def _work(app, db, ticks=4):
    providers = get_providers(app.state.settings, app.state.storage)
    for _ in range(ticks):
        run_once(db, providers, app.state.storage)


def test_two_takes_are_made_timed_and_one_is_preferred(app, db, owner, song):
    _style(owner, song, "pop, female lead, 120 BPM")
    made = owner.post(f"{song}/songs", json={})
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["songs_on"] and body["take_credits"] == 1.46 and body["estimate_credits"] == 2.92
    assert [(t["number"], t["status"]) for t in body["takes"]] == [(1, "making"), (2, "making")]
    _work(app, db)
    takes = owner.get(f"{song}/songs").json()["takes"]
    assert [(t["status"], t["preferred"]) for t in takes] == [("ready", True), ("ready", False)]
    assert takes[0]["seconds"] > 20 and len(takes[0]["peaks"]) == 200
    assert not takes[0]["out_of_date"]

    picked = owner.post(f"/songs/{takes[1]['id']}/preferred").json()
    assert picked["take"]["preferred"] and picked["was_preferred_id"] == takes[0]["id"]
    owner.post(f"/songs/{takes[0]['id']}/preferred")  # Undo
    assert [t["preferred"] for t in owner.get(f"{song}/songs").json()["takes"]] == [True, False]

    _style(owner, song, "rock, male lead")  # new words or style: the takes are out of date
    assert all(t["out_of_date"] for t in owner.get(f"{song}/songs").json()["takes"])
    r = owner.post(f"/songs/{takes[1]['id']}/preferred")
    assert (r.status_code, r.json()["detail"]) == (409, song_takes.OLDER_WORDS)


def test_a_skipped_or_repeated_line_is_advice_never_a_block(app, db, owner, song):
    _style(owner, song, "pop fake:drop-line")
    owner.post(f"{song}/songs", json={"count": 1})
    _style(owner, song, "pop fake:repeat-line")
    owner.post(f"{song}/songs", json={"count": 1})
    _work(app, db)
    dropped, repeated = owner.get(f"{song}/songs").json()["takes"]
    assert dropped["status"] == "ready" and dropped["advice"] == [
        "Timing guessed: line 4 (“Iron Paws, my best ally”) wasn't heard in this take."
    ]
    assert repeated["advice"] == ["Line 4 (“Iron Paws, my best ally”) is sung 2 times."]
    # The first take sings the older style line, so the current one became Preferred.
    assert (dropped["preferred"], repeated["preferred"]) == (False, True)


def test_a_failed_take_says_why_and_try_again_makes_it(app, db, owner, song):
    _style(owner, song, "pop fake:refuse")
    owner.post(f"{song}/songs", json={"count": 1})
    _work(app, db)
    take = owner.get(f"{song}/songs").json()["takes"][0]
    assert (take["status"], take["failed_reason"], take["retry_helps"]) == (
        "failed", music.REFUSED, True
    )  # fmt: skip
    assert "E005" not in owner.get(f"{song}/songs").text  # the raw reason is owner-only
    _style(owner, song, "pop")  # the words are changed, as the reason says
    again = owner.post(f"/songs/{take['id']}/try-again")
    assert again.status_code == 200 and again.json()["status"] == "making"
    _work(app, db)
    take = owner.get(f"{song}/songs").json()["takes"][0]
    assert (take["status"], take["preferred"], take["out_of_date"]) == ("ready", True, False)
    r = owner.post(f"/songs/{take['id']}/try-again")
    assert r.status_code == 409  # nothing failed: nothing to try again


def test_removing_the_preferred_take_hands_the_mark_on_and_undo_brings_it_back(
    app, db, owner, song
):
    _style(owner, song, "pop")
    owner.post(f"{song}/songs", json={})
    _work(app, db)
    first, second = owner.get(f"{song}/songs").json()["takes"]
    assert owner.delete(f"/songs/{first['id']}").status_code == 204
    left = owner.get(f"{song}/songs").json()["takes"]
    assert [(t["id"], t["preferred"]) for t in left] == [(second["id"], True)]
    assert owner.post(f"/songs/{first['id']}/restore").json()["preferred"]
    assert [t["preferred"] for t in owner.get(f"{song}/songs").json()["takes"]] == [True, False]


def test_a_song_needs_lyrics_and_a_song_script(app, owner, song):
    owner.put(song, json={"text": "[Verse]", "style_line": "pop"})
    r = owner.post(f"{song}/songs", json={})
    assert (r.status_code, r.json()["detail"]) == (422, music.NO_LYRICS)
    brand = owner.get("/brands").json()[0]["id"]
    story = owner.post("/scripts", json={"brand_id": brand, "title": "S", "text": "HI: there"})
    assert story.json()["kind"] == "story"
    r = owner.post(f"/scripts/{story.json()['id']}/drafts/0/songs", json={})
    assert r.status_code == 409 and "isn't a song" in r.json()["detail"]


def test_songs_off_here_says_so_instead_of_failing(app, owner, song):
    app.state.settings.fake_providers = False
    app.state.settings.generation_enabled = False
    assert owner.get(f"{song}/songs").json()["songs_on"] is False
    r = owner.post(f"{song}/songs", json={})
    assert (r.status_code, r.json()["detail"]) == (503, "Songs aren't switched on here.")


def test_editors_make_their_own_songs_in_credits_but_cant_touch_others(app, db, editor, song):
    assert editor.get(f"{song}/songs").status_code == 404  # not published: not theirs to see
    brand = editor.get("/brands").json()[0]["id"]
    mine = editor.post(
        "/scripts", json={"brand_id": brand, "title": "Mine", "kind": "song", "text": LYRICS}
    ).json()
    url = f"/scripts/{mine['id']}/drafts/0"
    _style(editor, url, "pop")
    made = editor.post(f"{url}/songs", json={})
    assert made.status_code == 201 and made.json()["estimate_credits"] == 2.92
    _work(app, db)
    assert_no_dollars(editor, [f"{url}/songs"])


def test_a_timing_that_cant_be_heard_can_be_spread_evenly(app, db, owner, song, monkeypatch):
    _style(owner, song, "pop")
    owner.post(f"{song}/songs", json={"count": 1})
    providers = get_providers(app.state.settings, app.state.storage)

    def slow(path, lyrics):
        raise RuntimeError("Reading the sung words took too long.")

    monkeypatch.setattr(providers["local"], "hear_song", slow)
    for _ in range(4):
        run_once(db, providers, app.state.storage)
    take = owner.get(f"{song}/songs").json()["takes"][0]
    assert (take["status"], take["retry_helps"]) == ("timing_failed", True)
    spread = owner.post(f"/songs/{take['id']}/spread-timing")
    assert spread.status_code == 200 and spread.json()["status"] == "timing"
    for _ in range(2):
        run_once(db, providers, app.state.storage)
    take = owner.get(f"{song}/songs").json()["takes"][0]
    assert (take["status"], take["timing_guessed"], take["preferred"]) == ("ready", True, True)
    assert take["advice"] == [song_takes.GUESSED]
