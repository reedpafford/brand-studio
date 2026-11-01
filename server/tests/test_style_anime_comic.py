"""Reed's anime-comic skill (docs/next/skills/anime-comic.md, #1097)."""

from app import prompts


def test_anime_comic_holds_reeds_skill():
    """Reed's anime-comic skill (docs/next/skills, #1097): one original graphic language set
    once, strong key poses, effects only when they serve the shot, no protected characters."""
    look = prompts.style("anime-comic")["sections"]
    assert "set once here and held in every shot" in look["sheet_look"]
    assert "franchise symbol" in look["sheet_look"] and "round the whole frame" in look["still"]
    assert "never several panels, a grid or a split frame" in look["still"]  # one image a shot
    for split in ("side-by-side", "panel-by-panel", "panel border"):
        assert split not in "\n".join(look.values()), split
    breakdown = prompts.system("breakdown", "anime-comic")
    assert "a power-up that shows how the product works" in breakdown
