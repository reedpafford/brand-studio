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


def test_narrated_clips_keep_the_actions_own_sound_with_no_voice_or_music():
    """Reed, 2026-10-29 (flows V6n): each take keeps its sound effects under the narration."""
    text = prompts.system("narrated_clip_prompts")
    assert "the action's own sound effects" in text and "silent picture" not in text
    assert "no voice and no music of its own" in text
    # Next-Lead: the silence checks refuse speech and voices, never a named sound effect
    audio = (
        "Audio: no one speaks (no voices, narration or dialogue), only the action's own sound "
        "effects: a dog's lick, a whoosh of kibble, a tail thumping, a bark. No music, background "
        "music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone "
        "or stinger. No subtitles."
    )
    prompt = (
        f"{audio}\nShot 1 (0–2 s): Biscuit licks the bowl clean with a wet slurp. No one speaks.\n"
        f"Shot 2 (2–4 s): kibble pours with a whoosh; he barks once and spins. No one speaks.\n"
        f"Keep: the kitchen.\n{audio}"
    )
    assert check.AUDIO_LINE.match(audio)
    assert check._silence(prompt, spoken=False) == []


def test_the_music_bed_is_an_instrumental_with_no_names():
    from app.prompts.schemas import NarrationMusic

    assert prompts.SCHEMAS["narration_music"] is NarrationMusic
    assert "Never name an artist" in prompts.system("narration_music")
    assert "narration_music" in prompts.NO_RULES  # not a script writer
    good = NarrationMusic(
        prompt="Dark, tense documentary underscore. Ticking pulse, low drones, sparse piano, soft "
        "hits. Slow, about 70 BPM. In the last third it lifts: warmer chords, brighter piano, a "
        "steady beat. Steady and low under the narration: no big drops, no solos, no sudden stops.",
        arc="tense, then hopeful in the last third",
    )
    assert check.narration_music(good) == []
    assert prompts.music_prompt(good).endswith(
        "Instrumental only: no vocals, no choir, no spoken word."
    )
    named = good.model_copy(update={"prompt": good.prompt + " Like Hans Zimmer."})
    assert any("names someone" in p for p in check.narration_music(named))
    sung = good.model_copy(update={"prompt": good.prompt + " A soft choir hums."})
    assert any("asks for a voice" in p for p in check.narration_music(sung))
    assert "<seconds>140</seconds>" in prompts.narration_music_input("Day one.", 139.6)
    assert "<note>" not in prompts.narration_music_input("Day one.", 10)


def test_the_narrator_check_advises_on_the_format():
    """flows ST0 and N1: "Make it Narrated" on a Dialogue script; on a Narrated one, Advice
    on each line spoken on camera."""
    vo = "SCENE 1\nBISCUIT (V.O.): Day one.\nHe sniffs."
    assert check.format_advice(vo, "dialogue") == [
        "Advice: This reads as narrated. Make it Narrated?"
    ]
    assert check.format_advice("SCENE 1\nMOM: Hi.", "dialogue") == []
    mixed = "SCENE 1\nBISCUIT (V.O.): Day one.\nMom: Dinner!\nCTA: Get Iron Paws."
    assert check.format_advice(mixed, "narrated") == [
        "Advice: line 3: This line is spoken on camera, but a Narrated script has one voice. "
        "The narrator will read it."
    ]
    assert check.format_advice(vo, "narrated") == [] == check.format_advice(vo, "song")


def test_the_narrator_reads_only_the_voiced_words():
    script = (
        "SCENE 1 — INT. KITCHEN\n[Camera] Slow push in.\nBISCUIT (V.O.): Day one.\nHe sniffs.\n"
        "★ fomo screen: Home\nBiscuit (V.O.): Nope.\nCTA: Get Iron Paws."
    )
    assert check.narration_text(script) == "Day one.\nNope."
    assert check.narration_text("My gut was a mess.\n\nThen came the greens.") == (
        "My gut was a mess.\nThen came the greens."
    )
