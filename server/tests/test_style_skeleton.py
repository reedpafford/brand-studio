"""Reed's skeleton-ad skill (docs/next/skills/skeleton-ad.md, #1095): Skeleton and its
Style Library (X-Ray, Mascot)."""

from app import prompts


def ids_after(look: str) -> list[str]:
    """The look's own lanes, right after it in Reed's order."""
    ids = [s["id"] for s in prompts.styles()]
    at = ids.index(look)
    return [i for i in ids[at + 1 :] if i.startswith(f"{look}-")][: len(ids)]


def test_skeleton_has_reeds_style_library_and_strategy():
    """Reed's skeleton-ad skill (docs/next/skills, #1095): Bare-Bones by default (Dressed is
    its outfit), X-Ray and Mascot as their own looks; the hook templates, three spines and the
    angle table; one line, one shot, one rung. Never a studio name outside Disney Pixar."""
    assert ids_after("skeleton") == ["skeleton-xray", "skeleton-cute"]
    bare = prompts.style("skeleton")["sections"]["sheet_look"]
    assert "smooth ivory-cream bones with realistic bone detail" in bare
    assert "organs (heart, lungs, intestines) glowing" in prompts.style("skeleton-xray")[
        "sections"]["sheet_look"]  # fmt: skip
    assert "oversized round skull" in prompts.style("skeleton-cute")["sections"]["sheet_look"]
    for look in ("skeleton", "skeleton-xray", "skeleton-cute"):
        script = prompts.system("script_draft", look)
        assert "How many ___ does it take to ___?" in script and "(1, 5, 25, 42)" in script
        assert "transformation is one option, not the default" in script, look
        assert "One line is one shot is one rung" in prompts.system("breakdown", look), look
        text = "\n".join(prompts.style(look)["sections"].values())
        assert "pixar" not in text.lower(), look
    assert "never the default skeleton" in prompts.system("storyboard", "skeleton-cute")


def test_skeleton_repairs_keep_a_noun():
    """QA-5's paper finding, checked here too: "gore" was deleted ("blood and gore" → "blood
    and"); it is replaced."""
    from app.prompts import check

    for look in ("skeleton", "skeleton-xray", "skeleton-cute"):
        assert ("gore", "glow") in prompts.look_banned(look), look
        assert check.look_words("Bones, no gore.", look)[0] == "Bones, no gore."  # a safeguard
        assert check.look_words("Blood and gore.", look)[0] == "Glow and glow.", look
