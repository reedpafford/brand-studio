"""Reed's skeleton-ad skill (#1095, now in app/guides/styles/skeleton): Skeleton and its
Style Library. Reed, 3 Nov (S1-S6, F6, from his six reference videos): the clear glass body
shell is the default, bare bones a lane, X-Ray folded into the shell, the Mascot in warm homes."""

from app import guides, looks, prompts

LOOKS = ("skeleton", "skeleton-bare", "skeleton-cute")


def ids_after(look: str) -> list[str]:
    """The look's own lanes, right after it in Reed's order."""
    ids = [s["id"] for s in prompts.styles()]
    at = ids.index(look)
    return [i for i in ids[at + 1 :] if i.startswith(f"{look}-")][: len(ids)]


def test_skeleton_has_reeds_style_library_and_strategy():
    """The glass shell by default (Dressed is its outfit), Bare-Bones and Mascot as lanes; the
    hook templates, three spines and the angle table; a shot per sentence or phrase. Never a
    studio name outside Disney Pixar."""
    assert ids_after("skeleton") == ["skeleton-bare", "skeleton-cute", "skeleton-xray"]
    glass = prompts.style("skeleton")["sections"]["sheet_look"]
    assert "clear, glossy, glass-like body shell" in glass
    bare = prompts.style("skeleton-bare")["sections"]["sheet_look"]
    assert "smooth ivory-cream bones with realistic bone detail" in bare
    assert "its bones are bare, with no outfit" in bare and "shell" not in bare
    assert "oversized round skull" in prompts.style("skeleton-cute")["sections"]["sheet_look"]
    assert "pastel" not in prompts.style("skeleton-cute")["sections"]["place_look"]
    for look in LOOKS:
        script = prompts.system("script_draft", look)
        assert "How many ___ does it take to ___?" in script and "(1, 5, 25, 42)" in script
        assert "transformation is one option, not the default" in script, look
        assert "One shot per sentence, or per phrase" in prompts.system("breakdown", look), look
        own = (*guides.TOKENS, "Stills", "Clips", "Breakdown", "Script")  # the site's own lines
        text = "\n".join(prompts.style(look)["sections"][k] for k in own)
        assert "pixar" not in text.lower(), look
        for part in ("pacing", "camera", "must keep", "safe to vary", "combines with"):
            assert prompts.style(look)["sections"][part], (look, part)  # lanes inherit them
    assert "never the default skeleton" in prompts.system("storyboard", "skeleton-cute")


def test_the_folded_xray_lane_is_hidden_and_draws_the_glass_shell():
    """A video already on X-Ray still loads, drawn in the glass shell; nobody picks it again."""
    xray = prompts.style("skeleton-xray")
    assert xray["hidden"] and xray["parent"] == "skeleton"
    for token in guides.TOKENS:
        assert xray["sections"][token] == prompts.style("skeleton")["sections"][token], token
    assert "skeleton-xray" not in prompts.style("skeleton")["sections"]["lanes"]
    assert "skeleton-xray" not in [x["id"] for x in looks.lanes("skeleton")]


def test_skeleton_repairs_keep_a_noun():
    """QA-5's paper finding, checked here too: "gore" was deleted ("blood and gore" → "blood
    and"); it is replaced."""
    from app.prompts import check

    for look in LOOKS:
        assert ("gore", "glow") in prompts.look_banned(look), look
        assert check.look_words("Bones, no gore.", look)[0] == "Bones, no gore."  # a safeguard
        assert check.look_words("Blood and gore.", look)[0] == "Glow and glow.", look
