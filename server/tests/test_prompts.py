import inspect
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

import evals
from app import prompts
from app.prompts import check, schemas
from evals import checks

EXAMPLES = Path(prompts.__file__).parent / "examples"
FOMO = {"screen:1": ["fomo-mention", "app-open"], "screen:2": ["trading", "win"],
        "screen:3": ["trading", "loss"], "screen:4": ["trading-desktop"]}  # fmt: skip


def example(step):
    ex = json.loads((EXAMPLES / f"{step}.json").read_text())
    return ex, prompts.SCHEMAS[step].model_validate(ex["output"])


def logo_once(bd):
    """fomo's trading screens are logo-only: the server counts them as the one logo it
    attached, screen:2 (clip_prompts.clip_problems), as the clip example does."""
    for shot in (s for scene in bd.scenes for s in scene.shots):
        shot.screen_ids = list(dict.fromkeys("screen:2" if s in ("screen:3", "screen:4") else s
                                             for s in shot.screen_ids))  # fmt: skip
    return bd


def script_of(ex):
    block = re.search(r"<script>\n(.*)\n</script>", ex["input"], re.S).group(1)
    return "\n".join(line.split("| ", 1)[1] for line in block.splitlines())


@pytest.mark.parametrize("step", sorted(set(prompts.SCHEMAS) - prompts.NO_RULES))
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
    assert check.clip_prompts(logo_once(bd), cp, 30, 10) == []


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
    assert "Advice: shot 2.1: 'loss' moment without its screen" in problems
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


def test_a_screen_that_prints_a_balance_never_ties_the_numbers():
    rich = {"id": 5, "name": "Home (rich)", "tags": ["home"], "default_for": ["win"],
            "balance": "$348,920.15"}  # fmt: skip
    block = prompts.brand_block({"name": "fomo"}, [rich])
    assert 'screen:5 "Home (rich)" (home), shows a balance of $348,920.15' in block
    for step in ("breakdown", "script_draft"):  # Current rules 14: numbers can be anything
        assert "use that number" not in prompts.system(step)
    for step in ("storyboard", "clip_prompts"):  # Reed #600: only the logo must be right
        text = (EXAMPLES.parent / f"{step}.md").read_text()
        assert "key number" not in text and "reads $" not in text, step


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


def test_no_prompt_file_keeps_a_merge_conflict_marker():
    for path in (EXAMPLES.parent).rglob("*"):
        if path.is_file() and path.suffix in {".md", ".json", ".py"}:
            text = path.read_text()
            assert not re.search(r"^(<{7}|={7}|>{7})( |$)", text, re.M), path


def test_breakdown_check_wants_the_main_character_in_every_montage_shot():
    ex, bd = example("breakdown")
    script = script_of(ex)
    assert check.breakdown(script, bd, FOMO, 4, 30) == []
    shot = next(s for s in bd.scenes[1].shots if s.id == "2.10")
    shot.character_ids = []
    assert check.breakdown(script, bd, FOMO, 4, 30) == [
        "Advice: shot 2.10: a montage shot without the main character"
    ]
    shot.action = "Malik's hands push open the glass door of a penthouse."
    assert check.breakdown(script, bd, FOMO, 4, 30) == []  # his hands count as him
    shot.action, shot.screen_ids = "The phone shows the chart.", ["screen:2"]
    shot.moment = "win"
    assert check.breakdown(script, bd, FOMO, 4, 30) == []  # so does his screen
    lone = bd.scenes[0].shots[1]  # 1.2: one quick empty insert between lines, not a montage
    assert not lone.line and not lone.character_ids and lone.seconds <= 0.6


def test_every_quick_cut_names_a_cast_member():
    _, cp = example("clip_prompts")
    prompt = cp.clips[0].prompt
    assert check._cuts_name_someone(prompt) == []
    empty = prompt.replace("behind Malik as he walks", "as a hand pushes")
    assert check._cuts_name_someone(empty) == [
        "shot 9: a quick cut names nobody (“a wide shot tracking in as a hand pushes”)"
    ]
    refs = next(line for line in empty.splitlines() if line.startswith("References: "))
    no_cast = empty.replace(refs, "References: [Image1] is the first frame.")
    assert check._cuts_name_someone(no_cast) == []


def test_breakdown_check_wants_grind_before_the_payoff_and_the_hook_first():
    ex, bd = example("breakdown")
    script = script_of(ex)
    assert check.breakdown(script, bd, FOMO, 4, 30) == []  # four beats before the fast run
    scene = bd.scenes[1]
    jump = scene.shots[:4] + scene.shots[7:]  # the old way: one trade, then the car
    scene.shots, bd.clips[1].shot_ids = jump, [s.id for s in jump]
    bd.clips[1].seconds = 7
    lines = check.breakdown(script, bd, FOMO, 4, 30)
    assert "Advice: shot 2.8: the montage reaches the payoff after 1 grind beats; add a red " \
        "day, a small win, another late night first" in lines  # fmt: skip
    _, bd = example("breakdown")
    first = bd.scenes[0].shots
    cut = {"script_lines": [3]}  # tied to Tasha's opening line, as the remake's cutaways were
    wide = first[1].model_copy(update={"id": "1.0", "action": "Wide of the kitchen."} | cut)
    guests = first[1].model_copy(update={"id": "1.01", "action": "Neighbours look in."} | cut)
    bd.scenes[0].shots = [wide, guests, *first]
    bd.clips[0].shot_ids = ["1.0", "1.01", *bd.clips[0].shot_ids]
    assert "Advice: shot 1.0: 2 shots come before the first line; open on the exchange " \
        "itself" in check.breakdown(script, bd, FOMO, 4, 30)  # fmt: skip


def test_app_screens_are_on_a_phone_in_hand_never_a_flat_on_screenshot():
    for step in ("breakdown", "storyboard", "clip_prompts", "improve"):  # Reed, 2026-10-27
        text = (EXAMPLES.parent / f"{step}.md").read_text().lower()
        assert "never a screenshot filling the frame flat-on" in text, step
    _, bd = example("breakdown")
    for shot in (s for scene in bd.scenes for s in scene.shots if s.screen_ids):
        assert shot.character_ids, shot.id  # his hand or face is in the shot
    for path in EXAMPLES.glob("*.json"):
        if path.name != "reel_watch.json":  # a reading of someone else's reel
            assert not re.search("fills the frame|flat-on", path.read_text()), path.name


def test_the_sheet_owns_the_face_in_every_prompt():
    """Reed (faces, #602), after docs/prompting/seedance-2.5.md §1-2 and nano-banana.md §2."""
    clip = prompts.system("clip_prompts")
    assert "the main character's sheet first" in clip
    assert "set each face and outfit and override the first frame where they differ" in clip
    assert "big glossy eyes" not in clip.split("Style: ", 1)[1].split("\n", 1)[0]
    assert "Keep: Aiden's identity and clothing stable in every shot" in clip
    for step in ("breakdown", "script_draft", "variations"):
        assert "never a new costume" in prompts.system(step)
    board = prompts.system("storyboard")
    assert "the main character's first: the sheet is the main reference for the face" in board
    _, cp = example("clip_prompts")
    refs = next(x for x in cp.clips[0].prompt.splitlines() if x.startswith("References: "))
    assert refs.index("override the first frame") < refs.index("[Image2] is Malik.")
    assert "[Image1] is the first frame." in refs  # the server's fix-up keeps this sentence


def test_no_prompt_or_example_keeps_a_rule_reed_replaced():
    """Current rules (ops/DECISIONS.md, #609): screens need only the logo (14), no end card or
    logo overlay (18), the sheets set faces (10), 3 screens a clip at most, one montage outfit."""
    old = ["key number", "use that number", "that same balance", "end card", "logo overlay",
           "big glossy", "subsurface", "expressive faces", "Keep a clip to 2 screens",
           "whatever he wears", "Macro insert of the phone"]  # fmt: skip
    files = [*EXAMPLES.parent.glob("*.md"), EXAMPLES.parent / "schemas.py"]
    texts = {p.name: p.read_text() for p in files if p.name != "sheet.md"}  # the sheet sets faces
    for path in EXAMPLES.glob("*.json"):
        if path.name != "reel_watch.json":  # a reading of someone else's reel
            texts[path.name] = json.dumps(json.loads(path.read_text())["output"])
    for name, text in texts.items():
        assert not [w for w in old if w in text], name
    for name in ("storyboard.md", "clip_prompts.md", "improve.md"):  # no figure asked of a screen
        assert "reads $" not in texts[name], name
    cases = (Path(evals.__file__).parent / "cases.json").read_text()
    assert "skyline arrival" not in cases and "ending on the skyline" not in cases  # rule 17


def test_a_clip_holds_one_scene_for_as_long_as_it_needs():
    """Rule 29 (Reed, 2026-10-28): split by scene or action, never by a clip-length number;
    only crossing a scene and the model's own max are flagged. For continuity, not face drift."""
    ex, bd = example("breakdown")
    script = script_of(ex)
    assert check.breakdown(script, bd, FOMO, 4, 30) == []
    bd.clips[0].seconds = 22  # the opening argument, no montage: one clip, as long as it needs
    assert check.breakdown(script, bd, FOMO, 4, 30) == []
    bd.clips[0].seconds = 31
    assert check.breakdown(script, bd, FOMO, 4, 30) == ["clip c1: 31 s is outside 4–30 s"]
    _, bd = example("breakdown")
    bd.clips[1].shot_ids += bd.clips[2].shot_ids  # the montage clip runs on into the kitchen
    bd.clips[1].seconds += bd.clips[2].seconds
    bd.clips = [bd.clips[0], bd.clips[1]]
    assert "Advice: clip c2 crosses scenes 2, 3; end it where the place or time changes" in (
        check.breakdown(script, bd, FOMO, 4, 30)
    )
    assert "one scene: always end it where the place or time changes" in prompts.system("breakdown")
    assert "Never another character's hands" in prompts.system("breakdown")
    clip = prompts.system("clip_prompts")
    assert "tears on the same face, never a younger or rounder one" in clip
    for step in ("clip_prompts", "storyboard"):  # the sheet's outfit, not the old role's
        assert "never one from the role's or the script's description" in prompts.system(step)


def test_breakdown_check_keeps_a_clip_to_three_screens():
    ex, bd = example("breakdown")
    script = script_of(ex)
    shot = next(s for s in bd.scenes[1].shots if s.id == "2.11")
    shot.screen_ids = ["screen:1"]
    assert check.breakdown(script, bd, FOMO, 4, 30) == [
        "clip c2: 4 screens; keep the 3 its beats need"
    ]


def _variation_case():
    ex, result = example("variations")
    original = script_of(ex)
    fomo = {"end_line": "Want to trade like me? Download fomo through the link in my bio."}
    return original, result, fomo["end_line"]


def test_variations_example_passes_and_every_check_says_what_to_do():
    original, result, end = _variation_case()
    cast = ["Malik", "Tasha"]
    assert check.variations(original, result, {}, end, ["can't lose"], 1, cast, "fomo") == []
    v = result.variations[0]
    v.script = v.script.replace("★ fomo screen: Token chart down — on Malik's phone\n", "")
    v.script = v.script.rsplit("\n", 1)[0] + "\nMALIK: You can't lose. Live-action tag here."
    assert check.variations(original, result, {}, end, ["can't lose"], 2, cast, "fomo") == [
        "1 variations, 2 asked for; regenerate",
        "Advice: variation 1: the last line doesn't mention the brand or where to find it",
        "variation 1 drops the ★ line for Token chart down; put it back where it fits",
        "variation 1 says “can't lose”, which the brand never says",
        "variation 1 brings back live action; that slot is the end line",
    ]


def test_variations_advice_covers_length_closeness_and_format():
    original, result, end = _variation_case()
    v = result.variations[0]
    v.script = original.replace("TASHA", "ROSE").replace("Tasha", "Rose")  # Tasha is gone
    problems = check.variations(
        original, result, {}, end, [], 1, ["Malik", "Tasha", "Bruno"], "fomo"
    )
    assert problems == [
        "variation 1 drops Tasha, a locked character",  # Bruno isn't in the original: no flag
        "Advice: variation 1 is very close to the original; regenerate with a note",
    ]
    v.script = "# The sneakers\n" + "MALIK: Hi.\n" + end.join(["MALIK: ", ""])
    assert check.variations(original, result, {}, end, [], 1, [], "fomo") == [
        "variation 1 drops the ★ line for Home (rich); put it back where it fits",
        "variation 1 drops the ★ line for Token chart down; put it back where it fits",
        "variation 1 drops the ★ line for Token chart up; put it back where it fits",
        "Advice: variation 1 has 14 spoken words, the original 54",
        "Advice: variation 1 runs 19 words in all, the original 204",
        "Advice: variation 1 is very close to the original; regenerate with a note",
        "Advice: variation 1: “# The sneakers” isn't house format",
    ]


def test_a_montage_invents_its_payoffs_never_the_reference_or_original_run(tmp_path):
    from evals.score import CASES, ROOT, reference_montage, score

    ref = "a black suit walking through a penthouse onto a night-skyline balcony"
    copied = (
        "Montage: keys dropped into his palm, Nate behind the wheel, the penthouse, the skyline."
    )
    assert checks.payoffs(copied) == ["keys", "a car", "a penthouse", "a skyline"]
    assert checks.repeated_payoffs(copied, ref, "the reference's") == [
        "Advice: the montage repeats the reference's payoffs (a penthouse, a skyline); invent "
        "ones that fit this story and its people"
    ]
    assert checks.repeated_payoffs("Montage: Nate on the balcony.", ref, "the reference's") == []
    altar = ROOT / "docs/references/fomo-DehudnaAmce/BREAKDOWN.json"
    ref = reference_montage(json.loads(altar.read_text()))
    _, drafts = example("script_draft")  # the worked examples invent their own
    for d in drafts.drafts:
        assert checks.repeated_payoffs(checks.montage_text(d.script), ref, "the reference's") == []
    original, result, _ = _variation_case()
    for v in result.variations:
        mine, theirs = checks.montage_text(v.script), checks.montage_text(original)
        assert checks.repeated_payoffs(mine, theirs, "the original's") == []
    case = next(c for c in CASES["cases"] if c["id"] == "fomo-altar-variations")
    again = {"title": "x", "premise": "x", "script": "\n".join(case["script"]), "changes": []}
    (tmp_path / f"{case['id']}.variations.json").write_text(json.dumps({"variations": [again]}))
    (tmp_path / f"{case['id']}.cast_slots.json").write_text('{"slots": []}')
    assert (
        "variation 1: Advice: the montage repeats the original's payoffs (keys, a car, a "
        "penthouse); invent ones that fit this story and its people"
    ) in score(tmp_path, case)


def test_the_evals_tell_and_check_the_brands_recent_payoffs(tmp_path):
    from evals.run import run_case
    from evals.score import CASES, score

    for step in ("breakdown", "script_draft", "variations"):  # Reed, 2026-10-27
        assert "<recent_payoffs>" in prompts.system(step)
    case = next(c for c in CASES["cases"] if c["id"] == "fomo-altar-variations")
    run_case(None, case, tmp_path, [], 0, dry=True)  # free: writes the prompt only
    told = (tmp_path / f"{case['id']}.variations.prompt.txt").read_text()
    assert '<recent_payoffs>\n"Lambo Halloween": A valet tosses Omar the keys' in told
    lambo = case["script"] + [
        "Wordless montage, Nate in every shot: the Lamborghini, then his yacht."
    ]
    again = {"title": "x", "premise": "x", "script": "\n".join(lambo), "changes": []}
    (tmp_path / f"{case['id']}.variations.json").write_text(json.dumps({"variations": [again]}))
    (tmp_path / f"{case['id']}.cast_slots.json").write_text('{"slots": []}')
    assert (
        "variation 1: Advice: the montage repeats a recent video's payoffs (keys, a car, a "
        "yacht); invent ones that fit this story and its people"
    ) in score(tmp_path, case)


def test_an_echo_repeats_what_was_said_to_his_face():
    said = "GIRLFRIEND: You're just a loser who doesn't get invited to anything.\n"
    assert checks.echo_lines(said + "GIRLFRIEND (V.O.): Doesn't get invited to anything.") == []
    assert checks.echo_lines(said + "GIRLFRIEND (V.O.): New position can't afford a ticket.") == [
        "Advice: the echo “New position can't afford a ticket.” calls back to nothing "
        "Girlfriend said; repeat “You're just a loser who doesn't get invited to anything.”"
    ]
    assert checks.echo_lines("BRUNO (V.O.): I was the worst dog on the street.") == []  # narrator
    lines = [
        "You're just a loser who doesn't get invited to anything.",
        "New position doesn't get invited to anything.",
        "Sorry, I don't get invited to anything.",
    ]  # the callback is no mishearing
    heard = [{"start": n, "end": n + 1, "text": t} for n, t in enumerate(lines)]  # fmt: skip
    assert check.misheard(heard) == [
        "Advice: “New position doesn't get invited to anything.” ends like “You're just a loser "
        "who doesn't get invited to anything.”; if it echoes it, the transcript may have misheard "
        "the start"
    ]
    for step in ("script_draft", "variations"):
        assert "Echoes repeat what was said." in prompts.system(step)


def test_eval_run_print_writes_the_variations_prompt_for_free(tmp_path):
    from evals.run import run_case
    from evals.score import CASES

    case = next(c for c in CASES["cases"] if c["id"] == "fomo-altar-variations")
    run_case(None, case, tmp_path, [], Decimal(0), dry=True)  # no client: nothing is called
    text = (tmp_path / "fomo-altar-variations.variations.prompt.txt").read_text()
    assert "# Step: Variations" in text and "<count>2</count>" in text
    assert "<cast>\nchar:1 Nate, the groom\nchar:2 Mia, the bride\n</cast>" in text
    assert "NATE: Sorry, I'm fully booked." in text


def test_eval_scoring_runs_the_variations_check(tmp_path):
    from evals.score import CASES, score

    case = next(c for c in CASES["cases"] if c["id"] == "ironpaws-pitbull1-variations")
    script = "\n".join(case["script"]).replace("Peanut butter flavor.", "Chicken flavor.")
    answer = {"variations": [{"title": "x", "premise": "x", "script": script, "changes": []}]}
    (tmp_path / "ironpaws-pitbull1-variations.variations.json").write_text(json.dumps(answer))
    one = {"description": "30s man, a cook", "recurring": True}
    slots = [
        one | {"role": "Bruno, the pitbull (narrator)", "kind": "Main", "appears_in": [0, 1]},
        one | {"role": "The crowd at the dog park", "kind": "Helper", "appears_in": [1]},
    ]
    (tmp_path / "ironpaws-pitbull1-variations.cast_slots.json").write_text(
        json.dumps({"slots": slots})
    )
    assert score(tmp_path, case) == [
        "variation 1 says “chicken”, which the brand never says",
        "Advice: variation 1 is very close to the original; regenerate with a note",
        "Advice: The crowd at the dog park: sounds like background people, who are never cast",
        "no slot matching any of ['owner']",
        "a slot for 'crowd'",
    ]


def test_cast_slots_keep_the_names_the_cast_and_scripts_use(tmp_path):
    from evals.score import CASES, score

    case = next(c for c in CASES["cases"] if c["id"] == "ironpaws-pitbull1-variations")
    answer = {"variations": [{"title": "x", "premise": "x", "script": "x", "changes": []}]}
    (tmp_path / f"{case['id']}.variations.json").write_text(json.dumps(answer))
    slot = {"description": "30s man, a cook", "kind": "Main", "appears_in": [0], "recurring": True}
    slots = [slot | {"role": "The dog (narrator)"}, slot | {"role": "His owner"}]
    (tmp_path / f"{case['id']}.cast_slots.json").write_text(json.dumps({"slots": slots}))
    problems = score(tmp_path, case)
    assert "Advice: no slot carries the name Bruno; use it in that role" in problems
    assert "no slot for Bruno" in problems


def test_every_speaker_is_a_slot_in_the_eval(tmp_path):
    from evals.score import CASES, score

    case = next(c for c in CASES["cases"] if c["id"] == "fomo-empty-chair-cast")
    slot = {"kind": "Main", "appears_in": [0], "recurring": True}
    slots = [
        slot | {"role": "Omar, the hero", "description": "Late-20s man, a line cook"},
        slot | {"role": "Friend, Omar's best friend", "description": "Late-20s man, a barber"},
    ]
    (tmp_path / f"{case['id']}.cast_slots.json").write_text(json.dumps({"slots": slots}))
    assert score(tmp_path, case) == [
        "Advice: no slot carries the name Waiter; use it in that role",
        "no slot for Waiter",
    ]


def test_one_person_is_one_slot_across_versions_in_the_eval(tmp_path):
    from evals.score import CASES, score

    case = next(c for c in CASES["cases"] if c["id"] == "fomo-kimchi-cast")
    one = {"description": "Mid-20s man, a barista", "kind": "Main", "recurring": True}
    slots = [
        one | {"role": "Nate, the hero", "appears_in": [0, 1]},
        one | {"role": "Kimchi, Nate's rich friend", "appears_in": [0, 1]},
    ]
    answer = tmp_path / f"{case['id']}.cast_slots.json"
    answer.write_text(json.dumps({"slots": slots}))
    assert score(tmp_path, case) == []  # "his friend with the supercar" is Kimchi
    twin = one | {"role": "His friend with the supercar", "appears_in": [1]}
    answer.write_text(json.dumps({"slots": [*slots, twin]}))
    assert score(tmp_path, case) == ["3 slots, expected at most 2"]


def test_cast_slots_example_passes_and_each_check_says_what_to_do():
    ex, result = example("cast_slots")
    versions = {
        int(n): "\n".join(line.split("| ", 1)[1] for line in body.splitlines())
        for n, body in re.findall(r'<version slot="(\d)">\n(.*?)\n</version>', ex["input"], re.S)
    }
    assert check.cast_slots(versions, result) == []
    assert check.cast_slots(versions, schemas.CastSlots(slots=[])) == ["no cast slots; regenerate"]
    no_friend = schemas.CastSlots(slots=result.slots[:2])  # a one-off who speaks is a role
    assert check.cast_slots(versions, no_friend) == [
        "Advice: no slot carries the name Dre; use it in that role"
    ]
    dre = result.slots[2]  # "his best friend" in the original is Dre: one person, one slot
    assert "Dre" not in versions[0] and 0 in dre.appears_in
    dre.may_be_same_as = "Aunt Tasha"  # a possible duplicate names another slot word for word
    assert check.cast_slots(versions, result) == [
        "Advice: Dre, Malik's best friend: may be the same as “Aunt Tasha”, which isn't another "
        "slot; name that slot's role word for word"
    ]
    dre.may_be_same_as = result.slots[1].role
    assert check.cast_slots(versions, result) == []
    extra = {"description": "30s man, a cook", "kind": "Helper", "recurring": False}
    result.slots += [
        schemas.CastSlot(role="Wedding guests", appears_in=[0], **extra),
        schemas.CastSlot(role="Malik, again", appears_in=[3], **extra),
    ]
    assert check.cast_slots(versions, result) == [
        "Advice: Wedding guests: sounds like background people, who are never cast",
        "Malik, again: version 3 doesn't exist; edit or regenerate",
        "Advice: two slots are called Malik; merge them",
    ]
    dre = schemas.CastSlots(
        slots=[schemas.CastSlot(role="Dre, the rival", appears_in=[0, 1], **extra)]
    )
    labels = {0: "DRE: Nice car.\nVOICEOVER: He won.\nNARRATOR (V.O.): Later.", 1: "DRE: Mine."}
    assert check.cast_slots(labels, dre) == []  # speaker labels aren't names
    assert check.cast_slots({0: "DRE: Nice car.", 1: "MALIK: Mine now."}, dre) == [
        "Advice: no slot carries the name Malik; use it in that role",
        "Advice: Dre, the rival: “Dre” isn't in version 1",
    ]


def test_quick_cut_check_is_advice_and_only_inside_a_montage_clip():
    _, bd = example("breakdown")
    _, cp = example("clip_prompts")  # clip c2 holds the montage
    c = cp.clips[0]
    c.prompt = c.prompt.replace("behind Malik as he walks", "as a hand pushes")
    flag = (
        "Advice: c2: shot 9: a quick cut names nobody (“a wide shot tracking in as a hand pushes”)"
    )
    assert flag in check.clip_prompts(bd, cp, 30, 10)
    for shot in bd.scenes[1].shots:  # slow the montage down: now it's not one
        shot.seconds = max(shot.seconds, 0.8)
    assert not [p for p in check.clip_prompts(bd, cp, 30, 10) if "names nobody" in p]


def test_an_adapted_draft_keeps_the_reels_lines_unless_new_lines_is_on():
    ex, result = example("script_draft")
    assert "<reference>" in ex["input"]
    path = Path(prompts.__file__).parents[3] / "docs/references/fomo-DehudnaAmce/BREAKDOWN.json"
    reel = list(dict.fromkeys(x["text"] for x in json.loads(path.read_text())["lines"]))
    for draft in result.drafts:
        assert check.reference_lines(draft.script, reel) == []
    swapped = result.drafts[0].script.replace("Sorry, I'm fully booked.", "Sorry, I'm busy.")
    assert check.reference_lines(swapped, reel) == [
        "Advice: the reel's line “Sorry, I'm fully booked.” is changed or missing"
    ]
    assert check.reference_lines(swapped, reel, new_lines=True) == []
    curly = "NATE: Sorry, I’m  fully booked."  # a phone's apostrophe and a double space
    assert check.reference_lines(curly, ["Sorry, I'm fully booked."]) == []
    # QA-Live run 3: the reel's lines are transcript chunks, cut across the script's lines,
    # in their own case and punctuation; kept words are never flagged.
    script = "NATE: Bro, you trade? Teach me!\nKIMCHI: Download fomo."
    assert check.reference_lines(script, ["bro you trade teach me", "Download fomo"]) == []
    assert check.reference_lines(script, ["bro you sell"]) != []


def test_a_redo_note_never_changes_what_is_said():
    _, bd = example("breakdown")  # c1: Tasha and Malik argue; c2 has one line, Malik's
    assert check.redo_note("Tasha should look angrier and lean in.", bd, "c1") == []
    assert check.redo_note('Say "Thirty days. Watch me." slower.', bd, "c1") == []
    assert check.redo_note('Tasha says "Give it back!"', bd, "c1") == [
        "The note quotes “Give it back!”, which nobody says in this clip. A note can change "
        "how a line is said, never its words."
    ]
    assert check.redo_note("Cut the line about groceries.", bd, "c1") == [
        "The note changes what's said. The spoken lines stay exactly as written; say how they "
        "should sound instead (louder, angrier, slower)."
    ]
    assert check.redo_note("Make Tasha shout at him here too.", bd, "c2") == [
        "Tasha has no line in this clip, so the note can't make them speak."
    ]
    for note in (  # QA on #276: notes about delivery or the shot, not the words
        "Please speak more slowly.",
        "Then speak louder.",
        "Cut to a closer shot on his last line.",
        "Add more energy to the lines.",
        "Change the lighting on his words.",
    ):
        assert check.redo_note(note, bd, "c1") == [], note


def test_nobody_speaks_unless_the_script_says_so():
    _, cp = example("clip_prompts")
    prompt = cp.clips[0].prompt
    assert check._silence(prompt, True) == []
    assert check._silence(prompt, False) == ["the audio line doesn't match whether anyone speaks"]
    montage = prompt.replace(
        "Shot 2 | 1-3 s. High-angle close-up, slow push in. Malik drops his head onto his arms "
        "in the blue glow, shoulders sagging, eyes shut. No one speaks.",
        "Shot 2 | 1-3 s. High-angle close-up. Malik stares at the loss and does not sell.",
    )
    assert check._silence(montage, True) == [
        "shot 2 has no line but doesn't say no one speaks",
        "shot 2: 'does not sell' reads like a line; show what the body does",
    ]
    calm = montage.replace(
        "stares at the loss and does not sell.", "stares; the dog does not move."
    )
    assert check._silence(calm, True) == ["shot 2 has no line but doesn't say no one speaks"]
    _, result = example("improve")
    quiet = result.prompt.replace("Audio: only the spoken lines and", check.SILENT.rstrip())
    assert check.AUDIO_LINE.match(quiet.splitlines()[0])
    assert check._silence(quiet, False) == []
    assert check._silence(quiet, True) == ["the audio line doesn't match whether anyone speaks"]


def test_shot_times_take_a_hyphen_or_an_en_dash():
    _, cp = example("clip_prompts")
    prompt = cp.clips[0].prompt
    assert "| 0-1 s." in prompt
    assert check._shape(prompt, 10) == check._shape(prompt.replace("-", "–"), 10)
    assert check._shape(prompt, 10)[0] == []
    assert check._shape(prompt.replace("0-1 s.", "0\ty1 s."), 10)[0] == [
        "shot 1 has no times; write them like “0-2 s.”"
    ]
    # Reed's c4: whole seconds with no full stop are never "not whole seconds" (the real
    # reason instead), and decimals are.
    assert check._shape(prompt.replace("0-1 s.", "0-1 s"), 10)[0] == [
        "shot 1's times need a full stop after “s”, like “0-2 s.”"
    ]
    assert check._shape(prompt.replace("0-1 s.", "0-1.5 s."), 10)[0] == [
        "shot 1's times aren't whole seconds; write them like “0-2 s.”"
    ]
    last = re.findall(r"^Shot \d+ \| \d+[-–]\d+ s\.", prompt, re.M)[-1]
    empty = prompt.replace(last, f"{last}\nShot 99 | 10-10 s.")  # the live test's 12–12 s
    assert check._shape(empty, 10)[0] == [
        "has an empty last shot (10–10 s). Remove it or give it a length."
    ]


def test_eval_scoring_reads_clip_prompt_words_outside_the_dialogue(tmp_path):
    from evals.score import CASES, score

    ex, bd = example("breakdown")
    _, cp = example("clip_prompts")
    case = next(c for c in CASES["cases"] if c["id"] == "fomo-thanksgiving")
    case = case | {"id": "ex", "steps": ["breakdown", "clip_prompts"]}
    case |= {"expect": {"clip_absent": ["beanie", "watch"], "clip_present": ["brindle"]}}
    (tmp_path / "ex.script.txt").write_text(script_of(ex))
    (tmp_path / "ex.breakdown.json").write_text(bd.model_dump_json())
    (tmp_path / "ex.clip_prompts.json").write_text(cp.model_dump_json())
    assert score(tmp_path, case) == [
        "clip prompts say 'beanie' outside the dialogue",
        "clip prompts never say 'brindle'",
    ]


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
    added = {line for line in apply_all(script, []).splitlines()} ^ set(
        apply_all(script, result.suggestions).splitlines()
    )
    kept = [
        line for line in apply_all(script, result.suggestions).splitlines() if line not in added
    ]
    assert kept == script.splitlines()


def test_clip_prompt_checks_catch_music_and_aspect():
    _, bd = example("breakdown")
    _, cp = example("clip_prompts")
    clip = cp.clips[0]
    clip.prompt = clip.prompt.split("\n", 1)[1] + "\nStyle: 9:16."
    clip.references.append(schemas.Reference(kind="image", id="char:2", role="Tasha"))
    assert check.clip_prompts(logo_once(bd), cp, 30, 10) == [
        "c2: doesn't open and close with the same audio line",
        "c2: has no Keep line before the closing audio line",
        "c2: writes aspect or resolution (those are settings)",
    ]  # the cast's order is the server's (clip_prompts.with_cast), never a problem


def test_the_keep_line_holds_every_attached_characters_look():
    _, bd = example("breakdown")
    _, cp = example("clip_prompts")
    assert check.clip_prompts(logo_once(bd), cp, 30, 10) == []
    clip = cp.clips[0]
    clip.prompt = clip.prompt.replace("[Image2] is Malik.", "[Image2] is Malik. [Image7] is Tasha.")
    assert "Advice: c2: the Keep line doesn't name Tasha; give their look and outfit" in (
        check.clip_prompts(bd, cp, 30, 10)
    )
    assert "never the rival's black leather jacket" in prompts.system("clip_prompts")
    for step in ("breakdown", "storyboard", "clip_prompts"):  # a locked look plays the role
        assert "call them by the role's name everywhere" in prompts.system(step)


def test_storyboard_check_keeps_character_sheets_within_the_model_limit():
    frame = {"clip_id": "c1", "shot_id": "1.1", "prompt": "x"}
    frames = schemas.StoryboardFrames(
        frames=[frame | {"reference_ids": ["char:1", "char:2", "char:3", "place:1"]}]
    )
    assert check.storyboard(frames, 14, 4) == []
    assert check.storyboard(frames, 14, 2) == ["c1: more references than the image model keeps"]


def test_frames_and_clips_attach_every_character_in_the_shot():
    _, bd = example("breakdown")
    first = bd.scenes[0].shots[0]
    cast = first.character_ids
    frame = {"clip_id": "c1", "shot_id": first.id, "prompt": "x"}
    bare = schemas.StoryboardFrames(frames=[frame | {"reference_ids": ["place:1"]}])
    assert check.storyboard(bare, 14, 4, bd) == [
        f"c1: {', '.join(cast)} in the shot without a sheet"
    ]
    full = schemas.StoryboardFrames(frames=[frame | {"reference_ids": cast}])
    assert check.storyboard(full, 14, 4, bd) == []
    _, cp = example("clip_prompts")
    c = cp.clips[0]
    who = next(r.id for r in c.references if r.id.startswith("char:"))
    c.references = [r for r in c.references if r.id != who]
    problems = check.clip_prompts(bd, cp, 30, 10)  # the server attaches it (with_cast)
    assert not [p for p in problems if who in p]


def test_storyboard_check_warns_on_words_the_image_model_refuses():
    def frames(prompt):
        f = {"clip_id": "c1", "shot_id": "1.1", "prompt": prompt, "reference_ids": []}
        return schemas.StoryboardFrames(frames=[f])

    refused = "His chin on her lap, in black leggings, crusty eyes and a bloody paw."
    assert check.storyboard(frames(refused), 14, 4) == [
        "Advice: c1: the image model may refuse “bloody, leggings”; soften it or draw it as is"
    ]
    fine = "Crusty eyes, his chin on her lap; she pours the bowl, he laps it up, a pie crust."
    assert check.storyboard(frames(fine), 14, 4) == []


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
        '"Token chart up" screen, logo and layout exact. [Image5] is the Iron Paws bag, '
        "shown exactly."
    )


def test_every_spoken_line_names_its_language():
    """Reed: a Change this… take spoke another language (2026-10-27). seedance-2.5.md §3."""
    for step in ("clip_prompts", "improve"):
        assert 'Name (in English, how it\'s said): "words"' in prompts.system(step)
    assert "never translate a line or drop its quotes or its label" in prompts.system("change")
    _, cp = example("clip_prompts")
    _, improved = example("improve")
    assert checks.unlabelled(cp.clips[0].prompt) == checks.unlabelled(improved.prompt) == []
    bare = improved.prompt.replace("(in English, ", "(")
    assert checks.unlabelled(bare) == [
        "Advice: Maya, Leo: say each spoken line's language, e.g. Maya (in English, …)"
    ]


def test_short_lines_and_clock_times_in_dialogue_dont_trip_the_clip_checks():
    _, bd = example("breakdown")
    _, cp = example("clip_prompts")
    shots = bd.scenes[1].shots
    clip = cp.clips[0]
    clip.prompt = clip.prompt.replace('"Come on. One more."', '"No."')
    clip.prompt = clip.prompt.replace("eyes red.", 'eyes red. Malik: "Okay, I know. It\'s 3:15."')
    shots[2].line, shots[4].line = "No.", "Okay, I know. It's 3:15."
    assert check.clip_prompts(logo_once(bd), cp, 30, 10) == []
    clip.prompt = clip.prompt.replace("eyes red.", "eyes red, a wall clock reading 3:12.")
    assert check.clip_prompts(logo_once(bd), cp, 30, 10) == []  # a clock outside the dialogue too
    shots[1].line = "No."  # a line said twice on purpose, quoted twice
    clip.prompt = clip.prompt.replace("eyes shut.", 'eyes shut. Malik (muttering): "No."')
    assert check.clip_prompts(logo_once(bd), cp, 30, 10) == []


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
    gap = result.prompt.replace("Shot 2 | 2-4 s.", "Shot 2 | 3-4 s.")
    assert check.improve(idea, schemas.ImprovedPrompt(prompt=gap), refs, 4, 8) == [
        "shot 2 starts at 3 s. The shot before ends at 2 s."
    ]
    curly = idea.replace('"I bought it at six cents."', "“I bought it at six cents.”")
    assert check.improve(curly, result, refs, 4, 8) == []
    reworded = result.prompt.replace("six cents", "6 cents")
    assert check.improve(curly, schemas.ImprovedPrompt(prompt=reworded), refs, 4, 8) == [
        "the line “I bought it at six cents.” isn't there once, word for word"
    ]
    for changed in ("I BOUGHT IT AT SIX CENTS.", "I bought it at six cents!!!"):
        tweaked = result.prompt.replace("I bought it at six cents.", changed)
        assert check.improve(idea, schemas.ImprovedPrompt(prompt=tweaked), refs, 4, 8) == [
            "the line “I bought it at six cents.” isn't there once, word for word"
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
    clip.prompt = clip.prompt.replace("Shot 1 | 0-1 s.", "Shot 1 | 0-1.2 s.")
    assert check.clip_prompts(logo_once(bd), cp, 30, 10) == [
        "c2: has no Summary line",
        "c2: shot 1's times aren't whole seconds; write them like “0-2 s.”",
        "c2: doesn't name [Image1] the first frame",
    ]


def test_a_tagged_brand_screen_line_still_needs_a_screen_in_the_breakdown():
    from evals.run import apply_all

    ex, bd = example("breakdown")
    script = script_of(ex).replace(
        "★ fomo screen: Token chart down", "[Brand screen] ★ fomo screen: Token chart down"
    )
    bd.scenes[1].shots[0].screen_ids = []
    assert "line 9 is a ★ screen line but no shot shows a screen" in check.breakdown(
        script, bd, FOMO, 4, 30
    )
    _, result = example("enhance")
    assert "[Camera] " in apply_all(script_of(example("enhance")[0]), result.suggestions)


def test_reference_block_drops_live_action_and_brand_block_carries_the_end_line():
    ref = json.loads(
        (
            Path(prompts.__file__).parents[3] / "docs/references/fomo-DehudnaAmce/BREAKDOWN.json"
        ).read_text()
    )
    block = prompts.reference_block(ref)
    assert "Shots 44–50 (42.67–45.02 s) are live action: always removed" in block
    assert "real creator" not in block.lower()
    end = "Want to trade like me? Download fomo through the link in my bio."
    assert f"names the brand and where to find it): {end}" in prompts.brand_block(
        {"name": "fomo", "end_line": end}, []
    )


def test_eval_scoring_checks_reference_words_and_the_end_line(tmp_path):
    from evals.score import CASES, score

    case = next(c for c in CASES["cases"] if c["id"] == "fomo-adapt-altar")
    case = case | {"steps": ["script_draft"]}
    good = "NATE: I do.\nBRIDE: HELL NO!\nBRIDE: I'm marrying him!\nNATE: What?!\n" \
        "BRIDE: I can't wait to spend forever with you.\nBRIDE (V.O.): Forever with you.\n" \
        "BRIDE: Nate? Nate?\nBRIDE: Huh?!\nNATE: Sorry, I'm fully booked.\n" \
        "NATE: Want to trade like me? Download fomo through the link in my bio."  # fmt: skip
    drafts = [{"hook_idea": "x", "script": good}, {"hook_idea": "y", "script": good}]
    (tmp_path / "fomo-adapt-altar.script_draft.json").write_text(json.dumps({"drafts": drafts}))
    assert score(tmp_path, case) == []
    drafts[1]["script"] = good.replace("Sorry, I'm fully booked.", "Sorry, I'm booked.")
    drafts[1]["script"] = drafts[1]["script"].rsplit("\n", 1)[0]
    (tmp_path / "fomo-adapt-altar.script_draft.json").write_text(json.dumps({"drafts": drafts}))
    assert score(tmp_path, case) == [
        "draft 2: 25 spoken words, expected 35–65",
        "draft 2: Advice: the reel's line “Sorry, I'm fully booked.” is changed or missing",
        "draft 2: Advice: the last line doesn't mention the brand or where to find it",
    ]


def test_sheet_prompts_are_house_style_with_no_names_or_text():
    sheet = prompts.sheet_prompt("character", "17, red beanie, grey hoodie, headphones")
    assert sheet.startswith("Generate a character turnaround sheet")
    assert "a front view, a side view in profile and a back view" in sheet
    assert "all three views are always there" in sheet  # a live sheet came back without its side
    assert "never a child's" in sheet and "6 heads" not in sheet  # Lexi, an adult, came out a child
    assert "never one that resembles a famous film, TV, comic or game character" in sheet
    assert "Keep the person, not a famous character's signature" in prompts.sheet_prompt(
        "character", from_photo=True
    )  # Seedance refused 23 takes of a look that read as a famous goth character (10-27)
    assert "an original character, never one that resembles" in prompts.system("cast_slots")
    assert "No text" in sheet and sheet.endswith(
        "The character: 17, red beanie, grey hoodie, headphones"
    )
    photo = prompts.sheet_prompt("character", from_photo=True, change="make the beanie navy")
    assert "Image 1 is a photo of a real person. Keep their likeness" in photo
    assert photo.endswith("change only this from the last sheet: make the beanie navy")
    place = prompts.sheet_prompt("place", "a small bedroom with a desk and one window")
    assert "no people" in place and "{" not in place + photo and "9:16" not in place + sheet


def test_a_made_look_is_checked_against_its_role_and_redone_once():
    text = prompts.system("look_fit")
    assert text.startswith("# Step: Look fit") and "Be engaging" not in text  # no writer rules
    assert "**Three views:**" in text and "slightly large head" not in text  # live run #16
    msg = prompts.look_fit_input("Mid-40s woman, a teacher; cardigan.", role="Ms Lee, the teacher")
    assert (
        msg
        == "<character>Mid-40s woman, a teacher; cardigan.</character>\n<role>the teacher</role>"
    )
    fit = schemas.LookFit(fits=False, seen="girl of about 10", problem="Draw an adult woman.")
    assert prompts.look_fit_redo("Mid-40s woman, a teacher", fit) == (
        "The character must read clearly as: Mid-40s woman, a teacher. Draw an adult woman."
    )


def test_the_projects_product_is_a_required_asset_like_a_screen():
    product = {"id": 2, "name": "Peanut butter bag"}
    block = prompts.brand_block({"name": "Iron Paws"}, [], product)
    assert 'Required product: product:2 "Peanut butter bag"' in block
    assert "Moments: brand-mention, end, feeding, product" in block
    needs = prompts.required([], product)
    assert needs == {"product:2": prompts.PRODUCT_MOMENTS}
    script = "Bruno sniffs the bowl.\n★ Iron Paws product: Peanut butter bag — by the bowl"
    shot = {"id": "1.1", "script_lines": [1, 2], "speaker": None, "line": None, "action": "x",
            "reaction": None, "camera": "x", "seconds": 4.0, "character_ids": [],
            "place_id": None, "moment": "feeding", "screen_ids": []}  # fmt: skip
    bd = schemas.Breakdown(
        hook="x",
        scenes=[{"id": 1, "heading": "INT. KITCHEN", "look": "x", "shots": [shot]}],
        clips=[{"id": "c1", "shot_ids": ["1.1"], "seconds": 4, "seam": "end"}],
    )
    problems = check.breakdown(script, bd, needs, 4, 30)
    assert "Advice: shot 1.1: 'feeding' moment without its screen" in problems
    bd.scenes[0].shots[0].screen_ids = ["product:2"]
    assert check.breakdown(script, bd, needs, 4, 30) == []


def altar_reel():
    from evals.score import CASES, reel_inputs

    case = next(c for c in CASES["cases"] if c["id"] == "reel-import-altar")
    ex = json.loads((EXAMPLES / "reel_watch.json").read_text())
    return case, schemas.ReelWatch.model_validate(ex["output"]), *reel_inputs(case)


def test_reel_watch_example_passes_and_becomes_the_scripts_reference():
    _, watch, transcript, cuts = altar_reel()
    assert check.reel_watch(watch, cuts, transcript) == []
    ref = prompts.reference_block(prompts.watch_breakdown(watch, transcript, cuts))
    assert '| groom: "I do."' in ref and '| bride: "HELL NO!"' in ref
    assert "Shots 44–50 (42.67–45.02 s) are live action" in ref and "\n45. " not in ref
    assert "caption" not in ref  # on-screen text never reaches the writer
    text = prompts.watch_system()
    assert text.startswith("# Step: Reel watch") and '"title": "ReelWatch"' in text


def test_reel_watch_check_says_what_to_fix():
    _, watch, transcript, cuts = altar_reel()
    near = watch.model_copy(deep=True)
    near.shots[2].start, near.shots[2].end = 0.8, 1.1  # rounded by the model: still the cut
    assert check.reel_watch(near, cuts, transcript) == []
    assert prompts.watch_breakdown(near, transcript, cuts)["shots"][2]["start"] == 0.82
    bad = watch.model_copy(deep=True)
    del bad.shots[4]
    bad.speakers[1].speaker = "the bride (flashback)"
    bad.speakers[3] = schemas.WatchSpeaker(line=12, speaker="groom")
    bad.shots[0].live_action = True
    assert check.reel_watch(bad, cuts, transcript) == [
        "shot 5 isn't the cut list's (49 shots, 50 cuts); regenerate",
        "a speaker for line 12, which the transcript doesn't have",
        "Advice: no speaker for “What?!”; say who says it",
        "Advice: one person under 2 names (the bride (flashback), bride); use one",
        "Advice: “I do.” is in a live-action shot, so it's dropped",
    ]


def test_an_imported_reels_draft_brings_in_no_new_speakers():
    reel = ["groom", "bride", "groom"]
    end = "Want to trade like me? Download fomo through the link in my bio."
    draft = f"NATE: I do.\nBRIDE: HELL NO!\nBRIDE (V.O.): Forever with you.\nNATE: {end}"
    assert check.reel_speakers(draft, reel, ["Nate"], end, "fomo") == []
    assert check.reel_speakers(draft + f"\nCREATOR: {end}", reel, ["Nate"], end, "fomo") == []
    extra = draft + "\nPRIEST: You may kiss the bride."
    assert check.reel_speakers(extra, reel, ["Nate"], end, "fomo") == [
        "Advice: 3 people speak, the reel has 2; give Priest's lines back to who says them "
        "in the reel"
    ]


def test_eval_scores_a_reel_import_from_the_watch_to_the_cast(tmp_path):
    from evals.run import run_case
    from evals.score import score

    case, watch, _, _ = altar_reel()
    run_case(None, case, tmp_path, [], Decimal(0), dry=True)  # free: writes the watch prompt
    assert (
        "<transcript>\n1| 0.00–0.36 I do."
        in (tmp_path / "reel-import-altar.reel_watch.prompt.txt").read_text()
    )
    (tmp_path / "reel-import-altar.reel_watch.json").write_text(watch.model_dump_json())
    end = case["expect"]["end_line"]
    good = "\n".join([
        "GROOM: I do.", "BRIDE: HELL NO!", "BRIDE: I'm marrying him!", "GROOM: What?!",
        "BRIDE: I can't wait to spend forever with you.", "BRIDE (V.O.): Forever with you.",
        "BRIDE: Nate? Nate?", "BRIDE: Huh?!", "GROOM: Sorry, I'm fully booked.", f"GROOM: {end}",
    ])  # fmt: skip
    drafts = [{"hook_idea": "x", "script": good}, {"hook_idea": "y", "script": good}]
    (tmp_path / "reel-import-altar.script_draft.json").write_text(json.dumps({"drafts": drafts}))
    slots = [{"role": r, "description": "30s man", "kind": k, "appears_in": [0], "recurring": True}
             for r, k in [("Groom", "Main"), ("Bride", "Main")]]  # fmt: skip
    (tmp_path / "reel-import-altar.cast_slots.json").write_text(json.dumps({"slots": slots}))
    assert score(tmp_path, case) == []
    watch.shots[44].live_action = False
    drafts[1]["script"] = good.replace("GROOM: What?!", "PRIEST: What?!")
    (tmp_path / "reel-import-altar.reel_watch.json").write_text(watch.model_dump_json())
    (tmp_path / "reel-import-altar.script_draft.json").write_text(json.dumps({"drafts": drafts}))
    assert score(tmp_path, case) == [
        "live-action shots [44, 46, 47, 48, 49, 50], expected [44, 45, 46, 47, 48, 49, 50]",
        "draft 2: Advice: 3 people speak, the reel has 2; give Priest's lines back to who says "
        "them in the reel",
    ]


def test_the_keep_line_names_the_face_and_a_visible_hair_cue():
    text = prompts.system("clip_prompts")  # Nate drifted heavier in a cap (altar v3, 2026-10-25)
    assert "same face shape, skin tone, age and build" in text
    assert "keep a cue of it visible" in text


def test_money_on_trading_screens_only_climbs():
    assert "**Money climbs.**" in prompts.system("script_draft")  # imported reels too
    _, bd = example("breakdown")
    shots = {s.id: s for scene in bd.scenes for s in scene.shots}
    shots["2.7"].action = "Malik at the desk; the balance reads $380."  # below +$420
    shots["2.4"].moment, shots["2.4"].action = "trading", "The token rockets up."
    problems = [p for p in check.breakdown(script_of(example("breakdown")[0]), bd, FOMO, 4, 30)
                if "$" in p or "reads" in p]  # fmt: skip
    assert problems == [
        "Advice: shot 2.4: say what the trading screen reads (e.g. “the balance reads $1,240”), "
        "bigger than the shot before"
    ]
    shots["2.4"].action = "The token rockets up: the balance reads $420."
    assert check._money_climbs(list(shots.values())) == [
        "Advice: shot 2.7: the screen reads $380, less than shot 2.4; the money only climbs"
    ]
    shots["2.4"].action = "A red tick first: the position reads −$80, then it turns."  # a loss
    shots["2.7"].action = "Malik at the desk; the position reads +$40 on a $12,400 balance."
    shots["3.2"].action = "Malik's phone slides to Tasha; the balance reads $348k."
    assert check._money_climbs(list(shots.values())) == []  # gains and balances apart
    shots["2.4"].action = "The token rockets up: the position reads +$420 (+38%)."
    shots["3.2"].action = "Malik's phone slides across the counter to Tasha."  # no payoff figure
    shots["3.6"].action = "Tasha holds the phone up in both hands."
    shots["2.7"].action = "Malik at the desk; the balance reads $12,400."
    shots["2.4"].moment = "win"
    assert check._money_climbs(list(shots.values())) == [
        "Advice: shot 2.7: the payoff reads under $100,000; make it clearly large (six figures "
        "or more)"
    ]
    _, cp = example("clip_prompts")
    assert check.clip_prompts(logo_once(bd), cp, 30, 10) == []  # the clip says what its shot says
    shots["2.7"].action = "Malik at the desk; the balance reads $12,900."
    assert check.clip_prompts(logo_once(bd), cp, 30, 10) == []  # Reed #600: numbers are free


def test_a_montages_invented_trading_screens_climb():
    _, bd = example("breakdown")
    _, cp = example("clip_prompts")  # c2: -$380, then +$420, then +$48,000
    clip = cp.clips[0]
    assert "[Image4] is the fomo logo: the word fomo in lowercase." in clip.prompt
    assert clip.prompt.count("an invented trading screen in the fomo style") == 3
    assert "layout exactly" not in clip.prompt  # never for an invented screen (rule 14)
    clip.prompt = clip.prompt.replace("+$48,000", "+$300")
    assert check.clip_prompts(logo_once(bd), cp, 30, 10) == [
        "Advice: c2: shot 7's trading screen reads +$300, not more than shot 4's; make each win "
        "bigger"
    ]
    clip.prompt = clip.prompt.replace("+$300", "-$300")  # a red day is a dip, never flagged
    assert check.clip_prompts(bd, cp, 30, 10) == []
    for step in ("clip_prompts", "storyboard", "improve"):
        assert "invented trading screen" in prompts.system(step), step
    assert "the fomo logo from [ImageN], the word fomo in lowercase" in prompts.system("change")


def test_invented_screens_spell_the_logo_and_scenes_stay_original():
    _, cp = example("clip_prompts")  # QA-Live, video #17: "JOMO", or the icon alone
    word = "the fomo logo from [Image4], the word fomo in lowercase, sharp and legible"
    assert cp.clips[0].prompt.count(word) == 3
    assert "with the word “fomo” in lowercase letters" in prompts.system("storyboard")  # quoted
    for step in ("clip_prompts", "improve"):  # Seedance: quotes are speech, so no quotes
        assert "the word fomo in lowercase" in prompts.system(step), step
    for step in ("breakdown", "storyboard", "clip_prompts", "improve"):  # clip 7's Up-like scene
        assert "never recreate a famous film, TV, comic or game scene" in prompts.system(step)


def test_a_frames_only_watch_says_so_and_keeps_the_cuts_and_words():
    _, _, transcript, cuts = altar_reel()
    text = prompts.reel_watch_input(transcript, cuts, frames_only=True)
    assert text.startswith("<watched_from>frames</watched_from>\n<cuts>\n1. 0.00–0.40")
    assert text.split("\n", 1)[1] == prompts.reel_watch_input(transcript, cuts)
    assert "**Frames only.**" in prompts.watch_system()
    assert "**A correction.**" in prompts.watch_system()  # Read it again (reel-import §5)
    assert "each row is one shot from <cuts>" in prompts.watch_system()
    assert "corner label gives its shot number and time" in prompts.watch_system()  # #304's grids


def test_an_adapted_montage_keeps_the_references_length():
    ref = json.loads(
        (Path(__file__).parents[2] / "docs/references/fomo-DehudnaAmce/BREAKDOWN.json").read_text()
    )
    assert "(11.7 s): keep about this length" in prompts.reference_block(ref)
    _, watch, transcript, cuts = altar_reel()  # an imported reel's montage says so too
    assert "(11.7 s): keep" in prompts.reference_block(
        prompts.watch_breakdown(watch, transcript, cuts)
    )
    assert "the montage runs about as long as its montage" in prompts.system("breakdown")


def test_a_role_says_its_age_gender_and_job_and_its_sheet_fits_the_part():
    slot = {"kind": "Main", "appears_in": [0], "recurring": True}
    result = schemas.CastSlots(slots=[
        {**slot, "role": "Ms Lee, the teacher", "description": "Kind, round glasses, a cardigan."},
        {**slot, "role": "Omar, the boyfriend", "description": "20s man, an office worker",
         "guessed": ["occupation"]},
    ])  # fmt: skip
    assert check.cast_slots({0: "MS LEE: Hi.\nOMAR: Hey."}, result) == [
        "Advice: Ms Lee, the teacher: the description doesn't say their age or gender"
    ]
    text = prompts.sheet_prompt(
        "character", "20s man, an office worker", role="Omar, the boyfriend"
    )
    assert "In the story they are the boyfriend; the age, gender and look fit that part." in text
    assert "Omar" not in text  # names are never drawn
    assert "starts with who they are: an age range, a gender and a role or job" in (
        prompts.system("cast_slots")
    )


def test_the_grind_shows_trading_and_phone_beats_play_for_drama():
    # Reed, after video #17: no tapping in fomo, and phones held up flat to the viewer
    assert "**Show the trading.** For a trading app (fomo)" in prompts.system("breakdown")
    for step in ("breakdown", "clip_prompts", "storyboard"):
        assert "a phone held up flat to" in prompts.system(step), step
        assert "screen's glow" in prompts.system(step), step
    assert "for a trading app, the trading itself" in prompts.system("script_draft")
    _, cp = example("clip_prompts")
    assert "Malik's thumb scrolls the coin list and taps Buy" in cp.clips[0].prompt


def test_the_app_bridge_is_only_for_an_app_brand():
    # Producer, before Reed's Iron Paws video: no "opening the app" beat for a bag brand
    for step in ("breakdown", "script_draft", "variations"):
        text = prompts.system(step)
        for at in [m.start() for m in re.finditer(r"opening the app|the app being opened", text)]:
            assert "app brand" in text[max(at - 160, 0) : at], step


def test_the_closing_call_to_action_only_has_to_name_the_brand():
    """Current rules 18 (Reed, 2026-10-28): the saved end line is the default wording; any
    closing line that names the brand passes, and a miss is Advice, never a block."""
    ex, bd = example("breakdown")
    script = script_of(ex)
    end = "Want to trade like me? Download fomo through the link in my bio."
    note = "Advice: the last line doesn't mention the brand or where to find it"

    def ending(last, brand="fomo"):
        found = script.replace(f"MALIK: {end}", last)
        return [p for p in check.breakdown(found, bd, FOMO, 4, 30, end, brand) if "last line" in p]

    assert ending(f"MALIK: {end}") == []
    assert ending("MALIK: Want to glow up like me? Get FOMO, link in my bio!") == []  # adapted
    assert ending("MALIK: Download Robinhood, link in bio.") == [note]  # another app: advice
    assert ending("MALIK: Get the app, link in bio.") == [note]
    assert ending("MALIK: Sorry, I'm fully booked.", brand="") == [note]
    assert not check.says_brand("NATE: My fomofriend.", "fomo")  # whole words only
    assert ending("MALIK: Bye.") == [note]
    other = script.replace(f"MALIK: {end}", "MALIK: Bye.")  # a brand with no end line: no note
    assert not [p for p in check.breakdown(other, bd, FOMO, 4, 30) if "last line" in p]
    cta = next(s for s in bd.scenes[2].shots if s.line == end)  # Reed, 2026-10-27
    cta.screen_ids = []
    assert (
        "Advice: shot 3.6: the end line's shot shows no screen; show the brand's real screen "
        "on the phone he holds up to the camera"
    ) in check.breakdown(script, bd, FOMO, 4, 30, end, "fomo")
    assert "approved" not in inspect.signature(check.breakdown).parameters


def test_pacing_is_by_purpose_and_scenes_hand_off():
    """Reed, 2026-10-28: no fixed timings in the creative guidance (rigid structure ruins
    creativity); quick cuts to whoever talks, wide for a reaction or action, holds that land,
    and scenes that end on a beat the next one answers. Brand-generic (the dog)."""
    for step in ("breakdown", "clip_prompts", "script_draft", "variations", "enhance", "improve"):
        text = prompts.system(step)
        for gone in (
            "once a second",
            "median shot",
            "about 12 s",
            "12 shots",
            "over 3 s",
            "3–5 s",
            "about 0.8 s",
            "about 0.4 s",
            "half a second",
            "fewer, longer",
        ):
            assert gone not in text, (step, gone)
    bd = prompts.system("breakdown")
    assert "Pace by purpose, never by the clock" in bd and "go wide when a reaction" in bd
    assert "for as long as it needs, up to the video model's max" in bd
    assert "**Endings flow.**" in bd and "the dog's ears dropping" in bd
    assert "The clip's last line never ends in its last moments" in prompts.system("clip_prompts")
    assert "**Scenes flow.**" in prompts.system("script_draft")
    assert "The hand-off" in schemas.Clip.model_fields["seam"].description
    assert not hasattr(check, "CLIP_S")


def test_no_numeric_rhythm_rules_are_left():
    """Rule 29 (Reed, 2026-10-28): rhythm is described by purpose (QA on #686)."""
    for step in ("breakdown", "script_draft"):
        text = prompts.system(step)
        for gone in ("every 1–3 s", "about 2 s of the real brand element", "by about 5 s"):
            assert gone not in text, (step, gone)


def test_a_camera_swap_is_staged_as_one():
    """Reed, QA-Live Run 3: the double CTA's camera swap read as a cut, not a flip."""
    assert "a whip pan or a flip into a front-facing selfie angle" in prompts.system("breakdown")
    clip = prompts.system("clip_prompts")
    assert "Whip pan into a front-facing selfie angle" in clip
    assert "never a plain cut to him holding the phone up" in clip
    assert "the bag for a product brand" in prompts.system("breakdown")  # brand-generic


def test_the_story_agrees_with_the_real_balance_and_variations_take_a_length():
    """QA-Live Run 3: the real Home screen's $348,920.15 at the CTA against a story that said
    $14,800; and "about 45 s" in a variations note came out at 60 s."""
    for step in ("script_draft", "breakdown", "variations"):
        assert "climb toward that balance" in prompts.system(step), step
    assert "never a different one the real screen would contradict" in prompts.system("breakdown")
    v = prompts.system("variations")
    assert "**Same size, unless asked.**" in v and "that length wins" in v


def test_a_requested_length_is_what_the_variations_length_advice_checks():
    original, result, end = _variation_case()
    v = result.variations[0]
    words = check.spoken_words(v.script)
    assert check.asked_seconds("Make it about 45 s, punchier") == 45
    assert check.asked_seconds("a 1 minute cut") == 60 and check.asked_seconds("funnier") is None
    assert check.asked_seconds("about 1.5 minutes") == 90  # QA on #700
    assert check.asked_seconds("a 90s style, funnier") is None
    assert check.asked_seconds("keep the 10 s montage but make it 30 seconds") == 30
    assert check.asked_seconds("make it 45s") == 45
    fits = round(words / 2)  # seconds this variation's words fit
    ok = check.variations(original, result, {}, end, [], 1, [], "fomo", note=f"about {fits} s")
    assert not [p for p in ok if "spoken words" in p or "words in all" in p]
    short = check.variations(original, result, {}, end, [], 1, [], "fomo", note="about 10 s")
    assert f"Advice: variation 1 has {words} spoken words; about 17–25 fit the 10 s asked for" in (
        short
    )


def test_c4s_shape_is_put_right_in_code_with_its_words_unchanged():
    """Reed's Iron Paws c4 (24 s): "Shot 18 | 18-23 s in the gut…" had no full stop and
    overlapped shot 17 (19-21 s), a shot ran 12.5-14 s, and the closing audio line didn't
    match the opening one. All of it is mechanical: repaired in code, free, no Claude call,
    and no other word changes."""
    from app.clip_prompts import repair_shape

    _, bd = example("breakdown")
    _, cp = example("clip_prompts")
    clip = cp.clips[0]
    planned = next(c for c in bd.clips if c.id == clip.clip_id)
    lines = clip.prompt.splitlines()
    shots = [i for i, x in enumerate(lines) if x.startswith("Shot ")]
    first, second = shots[0], shots[1]
    lines[first] = re.sub(r"\| \d+-\d+ s\.", "| 0-1.5 s.", lines[first])  # a decimal
    lines[second] = re.sub(r"\| \d+-\d+ s\.", "| 0-2 s", lines[second])  # overlap, no stop
    lines[-1] = lines[0].replace("No subtitles.", "Quiet. No subtitles.")  # closing differs
    broken = clip.model_copy(update={"prompt": "\n".join(lines)})
    assert len(check._shape(broken.prompt, planned.seconds)[0]) == 2
    fixed = repair_shape(broken, bd)
    assert check._shape(fixed.prompt, planned.seconds)[0] == []
    words = lambda p: re.sub(r"^Shot (\d+) \| [^ ]+ ?s\b\.?", r"Shot \1", p, flags=re.M)  # noqa: E731
    assert words(fixed.prompt).splitlines()[1:-1] == words(broken.prompt).splitlines()[1:-1]


def test_the_free_fix_never_drops_a_lip_sync_note():
    """Reed's c4: Fix this clip's prompt dropped "nobody on screen lip-syncs it", which
    invites lip-sync. It's put back before the Keep line."""
    from app.clip_prompts import _kept_voiceover

    _, cp = example("clip_prompts")
    clip = cp.clips[0]
    note = "The voiceover is Biscuit's narration; nobody on screen lip-syncs it."
    lines = clip.prompt.splitlines()
    before = "\n".join([*lines[:-2], note, *lines[-2:]])
    back = _kept_voiceover(clip, before).prompt.splitlines()
    assert back[-3:] == [note, *lines[-2:]] and _kept_voiceover(clip, clip.prompt) == clip


def test_a_summary_quoting_a_line_doesnt_count_it_twice():
    """QA-Live run 3, clip 4: "Teach me!" was in its shot and quoted in the Summary line, so
    "the line isn't there once" blocked a correct prompt."""
    _, bd = example("breakdown")
    _, cp = example("clip_prompts")
    clip = cp.clips[0]
    line = next(s.line for sc in bd.scenes for s in sc.shots if s.line and s.id in
                next(c.shot_ids for c in bd.clips if c.id == clip.clip_id))  # fmt: skip
    lines = clip.prompt.splitlines()
    at = next(i for i, x in enumerate(lines) if x.startswith("Summary: "))
    lines[at] += f' It ends on "{line}"'
    clip.prompt = "\n".join(lines)
    assert not [p for p in check.clip_prompts(logo_once(bd), cp, 30, 10) if "isn't there" in p]
