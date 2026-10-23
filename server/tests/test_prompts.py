import json
import re
from pathlib import Path

import pytest

from app import prompts
from app.prompts import check, schemas

EXAMPLES = Path(prompts.__file__).parent / "examples"
FOMO = {"screen:1": ["fomo-mention", "app-open"], "screen:2": ["trading", "win"],
        "screen:3": ["trading", "loss"], "screen:4": ["trading-desktop"]}  # fmt: skip


def example(step):
    ex = json.loads((EXAMPLES / f"{step}.json").read_text())
    return ex, prompts.SCHEMAS[step].model_validate(ex["output"])


def script_of(ex):
    block = re.search(r"<script>\n(.*)\n</script>", ex["input"], re.S).group(1)
    return "\n".join(line.split("| ", 1)[1] for line in block.splitlines())


@pytest.mark.parametrize("step", prompts.SCHEMAS)
def test_every_step_has_a_system_prompt_with_both_rules(step):
    text = prompts.system(step)
    assert "Be engaging" in text and "required screens" in text


@pytest.mark.parametrize("step", prompts.SCHEMAS)
def test_schemas_use_only_what_structured_outputs_accept(step):
    dumped = json.dumps(prompts.SCHEMAS[step].model_json_schema())
    for unsupported in ("minimum", "maximum", "minLength", "maxLength", "pattern"):
        assert f'"{unsupported}"' not in dumped


def test_worked_examples_pass_their_own_checks():
    ex, result = example("enhance")
    assert check.enhance(script_of(ex), result, FOMO) == []
    ex, bd = example("breakdown")
    assert check.breakdown(script_of(ex), bd, FOMO, 4, 30) == []
    _, cp = example("clip_prompts")
    assert check.clip_prompts(bd, cp, 30, 10) == []


def test_checks_catch_added_words_a_missing_screen_and_a_long_clip():
    script = "SCENE 1 — INT. ROOM — DAY\nLEO: I'm down.\nHe trades."
    mark = {"id": "s1", "kind": "action", "anchor": {"line": 2, "quote": "I'm down."}}
    mark |= {"placement": "after", "text": 'LEO: "Wait."', "screen_id": None, "reason": "x"}
    adds_words = schemas.EnhanceResult(suggestions=[mark], notes=[])
    assert check.enhance(script, adds_words, FOMO) == ["s1: adds spoken words"]
    _, bd = example("breakdown")
    shot = bd.scenes[1].shots[0]
    shot.screen_ids = []
    bd.clips[1].seconds = 31
    problems = check.breakdown(script_of(example("breakdown")[0]), bd, FOMO, 4, 30)
    assert "shot 2.1: 'loss' moment without its screen" in problems
    assert "line 9 is a ★ screen line but no shot shows a screen" in problems
    assert "clip c2: 31 s is outside 4–30 s" in problems


def test_brand_block_lists_required_screens_and_their_moments():
    block = prompts.brand_block(
        {"name": "fomo", "never_say": ["guaranteed"]},
        [{"id": 2, "name": "Token chart up", "tags": ["trading"], "default_for": ["win"]},
         {"id": 9, "name": "Settings", "tags": [], "default_for": []}],
    )  # fmt: skip
    assert '- screen:2 "Token chart up" (trading) — required at: win' in block
    assert "Moments: win" in block and "Never say: guaranteed" in block
    assert block.index("Other screens") < block.index("screen:9")


def test_number_lines():
    assert prompts.number_lines("a\nb") == "1| a\n2| b"


def test_eval_scoring_counts_marks_and_reads_notes(tmp_path):
    from evals.score import CASES, score

    case = next(c for c in CASES["cases"] if c["id"] == "fomo-tight")
    answer = tmp_path / "fomo-tight.enhance.json"
    answer.write_text('{"suggestions": [], "notes": []}')
    assert score(tmp_path, case) == []
    mark = {"kind": "camera", "anchor": {"line": 8, "quote": "LEO: Six cents."}}
    mark |= {"placement": "after", "text": "Push-in.", "screen_id": None, "reason": "x"}
    marks = [mark | {"id": f"s{i}"} for i in range(4)]
    answer.write_text(json.dumps({"suggestions": marks, "notes": []}))
    assert score(tmp_path, case) == ["4 suggestions, expected at most 3"]


def test_reference_block_keeps_timing_and_lines_but_not_on_screen_text():
    ref = {"logline": "Dumped at the altar.", "duration_seconds": 45.0,
           "hook": {"seconds": 4.9, "mechanic": "Cold open."},
           "beats": [{"start": 0, "end": 4.9, "summary": "HOOK", "emotion": "shock"}],
           "shots": [{"n": 1, "start": 0, "end": 0.4, "framing": "ECU", "camera": "push-in",
                      "action": "Bride screams", "emotion": "rage", "line": "HELL NO!",
                      "speaker": "bride", "text_on_screen": "HELL [do not copy]"}]}  # fmt: skip
    block = prompts.reference_block(ref, "the montage")
    assert '1. 0.00–0.40 ECU; push-in | Bride screams | rage | bride: "HELL NO!"' in block
    assert "do not copy" not in block and "Replace: the montage" in block


def test_accepting_every_suggestion_leaves_the_script_text_identical():
    from evals.run import apply_all

    ex, result = example("enhance")
    script = script_of(ex)
    added = {s.text for s in result.suggestions}
    kept = [
        line for line in apply_all(script, result.suggestions).splitlines() if line not in added
    ]
    assert kept == script.splitlines()


def test_clip_prompt_checks_catch_music_aspect_and_cast_order():
    _, bd = example("breakdown")
    _, cp = example("clip_prompts")
    clip = cp.clips[0]
    clip.prompt = clip.prompt.split("\n", 1)[1] + "\nStyle: 9:16."
    clip.references[1], clip.references[2] = clip.references[2], clip.references[1]
    assert check.clip_prompts(bd, cp, 30, 10) == [
        "c2: doesn't open and close with the same audio line",
        "c2: has no Keep line before the closing audio line",
        "c2: writes aspect or resolution (those are settings)",
        "c2: characters aren't attached in the order they appear",
    ]


def test_storyboard_check_keeps_character_sheets_within_the_model_limit():
    frame = {"clip_id": "c1", "shot_id": "1.1", "prompt": "x"}
    frames = schemas.StoryboardFrames(
        frames=[frame | {"reference_ids": ["char:1", "char:2", "char:3", "place:1"]}]
    )
    assert check.storyboard(frames, 14, 4) == []
    assert check.storyboard(frames, 14, 2) == ["c1: more references than the image model keeps"]


def test_reference_lines_bind_each_image_in_upload_order():
    refs = [
        {"kind": "character", "name": "Aiden"},
        {"kind": "character", "name": "Aiden"},
        {"kind": "place", "name": "kitchen"},
        {"kind": "screen", "name": "Token chart up", "brand": "fomo"},
        {"kind": "product", "name": "bag", "brand": "Iron Paws"},
    ]
    assert prompts.reference_lines(refs) == (
        "[Image1] and [Image2] are Aiden. [Image3] is the kitchen. [Image4] is the fomo "
        '"Token chart up" screen, shown exactly. [Image5] is the Iron Paws bag, shown exactly.'
    )


def test_short_lines_and_clock_times_in_dialogue_dont_trip_the_clip_checks():
    _, bd = example("breakdown")
    _, cp = example("clip_prompts")
    shot = bd.scenes[1].shots[1]
    clip = cp.clips[0]
    clip.prompt = clip.prompt.replace(shot.line, "No.").replace("Okay. Show me how.", "It's 3:15.")
    clip.prompt = clip.prompt.replace("Trust your setup.", "Trust your setup. Okay, I know.")
    bd.scenes[1].shots[3].line = "Don't you dare sell. Trust your setup. Okay, I know."
    shot.line = "No."
    bd.scenes[1].shots[7].line = "It's 3:15."
    assert check.clip_prompts(bd, cp, 30, 10) == []
    bd.scenes[1].shots[8].line = "No."  # a line said twice on purpose, quoted twice
    clip.prompt = clip.prompt.replace('"Should I still go to school? Comment below."', '"No."')
    assert check.clip_prompts(bd, cp, 30, 10) == []


def test_improve_keeps_the_editors_words_and_the_reference_lines():
    ex, result = example("improve")
    idea = re.search(r"<idea>(.*)</idea>", ex["input"], re.S).group(1)
    refs = re.search(r"<references>(.*)</references>", ex["input"], re.S).group(1)
    assert check.improve(idea, result, refs, 4, 8) == []
    twice = idea + ' Then again: "I bought it at six cents."'
    callback = result.prompt.replace(
        "holds the stare.", 'holds the stare. Leo: "I bought it at six cents."'
    )
    assert check.improve(twice, schemas.ImprovedPrompt(prompt=callback), refs, 4, 8) == []
    gap = result.prompt.replace("Shot 2 | 2–4 s.", "Shot 2 | 3–4 s.")
    assert check.improve(idea, schemas.ImprovedPrompt(prompt=gap), refs, 4, 8) == [
        "shot times aren't whole seconds back to back from 0"
    ]
    result.prompt = result.prompt.replace("six cents", "6 cents").replace(refs, "[Image1] is Leo.")
    assert check.improve(idea, result, refs, 3, 8) == [
        "the line “I bought it at six cents.” isn't there once, word for word",
        "the reference lines aren't copied exactly",
        "4 shots, the brief asks for 3",
    ]


def test_clip_prompt_check_wants_first_frame_summary_and_whole_seconds():
    _, bd = example("breakdown")
    _, cp = example("clip_prompts")
    clip = cp.clips[0]
    clip.prompt = re.sub(r"Summary: .*\n", "", clip.prompt)
    clip.prompt = clip.prompt.replace("[Image1] is the first frame.", "[Image1] storyboard frame.")
    clip.prompt = clip.prompt.replace("Shot 1 | 0–1 s.", "Shot 1 | 0–1.2 s.")
    assert check.clip_prompts(bd, cp, 30, 10) == [
        "c2: has no Summary line",
        "c2: shot times aren't whole seconds back to back from 0",
        "c2: doesn't name [Image1] the first frame",
    ]
