"""Write 2 song directions (flows S3) on a Song version, Use one with Undo, its claims, and
removing a card, all on the free stand-ins (no paid calls)."""

from app import song_directions
from app.models.jobs import Job
from tests.test_song_takes import _work, song  # noqa: F401 - fixture

SCRIPT = "Your dog's gut is a mess\nIron Paws fixes it\nLink in my bio"


def _base(url):
    return url.rsplit("/drafts", 1)[0]


def _version(client, url):
    return client.get(_base(url)).json()["versions"][0]


def test_two_directions_are_written_from_a_script_and_one_is_used_with_undo(
    app,
    db,
    owner,
    song,  # noqa: F811
):
    before = _version(owner, song)
    assert before["directions_estimate_credits"] > 0 and before["directions_stop"] is None
    made = owner.post(f"{song}/directions", json={"source": SCRIPT, "sounds_like": "Jack Johnson"})
    assert made.status_code == 201, made.text
    job = db.get(Job, made.json()["id"])
    assert job.input["step"] == "song_directions" and "<source>" in job.input["prompt"]
    assert "<sounds_like>Jack Johnson</sounds_like>" in job.input["prompt"]
    assert _version(owner, song)["directions_job"]["status"] in ("queued", "running")
    _work(app, db)
    version = _version(owner, song)
    a, b = version["song_directions"]
    assert version["directions_job"] is None
    assert a["recommended"] and not b["recommended"] and "Your dog's gut is a mess" in a["lyrics"]
    assert b["left_out"] == ["Link in my bio"] and "sung words" in a["length_note"]

    used = owner.post(f"{song}/directions/{b['id']}/use").json()
    after = _version(owner, song)
    assert after["text"] == b["lyrics"] and after["style_line"] == b["style_line"]
    assert after["claims_to_check"] == ["It feels so right"]
    assert used["was_text"] == before["text"]
    assert owner.post(f"{song}/claims/keep").status_code == 204
    assert _version(owner, song)["claims_to_check"] == []
    undo = {"text": used["was_text"], "style_line": used["was_style_line"]}
    assert owner.put(song, json=undo).status_code == 200  # Undo
    assert _version(owner, song)["text"] == before["text"]


def test_writing_more_keeps_the_older_pair_and_a_card_can_be_removed(
    app,
    db,
    owner,
    song,  # noqa: F811
):
    for _ in range(2):
        owner.post(f"{song}/directions", json={})
        _work(app, db)
    cards = _version(owner, song)["song_directions"]
    assert len(cards) == 4
    assert owner.delete(f"{song}/directions/{cards[0]['id']}").status_code == 204
    assert len(_version(owner, song)["song_directions"]) == 3
    owner.post(f"{song}/directions/{cards[0]['id']}/restore")  # Undo
    assert len(_version(owner, song)["song_directions"]) == 4


def test_nothing_to_go_on_says_what_to_add(app, owner):
    brand = owner.get("/brands").json()[0]["id"]
    empty = owner.post("/scripts", json={"brand_id": brand, "title": "x", "description": "",
                                         "kind": "song", "text": ""}).json()  # fmt: skip
    url = f"/scripts/{empty['id']}/drafts/0"
    assert _version(owner, url)["directions_stop"] == song_directions.NOTHING
    r = owner.post(f"{url}/directions", json={})
    assert (r.status_code, r.json()["detail"]) == (409, song_directions.NOTHING)


def test_a_length_note_never_reads_0_60():
    from app.prompts import check

    assert check._clock(59.6) == "1:00" and check._clock(119.7) == "2:00"
    assert "0:60" not in check.length_note(" ".join(["la"] * 143))
