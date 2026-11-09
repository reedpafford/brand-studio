"""A note in brackets in a script is direction, never spoken: a line that is only a note
("[she looks at the camera and sighs]", "[cut to the app]") and a note inside a spoken line
("I said [quietly] no"). "[Tag] text" lines work as before. The breakdown still sees them."""

import copy

from app import breakdown_fix, director_song, narration, watch_cut
from app.models.songs import SongTake
from app.prompts import check, number_lines, spoken_words
from app.prompts.schemas import Breakdown
from tests.test_breakdown import BREAKDOWN

PROSE = (
    "My gut was a mess.\n[she looks at the camera and sighs]\n  [cut to the app]  \n"
    "I said [quietly] no.\n[Camera] Slow push in.\nThen came the greens."
)
SAID = "My gut was a mess.\nI said no.\nThen came the greens."


def test_the_narrator_never_reads_a_note():
    assert check.narration_text(PROSE) == SAID
    assert narration.job(PROSE)["input"]["prompt"] == SAID  # the talker's take says the same
    vo = "SCENE 1\nBISCUIT (V.O.): Day one.\n[cut to the bowl]\nBISCUIT (V.O.): Nope [beat] gone."
    assert check.narration_text(vo) == "Day one.\nNope gone."


def test_a_note_never_counts_as_spoken_words_or_time():
    assert spoken_words(PROSE) == len(SAID.split())
    assert spoken_words("MAYA: I said [quietly] no.\n[she sighs]") == 3
    assert check._said("[cut to the app]", False) == "" == check._said("[Camera] Push.", False)
    assert check._said("MAYA: I said [quietly] no.", True) == "I said no."
    assert check.narrator("SCENE 1\n[she sighs]") is None  # a silent story: no narrator


def test_the_word_checks_never_want_a_note_heard():
    heard = [{"word": w, "start": n * 0.4, "end": n * 0.4 + 0.3}
             for n, w in enumerate(SAID.split())]  # fmt: skip
    take = SongTake(kind=narration.KIND, lyrics=PROSE, timing={"words": heard})
    lines = [{"text": x, "heard": 1.0} for x in check.narration_text(PROSE).splitlines()]
    assert director_song._missing(take, lines) == []
    assert narration.extras(check.narration_text(PROSE), heard) == []
    assert not {"sighs", "cut", "quietly"} & watch_cut._script_words(PROSE)


def test_a_shot_line_drops_its_note_and_still_matches_the_script():
    """The breakdown reads the script with its notes (direction); a shot's line, what the
    video model says, never keeps one, and still matches the script's words."""
    script = "SCENE 1\nMOM: Nate, where is all your money?\nNATE: I bought [quietly] the dip."
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][0]["script_lines"] = [1, 2]
    bd["scenes"][0]["shots"][1].update(script_lines=[3], line="I bought [quietly] the dip.")
    plan = Breakdown.model_validate(bd)
    assert plan.scenes[0].shots[1].line == "I bought the dip."
    assert "line differs" not in " ".join(check.breakdown(script, plan, {}, 4, 15))
    assert breakdown_fix._said("NATE: I bought [quietly] the dip.") == "I bought the dip."
    assert "3| NATE: I bought [quietly] the dip." in number_lines(script)  # what the steps read


def test_a_note_under_a_screenplay_speaker_stays_direction():
    pasted = "INT. KITCHEN\n\nMAYA\n[she sighs]\nI never wanted this.\n\nTOM (O.S.)\nThen why?"
    assert check.screenplay(pasted) == (
        "INT. KITCHEN\n\nMAYA: I never wanted this.\n[she sighs]\n\nTOM (O.S.): Then why?"
    )


def test_a_minimax_reading_copied_with_a_note_is_read_without_it():
    voice = narration.MINIMAX_VOICES[0]
    sent = narration.job("I said [quietly] no.", voice, reading="I said [quietly] <#0.2#> no.")
    assert sent["input"]["text"] == "I said <#0.2#> no."
