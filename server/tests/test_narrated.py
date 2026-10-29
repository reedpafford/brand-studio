"""Narrated videos (flows N1, V6n): one narrator track under silent clips, timed to its
sentences, as a song video is timed to its lines."""

from app import prompts
from app.prompts import check


def test_the_cast_read_signal_finds_a_script_that_is_all_one_narrator():
    vo = "SCENE 1 — INT. KITCHEN\nBISCUIT (V.O.): Day one.\nHe sniffs.\nBISCUIT (V.O.): Nope."
    assert check.narrator(vo) == "Biscuit"
    assert check.narrator("My gut was a mess.\nThen came the greens.") == "Narrator"  # prose
    assert check.narrator("SCENE 1\nMOM: Hi.\nBISCUIT (V.O.): Day one.") is None  # on camera
    assert check.narrator("SCENE 1\nA (V.O.): One.\nB (V.O.): Two.") is None  # two voices
    assert check.narrator("SCENE 1 — INT. KITCHEN\nHe sniffs the bowl.") is None  # silent story
    assert check.narrator("") is None
    # Flow-QA on #828: labels in any case; directions like "CTA:" are never a speaker
    assert check.narrator("Mia: Wait, it dipped?\nJoe: Buy it.") is None  # on camera
    assert check.narrator("Biscuit (V.O.): Day one.\nBiscuit (V.O.): Nope.") == "Biscuit"
    assert check.narrator("BISCUIT (V.O.): Day one.\nCTA: Get Iron Paws.") == "Biscuit"


def test_narrated_steps_are_the_story_steps_plus_their_own_part():
    for step, story, part in (
        ("narrated_breakdown", "breakdown", "**The narration is the clock.**"),
        ("narrated_clip_prompts", "clip_prompts", "**Narrated.**"),
    ):
        text, base = prompts.system(step), prompts.system(story)
        assert text.startswith(base.split("## Worked example")[0].strip()), step
        assert part in text and part not in base, step
        assert "## Worked example" not in text, step  # the story example would teach dialogue
    assert "moves their lips" in prompts.system("narrated_clip_prompts")
    assert prompts.SCHEMAS["narrated_breakdown"] is prompts.SCHEMAS["song_breakdown"]


def test_a_narrated_breakdown_is_checked_on_its_sentences_like_a_song():
    from tests.test_song import _breakdown, _shot

    script = "Bowl stays full\nThen the green goes on\nGet Iron Paws now"
    timing = {"seconds": 6.0, "lines": [{"start": 0.0, "end": 2.0, "text": "Bowl stays full"},
              {"start": 2.0, "end": 4.0, "text": "Then the green goes on"},
              {"start": 4.0, "end": 6.0, "text": "Get Iron Paws now"}]}  # fmt: skip
    shots = [_shot("1.1", [1], 0.0, 2.0), _shot("1.2", [2], 2.0, 4.0),
             _shot("1.3", [3], 4.0, 6.0, line="Get Iron Paws now")]  # fmt: skip
    problems = check.song_breakdown(script, _breakdown(shots), timing, {}, 4, 15, written=True)
    assert "shot 1.3: a B-roll shot has a line; B-roll is silent picture" in problems
    assert "1| 0.00–2.00 Bowl stays full" in prompts.song_block(timing)
