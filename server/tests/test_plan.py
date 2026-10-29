"""The scene plan (flows 1b, P1): the script's words grouped into scenes before the breakdown."""

from app import prompts
from app.prompts import check
from app.prompts.schemas import PlanLine, PlanScene, ScenePlan, Structure

SCRIPT = """SCENE 1 — INT. LIVING ROOM — DAY
BISCUIT (V.O.): Day one. I lick my paws.
He licks.
BISCUIT (V.O.): She tries a spray.

SCENE 2 — INT. KITCHEN — DAY
BISCUIT (V.O.): Then she found Iron Paws."""


def _plan(*scenes) -> ScenePlan:
    shape = Structure(name="Pet supplement", parts=["Problem", "Discovery"], based_on="pattern")
    return ScenePlan(structure=shape, cast=["char:1", "char:2"], scenes=list(scenes))


def _scene(id, place, lines, cast=("char:1",), product=None) -> PlanScene:
    lines = [PlanLine(line=n, action=f"action {n}", product=product) for n in lines]
    return PlanScene(id=id, part="Problem", place=place, cast=list(cast), lines=lines)


GOOD = _plan(
    _scene(1, "INT. LIVING ROOM — DAY", [2, 3, 4]),
    _scene(2, "INT. KITCHEN — DAY", [7], product="product:1"),
)


def test_every_line_with_words_is_in_one_scene_once_in_order():
    assert prompts.plan_lines(SCRIPT) == [2, 3, 4, 7]  # headings and blank lines aren't planned
    assert check.plan(SCRIPT, GOOD, ["char:1", "char:2"], ["product:1"]) == []
    gap = _plan(_scene(1, "INT. LIVING ROOM — DAY", [2, 3]), GOOD.scenes[1])
    assert check.plan(SCRIPT, gap, ["char:1"], ["product:1"]) == ["lines 4 are in no scene"]
    twice = _plan(_scene(1, "INT. LIVING ROOM — DAY", [2, 3, 4]),
                  _scene(2, "INT. KITCHEN — DAY", [4, 7], product="product:1"))  # fmt: skip
    assert "lines 4 are in more than one scene" in check.plan(
        SCRIPT, twice, ["char:1"], ["product:1"]
    )
    swapped = _plan(_scene(1, "INT. LIVING ROOM — DAY", [3, 2, 4]), GOOD.scenes[1])
    assert check.plan(SCRIPT, swapped, ["char:1"], ["product:1"]) == [
        "the lines are out of order: every line stays where the script has it"
    ]
    heading = _plan(_scene(1, "INT. LIVING ROOM — DAY", [1, 2, 3, 4]), GOOD.scenes[1])
    assert "lines 1 aren't script lines with words" in check.plan(
        SCRIPT, heading, ["char:1"], ["product:1"]
    )


def test_the_plans_advice_names_its_press():
    bad = _plan(
        _scene(1, "INT. LIVING ROOM, then EXT. PARK — DAY", [2, 3, 4], cast=["char:1", "char:9"]),
        _scene(2, "INT. KITCHEN — DAY", [7]),
    )
    problems = check.plan(SCRIPT, bad, ["char:1"], ["product:1"])
    assert (
        "Advice: scene 1: two places (“INT. LIVING ROOM, then EXT. PARK — DAY”); Split here"
        in problems
    )
    assert "Advice: scene 1: char:9 isn't in the cast" in problems
    assert "Advice: the product is never shown; ★ a line" in problems
    wrong_star = _plan(GOOD.scenes[0], _scene(2, "INT. KITCHEN — DAY", [7], product="product:7"))
    assert check.plan(SCRIPT, wrong_star, ["char:1"], ["product:1"]) == [
        "scene 2: ★ product:7 isn't the brand's product or screen"
    ]
    long = check.plan(SCRIPT, GOOD, ["char:1"], ["product:1"], fmt="narrated", max_seconds=2)
    assert "Advice: scene 1 runs about 3 s, over one clip's 2 s; Split here" in long


def test_change_this_scene_keeps_its_lines_and_carries_the_plan():
    assert check.plan_scene(GOOD.scenes[0], GOOD.scenes[0]) == []
    assert check.plan_scene(GOOD.scenes[0], _scene(1, "INT. LIVING ROOM — DAY", [2, 3])) == [
        "the changed scene's lines differ: keep the same lines, in order"
    ]
    text = prompts.system("plan_scene")
    assert text.startswith(prompts.system("plan")) and "**Change one scene.**" in text
    assert prompts.SCHEMAS["plan_scene"] is PlanScene and prompts.SCHEMAS["plan"] is ScenePlan
    block = prompts.plan_block(GOOD, SCRIPT)
    assert "Scene 2 (Problem): INT. KITCHEN — DAY · char:1" in block
    assert "7| BISCUIT (V.O.): Then she found Iron Paws.\n   → action 7 ★ product:1" in block
    message = prompts.plan_scene_input("<brief>x</brief>", GOOD, SCRIPT, 1, "funnier")
    assert message.endswith("</plan>\n<scene>1</scene>\n<note>funnier</note>")


def test_the_plan_prompt_keeps_the_words_and_names_its_patterns():
    text = prompts.system("plan")
    for part in ("rule 19", "rule 29", "**Proven patterns**", "**Pet supplement:**", "★"):
        assert part in text, part
    message = prompts.plan_input("Brief.", ["char:1 Biscuit: a pit bull"], SCRIPT, "narrated",
                                 "Seedance, 12 s a clip", note="make it funny")  # fmt: skip
    assert "<format>narrated</format>" in message and "7| BISCUIT (V.O.)" in message
    assert "<note>make it funny</note>" in message and "<reference>" not in message


def test_a_video_made_before_plans_gets_its_plan_from_the_breakdown():
    from tests.test_song import _breakdown, _shot

    bd = _breakdown([_shot("1.1", [2, 3], 0, 2), _shot("1.2", [4], 2, 4)])
    bd.scenes[0].shots[1].screen_ids = ["product:1"]
    plan = prompts.plan_from_breakdown(bd)
    assert plan.structure.name == "From the breakdown" and len(plan.scenes) == 1
    assert [x.line for x in plan.scenes[0].lines] == [2, 3, 4]
    assert (
        plan.scenes[0].lines[2].product == "product:1" and plan.scenes[0].lines[0].product is None
    )
