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
    return check.song_breakdown(LYRICS, bd, SONG, {}, 4, 15, written=True)


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
    assert "<length>30 s (about 66 sung words)</length>" in prompts.song_directions_input(
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
    edited = check.song_breakdown(LYRICS, _breakdown(shots), SONG, {}, 4, 15)  # an edit
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


def test_a_script_is_adapted_line_by_line_and_the_cut_says_what_it_drops():
    """Reed's pilot: he brought a voice-over script, not lyrics (song-pilot-notes.md)."""
    sent = prompts.song_directions_input(
        "Goal: x", ["char:1 Biscuit"], source="Biscuit won't eat.\nThen the green goes on."
    )
    assert "<source>\n1| Biscuit won't eat.\n2| Then the green goes on.\n</source>" in sent
    text = prompts.system("song_directions")
    assert "**Adapting a script.**" in text and "`left_out`" in text
    assert "left_out" in schemas.SongDirection.model_fields


def test_a_sounds_like_song_becomes_a_style_line_without_its_name():
    ex = json.loads((EXAMPLES / "song_directions.json").read_text())
    result = schemas.SongDirections.model_validate(ex["output"])
    like = "Better Together by Jack Johnson"
    assert "<sounds_like>Better Together by Jack Johnson</sounds_like>" in (
        prompts.song_directions_input("Goal: x", [], sounds_like=like)
    )
    assert check.song_directions(result, "Iron Paws", 30, sounds_like=like) == []
    result.directions[0].style_line = "acoustic pop like Jack Johnson, 96 BPM"
    problems = check.song_directions(result, "Iron Paws", 30, sounds_like=like)
    assert any("names “Jack Johnson”" in p and p.startswith("Advice: ") for p in problems)
    notes = check.without_names(result, like)  # the free repair, before anyone sees it
    assert result.directions[0].style_line == "acoustic pop, 96 BPM"
    assert notes == ["Advice: direction 1: took “Jack Johnson” out of the style line "
                     "(the music service refuses names)"]  # fmt: skip
    assert check.song_directions(result, "Iron Paws", 30, sounds_like=like) == []
    assert check.without_names(result, like) == []  # again changes nothing
    assert "describes that sound instead, never the name" in prompts.system("song_directions")


def test_the_length_is_shown_before_the_lyrics_are_locked():
    lyrics = "[Verse]\n" + "\n".join(["one two three four five"] * 73)  # the pilot's 365 words
    words, short, long = check.sung_length(lyrics)
    assert words == 365 and 150 <= short <= 160 and 180 <= long <= 185
    assert check.length_note(lyrics) == "365 sung words: a song of about 2:32–3:02."
    near = "\n".join(["one two three four five six seven eight nine ten eleven"] * 13)
    assert check.length_note(near) == "143 sung words: a song of about 1:00–1:12."  # not 0:60


def test_each_shot_plays_while_its_line_is_sung():
    shots = [_shot("1.1", [2], 0.0, 1.0), _shot("1.2", [3], 1.0, 4.0),
             _shot("1.3", [4, 5], 4.0, 6.0, sung=True, line="Get Iron Paws now")]  # fmt: skip
    problems = _check(_breakdown(shots))
    assert "Advice: shot 1.1: ends in the middle of a sung line" in problems  # line 1: 0.1–1.9
    clock = [p for p in problems if "is sung at" in p]
    assert clock == []  # each shot overlaps its line enough
    late = [_shot("1.1", [2], 0.0, 0.5), _shot("1.2", [3], 0.5, 4.0),
            _shot("1.3", [4, 5], 4.0, 6.0, sung=True, line="Get Iron Paws now")]  # fmt: skip
    found = _check(_breakdown(late))
    assert "Advice: shot 1.1: line 2 is sung at 0.10–1.90 s, but the shot runs 0.00–0.50 s" in found
    assert "the measured line times in <song> are that clock" in prompts.system("song_breakdown")


def test_the_prompts_carry_what_made_reeds_song_ads_good():
    """docs/next/song-ad-workflow.md: the reference's shape, the chanted symptom hook, the
    visual shape, cartoon exaggeration, the four product moments, and 16 s clips with people."""
    sent = prompts.song_directions_input("Goal: x", [], reference="Transcript: ... 100 BPM")
    assert "<reference>\nTranscript: ... 100 BPM\n</reference>" in sent
    directions = prompts.system("song_directions")
    assert "**Following a reference.**" in directions and "Never copy its lyrics" in directions
    assert "the symptom list, chanted" in directions
    breakdown = prompts.system("song_breakdown")
    for part in ("**The shape that sells.**", "mid-air leap", "nudges the product to the lens",
                 "never gross", "at four moments", "16 s at most"):  # fmt: skip
        assert part in breakdown, part
    assert "## Style:" not in prompts.system("breakdown")  # story breakdowns untouched


STUDY = {
    "seconds": 128.0,
    "bpm": 97.6,
    "sections": [
        {
            "name": "Hook",
            "start": 0.0,
            "end": 9.0,
            "lines": [
                "Scratching all night, that's my belly crying out",
                "Licking my paws, that's my belly crying out",
            ],
        },
        {"name": "Verse", "start": 9.0, "end": 30.0, "lines": ["You fed me chicken every day"]},
    ],  # fmt: skip
    "words": [{"word": "Scratching", "start": 0.1, "end": 0.6}],
}


def test_a_song_ad_study_guides_the_shape_and_its_lines_are_never_reused():
    """flows S3a: the study gives the structure, section lengths, pace and tempo; its words
    are someone else's song."""
    block = prompts.song_study_block(STUDY)
    assert block.startswith("A song ad that works: 2:08 long, about 98 BPM.")
    assert "- 0–9 s Hook: 2 lines, 16 words" in block
    assert "  | Scratching all night, that's my belly crying out" in block
    assert "Scratching" in block and "0.6" not in block  # its words' times stay out
    text = prompts.system("song_directions")
    assert "no line of yours repeats one of its lines" in text and "about 98 BPM" in text
    ex = json.loads((EXAMPLES / "song_directions.json").read_text())
    result = schemas.SongDirections.model_validate(ex["output"])
    assert check.song_directions(result, "Iron Paws", 30, study=STUDY) == []
    result.directions[1].lyrics += "\n[Bridge]\nScratching all night, that's my belly crying out"
    problems = check.song_directions(result, "Iron Paws", 30, study=STUDY)
    assert ("direction 2: “Scratching all night, that's my belly crying out” repeats a line of "
            "the reference song") in problems  # fmt: skip
    assert not problems[0].startswith("Advice: ")  # a fix: written again


def test_names_go_in_any_case_and_leave_a_tidy_style_line():
    """Flow-QA on #819: lowercase names stayed, and the leftovers read badly."""
    ex = json.loads((EXAMPLES / "song_directions.json").read_text())
    result = schemas.SongDirections.model_validate(ex["output"])
    cases = [
        ("jack johnson", "laid-back pop like jack johnson, upbeat", "laid-back pop, upbeat"),
        ("Fleetwood Mac", "pop , fleetwood mac , upbeat", "pop, upbeat"),
        ("Coldplay", "Coldplay-style stadium rock, 120 BPM", "stadium rock, 120 BPM"),
        ("Bon Iver", "indie folk, Bon Iver,  falsetto", "indie folk, falsetto"),
    ]
    for like, style, tidy in cases:
        result.directions[0].style_line = style
        notes = check.without_names(result, like)
        assert result.directions[0].style_line == tidy, (like, result.directions[0].style_line)
        assert len(notes) == 1 and check.without_names(result, like) == []
    assert check._names("Better Together by Jack Johnson") == ["Better Together", "Jack Johnson"]


def test_the_directions_job_has_one_call_that_repairs_then_checks():
    """Flow-QA on #819: nothing called the repair or the copy check; one entry point does."""
    ex = json.loads((EXAMPLES / "song_directions.json").read_text())
    result = schemas.SongDirections.model_validate(ex["output"])
    result.directions[0].style_line = "breezy pop like Jack Johnson, 100 BPM"
    notes, fixes = check.finish_directions(result, "Iron Paws", 30, "Jack Johnson", STUDY)
    assert result.directions[0].style_line == "breezy pop, 100 BPM" and fixes == []
    assert notes and notes[0].startswith("Advice: direction 1: took “Jack Johnson”")
    result.directions[1].lyrics += "\n[Bridge]\nScratching all night, that's my belly crying out"
    _, fixes = check.finish_directions(result, "Iron Paws", 30, "Jack Johnson", STUDY)
    assert any("repeats a line of the reference song" in f for f in fixes)  # ask once more


def test_only_real_names_go_and_a_style_line_is_never_left_empty():
    """QA and Flow-QA on #819: a genre typed as "sounds like" stripped the style line, and a
    one-word title stripped a mood word. Only artist and song names go (the Producer)."""
    assert check.strip_names("upbeat pop, female lead, 96 BPM", "upbeat pop") == (
        "upbeat pop, female lead, 96 BPM", [])  # fmt: skip
    assert check.strip_names("country and pop, warm vocal", "country and pop") == (
        "country and pop, warm vocal", [])  # fmt: skip
    assert check.strip_names("happy pop, 120 BPM", "Happy by Pharrell") == (
        "happy pop, 120 BPM", [])  # fmt: skip
    assert check.strip_names("pop like Pharrell, 120 BPM", "Happy by Pharrell") == (
        "pop, 120 BPM", ["Pharrell"])  # fmt: skip
    assert check.strip_names("laid-back like jack johnson", "jack johnson")[0] == "laid-back"
    assert check.strip_names("Jack Johnson", "Jack Johnson") == ("pop", ["Jack Johnson"])
    assert check.strip_names("Jack Johnson acoustic", "Jack Johnson")[0] == "acoustic"
