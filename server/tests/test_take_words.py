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
        assert "the action may have been spoken" in found[0]["text"]
        assert "no “replies” or “answers” in the action" in found[0]["change_note"]


@pytest.mark.parametrize("misheard", ["Fobo", "Fogo", "Foho", "FOMA"])
def test_the_brand_said_wrong_is_flagged_with_how_to_say_it(misheard):
    found = compare(LINES, _heard(f"{misheard} made me rich!", "No way."), "fomo", "FOH-moh", [])
    assert _kinds(found) == [("name", 0.5)]
    assert "Listen first: the transcript can mishear." in found[0]["text"]
    # never quoting the word misheard: a Redo note may quote only what the clip says
    assert found[0]["change_note"] == "Say fomo as FOH-moh."


def test_words_near_the_brand_that_arent_it_are_left_alone():
    heard = _heard("Fomo made me rich!", "No way.", "For more, homo sapiens, form.")
    assert _kinds(compare(LINES, heard, "fomo", "FOH-moh", [])) == [("extra", 4.5)]


def test_how_the_brand_is_said_comes_from_its_notes():
    brand = Brand(name="fomo", tone_notes="Playful. Always say fomo as FOH-moh.")
    assert say(brand) == "FOH-moh"
    assert say(Brand(name="Acme", tone_notes="Calm.\nSay Acme ACK-mee")) == "ACK-mee"
    assert say(Brand(name="Acme", tone_notes="")) == "Acme"  # as written


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
    kept = editor.post(url).json()
    assert kept["status"] == "ok"  # Looks fine, as for any check
    assert [f["kind"] for f in kept["kept"]] == ["missing"]  # still said, as kept (Reed, 4 Nov)
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


def test_a_failed_queue_never_stops_the_take(app, db, editor, setup, clip, monkeypatch, caplog):  # noqa: F811, E501
    monkeypatch.setattr("app.item_checks.on", lambda: True)

    def broken(*args):
        raise RuntimeError("no file")

    monkeypatch.setattr("app.take_words.queue", broken)
    clips = f"/projects/{setup['project']}/clips"
    editor.post(f"{clips}/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    (take,) = editor.get(clips).json()[0]["takes"]  # saved and picked all the same
    assert take["words"] is None and take["verdict"] != "flagged"
    assert "couldn't queue the watch of take" in caplog.text
    assert db.query(Job).filter(Job.kind == "take_listen").count() == 0


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
    monkeypatch.setattr("app.reel.transcribe", lambda path, sounds=False, words=False,
                        first=False, fillers=False: asked.update(sounds=sounds, first=first)
                        or [])  # fmt: skip
    monkeypatch.setattr("app.deep_watch.probe", lambda path: {"audio": True})  # it has sound
    LocalProvider(None).hear_take(tmp_path / "take.mp4", {})
    assert asked == {"sounds": True, "first": False}  # whisper keeps its "(gasps)" tags
    LocalProvider(None).hear_take(tmp_path / "take.mp4", {"silent": True})  # B-roll
    assert asked == {"sounds": True, "first": True}  # read only when speech is heard first
    said = [h["text"] for h in hear_take(tmp_path, {"lines": LINES, "prompt": "fake:gasp"})]
    assert said[-1] == "(gasps)"


def test_in_a_song_or_narrated_video_any_voice_in_a_take_is_a_fault():
    """Song-Producer: B-roll only; nobody speaks or sings on screen."""
    from app.take_words import voices

    heard = [{"start": 0.5, "end": 1.8, "text": "Can't believe it worked.", "speaker": None},
             {"start": 2.0, "end": 2.4, "text": "(music)", "speaker": None}]  # fmt: skip
    (found,) = voices(heard, "song")
    assert found["kind"] == "voiced" and found["span"] == [0.5, 1.8]
    assert (
        found["text"].startswith("“Can't believe it worked.” at 0:00")
        and "this clip isn't planned to speak" in (found["text"])
    )
    assert found["change_note"].endswith("the song carries every word.")
    assert voices([], "narrated") == []
    assert voices(heard, "narrated")[0]["change_note"].endswith("the narrator carries every word.")


def test_a_narrated_takes_voices_are_muted_at_once(db, monkeypatch):
    from types import SimpleNamespace

    from app import take_words

    take = SimpleNamespace(made_with={}, clip_id=1)
    monkeypatch.setattr(take_words.plans, "fmt", lambda db, project: "narrated")
    monkeypatch.setattr(db, "get", lambda model, i: {"ClipTake": take}.get(
        model.__name__, SimpleNamespace(seconds=5)))  # fmt: skip
    row = SimpleNamespace(project_id=1, target_id=1,
                          findings=[{"kind": "voiced", "span": [0.5, 1.8]}])  # fmt: skip
    take_words._mute_voices(db, row)
    assert take.made_with["mutes"] == [[0.5, 1.8]]


def test_the_stand_in_hears_each_line_at_a_speaking_pace_inside_its_take():
    """QA (S4): the stand-in's words sit where a person says them, always inside the take, so
    the cut editor keeps every word through its edits on a stand-in video."""
    from app.providers.fake_local import _timed

    short = [f"Look at the dip {n}." for n in range(1, 9)]  # 8 short lines in a 14 s take
    heard = _timed(short, 14.0)
    words = [w for line in heard for w in line["words"]]
    assert words[0]["start"] == 0.5 and words[-1]["end"] <= 13.6  # inside, with a tail
    assert all(a["end"] <= b["start"] for a, b in zip(words, words[1:], strict=False))
    roomy = _timed(["Fomo made me rich!", "No way."], 8.0)
    first = roomy[0]
    assert first["end"] - first["start"] == pytest.approx(4 / 3.4, abs=0.02)  # 3.4 words a second
    assert roomy[1]["start"] - first["end"] == pytest.approx(0.7, abs=0.02)  # then a pause
    squeezed = _timed(short, 4.0)  # a take shorter than its lines: they're said faster
    assert squeezed[-1]["words"][-1]["end"] <= 3.6


def test_a_stand_in_dialogue_cut_trims_undoes_and_redoes_without_losing_a_word(
    app, db, owner, editor, monkeypatch
):
    """QA (S4, the board's path): on a stand-in video from a published script with many short
    lines, the cut editor's trim goes through (it said "would lose the word" when the
    stand-in heard its words past the take's end), and Undo and Redo work."""
    from decimal import Decimal

    from app.routes import freestyles
    from tests.test_freestyle_dialogue import _run
    from tests.test_new_video import _published

    lines = [f"{'MIA' if n % 2 else 'LEO'}: Look at the dip {n}." for n in range(1, 9)]
    script = "\n".join(["SCENE 1 — INT. KITCHEN — DAY", *lines])
    app.state.settings.fake_providers = True
    monkeypatch.setattr("app.item_checks.on", lambda: True)  # as on the test site
    monkeypatch.setattr(freestyles, "budget", lambda db, project: Decimal(10_000))
    fs = editor.post("/freestyles", json={"shape": "9:16", "script_id": _published(owner, script)})
    _run(app, db, ticks=200)
    base = f"/projects/{fs.json()['project_id']}"
    assert editor.get(f"{base}/director").json()["status"] == "delivered"
    (piece,) = editor.get(f"{base}/cut").json()["timeline"]["pieces"]
    trim = {"kind": "trim", "piece": piece["id"], "end": round(piece["end"] - 0.2, 2), "snap": True}
    made = editor.post(f"{base}/cut/edits", json=trim)
    assert made.status_code == 201, made.text
    assert editor.post(f"{base}/cut/undo").status_code in (200, 201)
    assert editor.get(f"{base}/cut").json()["can_redo"]
    assert editor.post(f"{base}/cut/redo").status_code in (200, 201)
    assert editor.get(f"{base}/cut").json()["changes"] == 1  # the trim, back


def test_a_short_line_heard_run_together_with_another_counts_as_said():
    """Movie video 287 (Omni's own voices): "Oh." and "Hey." were flagged as not heard, and
    "Hey, Granny means well." as unscripted (to mute), though both were said: Whisper ran each
    into a neighbouring line. A line's words inside one heard line count as said, a one-word
    line within its shot's window, and a heard line made of pieces of lines is no extra. The
    words are 287's takes as the site heard them; take 2 of clip 1 really has no "Oh."."""
    import json
    from pathlib import Path

    heard = json.loads((Path(__file__).parent / "fixtures/take_words_287.json").read_text())

    def lines(*shots):  # (who, line, start, end), as the clip's shots time them
        return [{"who": w, "text": t, "start": a, "end": b} for w, t, a, b in shots]

    c1 = lines(("Granny", "Oh honey, congratulations! When are you due?", 0, 4),
               ("Maya", "I'm not pregnant.", 4, 6), ("Granny", "Oh.", 6, 7))  # fmt: skip
    c2 = lines(("Jess", "Hey.", 0, 1),
               ("Jess", "Granny means well. That's not fat, Maya. That's bloat.", 1, 6),
               ("Jess", "Your gut's backed up.", 6, 8),
               ("Jess", "Mine was too.", 8, 10))  # fmt: skip
    pouch = "Two of these every morning. Oil of oregano with black seed oil."
    c3 = lines(("Jess", pouch, 0, 6),
               ("Maya", "Resilia?", 6, 8),
               ("Jess", "Thirty days. Now Granny asks me how I stay so flat.", 8, 13))  # fmt: skip

    def found(said, take):
        return [(f["kind"], f["text"]) for f in compare(said, heard[take], "Resilia", "", [])]

    assert found(c1, "c1_take1") == []
    assert found(c1, "c1_take2") == [("missing", "Not heard: Granny: “Oh.”")]  # said nowhere
    assert found(c2, "c2_take1") == [] and found(c2, "c2_take2") == []
    for invented in ("Granny, your gut's fat.", "Well, that's not well."):  # script words, new
        said = [*heard["c2_take2"], {"text": invented, "start": 10.0, "end": 11.0}]  # lines
        assert [f["kind"] for f in compare(c2, said, "Resilia", "", [])] == ["extra"], invented
    assert found(c3, "c3_take1") == []  # "30 days." is the start of its line, not an extra
