"""flows 1b: the advisory check on a still or a take (P4), and P3's free on-screen text fix."""

from app import prompts
from app.prompts import check
from app.prompts.schemas import Finding, ItemCheck

AUDIO = "Audio: no one speaks (no voices, narration or dialogue), only a kitchen. No subtitles."


def test_on_screen_words_are_taken_out_but_never_a_spoken_line_or_the_brands_label():
    prompt = "\n".join([
        AUDIO,
        "Shot 1 | 0-2 s. Close-up. He licks the bowl; a text overlay reads DAY 1. No one speaks.",
        'Shot 2 | 2-4 s. Title card: Weeks later. Mom smiles. Mom: "Captions are silly, right?"',
        "Shot 3 | 4-6 s. The bag on the counter, label to camera, logo text sharp. No one speaks.",
        "Shot 4 | 6-8 s. Close-up. The fomo logo reads sharp, the label legible. No one speaks.",
        AUDIO,
    ])  # fmt: skip
    fixed, removed = check.text_on_screen(prompt)
    assert removed == ["text overlay", "Title card", "logo text"]
    assert fixed.splitlines() == [
        AUDIO,
        "Shot 1 | 0-2 s. Close-up. He licks the bowl. No one speaks.",
        'Shot 2 | 2-4 s. Mom smiles. Mom: "Captions are silly, right?"',
        "Shot 3 | 4-6 s. The bag on the counter, label to camera. No one speaks.",
        "Shot 4 | 6-8 s. Close-up. The fomo logo reads sharp, the label legible. No one speaks.",
        AUDIO,
    ]
    assert check.text_on_screen(fixed) == (fixed, [])  # doing it again changes nothing
    curly = check.text_on_screen("Shot 1 | 0-2 s. A caption pops up, Mom: “Hi, you.” No one else.")
    assert curly == ("Shot 1 | 0-2 s. Mom: “Hi, you.” No one else.", ["caption"])


def test_the_item_check_is_advice_about_the_references_it_was_given():
    assert prompts.SCHEMAS["item_check"] is ItemCheck and "item_check" in prompts.NO_RULES
    assert "pass" not in ItemCheck.model_fields and "fits" not in ItemCheck.model_fields
    text = prompts.system("item_check")
    for part in ("**Face:**", "**Outfit:**", "**Product**", "When in doubt, it's fine"):
        assert part in text, part
    message = prompts.item_check_input(
        "Biscuit licks the bowl", [("char:1", "Biscuit: fawn Frenchie, red bandana")],
        ("product:1", "Iron Paws peanut butter bag"), frames=3,
    )  # fmt: skip
    assert "<item>Images 1–3 are frames of one take, in order.</item>" in message
    assert (
        '<sheet image="4" id="char:1">' in message
        and '<product image="5" id="product:1">' in message
    )
    assert "<item>Image 1 is the still.</item>" in prompts.item_check_input("x", [("char:1", "B")])

    def f(kind, who):
        return Finding(kind=kind, who=who, says="s", note="n")

    found = ItemCheck(findings=[f("face", "char:1"), f("product", "product:1"),
                                f("face", "char:9"), f("product", "char:1")])  # fmt: skip
    kept = check.item_check(found, ["char:1"])  # no product image given
    assert [(x.kind, x.who) for x in kept.findings] == [("face", "char:1")]
