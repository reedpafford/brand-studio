"""Song ads (Reed, 2026-10-28): 2 song directions to pick from, then a breakdown timed to the
measured song: B-roll under it, lip-sync only where the script asks."""

import json

from app import prompts
from app.prompts import check, schemas
from app.prompts.schemas import SongBreakdown

EXAMPLES = prompts.HERE / "examples"
LYRICS = (
    "[Verse 1]\nBowl stays full\nThen the green goes on\n[Chorus] [Lip-sync]\nGet Iron Paws now"
)
SONG = {
    "seconds": 6.0,
    "bpm": 120,
    "beats": [x / 2 for x in range(13)],
    "sections": [
        {"name": "Verse", "start": 0.0, "end": 4.0, "cuts": [2.0]},
        {"name": "Chorus", "start": 4.0, "end": 6.0, "cuts": []},
    ],
    "lines": [
        {"section": "Verse", "text": "Bowl stays full", "start": 0.1, "end": 1.9, "heard": 1},
        {
            "section": "Verse",
            "text": "Then the green goes on",
            "start": 2.1,
            "end": 3.8,
            "heard": 0,
        },
    ],
    "words": [{"word": "Bowl", "start": 0.1, "end": 0.4}],  # for the screens, not Claude
    "peaks": [0.1, 0.9],
}


def _shot(sid, lines, start, end, sung=False, line=None):
    return {"id": sid, "script_lines": lines, "speaker": "Tasha" if line else None,
            "line": line, "action": "Biscuit turns from the bowl.", "reaction": None,
            "camera": "Close-up, static", "seconds": end - start, "character_ids": ["char:1"],
            "place_id": None, "moment": None, "screen_ids": [], "song_start": start,
            "song_end": end, "sung": sung}  # fmt: skip


def _breakdown(shots, clip_seconds=6):
    return SongBreakdown.model_validate({
        "hook": "The full bowl, ignored.",
        "scenes": [{"id": 1, "heading": "INT. KITCHEN — DAY", "look": "warm", "shots": shots}],
        "clips": [{"id": "c1", "shot_ids": [s["id"] for s in shots], "seconds": clip_seconds,
                   "seam": "end"}],
    })  # fmt: skip


def _check(bd):
    return check.song_breakdown(LYRICS, bd, SONG, {}, 4, 15)


def test_the_worked_directions_pass_their_own_check():
    ex = json.loads((EXAMPLES / "song_directions.json").read_text())
    result = schemas.SongDirections.model_validate(ex["output"])
    assert check.song_directions(result, "Iron Paws", 30) == []
    assert "## Worked example" in prompts.system("song_directions")


def test_directions_advise_on_length_style_and_the_brand_line():
    ex = json.loads((EXAMPLES / "song_directions.json").read_text())
    result = schemas.SongDirections.model_validate(ex["output"])
    result.directions[0].style_line = " ".join(["pop"] * 26)
    result.directions[1].lyrics = "[Chorus]\nShort and sweet"
    problems = check.song_directions(result, "Iron Paws", 30)
    assert "Advice: direction 1: the style line is over 25 words" in problems
    assert f"Advice: direction 2: {check.NO_CTA}" in problems
    assert any(p.startswith("Advice: direction 2: 3 sung words") for p in problems)
    result.directions.pop()
    assert "1 directions; write exactly 2" in check.song_directions(result, "Iron Paws")


def test_a_song_breakdown_is_the_breakdown_plus_its_own_part():
    song, story = prompts.system("song_breakdown"), prompts.system("breakdown")
    assert song.startswith(story.split("## Worked example")[0].strip())  # same rules first
    assert "# Song ads" in song and "# Song ads" not in story
    assert "## Worked example" not in song  # the story example would teach dialogue shots
    assert "Style: Song" not in song
    assert prompts.style("song")["sections"].get("clip") in prompts.system("clip_prompts", "song")


def test_song_block_lists_sections_beats_and_timed_lines():
    block = prompts.song_block(SONG)
    assert block.startswith('<song seconds="6.00" bpm="120">')
    assert "- 0.00–4.00 Verse (cuts: 2.00)" in block and "- 4.00–6.00 Chorus\n" in block
    assert "Beats: 0.00 0.50 1.00" in block
    assert "1| 0.10–1.90 Bowl stays full\n" in block
    assert "2| 2.10–3.80 Then the green goes on (times guessed)" in block
    assert "peaks" not in block and "0.40" not in block  # words and peaks stay out
    assert "<length>30 s (about 75 sung words)</length>" in prompts.song_directions_input(
        "Goal: x", ["char:1 Biscuit"], "folk", 30
    )


def test_a_clean_song_breakdown_passes():
    shots = [_shot("1.1", [1, 2], 0.0, 2.0), _shot("1.2", [3], 2.0, 4.0),
             _shot("1.3", [4, 5], 4.0, 6.0, sung=True, line="Get Iron Paws now")]  # fmt: skip
    assert _check(_breakdown(shots)) == []


def test_gaps_and_a_speaking_b_roll_shot_need_a_fix_and_the_rest_is_advice():
    shots = [_shot("1.1", [1, 2], 0.0, 2.2), _shot("1.2", [3], 2.5, 4.6, sung=True),
             _shot("1.3", [4, 5], 4.6, 5.0, line="Get Iron Paws now")]  # fmt: skip
    problems = _check(_breakdown(shots))
    assert (
        "shot 1.2: starts at 2.50 s, not 2.20 s; the shots run back to back over the song"
        in problems
    )
    assert "shot 1.3: a B-roll shot has a line; B-roll is silent picture" in problems
    assert "the shots end at 5.00 s, the song at 6.00 s" in problems
    assert "Advice: shot 1.1: an edge is off the beat; cut on a beat" in problems
    assert "Advice: shot 1.2: runs across a section's edge" in problems
    assert (
        "Advice: Shot 1.2 is Sung, but nobody asked for lip-sync there. Make it B-roll?" in problems
    )
    edited = check.song_breakdown(LYRICS, _breakdown(shots), SONG, {}, 4, 15, written=False)
    assert not [p for p in edited if "nobody asked" in p]  # the editor's own flip (rule 31)
    assert not [p for p in problems if "[Lip-sync]" in p]  # never asks to change the lyrics


def test_lip_sync_is_asked_by_a_line_or_its_section():
    assert check.lip_synced(LYRICS) == {5}
    assert check.lip_synced("[Verse]\nOne [Lip-sync]\nTwo") == {2}
    assert check.sung_lines(LYRICS) == ["Bowl stays full", "Then the green goes on",
                                        "Get Iron Paws now"]  # fmt: skip


def test_a_sung_clip_binds_the_song_and_its_audio_line_passes():
    line = ("Audio: only the song from [Audio1], sung by Tasha, and kitchen hum. No other "
            "music, voices or narration. No subtitles.")  # fmt: skip
    assert check.AUDIO_LINE.match(line)
    text = prompts.system("song_clip_prompts")
    assert text.startswith(prompts.system("clip_prompts").split("## Worked example")[0].strip())
    assert "**Songs.**" in text and "audio:song:<clip id>" in text
    assert "**Songs.**" not in prompts.system("clip_prompts")  # story videos stay as they were


def test_suno_gets_the_lyrics_word_for_word_without_our_marks():
    sent = prompts.song_request(LYRICS, "indie folk, warm female lead, 100 BPM.")
    assert sent["lyrics"] == (
        "[Intro: vocals start immediately]\n[Verse 1]\nBowl stays full\n"
        "Then the green goes on\n[Chorus]\nGet Iron Paws now\n[End]"
    )
    assert sent["style"].startswith("indie folk, warm female lead, 100 BPM, vocals start")
    assert "spoken word" in sent["exclude_styles"]


def test_directions_list_claims_the_brand_never_made():
    field = schemas.SongDirection.model_fields["unchecked_claims"]
    assert "word for word" in field.description
    assert "`unchecked_claims`" in prompts.system("song_directions")
