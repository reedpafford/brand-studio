"""The style registry (Reed, 2026-10-28): our current look is the House style and stays the
default, unchanged; Starpop's styles are guides in app/guides/styles, in Reed's order."""

import pytest

from app import guides, prompts
from app.prompts import HERE, schemas

TOKENS = list(guides.TOKENS)
SITE = ("Stills", "Clips", "Breakdown", "Script")  # the site's own guidance, before the skills


def test_reeds_order_and_only_house_starts_on():
    ids = [s["id"] for s in prompts.styles()]
    assert ids[:4] == ["house", "disney-pixar", "zack-d", "skeleton"]
    assert {"claymation", "anime-comic", "paper", "watercolor", "wool-crochet"} <= set(ids)
    # A look's own lanes (order 5.1, 5.2…) sit right after it, in order; no PR lists them here
    styles = prompts.styles()
    for before, s in zip(styles, styles[1:], strict=False):
        if s["order"] != int(s["order"]):
            assert int(before["order"]) == int(s["order"]), s["id"]
    assert ids.index("paper") + 4 == ids.index("paper-origami")  # Reed's five paper lanes
    # Formats are their own guides (Reed, 2 Nov: Zack D is both a format and a style)
    assert [(f["id"], f["engine"]) for f in guides.formats()] == [
        ("dialogue", "story"),
        ("song", "song"),
        ("narrated", "narrated"),
        ("zack-d", "narrated"),
        ("presenter", "narrated"),
    ]
    assert [s["id"] for s in prompts.styles() if s["on"]] == ["house"]
    for s in prompts.styles():
        assert s["kind"] in ("look", "lane") and s["blurb"], s["id"]
        assert set(TOKENS) <= set(s["sections"]), s["id"]
    assert guides.video_format("story", "zack-d") == "zack-d"  # until scripts carry a format
    assert guides.video_format("song", "zack-d") == "song"
    assert guides.video_format("", "claymation-goofy") == "dialogue"


def test_house_is_the_step_files_as_they_were():
    """House fills each {{token}} with the words the step files had, so nothing changes."""
    house = prompts.style("house")["sections"]
    for step in prompts.SCHEMAS:
        text = prompts.system(step)
        assert text == prompts.system(step, "house"), step
        if not step.startswith(("song_", "narrated_")):  # those steps are their format's
            assert text == prompts.system(step, "house", "story"), step
        assert "{{" not in text, step
    assert house["still_look"] in prompts.system("storyboard")
    assert f"Style: {house['clip_style']}." in prompts.system("clip_prompts")
    assert house["sheet_look"] in prompts.sheet_prompt("character", "a man")
    assert house["place_look"] in prompts.sheet_prompt("place", "a kitchen")
    for name in ("storyboard", "clip_prompts", "improve", "look_fit", "sheet"):
        assert "{{" in (HERE / f"{name}.md").read_text(), name  # the look lives in guides/


@pytest.mark.parametrize("style_id", [s["id"] for s in prompts.styles()])
def test_each_style_fills_every_step_and_sends_no_data(style_id):
    chosen = prompts.style(style_id)
    for step in prompts.SCHEMAS:
        text = prompts.system(step, style_id)
        assert "{{" not in text, step
        for name in guides.DATA:  # data, never sent to a model
            assert f"### {name}\n" not in text, step
        wanted = [v for k, v in chosen["sections"].items()
                  if k in prompts.GUIDES and step in prompts.GUIDES[k]]  # fmt: skip
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
    for s in [*prompts.styles(), *guides.formats()]:
        text = "\n".join(v for k, v in s["sections"].items() if k in (*TOKENS, *SITE))
        assert "frame from a Pixar" not in text and "from an animated Pixar" not in text, s["id"]
        if "Script" in s["sections"]:
            assert "word for word" in s["sections"]["Script"], s["id"]


def test_the_first_looks_have_banned_words_and_a_fix_for_each_failure():
    """flows ST2: banned words repaired in code, free; a fix per failure id (Next-Server's
    `refused`, the advisory check's face, outfit and product)."""
    for look in ("house", "disney-pixar", "zack-d", "skeleton"):
        assert prompts.look_banned(look), look
        assert set(prompts.look_fixes(look)) == {"refused", "face", "outfit", "product"}, look
    assert ("Pixar-style", "semi-realistic 3D") in prompts.look_banned("zack-d")  # Reed, 3 Nov: Z1
    # the look's own name never goes to a model (Next-Lead on #1009)
    from app.prompts import check

    said = check.look_words("A kitchen in the style of Zack D. Films, a Zack D close-up.", "zack-d")
    assert said[0] == "A kitchen, a close-up.", said[0]
    # QA on #1009: tidying a repair never touches a quote (rule 19), nor leaves a trailing space
    for quote in ('"Voilà : ça va ; très bien ."', '"Hello , world : ok"', '"Wait . . .  what"'):
        line = f"Mia says {quote} in the style of Zack D. Films"
        assert check.look_words(line, "zack-d")[0] == f"Mia says {quote}", line
    assert prompts.look_banned("claymation") == []
    assert set(prompts.look_fixes("claymation")) == {"refused", "face", "outfit", "product"}
    assert prompts.look_fixes("claymation-goofy") == {}  # a lane's empty `fixes`: none, as before


def test_a_looks_banned_words_are_repaired_but_never_in_a_spoken_line():
    from app.prompts import check

    prompt = "\n".join([
        "Audio: only the spoken lines and a hum. No music. No subtitles.",
        "Shot 1 | 0-2 s. A bloody bone beside a corpse. Mom: “The blood is mine.”",
        "Setting: the Blood pools red.",
    ])  # fmt: skip
    fixed, changed, advice = check.look_words(prompt, "skeleton")
    assert fixed.splitlines()[1:] == [
        "Shot 1 | 0-2 s. A glowing bone beside a skeleton. Mom: “The blood is mine.”",
        "Setting: the Glow pools red.",
    ]
    assert changed == ["bloody → glowing", "corpse → skeleton", "blood → glow"]
    assert advice == ["Advice: “blood” is in a quoted line; the look avoids it"]
    assert check.look_words(fixed, "skeleton")[1] == []  # doing it again changes nothing
    assert check.look_words("A live-action kitchen.", "house")[0] == "A kitchen."
    # Flow-QA on #908: a safeguard keeps its words
    for safe, look in (("Bones and glow, no blood, no gore.", "skeleton"),
                       ("Not a cartoon, no chibi faces.", "zack-d"),
                       ("Not photorealistic: stylised.", "house"),
                       ("Never Pixar-style.", "zack-d")):  # fmt: skip
        assert check.look_words(safe, look)[:2] == (safe, []), safe


def test_reeds_looks_are_one_per_style_and_their_lanes_choose_per_video():
    """Reed, 1 Nov: "Why are there so many different types for one style? The style would be
    'skeleton' or 'paper mache'." One look each; its lanes are files kept word for word, and the
    plan picks one per video, the skill's recommended lane by default."""
    looks = [s["id"] for s in prompts.styles() if s["kind"] == "look"]
    lanes = {s["id"]: s["parent"] for s in prompts.styles() if s["kind"] == "lane"}
    assert lanes == {"paper-flat": "paper", "paper-handmade": "paper", "paper-collage": "paper",
                     "paper-origami": "paper", "claymation-goofy": "claymation",
                     "claymation-clean": "claymation", "claymation-puppet": "claymation",
                     "skeleton-bare": "skeleton", "skeleton-cute": "skeleton",
                     "skeleton-xray": "skeleton"}  # fmt: skip
    assert not set(lanes) & set(looks) and set(lanes.values()) <= set(looks)
    for parent in set(lanes.values()):
        plan = prompts.system("plan", parent)
        assert "This look has lanes" in plan and '- "" (the default' in plan, parent
        shown = [x for x, p in lanes.items() if p == parent and not prompts.style(x)["hidden"]]
        assert all(f'- "{lane}": ' in plan for lane in shown), parent
    assert "This look has lanes" not in prompts.system("plan", "paper-flat")  # chosen already
    assert "This look has lanes" not in prompts.system("storyboard", "paper")  # the plan's only
    assert "**The lane.**" in prompts.system("plan")
    assert schemas.Structure.model_fields["lane"].default == ""
    assert "Layered papercraft" in prompts.style("paper")["sections"]["lanes"]
    assert "Cinematic claymation" in prompts.style("claymation")["sections"]["lanes"]
    assert "Bare-Bones" in prompts.style("skeleton")["sections"]["lanes"]


def test_every_look_has_a_sample_person():
    """flows ST3: a look's sample still shows `## sample` when the brand has no hero."""
    for s in prompts.styles():
        sample = prompts.look_sample(s["id"])
        assert sample, s["id"]  # a lane keeps Reed's own
        assert "\n" not in sample and len(sample.split()) <= 30, s["id"]
    assert "skeleton" in prompts.look_sample("skeleton")
    for step in prompts.SCHEMAS:  # data, never step guidance
        assert prompts.look_sample("zack-d") not in prompts.system(step, "zack-d"), step


def test_a_looks_sample_still_redraws_the_hero_in_the_look():
    """Reed, 2026-10-29: tonight's samples read as generic Pixar, because the hero's House
    sheet was copied "exactly". The sample uses the picture for who, the look for how."""
    text = prompts.sample_still_prompt("claymation", "Mia", from_picture=True)
    assert text.startswith(prompts.style("claymation")["sections"]["still_look"])
    assert prompts.style("claymation")["sections"]["sheet_look"] in text
    assert "copy who they are, never how they are drawn" in text and "exactly" not in text
    own = prompts.sample_still_prompt("zack-d")
    assert prompts.look_sample("zack-d").rstrip(".") in own and "[Image1]" not in own
    # Skeleton's sample is always its own skeleton, never the brand's human hero
    own = [s["id"] for s in prompts.styles() if s["own_sample"]]
    assert own == [
        "skeleton",
        "skeleton-bare",
        "skeleton-cute",
        "skeleton-xray",
        "dr-pickle",
    ]  # D3, 3 Nov


def test_a_look_is_described_by_its_own_tells_never_by_another_studio():
    """The Producer, 2026-10-29: only Disney Pixar (and House, which is built on it) may name a
    studio in its look lines and the site's guidance; every other look describes what it looks
    like (Reed's skills may still name one: the brief says to follow the video's look)."""
    studios = ("pixar", "disney", "ghibli", "aardman", "laika")
    for s in prompts.styles():
        if s["id"] in ("house", "disney-pixar"):
            continue
        for name in (*TOKENS, *SITE):
            text = s["sections"].get(name, "")
            assert not any(x in text.lower() for x in studios), (s["id"], name)


def test_the_worked_example_speaks_the_videos_look_and_house_is_unchanged():
    """QA after #1009: the clip example's "Style: Pixar-style 3D…" line steered every
    look's clips toward House. Another look's example carries its own lines."""
    house = prompts.style("house")["sections"]["clip_style"]
    assert house in prompts.system("clip_prompts")  # House as it was
    for s in prompts.styles():
        if s["id"] == "house" or s["kind"] != "look":
            continue
        text = prompts.system("clip_prompts", s["id"], "dialogue")  # the fomo examples' format
        example = text.split("## Worked example", 1)[1].split("\n## ", 1)[0]
        assert house not in example and s["sections"]["clip_style"] in example, s["id"]


def test_the_reel_watch_example_names_no_studio():
    """QA-3: a watched reel's look is told in plain words, never 'Pixar-style'. It is carried
    into a video's reference shots, whatever that video's look."""
    import json

    assert "pixar" not in prompts.watch_system().lower()
    assert "pixar" not in json.dumps(schemas.ReelWatch.model_json_schema()).lower()


def test_claymation_has_reeds_four_lanes_with_their_blocks_word_for_word():
    """Reed's claymation skill (#1095, now in its guide): one lane a video, each its own look,
    its style block word for word; the motion guard in every clip; never smooth CGI."""
    root = guides.ROOT / "styles" / "claymation"  # hidden lanes keep their menu part (C8)
    skill = "".join(x.read_text() for x in (root / "guide.md", *sorted(root.glob("lanes/*.md"))))
    blocks = {
        "claymation": "Detailed cinematic claymation scene — hand-sculpted plasticine",
        "claymation-goofy": "Goofy claymation scene — everything sculpted from plasticine",
        "claymation-clean": "Polished claymation scene — everything sculpted from smooth",
        "claymation-puppet": "Stop-motion clay puppet scene — clay characters detailed",
    }
    for look, start in blocks.items():
        still = prompts.style(look)["sections"]["still_look"]
        block = start + skill.split(f"`{start}", 1)[1].split("`", 1)[0]
        assert block in still, look
        clip = prompts.system("clip_prompts", look)
        assert "gentle smooth motion with one action per shot" in clip, look  # Reed, 3 Nov (C1)
        assert "Every cartoon touch is sculpted in clay." in clip and "12fps" not in clip, look
        assert "Animation must start at the first frame." in clip, look
    assert "never sticking out in every direction" in prompts.system(
        "storyboard", "claymation-goofy"
    )
    assert "clay imitation of" in prompts.system("storyboard", "claymation")
    assert "young clay skin" not in prompts.style("claymation")["sections"]["sheet_look"]  # age


def test_disney_pixar_holds_reeds_skill():
    """Reed's disney-pixar skill (#1095), where the site doesn't differ: the camera block's
    close, sculpted hair bands, label copy with its colour, mechanism and body shots in plain
    words, and the three kinds of transition."""
    look = prompts.style("disney-pixar")["sections"]
    assert "A stylised 3D animated render." in look["still_look"]
    assert "crisp light-and-shadow bands" in look["sheet_look"]
    still = prompts.system("storyboard", "disney-pixar")
    assert "with its colour" in still and "never clinical terms" in still
    assert "a pancake becomes the sun" in prompts.system("clip_prompts", "disney-pixar")
    assert "four to five heads tall" not in look["sheet_look"]  # adults keep adult proportions


def test_ugc_loads_off_with_its_spec_and_keeps_its_studies_out_of_the_prompts():
    """Reed's Drive folder "UGC (B-roll)", 3 Nov: a new style named "UGC", off until Reed
    switches it on. Its per-video notes are evidence (notes.md), never loaded into a step.
    Captions come in post production (Reed, 3 Nov), so the guide gives no caption look."""
    ugc = prompts.style("ugc")
    assert ugc["name"] == "UGC" and not ugc["on"] and ugc["kind"] == "look"
    spec = ("pacing", "must keep", "safe to vary", "combines with", "camera", "sample")
    for name in (*TOKENS, *spec):
        assert ugc["sections"].get(name), name
    assert "caption look" not in "\n".join(ugc["sections"].values()).lower()
    assert set(prompts.look_fixes("ugc")) == {"refused", "face", "outfit", "product"}
    assert ("Pixar-style", "realistic") in prompts.look_banned("ugc")
    notes = sorted((guides.ROOT / "styles" / "ugc" / "examples").glob("*/notes.md"))
    assert len(notes) == 4 and guides.studies("dialogue", "ugc") == []
    brief = prompts.system("breakdown", "ugc")
    assert "## Style: UGC\n" in brief and ugc["sections"]["must keep"] in brief
    assert notes[0].read_text()[:200] not in brief


def test_claymation_allows_smooth_and_still_bans_polished_and_glossy():
    """Reed, Round 2 (7 Nov): "smooth" is no longer banned in Claymation; "polished" and
    "glossy" still turn the clay into CGI, and the hand-made texture words stay."""
    for look in ("claymation", "claymation-goofy", "claymation-puppet"):
        text = prompts.system("clip_prompts", look) + prompts.system("storyboard", look)
        assert "Never call the clay smooth" not in text and 'never write "smooth,' not in text
        assert "Never call the clay polished or glossy" in text, look
    guide = (guides.ROOT / "styles" / "claymation" / "guide.md").read_text()
    assert "Smooth is fine (smooth motion, smooth-matte clay)" in guide
    assert 'never write "polished" or "glossy" for the clay' in guide
