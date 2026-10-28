"""The style registry (Reed, 2026-10-28): our current look is the House style and stays the
default, unchanged; Starpop's styles are entries in styles/, in Reed's order."""

import pytest

from app import prompts
from app.prompts import HERE

TOKENS = ["sheet_look", "place_look", "still_look", "clip_style", "fit_look"]


def test_reeds_order_and_only_house_starts_on():
    ids = [s["id"] for s in prompts.styles()]
    assert ids[:5] == ["house", "disney-pixar", "song", "zack-d", "skeleton"]
    assert [s["id"] for s in prompts.styles() if s["on"]] == ["house"]
    for s in prompts.styles():
        assert s["kind"] in ("look", "format") and s["blurb"], s["id"]
        assert set(TOKENS) <= set(s["sections"]), s["id"]
        assert set(s["sections"]) <= set(TOKENS) | set(prompts.GUIDES), s["id"]


def test_house_is_the_step_files_as_they_were():
    """House fills each {{token}} with the words the step files had, so nothing changes."""
    house = prompts.style("house")["sections"]
    assert set(house) == set(TOKENS)  # no extra guidance: the step files are its rules
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
