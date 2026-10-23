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


def test_checks_catch_a_rewrite_a_missing_screen_and_a_long_clip():
    script = "SCENE 1 — INT. ROOM — DAY\nLEO: I'm down.\nHe trades."
    mark = {"id": "s1", "kind": "action", "anchor": {"line": 2, "quote": "I'm down."}}
    mark |= {"placement": "replace", "text": "He groans.", "screen_id": None, "reason": "x"}
    rewrite = schemas.EnhanceResult(suggestions=[mark])
    assert check.enhance(script, rewrite, FOMO) == ["s1: rewrites spoken words"]
    _, bd = example("breakdown")
    shot = bd.scenes[1].shots[0]
    shot.screen_ids = []
    bd.clips[1].seconds = 31
    problems = check.breakdown(script_of(example("breakdown")[0]), bd, FOMO, 4, 30)
    assert "shot 2.1: 'loss' moment without its screen" in problems
    assert "clip c2: 31 s is outside 4–30 s" in problems


def test_a_script_without_names_is_all_voiceover():
    lines = [
        "SCENE 1 — INT. KITCHEN — DAY",
        "Crusty eyes every morning.",
        "★ Iron Paws screen: bag",
    ]
    assert check.spoken_lines(lines) == {2}
    assert check.spoken_lines(["Mia waves.", "MIA: Hi."]) == {2}


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


def test_eval_scoring_flags_a_cut_dialogue_line(tmp_path):
    from evals.score import CASES, score

    case = next(c for c in CASES["cases"] if c["id"] == "fomo-tight")
    answer = tmp_path / "fomo-tight.enhance.json"
    answer.write_text('{"suggestions": []}')
    assert score(tmp_path, case) == []
    mark = {"id": "s1", "kind": "cut", "anchor": {"line": 8, "quote": "LEO: Six cents."}}
    mark |= {"placement": "replace", "text": "", "screen_id": None, "reason": "x"}
    answer.write_text(json.dumps({"suggestions": [mark]}))
    assert score(tmp_path, case) == ["line 8 should be left alone"]
