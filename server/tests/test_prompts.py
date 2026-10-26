import json
import re
from decimal import Decimal
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


def test_a_screen_that_prints_a_balance_gives_the_payoff_its_number():
    rich = {"id": 5, "name": "Home (rich)", "tags": ["home"], "default_for": ["win"],
            "balance": "$348,920.15"}  # fmt: skip
    block = prompts.brand_block({"name": "fomo"}, [rich])
    assert 'screen:5 "Home (rich)" (home), shows a balance of $348,920.15' in block
    for step in ("breakdown", "script_draft", "clip_prompts"):
        assert "shows a balance" in prompts.system(step)


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
    empty = prompt.replace("behind Malik as he pushes open", "as a hand pushes open")
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
    assert check.variations(original, result, {}, end, ["can't lose"], 1, cast) == []
    v = result.variations[0]
    v.script = v.script.replace("★ fomo screen: Token chart down — on Malik's phone\n", "")
    v.script = v.script.rsplit("\n", 1)[0] + "\nMALIK: You can't lose. Live-action tag here."
    assert check.variations(original, result, {}, end, ["can't lose"], 2, cast) == [
        "1 variations, 2 asked for; regenerate",
        "Advice: variation 1 doesn't end on the brand's end line",  # made from approved words
        "variation 1 drops the ★ line for Token chart down; put it back where it fits",
        "variation 1 says “can't lose”, which the brand never says",
        "variation 1 brings back live action; that slot is the end line",
    ]


def test_variations_end_line_ignores_case_and_a_near_miss_is_advice():
    original, result, end = _variation_case()
    v = result.variations[0]
    body = v.script.rsplit("\n", 1)[0]
    v.script = body + "\nMALIK: WANT TO TRADE LIKE ME? DOWNLOAD FOMO THROUGH THE LINK IN MY BIO"

    def ends(script):
        v.script = script
        found = check.variations(original, result, {}, end, [], 1, brand="fomo")
        return [p for p in found if "end line" in p]

    assert ends(v.script) == []
    assert ends(body + "\nMALIK: Want to trade like me? Get FOMO through the link in my bio.") == [
        "Advice: variation 1's last line is close to the brand's end line, not word for word"
    ]
    rival = "\nMALIK: Want to trade like me? Download Robinhood through the link in my bio."
    assert ends(body + rival) == [  # from an approved original: advice, never a block
        "Advice: variation 1 doesn't end on the brand's end line"
    ]


def test_on_approved_words_the_end_line_never_blocks():
    """Reed: once he approved the script, the end line is advice at most, any wording."""
    ex, bd = example("breakdown")
    end = "Want to trade like me? Download fomo through the link in my bio."
    tag = "★ fomo screen: Home — closing tag"
    script = script_of(ex).replace(tag, f"MALIK: Get the app, link in bio.\n{tag}")
    approved = check.breakdown(script, bd, FOMO, 4, 30, end_line=end, brand="fomo", approved=True)
    draft = check.breakdown(script, bd, FOMO, 4, 30, end_line=end, brand="fomo")
    assert "Advice: the script doesn't end on the brand's end line" in approved
    assert "the script doesn't end on the brand's end line" not in approved
    assert "the script doesn't end on the brand's end line" in draft  # still blocks a draft


def test_variations_advice_covers_length_closeness_and_format():
    original, result, end = _variation_case()
    v = result.variations[0]
    v.script = original.replace("TASHA", "ROSE").replace("Tasha", "Rose")  # Tasha is gone
    problems = check.variations(original, result, {}, end, [], 1, ["Malik", "Tasha", "Bruno"])
    assert problems == [
        "variation 1 drops Tasha, a locked character",  # Bruno isn't in the original: no flag
        "Advice: variation 1 is very close to the original; regenerate with a note",
    ]
    v.script = "# The sneakers\n" + "MALIK: Hi.\n" + end.join(["MALIK: ", ""])
    assert check.variations(original, result, {}, end, [], 1, []) == [
        "variation 1 drops the ★ line for Home (rich); put it back where it fits",
        "variation 1 drops the ★ line for Token chart down; put it back where it fits",
        "variation 1 drops the ★ line for Token chart up; put it back where it fits",
        "Advice: variation 1 has 14 spoken words, the original 54",
        "Advice: variation 1 runs 19 words in all, the original 195",
        "Advice: variation 1 is very close to the original; regenerate with a note",
        "Advice: variation 1: “# The sneakers” isn't house format",
    ]


def test_an_echo_repeats_what_was_said_to_his_face():
    said = "GIRLFRIEND: You're just a loser who doesn't get invited to anything.\n"
    assert check.echo_lines(said + "GIRLFRIEND (V.O.): Doesn't get invited to anything.") == []
    assert check.echo_lines(said + "GIRLFRIEND (V.O.): New position can't afford a ticket.") == [
        "Advice: the echo “New position can't afford a ticket.” calls back to nothing "
        "Girlfriend said; repeat “You're just a loser who doesn't get invited to anything.”"
    ]
    assert check.echo_lines("BRUNO (V.O.): I was the worst dog on the street.") == []  # narrator
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


def test_cast_slots_example_passes_and_each_check_says_what_to_do():
    ex, result = example("cast_slots")
    versions = {
        int(n): "\n".join(line.split("| ", 1)[1] for line in body.splitlines())
        for n, body in re.findall(r'<version slot="(\d)">\n(.*?)\n</version>', ex["input"], re.S)
    }
    assert check.cast_slots(versions, result) == []
    assert check.cast_slots(versions, schemas.CastSlots(slots=[])) == ["no cast slots; regenerate"]
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
    c.prompt = c.prompt.replace("behind Malik as he pushes open", "as a hand pushes open")
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


def test_clip_prompt_checks_catch_music_aspect_and_cast_order():
    _, bd = example("breakdown")
    _, cp = example("clip_prompts")
    clip = cp.clips[0]
    clip.prompt = clip.prompt.split("\n", 1)[1] + "\nStyle: 9:16."
    clip.references.append(schemas.Reference(kind="image", id="char:2", role="Tasha"))
    assert check.clip_prompts(bd, cp, 30, 10) == [
        "c2: doesn't open and close with the same audio line",
        "c2: has no Keep line before the closing audio line",
        "c2: writes aspect or resolution (those are settings)",
        "c2: characters aren't attached in the order they appear",
    ]


def test_the_keep_line_holds_every_attached_characters_look():
    _, bd = example("breakdown")
    _, cp = example("clip_prompts")
    assert check.clip_prompts(bd, cp, 30, 10) == []
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
    problems = check.clip_prompts(bd, cp, 30, 10)
    assert f"{c.clip_id}: {who} is in the clip but its sheet isn't attached" in problems


def test_storyboard_check_warns_on_words_the_image_model_refuses():
    def frames(prompt):
        f = {"clip_id": "c1", "shot_id": "1.1", "prompt": prompt, "reference_ids": []}
        return schemas.StoryboardFrames(frames=[f])

    refused = "His chin on her lap, in black leggings, crusty eyes and a bloody paw."
    assert check.storyboard(frames(refused), 14, 4) == [
        "c1: the image model may refuse “bloody, crusty, lap, leggings”; say it gently"
    ]
    fine = "Beside her on a wet street: faint tear stains, a pink sore paw; she drops to her knees."
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


def test_short_lines_and_clock_times_in_dialogue_dont_trip_the_clip_checks():
    _, bd = example("breakdown")
    _, cp = example("clip_prompts")
    shots = bd.scenes[1].shots
    clip = cp.clips[0]
    clip.prompt = clip.prompt.replace('"Come on. One more."', '"No."')
    clip.prompt = clip.prompt.replace("eyes red.", 'eyes red. Malik: "Okay, I know. It\'s 3:15."')
    shots[2].line, shots[4].line = "No.", "Okay, I know. It's 3:15."
    assert check.clip_prompts(bd, cp, 30, 10) == []
    clip.prompt = clip.prompt.replace("eyes red.", "eyes red, a wall clock reading 3:12.")
    assert check.clip_prompts(bd, cp, 30, 10) == []  # a clock outside the dialogue too
    shots[1].line = "No."  # a line said twice on purpose, quoted twice
    clip.prompt = clip.prompt.replace("eyes shut.", 'eyes shut. Malik (muttering): "No."')
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
    assert check.clip_prompts(bd, cp, 30, 10) == [
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
    assert f"End line (every video ends on it, word for word): {end}" in prompts.brand_block(
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
        "draft 2: doesn't end on the brand's end line",
    ]


def test_breakdown_check_wants_the_script_to_end_on_the_brands_end_line():
    ex, bd = example("breakdown")
    script = script_of(ex)
    end = "Want to trade like me? Download fomo through the link in my bio."
    assert check.breakdown(script, bd, FOMO, 4, 30, end_line=end) == [
        "the script doesn't end on the brand's end line"
    ]
    ended = script.replace(
        "★ fomo screen: Home — closing tag", f"MALIK: {end}\n★ fomo screen: Home — closing tag"
    )
    assert "the script doesn't end on the brand's end line" not in check.breakdown(
        ended, bd, FOMO, 4, 30, end_line=end
    )


def test_the_end_line_ignores_case_and_punctuation_and_a_near_miss_is_advice():
    """Reed: "Marriage Rejection" ends on fomo's end line with FOMO in caps; never blocked."""
    end = "Want to trade like me? Download fomo through the link in my bio."
    caps = "NATE: Want to trade like me?! Download FOMO through the link in my bio"
    curly = "NATE: “Want to trade like me… download fomo, through the link in my bio!”"
    near = "NATE: Want to trade like me? Get fomo through the link in my bio."
    other = "NATE: Sorry, I'm fully booked."
    assert [check.ends_on(end, x, "fomo") for x in (caps, curly, near, other)] == [
        "yes", "yes", "near", "no"
    ]  # fmt: skip
    assert check.ends_on(end, "NATE: ... in my biology", "fomo") != "yes"  # whole words only
    assert check.ends_on("", other) == "yes"  # a brand with no end line
    # QA #393: a near miss must still name the brand, or it blocks as before
    rival = "NATE: Want to trade like me? Download Robinhood through the link in my bio."
    vague = "NATE: Want to trade like me? Download the app through the link in my bio."
    assert check.ends_on(end, rival, "fomo") == check.ends_on(end, vague, "fomo") == "no"
    assert check.ends_on(end, near, "") == "no"  # no brand name to check: blocks
    # The end line split over the last two lines, its last part with FOMO in caps
    split = ("NATE: Want to trade like me?", "NATE: Download FOMO through the link in my bio!")
    assert check.ends_on(end, split[1], "fomo", before=split[0]) == "yes"
    # Reed: a near match never blocks. Half the end line's words and the brand: Advice
    assert check.ends_on(end, split[1], "fomo") == "near"
    assert check.ends_on(end, split[1], "fomo", before="NATE: Sorry.") == "near"
    assert check.ends_on(end, "NATE: Get FOMO in my bio.", "fomo") == "no"  # under half
    assert check.ends_on(end, "BRIDE: Huh?!", "fomo", before=caps) == "no"  # not the last line

    ex, bd = example("breakdown")
    script = script_of(ex)

    tag = "★ fomo screen: Home — closing tag"

    def ending(last):
        found = script.replace(tag, f"{last}\n{tag}")
        return check.breakdown(found, bd, FOMO, 4, 30, end_line=end, brand="fomo")

    assert not [p for p in ending(caps) if "end line" in p]  # passes cleanly
    assert not [p for p in ending(curly) if "end line" in p]
    advice = [p for p in ending(near) if "end line" in p]
    assert advice == [
        "Advice: the last line is close to the brand's end line but not word for word"
    ]
    assert "the script doesn't end on the brand's end line" in ending(other)  # still blocks
    assert "the script doesn't end on the brand's end line" in ending(rival)  # another app
    assert not [p for p in ending("\n".join(split)) if "end line" in p]  # split, caps
    assert [p for p in ending(split[1]) if "end line" in p] == [  # Reed's exact line, alone
        "Advice: the last line is close to the brand's end line but not word for word"
    ]


def test_sheet_prompts_are_house_style_with_no_names_or_text():
    sheet = prompts.sheet_prompt("character", "17, red beanie, grey hoodie, headphones")
    assert sheet.startswith("Generate a character turnaround sheet")
    assert "front view, full body side view and full body back view" in sheet
    assert "No text" in sheet and sheet.endswith(
        "The character: 17, red beanie, grey hoodie, headphones"
    )
    photo = prompts.sheet_prompt("character", from_photo=True, change="make the beanie navy")
    assert "Image 1 is a photo of a real person. Keep their likeness" in photo
    assert photo.endswith("except this change from the last sheet: make the beanie navy")
    place = prompts.sheet_prompt("place", "a small bedroom with a desk and one window")
    assert "no people" in place and "{" not in place + photo and "9:16" not in place + sheet


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
    assert "shot 1.1: 'feeding' moment without its screen" in problems
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
    assert check.reel_speakers(draft, reel, ["Nate"], end) == []
    assert check.reel_speakers(draft + f"\nCREATOR: {end}", reel, ["Nate"], end) == []
    extra = draft + "\nPRIEST: You may kiss the bride."
    assert check.reel_speakers(extra, reel, ["Nate"], end) == [
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
    shots["2.7"].action = "Malik at the desk; the balance reads $12,400."
    shots["2.4"].moment = "win"
    assert check._money_climbs(list(shots.values())) == [
        "Advice: shot 2.7: the payoff reads under $100,000; make it clearly large (six figures "
        "or more)"
    ]
    _, cp = example("clip_prompts")
    assert check.clip_prompts(bd, cp, 30, 10) == []  # the clip says what its shot says
    shots["2.7"].action = "Malik at the desk; the balance reads $12,900."
    assert check.clip_prompts(bd, cp, 30, 10) == [
        "Advice: c2: shot 2.7's screen should read $12,900"
    ]


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
