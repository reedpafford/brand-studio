"""One place per format and per style (app/guides, read only by app/guides.py)."""

from pathlib import Path

from app import guides, prompts

APP = Path(guides.__file__).parent


def test_every_writing_step_gets_craft_the_format_and_the_style():
    """Reed, 2 Nov: one director, briefed by the guides, at every step it writes."""
    craft = (guides.ROOT / "craft.md").read_text()
    song, goofy = guides.format_("song")["sections"], guides.style("claymation-goofy")["sections"]
    for step in guides.BRIEFED:
        text = prompts.system(step, "claymation-goofy", "song")
        assert craft in text, step
        assert "## Format: Song\nThis video is a Song video in the Goofy Claymation style" in text
        assert song["Stills"] in text and song["Locked rules"] in text, step
        assert "## Style: Goofy Claymation" in text and goofy["Stills"] in text, step
        assert goofy["Prompt rules"] in text, step  # its style's skill, inherited
        assert text.index("## Producer craft") < text.index("## Format:") < text.index("## Style:")
    for step in ("script_draft", "enhance", "variations", "improve", "item_check"):
        assert craft not in prompts.system(step, "claymation-goofy", "song"), step
    zack = prompts.system("breakdown", "zack-d", "story")  # Zack D: its format and its style
    assert "## Format: Zack D" in zack and "## Style: Zack D" in zack
    assert guides.format_("zack-d")["sections"]["Step 3 — Voiceover in the Zack D voice"] in zack


def test_a_lane_holds_only_its_differences_and_inherits_the_rest():
    parent, lane = guides.style("paper"), guides.style("paper-flat")
    own = (guides.ROOT / "styles" / "paper" / "lanes" / "paper-flat.md").read_text()
    assert parent["sections"]["Clips"] not in own  # written once, in the style
    assert lane["sections"]["Clips"] == parent["sections"]["Clips"]
    assert lane["sections"]["banned"] == parent["sections"]["banned"]
    assert lane["sections"]["Prompt rules"] == parent["sections"]["Prompt rules"]
    assert lane["sections"]["Stills"] != parent["sections"]["Stills"]  # its own replaces it
    assert "lanes" not in lane["sections"] and lane["image_model"] == parent["image_model"]
    assert guides.style("skeleton-cute")["own_sample"]  # front matter it leaves out is inherited


def test_the_format_picker_lists_every_format(owner):
    found = owner.get("/formats").json()
    assert [f["id"] for f in found] == ["dialogue", "song", "narrated", "zack-d"]
    assert set(found[0]) == {"id", "name", "engine", "blurb", "on"} and found[0]["on"]


def test_only_guides_py_reads_the_guide_files():
    """No other module opens a file under app/guides (Reed edits them; one reader)."""
    for path in APP.rglob("*.py"):
        if path.name == "guides.py" and path.parent == APP:
            continue
        text = path.read_text()
        assert "guides.ROOT" not in text and '"guides"' not in text, path
        assert "guides/" not in text.replace("app/guides/", ""), path
