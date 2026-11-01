"""The take's words check (take-review checklist B 1, 2 and 9): what a take says against the
script's lines for its clip. Advice only, heard on the free stand-in (no paid calls)."""

import pytest

from app.item_checks import CheckOut, FindingOut, verdict
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


def test_a_new_take_is_heard_and_its_advice_shows(app, db, editor, setup, clip, monkeypatch):  # noqa: F811, E501
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
    (take,) = editor.get(clips).json()[0]["takes"]
    words = take["words"]
    assert words["status"] == "advice" and take["verdict"] == "flagged"
    assert [f["kind"] for f in words["findings"]] == ["missing"]
    assert words["findings"][0]["note"].endswith(f"“{lines[-1]['text']}”")
    review = editor.get(f"/projects/{setup['project']}/checks").json()
    assert [(i["label"], i["findings"]) for i in review["items"]] == [("Clip c1 · take 1", 1)]
    url = f"/projects/{setup['project']}/checks/{words['id']}/findings/0/dismiss"
    assert editor.post(url).json()["status"] == "ok"  # Looks fine, as for any check
    assert db.get(ItemCheck, words["id"]).target == "words"


def test_a_takes_verdict_comes_from_all_its_checks_for_self_approval_later():
    def out(status, found=0):
        return CheckOut(id=1, status=status, findings=[
            FindingOut(index=i, kind="extra", text="", note="") for i in range(found)])  # fmt: skip

    assert verdict([out("ok"), out("ok")]) == "clean"
    assert verdict([out("ok"), None]) == "clean"  # a clip with no lines has no words check
    assert verdict([out("ok"), out("advice", 1)]) == "flagged"
    assert verdict([out("checking"), out("advice", 2)]) == "flagged"
    assert verdict([out("ok"), out("checking")]) == "checking"
    for unsure in ([None, None], [out("skipped"), out("ok")], [out("failed")]):
        assert verdict(unsure) == "unchecked"  # never self-approved on a check that didn't run


def test_a_gasp_nobody_asked_for_and_a_second_one_are_advice():
    found = compare(LINES, _heard("(gasps) Fomo made me rich!", "No way.", "Haah!"), "fomo",
                    "FOH-moh", ["Mia waves her phone."])  # fmt: skip
    assert _kinds(found) == [("sound", 0.5), ("sound", 4.5)]  # both lines still count as said
    in_line, alone = found
    assert in_line["text"] == "“(gasps)” at 0:00.5: a gasp or breath the script doesn't ask for."
    assert in_line["change_note"] == ("A gasp here isn't asked for by the script; keep it only "
                                      "if it serves the moment.")  # fmt: skip
    assert alone["text"].startswith("“Haah” at 0:04.5: another gasp or breath in this clip.")
    assert alone["text"].endswith("It can be muted in the cut (0:04.5–0:05.8).")  # only a breath


def test_a_sound_the_script_or_action_asks_for_is_on_purpose_and_other_tags_arent_lines():
    heard = _heard("Fomo made me rich!", "No way.", "[breathing heavily]", "(upbeat music)")
    assert compare(LINES, heard, "fomo", "FOH-moh", ["Bo catches his breath"]) == []
    scripted = [*LINES, {"who": "BO", "text": "(gasps) It's up!"}]
    heard = _heard("Fomo made me rich!", "No way.", "(gasps) It's up!")
    assert compare(scripted, heard, "fomo", "FOH-moh", []) == []
    twice = _heard("(gasps) Fomo made me rich!", "No way.", "(gasps) It's up!")
    (again,) = compare(scripted, twice, "fomo", "FOH-moh", [])  # asked for once, heard twice
    assert again["at"] == 4.5 and "another gasp" in again["text"]


def test_a_scripted_one_word_line_is_a_line_not_a_gasp():
    for word in ("Oh.", "Hmm.", "Huh?", "Ah!"):
        lines = [*LINES, {"who": "MIA", "text": word}]
        heard = _heard("Fomo made me rich!", "No way.", word)
        assert compare(lines, heard, "fomo", "FOH-moh", []) == [], word  # neither, said right


def test_takes_are_heard_with_their_sounds_and_the_stand_in_gasps_on_cue(monkeypatch, tmp_path):
    asked = {}
    monkeypatch.setattr("app.reel.transcribe", lambda path, sounds=False: asked.update(
        sounds=sounds) or [])  # fmt: skip
    LocalProvider(None).hear_take(tmp_path / "take.mp4", {})
    assert asked == {"sounds": True}  # whisper keeps its "(gasps)" tags for a take
    said = [h["text"] for h in hear_take(tmp_path, {"lines": LINES, "prompt": "fake:gasp"})]
    assert said[-1] == "(gasps)"
