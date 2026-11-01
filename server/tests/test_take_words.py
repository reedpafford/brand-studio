"""The take's words check (take-review checklist B 1, 2 and 9): what a take says against the
script's lines for its clip. Advice only, heard on the free stand-in (no paid calls)."""

import pytest

from app.models.brands import Brand
from app.models.checks import ItemCheck
from app.models.jobs import Job
from app.providers.fake_local import hear_take
from app.providers.local import LocalProvider
from app.take_words import compare, say
from app.worker import run_once
from tests.test_clip_takes import FakeSeedance, _mp4, _work, clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture

LINES = [{"who": "MIA", "text": "Fomo made me rich!"}, {"who": "BO", "text": "No way."}]


def _heard(*said: str) -> list[dict]:
    return [{"start": 2.0 * i + 0.5, "end": 2.0 * i + 1.8, "text": t} for i, t in enumerate(said)]


def _kinds(findings: list[dict]) -> list[tuple]:
    return [(f["kind"], f["at"]) for f in findings]


def test_a_take_that_says_its_lines_has_no_advice():
    heard = _heard("FOMO made me rich", "no way")  # case and punctuation don't count
    assert compare(LINES, heard, "fomo", "FOH-moh", ["Mia waves her phone."]) == []


def test_a_missing_line_and_an_unscripted_one_with_where_to_mute_it():
    found = compare(LINES, _heard("Fomo made me rich!", "Let's go home."), "fomo", "FOH-moh",
                    ["Mia waves her phone."])  # fmt: skip
    assert _kinds(found) == [("missing", None), ("extra", 2.5)]
    missing, extra = found
    assert missing["text"] == "Not heard: BO: “No way.”" and missing["role"] == "BO"
    assert missing["change_note"] == "Make sure BO says, word for word: “No way.”"
    assert "It can be muted in the cut (0:02.5–0:03.8)" in extra["text"]
    assert (
        extra["change_note"] == "Say only the script's lines, word for word: no “Let's go home.”."
    )


def test_inner_speech_or_a_reply_in_the_action_is_called_a_spoken_action():
    for action in ("Bo thinks: can't believe it worked", "Mia replies with a grin"):
        found = compare(LINES, _heard("Fomo made me rich!", "No way.", "Can't believe it worked."),
                        "fomo", "FOH-moh", [action])  # fmt: skip
        assert _kinds(found) == [("voiced", 4.5)]
        assert "the action was spoken" in found[0]["text"]
        assert "no “replies” or “answers” in the action" in found[0]["change_note"]


@pytest.mark.parametrize("misheard", ["Fobo", "Fogo", "Foho", "FOMA"])
def test_the_brand_said_wrong_is_flagged_with_how_to_say_it(misheard):
    found = compare(LINES, _heard(f"{misheard} made me rich!", "No way."), "fomo", "FOH-moh", [])
    assert _kinds(found) == [("name", 0.5)]
    assert "Listen first: the transcript can mishear." in found[0]["text"]
    assert found[0]["change_note"] == f"Say fomo as FOH-moh, never “{misheard}”."


def test_words_near_the_brand_that_arent_it_are_left_alone():
    heard = _heard("Fomo made me rich!", "No way.", "For more, homo sapiens, form.")
    assert _kinds(compare(LINES, heard, "fomo", "FOH-moh", [])) == [("extra", 4.5)]


def test_how_the_brand_is_said_comes_from_its_notes():
    brand = Brand(name="fomo", tone_notes="Playful. Always say fomo as FOH-moh.", do_list=[])
    assert say(brand) == "FOH-moh"
    assert say(Brand(name="Acme", tone_notes="Calm.", do_list=["Say Acme ACK-mee"])) == "ACK-mee"
    assert say(Brand(name="Acme", tone_notes="", do_list=[])) == "Acme"  # as written


def test_a_new_take_is_heard_and_its_words_advice_shows_on_the_take(
    app, db, editor, setup, clip, monkeypatch
):  # noqa: F811
    monkeypatch.setattr("app.item_checks.on", lambda: True)  # as on the test site's stand-ins
    clips = f"/projects/{setup['project']}/clips"
    editor.post(f"{clips}/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    (take,) = editor.get(clips).json()[0]["takes"]
    assert take["words"]["status"] == "checking"  # never blocks
    listen = db.query(Job).filter(Job.kind == "take_listen").one()
    assert listen.credits == 0 and listen.provider == "local"  # free, on our own server
    lines = listen.input["lines"]
    assert lines and all(line["text"] for line in lines)

    def drop_last(path, job):  # the stand-in hearing, missing the clip's last line
        return hear_take(path, {**job, "prompt": "fake:drop-line"})

    local = LocalProvider(app.state.storage, hear_take=drop_last)
    run_once(db, {"local": local}, app.state.storage, only={"local"})
    words = editor.get(clips).json()[0]["takes"][0]["words"]
    assert words["status"] == "advice"
    assert [f["kind"] for f in words["findings"]] == ["missing"]
    assert words["findings"][0]["note"].endswith(f"“{lines[-1]['text']}”")
    review = editor.get(f"/projects/{setup['project']}/checks").json()
    assert [(i["label"], i["findings"]) for i in review["items"]] == [("Clip c1 · take 1", 1)]
    url = f"/projects/{setup['project']}/checks/{words['id']}/findings/0/dismiss"
    assert editor.post(url).json()["status"] == "ok"  # Looks fine, as for any check
    assert db.get(ItemCheck, words["id"]).target == "words"
