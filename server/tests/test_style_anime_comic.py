"""Reed’s anime-comic skill (#1097, now in app/guides/styles/anime-comic)."""

from app import guides, prompts


def test_anime_comic_holds_reeds_skill():
    """Reed's anime-comic skill (#1097): one original graphic language set
    once, strong key poses, effects only when they serve the shot, no protected characters."""
    look = prompts.style("anime-comic")["sections"]
    assert "set once here and held in every shot" in look["sheet_look"]
    assert "franchise symbol" in look["sheet_look"] and "round the whole frame" in look["Stills"]
    assert "never several panels, a grid or a split frame" in look["Stills"]  # one image a shot
    own = (*guides.TOKENS, "Stills", "Clips", "Breakdown")  # the site's own lines
    for split in ("side-by-side", "panel-by-panel", "panel border"):
        assert split not in "\n".join(look[k] for k in own), split
    breakdown = prompts.system("breakdown", "anime-comic")
    assert "a power-up that shows how the product works" in breakdown
