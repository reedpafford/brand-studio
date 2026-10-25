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


def test_no_prompt_file_keeps_a_merge_conflict_marker():
    for path in (EXAMPLES.parent).rglob("*"):
        if path.is_file() and path.suffix in {".md", ".json", ".py"}:
            text = path.read_text()
            assert not re.search(r"^(<{7}|={7}|>{7})( |$)", text, re.M), path


def test_breakdown_check_wants_the_main_character_in_every_montage_shot():
    ex, bd = example("breakdown")
    script = script_of(ex)
    assert check.breakdown(script, bd, FOMO, 4, 30) == []
    shot = next(s for s in bd.scenes[1].shots if s.id == "2.7")
    shot.character_ids = []
    assert check.breakdown(script, bd, FOMO, 4, 30) == [
        "Advice: shot 2.7: a montage shot without the main character"
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
        "shot 6: a quick cut names nobody (“a wide shot tracking in as a hand pushes”)"
    ]
    refs = next(line for line in empty.splitlines() if line.startswith("References: "))
    no_cast = empty.replace(refs, "References: [Image1] is the first frame.")
    assert check._cuts_name_someone(no_cast) == []


def test_breakdown_check_keeps_a_clip_to_three_screens():
    ex, bd = example("breakdown")
    script = script_of(ex)
    shot = next(s for s in bd.scenes[1].shots if s.id == "2.12")
    shot.screen_ids = ["screen:1"]
    assert check.breakdown(script, bd, FOMO, 4, 30) == [
        "clip c2: 4 screens; keep the 3 its beats need"
    ]


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
        "shot times aren't whole seconds back to back from 0"
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
    clip.prompt = clip.prompt.replace(
        "slow, small grin.", 'slow, small grin. Malik: "Okay, I know. It\'s 3:15."'
    )
    shots[2].line, shots[7].line = "No.", "Okay, I know. It's 3:15."
    assert check.clip_prompts(bd, cp, 30, 10) == []
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
        "shot times aren't whole seconds back to back from 0"
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
        "c2: shot times aren't whole seconds back to back from 0",
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
        "draft 2: the reference's line “Sorry, I'm fully booked.” isn't kept word for word",
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
