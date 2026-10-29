"""The style registry (Reed, 2026-10-28): our current look is the House style and stays the
default, unchanged; Starpop's styles are entries in styles/, in Reed's order."""

import pytest

from app import prompts
from app.prompts import HERE

TOKENS = ["sheet_look", "place_look", "still_look", "clip_style", "fit_look"]


def test_reeds_order_and_only_house_starts_on():
    ids = [s["id"] for s in prompts.styles()]
    assert ids[:5] == ["house", "disney-pixar", "song", "zack-d", "skeleton"]
    assert set(ids[5:]) == {"claymation", "anime-comic", "paper", "watercolor", "wool-crochet",
                            "whiteboard", "vox", "podcast"}  # fmt: skip
    for own_flow in ("whiteboard", "podcast"):  # they need their own flows first (spec)
        assert prompts.style(own_flow)["kind"] == "format"
    for on_story in ("zack-d", "skeleton"):  # pickable on a story script (flows Q4)
        assert prompts.style(on_story)["kind"] == "look"
    # no look is narrated any more: narration is the Narrated format (Reed, 2026-10-29)
    assert all("narrated" not in s for s in prompts.styles())
    assert not any("narrated:" in (HERE / "styles" / f"{s['id']}.md").read_text()
                   for s in prompts.styles())  # fmt: skip
    assert [s["id"] for s in prompts.styles() if s["on"]] == ["house"]
    for s in prompts.styles():
        assert s["kind"] in ("look", "format") and s["blurb"], s["id"]
        assert set(TOKENS) <= set(s["sections"]), s["id"]
        assert set(s["sections"]) <= set(TOKENS) | set(prompts.GUIDES) | prompts.DATA, s["id"]


def test_house_is_the_step_files_as_they_were():
    """House fills each {{token}} with the words the step files had, so nothing changes."""
    house = prompts.style("house")["sections"]
    assert set(house) == set(TOKENS) | prompts.DATA  # no guidance: the step files are its rules
    for step in prompts.SCHEMAS:
        text = prompts.system(step)
        assert text == prompts.system(step, "house")
        assert "{{" not in text and "## Style:" not in text, step
    assert house["still_look"] in prompts.system("storyboard")
    assert f"Style: {house['clip_style']}." in prompts.system("clip_prompts")
    assert house["sheet_look"] in prompts.sheet_prompt("character", "a man")
    assert house["place_look"] in prompts.sheet_prompt("place", "a kitchen")
    for name in ("storyboard", "clip_prompts", "improve", "look_fit", "sheet"):
        assert "{{" in (HERE / f"{name}.md").read_text(), name  # the look lives in styles/


@pytest.mark.parametrize("style_id", [s["id"] for s in prompts.styles()])
def test_each_style_fills_every_step_and_adds_its_guidance_where_it_belongs(style_id):
    chosen = prompts.style(style_id)
    for step in prompts.SCHEMAS:
        text = prompts.system(step, style_id)
        assert "{{" not in text, step
        guides = [k for k, steps in prompts.GUIDES.items() if step in steps]
        wanted = [chosen["sections"][k] for k in guides if k in chosen["sections"]]
        assert ("## Style:" in text) == bool(wanted), step
        assert all(w in text for w in wanted), step
    for kind in ("character", "place"):
        sheet = prompts.sheet_prompt(kind, "x", style_id=style_id)
        assert chosen["sections"][f"{'sheet' if kind == 'character' else 'place'}_look"] in sheet


def test_a_style_changes_the_look_but_never_the_rules():
    pixar = prompts.system("clip_prompts", "disney-pixar")
    assert "Style: Smooth cinematic 3D animation in the style of a Pixar feature film" in pixar
    rules = pixar.split("## Worked example")[0]  # the example stays House, and says so
    assert "warm amber key against cool blue shadows" not in rules
    assert "**Never reads as sexual.**" in pixar and "**Brand screens.**" in pixar
    assert "Skeleton" in prompts.system("script_draft", "skeleton")
    assert "## Style:" not in prompts.system("script_draft", "disney-pixar")  # a look only


def test_an_unknown_style_is_refused():
    with pytest.raises(ValueError, match="unknown style"):
        prompts.system("storyboard", "pixar")
    with pytest.raises(ValueError):
        prompts.sheet_prompt("character", "x", style_id="Disney Pixar")  # ids, not names


def test_styles_borrow_a_studio_look_never_its_frame_and_never_rewrite_lines():
    """Flow-QA: "a frame from a Pixar film" may be refused as a copy; "in the style of" is
    safe. Next-Lead: a format's script notes never change an existing script's lines."""
    for s in prompts.styles():
        text = "\n".join(s["sections"].values())
        assert "frame from a Pixar" not in text and "from an animated Pixar" not in text, s["id"]
        if "script" in s["sections"] and s["id"] in ("zack-d", "skeleton"):
            assert "word for word" in s["sections"]["script"], s["id"]


def test_the_first_looks_have_banned_words_and_a_fix_for_each_failure():
    """flows ST2: banned words repaired in code, free; a fix per failure id (Next-Server's
    `refused`, the advisory check's face, outfit and product)."""
    for look in ("house", "disney-pixar", "zack-d", "skeleton"):
        assert prompts.look_banned(look), look
        assert set(prompts.look_fixes(look)) == {"refused", "face", "outfit", "product"}, look
    assert ("stage", "world") in prompts.look_banned("zack-d")
    assert prompts.look_banned("claymation") == [] and prompts.look_fixes("claymation") == {}
    for step in prompts.SCHEMAS:  # data, never sent to a model
        assert "## banned" not in prompts.system(step, "zack-d"), step


def test_a_looks_banned_words_are_repaired_but_never_in_a_spoken_line():
    from app.prompts import check

    prompt = "\n".join([
        "Audio: only the spoken lines and a hum. No music. No subtitles.",
        "Shot 1 | 0-2 s. A bowl floats on a stage. Mom: “The stage is mine.” No one speaks.",
        "Setting: the Stage glows cyan.",
    ])  # fmt: skip
    fixed, changed, advice = check.look_words(prompt, "zack-d")
    assert fixed.splitlines()[1:] == [
        "Shot 1 | 0-2 s. A bowl rests in the world. Mom: “The stage is mine.” No one speaks.",
        "Setting: the World glows cyan.",
    ]
    assert changed == ["on a stage → in the world", "floats → rests", "stage → world"]
    assert advice == ["Advice: “stage” is in a quoted line; the look avoids it"]
    assert check.look_words(fixed, "zack-d")[1] == []  # doing it again changes nothing
    assert check.look_words("A live-action kitchen.", "house")[0] == "A kitchen."
    # Flow-QA on #908: a safeguard keeps its words
    for safe, look in (("Bones and glow, no blood, no gore.", "skeleton"),
                       ("The bowl is not floating.", "zack-d"),
                       ("Not photorealistic: stylised.", "house"),
                       ("Never on a stage.", "zack-d")):  # fmt: skip
        assert check.look_words(safe, look)[:2] == (safe, []), safe


def test_every_look_has_a_sample_person_and_formats_have_none():
    """flows ST3: a look's sample still shows `## sample` when the brand has no hero."""
    for s in prompts.styles():
        sample = prompts.look_sample(s["id"])
        assert bool(sample) == (s["kind"] == "look"), s["id"]
        assert "\n" not in sample and len(sample.split()) <= 30, s["id"]
    assert "skeleton" in prompts.look_sample("skeleton")
    for step in prompts.SCHEMAS:  # data, never step guidance
        assert prompts.look_sample("zack-d") not in prompts.system(step, "zack-d"), step
