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
        if s["kind"] == "look":  # a format (Song) has no look of its own: it takes the video's
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


@pytest.mark.parametrize("style_id", [s["id"] for s in prompts.styles() if s["kind"] == "look"])
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
    assert ("Pixar-style", "semi-realistic 3D") in prompts.look_banned("zack-d")
    # the look's own name never goes to a model (Next-Lead on #1009)
    from app.prompts import check

    said = check.look_words("A kitchen in the style of Zack D. Films, a Zack D close-up.", "zack-d")
    assert said[0] == "A kitchen, a close-up.", said[0]
    # QA on #1009: tidying a repair never touches a quote (rule 19), nor leaves a trailing space
    for quote in ('"Voilà : ça va ; très bien ."', '"Hello , world : ok"', '"Wait . . .  what"'):
        line = f"Mia says {quote} in the style of Zack D. Films"
        assert check.look_words(line, "zack-d")[0] == f"Mia says {quote}", line
    assert prompts.look_banned("claymation") == [] and prompts.look_fixes("claymation") == {}
    for step in prompts.SCHEMAS:  # data, never sent to a model
        assert "## banned" not in prompts.system(step, "zack-d"), step


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


def test_every_look_has_a_sample_person_and_formats_have_none():
    """flows ST3: a look's sample still shows `## sample` when the brand has no hero."""
    for s in prompts.styles():
        sample = prompts.look_sample(s["id"])
        assert bool(sample) == (s["kind"] == "look"), s["id"]
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
    assert [s["id"] for s in prompts.styles() if s["own_sample"]] == ["skeleton"]


def test_zack_d_is_the_real_channels_look_not_a_cyan_cartoon():
    """Reed's references (YouTube shorts): semi-realistic 3D like a game cutscene."""
    zack = prompts.style("zack-d")["sections"]
    for part in ("sheet_look", "place_look", "still_look", "clip_style"):
        assert "semi-realistic 3D" in zack[part] or "Semi-realistic 3D" in zack[part], part
        assert "cyan" not in zack[part] and "Pixar register" not in zack[part], part


def test_a_look_is_described_by_its_own_tells_never_by_another_studio():
    """The Producer, 2026-10-29: only Disney Pixar (and House, which is built on it) may name a
    studio; every other look describes what it looks like. Song is a type in any look, with no
    look of its own (Song in any look)."""
    studios = ("pixar", "disney", "ghibli", "aardman", "laika")
    for s in prompts.styles():
        if s["id"] in ("house", "disney-pixar"):
            continue
        for name, text in s["sections"].items():
            if name in prompts.DATA:  # banned words name a studio to take it out
                continue
            assert not any(x in text.lower() for x in studios), (s["id"], name)


def test_the_worked_example_speaks_the_videos_look_and_house_is_unchanged():
    """QA after #1009: the clip example's "Style: Pixar-style 3D…" line steered every
    look's clips toward House. Another look's example carries its own lines."""
    house = prompts.style("house")["sections"]["clip_style"]
    assert house in prompts.system("clip_prompts")  # House as it was
    for s in prompts.styles():
        if s["id"] == "house" or s["kind"] != "look":
            continue
        text = prompts.system("clip_prompts", s["id"])
        example = text.split("## Worked example", 1)[1].split("## Style:", 1)[0]
        assert house not in example and s["sections"]["clip_style"] in example, s["id"]


def test_the_reel_watch_example_names_no_studio():
    """QA-3: a watched reel's look is told in plain words, never 'Pixar-style'. It is carried
    into a video's reference shots, whatever that video's look."""
    import json

    from app.prompts import schemas

    assert "pixar" not in prompts.system("reel_watch").lower()
    assert "pixar" not in json.dumps(schemas.ReelWatch.model_json_schema()).lower()


def test_song_has_only_its_guides_and_takes_its_look_from_the_video():
    """Song in any look: song.md carries no look of its own, so nothing pulls a Clay song
    toward Pixar; a story's prompts are as before."""
    song = prompts.style("song")["sections"]
    assert set(song) == {"still", "clip"}
    for step in ("clip_prompts", "storyboard"):
        made = prompts.system(step, "claymation", "song")
        assert "Pixar musical" not in made and "Pixar animated feature" not in made, step
        assert "## Format: Song\nThis video is a Song video in the Claymation look" in made
