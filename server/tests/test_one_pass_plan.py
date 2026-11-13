"""The one-pass director's free checks and code-built rows (app/one_pass.py,
app/one_pass_assemble.py): no database, no call."""

import copy

from app import one_pass, prompts
from app.one_pass_assemble import spoken, to_breakdown
from app.prompts.schemas import ShootingPlan
from app.providers.fake_local import FakeWriter

SCRIPT = ("INT. KITCHEN - DAY\nMia stirs a pot.\nMIA: The market opened at nine.\n"
          "LEO (O.S.): And we [quietly] were ready.\n★ fomo screen: Home\n"
          "CTA: Download it.")  # fmt: skip
ASKED = {"script": SCRIPT, "cast": ["Mia"], "assets": ["char:1", "screen:2"],
         "timing": {"fast": 4.8, "pause": 0.2},
         "limits": {"min": 4, "max": 15, "people": 6}}  # fmt: skip


def _plan() -> dict:
    """The stand-in's plan for SCRIPT: one clip, a shot a spoken line."""
    prompt = (f"<video_model>X: 4–15 s per clip</video_model>\n<cast>\nchar:1 | Mia\n</cast>\n"
              f"<script>\n{prompts.number_lines(SCRIPT)}\n</script>")  # fmt: skip
    return ShootingPlan.model_validate(FakeWriter()._one_pass(prompt)).model_dump()


def _fixes(change, **asked) -> list[str]:
    plan = copy.deepcopy(_plan())
    change(plan)
    return one_pass.checked({**ASKED, **asked}, plan)[1]


def test_the_schema_is_registered_and_strict_friendly():
    schema = prompts.SCHEMAS["one_pass"].model_json_schema()
    assert prompts.SCHEMAS["one_pass"] is ShootingPlan
    assert str(schema).count("anyOf") == 1  # one nullable field (a shot's line): no other union
    for part in [schema, *schema["$defs"].values()]:  # every field required, none defaulted
        assert set(part["required"]) == set(part["properties"])
    # a tripwire, not a limit of the service: the director's own schema (about 20,000) is the
    # one that grew past Anthropic's grammar; raised from 6,000 for a clip's `opening`
    assert len(str(schema)) < 6500


def test_only_a_speakers_line_is_spoken_and_its_notes_are_never_words():
    assert spoken(SCRIPT) == {3: ("Mia", "The market opened at nine."),
                              4: ("Leo (O.S.)", "And we were ready.")}  # fmt: skip


def test_the_stand_ins_plan_passes_and_an_unknown_asset_is_just_left_out():
    plan = _plan()
    plan["clips"][0]["assets"] = ["screen:2", "prop:99"]
    out, fixes = one_pass.checked(ASKED, plan)
    assert fixes == [] and out["clips"][0]["assets"] == ["screen:2"]
    assert [s["line"] for s in out["clips"][0]["shots"]] == [3, 4]  # numbers, never words
    assert [r["name"] for r in out["roles"]] == ["Leo"]  # Mia is in <cast>


def test_every_spoken_line_is_in_one_shot_once_and_in_order():
    def no_line(p):
        p["clips"][0]["shots"][1]["line"] = None

    def twice(p):
        p["clips"][0]["shots"][1]["line"] = 3

    def swapped(p):
        p["clips"][0]["shots"].reverse()

    def an_action(p):
        p["clips"][0]["shots"][0]["line"] = 2

    assert _fixes(no_line) == ["line 4 is in no shot"]
    assert _fixes(twice) == ["line 4 is in no shot", "line 3 is in more than one shot"]
    assert _fixes(swapped) == ["the lines are out of order: every line stays where the "
                               "script has it"]  # fmt: skip
    assert _fixes(an_action)[1].startswith("line 2 is not a spoken line of the script")


def test_with_every_hook_wanted_each_openings_clips_come_first_then_the_body():
    def body_first(p):
        p["clips"] = [{**p["clips"][0], "id": "c1", "opening": 0},
                      {**p["clips"][0], "id": "c2", "opening": 1, "shots": []}]  # fmt: skip

    assert _fixes(body_first)[0].startswith("each opening's clips come first, in order")


def test_a_scripts_other_openings_are_named_and_in_no_shot():
    """Reed's scripts give several hooks before one body ("Hook 1", "Hook 2"; RP5's V1 to V3):
    every hook's lines used to be filmed one after another. The first is filmed with the body;
    the plan names the others' lines, which no shot says. Never a way to drop the body."""

    def first_only(p):  # line 3 is another opening: named, and in no shot
        p["clips"][0]["shots"][0]["line"] = None
        p["treatment"]["other_openings"] = [3]

    def the_body(p):  # line 4 comes after everything filmed: it is no opening
        p["clips"][0]["shots"][1]["line"] = None
        p["treatment"]["other_openings"] = [4]

    assert _fixes(first_only) == []

    def apart(p):  # one list an opening: the versions are made from them, one each
        first_only(p)
        p["treatment"]["other_openings"] = [[3]]

    assert _fixes(apart) == []
    flat = ShootingPlan.model_validate({**_plan(), "treatment": {
        **_plan()["treatment"], "other_openings": [3, 4]}})  # fmt: skip
    assert flat.treatment.other_openings == [[3, 4]]  # a plan saved before: one other opening
    assert _fixes(the_body) == ["line 4 is no alternative opening: it comes after the body"]
    assert ShootingPlan.model_validate(
        {
            **_plan(),
            "treatment": {k: v for k, v in _plan()["treatment"].items() if k != "other_openings"},
        }
    )  # an older plan


def test_a_clip_fits_its_model_and_a_line_fits_its_shot():
    def long(p):
        p["clips"][0]["shots"][0]["seconds"] = 14

    def rushed(p):
        p["clips"][0]["shots"][0]["seconds"] = 1
        p["clips"][0]["shots"][1]["seconds"] = 9

    def crowd(p):
        p["clips"][0]["shots"][0]["people"] = ["Mia", *"ABCDEF"]
        p["roles"] += [{"name": n, "description": "x"} for n in "ABCDEF"]

    assert _fixes(long) == ["clip c1 is 17 s: this video model makes 4–15 s a clip"]
    slow = {"timing": {"fast": 2.0, "pause": 0.5}}  # this style's own speaking pace
    assert _fixes(rushed, **slow) == ["clip c1 shot 1: line 3 needs about 3 s, it has 1"]
    assert _fixes(crowd)[0].startswith("clip c1 names 8 people: this video model carries 6")


def test_everyone_in_a_shot_is_in_the_cast_or_described():
    def stranger(p):
        p["clips"][0]["shots"][0]["people"] = ["Mia", "Dana"]

    def undescribed(p):
        p["roles"] = []
        p["clips"][0]["shots"][0]["people"] = ["Leo"]

    assert _fixes(stranger)[0].startswith("Dana: in a shot, but neither in <cast> nor in `roles`")
    assert _fixes(undescribed)[0].startswith("Leo: in a shot")


def test_the_plan_becomes_shots_with_the_scripts_own_words():
    plan = ShootingPlan.model_validate(_plan())
    bd = to_breakdown(plan, SCRIPT, {"Mia": "char:1", "Leo": "slot:7"}, {plan.clips[0].place:
                                                                         "place:4"})  # fmt: skip
    (scene,), (clip,) = bd.scenes, bd.clips
    first, second = scene.shots
    assert (first.speaker, first.line) == ("Mia", "The market opened at nine.")
    assert (second.speaker, second.line) == ("Leo (O.S.)", "And we were ready.")
    assert first.script_lines == [1, 2, 3] and second.script_lines == [4, 5, 6]  # none left out
    assert (first.character_ids, second.character_ids) == (["char:1"], ["slot:7"])
    assert first.place_id == "place:4" and scene.heading == "INT. KITCHEN - DAY"
    assert clip.shot_ids == ["1.1", "1.2"] and clip.seconds == sum(
        s.seconds for s in plan.clips[0].shots) and clip.seam == "end"  # fmt: skip


def test_a_plan_made_again_keeps_the_clips_a_note_leaves_alone():
    old = _plan()
    old["clips"].append({**copy.deepcopy(old["clips"][0]), "id": "c2"})
    new = copy.deepcopy(old)
    new["clips"][0]["summary"] = "The same scene, reworded."  # not asked for: kept as it was
    new["clips"][1]["shots"][0]["action"] = "Wider, as asked."
    kept = one_pass._kept(old, new, "Redo clip 2 wider.")
    assert kept["clips"][0] == old["clips"][0] and kept["clips"][1] == new["clips"][1]
    assert one_pass._kept(old, new, "Make it all warmer.") == new  # no clip named: as planned


def test_a_presenter_the_plan_names_as_the_script_describes_them_is_still_the_presenter():
    """Videos 370 and 390 (11 Nov): the script says "a dad in his fifties talks to his phone",
    the plan cast "Dad", and four plans in a row were refused: "The presenter: in a shot, but
    neither in <cast> nor in `roles`"."""
    script = "[A dad in his fifties talks to his phone in his truck.]\nI voted for this."
    asked = {**ASKED, "script": script, "cast": [], "talker": "The presenter"}
    shot = {
        "seconds": 5,
        "camera": "Chest-up, locked",
        "action": "He talks to the lens.",
        "people": ["Dad"],
        "extras": "",
        "line": 2,
        "how": "angry",
        "at": 0,
    }
    clip = {**_plan()["clips"][0], "kind": "host", "shots": [shot]}
    plan = {
        **_plan(),
        "clips": [clip],
        "voices": [{"who": "Dad", "sounds": "a gravelly baritone"}],
        "roles": [{"name": "Dad", "description": "A weathered man in his fifties"}],
    }
    out, fixes = one_pass.checked(asked, plan)
    assert fixes == []
    assert [r["name"] for r in out["roles"]] == ["The presenter"]
    assert out["clips"][0]["shots"][0]["people"] == out["voices"][0]["who"].split("|") == [
        "The presenter"]  # fmt: skip
