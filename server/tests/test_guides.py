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


RELEASE = ("house", "disney-pixar", "claymation", "skeleton", "zack-d")  # Reed's Drive, 3 Nov


def test_each_release_style_holds_its_own_pacing_and_3d_only_where_it_is_3d():
    """Reed, 3 Nov: pacing is a per-style range (set later from the reference videos), and
    "stylized 3D characters" belongs to the 3D styles only, never to every video."""
    assert "stylized 3D" not in (APP / "prompts" / "rules.md").read_text()
    for look in RELEASE:
        pacing = guides.style(look)["sections"]["pacing"]
        assert pacing.strip(), look  # the placeholder until a style's references are measured
        assert f"### pacing\n{pacing}" in prompts.system("breakdown", look), look
        said = "stylized 3D characters" in guides.style(look)["sections"].get("The videos", "")
        assert said == (look != "claymation"), look


def test_release_guides_hold_no_chat_steps_starpop_assets_or_unused_models():
    """Reed, 3 Nov: "Automated steps shouldn't contain chat instructions. Just stay true to the
    ux flow we built." No waiting on a user, hand-off lines, Starpop links or voice ids, models
    the site doesn't use, Starpop's parent prompt, or Pixar wording outside Disney Pixar."""
    texts = {s: guides.style(s)["sections"] for s in RELEASE}
    texts |= {f: guides.format_(f)["sections"] for f in ("dialogue", "song", "narrated", "zack-d")}
    texts["craft"] = {"craft": (guides.ROOT / "craft.md").read_text()}
    for name, sections in texts.items():
        text = "\n".join(v for k, v in sections.items() if k != "banned").lower()
        for gone in ("wait for the user", "wait for each", "hand-off:", "starpop", "fish-audio",
                     "elevenlabs", "seedream", "nano banana", "gpt image", "seedance",
                     "foundations", "parent's", "reed picks"):  # fmt: skip
            assert gone not in text, (name, gone)
        if name not in ("house", "disney-pixar"):  # House is built on that look (test_styles)
            assert "pixar" not in text, name


def test_hidden_lanes_still_load_but_are_off_the_picker_and_the_menu():
    """Reed, 3 Nov (C8): Clean and Puppet claymation are hidden until a reference shows them,
    not deleted: a video already in one still loads it."""
    from app import looks

    listed = [x["id"] for x in looks.lanes("claymation")]
    assert listed == ["claymation-goofy"]
    menu = guides.style("claymation")["sections"]["lanes"]
    for lane in ("claymation-clean", "claymation-puppet"):
        assert guides.style(lane)["hidden"] and guides.style(lane)["parent"] == "claymation"
        assert lane not in menu


def test_camera_behaviour_is_each_styles_own_and_house_follows_the_reels():
    """Reed, 3 Nov (F8, H2): no global camera rule; the style's camera section decides. House:
    "Sure follow the reels, but remain incredibly engaging"."""
    rules = (APP / "prompts" / "rules.md").read_text()
    assert "Camera behaviour follows the style guide's camera section." in rules
    assert "Most shots carry a camera move" not in rules
    camera = guides.style("house")["sections"]["camera"]
    assert "mostly holds and moves on beats" in camera and "incredibly engaging" in camera
    assert "It holds still, the people move." in camera
    assert f"### camera\n{camera}" in prompts.system("breakdown", "house")


def test_house_light_is_the_time_of_day_and_its_guides_leave_captions_to_post():
    """Reed, 3 Nov (H1; "Captions, on all videos, come in post production")."""
    house = guides.style("house")
    assert all("cool blue shadows" not in v for v in guides.tokens("house").values())
    assert "time of day" in house["sections"]["place_look"] and "time of day" in house["blurb"]
    for guide in (guides.ROOT / "styles" / "house", guides.ROOT / "formats" / "dialogue"):
        assert "caption" not in (guide / "guide.md").read_text().lower(), guide


def test_dialogue_has_an_optional_closing_slot_for_the_brands_real_thing():
    """Reed, 3 Nov (H8)."""
    slot = guides.format_("dialogue")["sections"]["closing slot"]
    assert "optional closing slot for the brand's real thing" in slot


def test_rival_products_may_be_characters_only_where_the_style_says_so():
    """Reed, 3 Nov (P1): germs, ingredients and rival products may have faces in Disney Pixar;
    the brand's product never. Rule 2 keeps its ban and lets a style guide open it."""
    rules = (APP / "prompts" / "rules.md").read_text()
    assert "never put a competitor's or made-up product on screen, unless the style guide" in rules
    assert "Pixar" not in rules  # rules.md goes to every style: no studio names
    assert "the brand's own product is always the real one" in rules
    stills = guides.style("disney-pixar")["sections"]["Stills"]
    assert "The brand's product never has a face; germs, ingredients and rival products" in stills
