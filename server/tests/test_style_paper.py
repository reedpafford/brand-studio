"""Reed’s paper skill (#1095, now in app/guides/styles/paper): Paper and its four lanes."""

from app import guides, prompts


def test_paper_has_reeds_five_lanes_with_their_blocks_word_for_word():
    """Reed’s paper skill (#1095): one lane a video, each its own look, its
    style and physicality blocks word for word; the camera inside the paper world."""
    skill = (guides.ROOT / "styles" / "paper" / "guide.md").read_text()
    blocks = [b.split("`", 1)[0] for b in skill.split("- Style block: `")[1:]]
    looks = ["paper", "paper-flat", "paper-handmade", "paper-collage", "paper-origami"]
    assert len(blocks) == len(looks)
    phys = skill.split("## The physicality block", 1)[1].split("```\n", 2)[1].strip()
    for look, block in zip(looks, blocks, strict=True):
        still = prompts.style(look)["sections"]["still_look"]
        if look == "paper-collage":  # its printed scraps become textless (QA-5 on #1110)
            block = block.split(" structures built from")[0]
        assert block in still, look
        assert (phys in still) == (look != "paper-origami"), look  # origami: folded edges
        assert "paper" in prompts.style(look)["sections"]["clip_style"].lower(), look  # not clay
        assert "the camera is inside the scene" in prompts.system("storyboard", look), look
        assert ("diorama", "paper scene") in prompts.look_banned(look), look
    assert "crisp crease lines" in prompts.style("paper-origami")["sections"]["still_look"]
    assert "photo cutout of the real product" in prompts.system("storyboard", "paper-collage")


def test_paper_footage_has_no_printed_words_and_repairs_keep_a_noun():
    """QA-5 on #1110: collage clippings and stamps put printed text in the footage, and
    "tabletop →" left "on a wooden, smiling"."""
    from app.prompts import check

    for look in ("paper", "paper-flat", "paper-handmade", "paper-collage", "paper-origami"):
        text = "\n".join(prompts.style(look)["sections"][k] for k in (*guides.TOKENS, "Clips"))
        for printed in ("newspaper", "magazine", "stamps", "newsprint", "clippings"):
            assert printed not in text.lower(), (look, printed)
        fixed = check.look_words("Mia sits on a wooden tabletop, smiling.", look)[0]
        assert fixed == "Mia sits on a wooden paper surface, smiling.", (look, fixed)
    assert "Every scrap is textless" in prompts.system("storyboard", "paper-collage")
    for s in prompts.styles():  # a noun is replaced, never deleted ("a wooden," behind)
        deleted = {w.lower() for w, new in prompts.look_banned(s["id"]) if not new}
        assert not deleted & {"tabletop", "table", "board", "diorama", "shadow box"}, s["id"]


def test_a_safeguard_after_nothing_is_never_rewritten():
    """Next-Lead on #1115: "Nothing gory, no blood." became "Nothing, no blood."."""
    from app.prompts import check

    for line in ("Nothing gory, no blood.", "Bones and glow, none of it gory."):
        assert check.look_words(line, "skeleton")[:2] == (line, []), line
    assert check.look_words("A gory scene.", "skeleton")[0] == "A scene."  # still repaired


def test_nothing_but_is_not_a_safeguard_and_collage_allows_story_text():
    """Next-Lead on #1120: "nothing but X" asks for X; and rule 32 lets a collage show a
    story-needed sign, 3D number or the product's label, stated exactly."""
    from app.prompts import check

    assert check.look_words("Nothing but gore here.", "skeleton")[0] == "Nothing but glow here."
    collage = prompts.style("paper-collage")["sections"]
    assert "printed words on any scrap" in collage["place_look"]
    assert "The product's own label, a 3D number or a sign the story needs" in collage["Stills"]
