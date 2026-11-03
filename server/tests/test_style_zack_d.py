"""Reed’s Zack D skill (#1097, now its format and its style in app/guides; Reed: "Skill,
drop realistic")."""

from app import prompts


def test_zack_d_follows_reeds_skill_a_blue_world_journey():
    """Reed, 1 Nov: "Skill, drop realistic" (#1097): a friendly 3D
    look on an infinite blue world, one continuous camera journey under a calm narrator."""
    zack = prompts.style("zack-d")["sections"]
    for part in ("place_look", "still_look", "clip_style"):
        assert "infinite bright cyan-blue world" in zack[part], part
        assert "semi-realistic" not in zack[part].lower() and "stage" not in zack[part], part
    world = "This world is an infinite canvas: it continues unbroken past every edge of the frame"
    assert world in zack["still_look"] and "no grid lines anywhere" in zack["still_look"]
    assert zack["clip_style"].endswith("No captions")  # "Style: ….  No captions." every clip
    assert "No captions." in prompts.system("clip_prompts", "zack-d")
    board = prompts.system("breakdown", "zack-d")
    for part in ("podium, prop island, macro cutaway, data object", "about every 4–8 s",
                 "two other distinct opening pictures", "rides the camera move"):  # fmt: skip
        assert part in board, part
    still = prompts.system("storyboard", "zack-d")
    for part in (
        "The best visual wins; the blue world is home",
        "Colour is state",
        "Graphics are objects, never overlays",
        "never changes while the world",
    ):
        assert part in still, part
    assert ("on the stage", "in the world") in prompts.look_banned("zack-d")
    from app.prompts import check

    # QA-5 on #1122: repairs are phrase-level, only where "stage" means the set.
    assert check.look_words("He stands on the stage.", "zack-d")[0] == "He stands in the world."
    kept_as_written = (
        "At this stage the price doubles.",
        "Stage 1: the savings jar fills.",
        "His thumb hovers over Sell.",
        "The drone is hovering above the podium.",
        "Dust floating in the light.",
    )
    for kept in kept_as_written:
        assert check.look_words(kept, "zack-d")[0] == kept, kept
