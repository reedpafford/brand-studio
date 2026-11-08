"""Reed’s Zack D (#1097, now its format and its style in app/guides). Reed, 3 Nov: "Follow
the originals" (realistic game-engine 3D on real sets, one continuous following camera)."""

from app import prompts


def test_zack_d_follows_the_originals_one_real_set_one_following_camera():
    """Reed, 3 Nov (Z1–Z5, F2): semi-realistic game-engine 3D on one real set (cyan optional),
    no hard cuts, glows on single parts, no podiums, 3D numerals or scale anchor, a gag
    ending and a brisk, continuous narrator."""
    zack = prompts.style("zack-d")["sections"]
    for part in ("sheet_look", "place_look", "still_look", "clip_style", "fit_look"):
        assert "semi-realistic 3d" in zack[part].lower(), part
        assert "stage" not in zack[part] and "blue world" not in zack[part], part
    assert zack["clip_style"].endswith("No captions")  # "Style: ….  No captions." every clip
    assert "No captions." in prompts.system("clip_prompts", "zack-d")
    assert (
        "never a hard cut" in zack["clip_style"]
        and "One continuous following camera" in zack["camera"]
    )
    board = prompts.system("breakdown", "zack-d")
    for part in ("Start mid-action", "two other distinct opening pictures", "rides the camera move",
                 "one small visual gag", "a new camera beat every 2–3 s"):  # fmt: skip
        assert part in board, part
    for gone in ("podium", "data object", "about every 4–8 s", "unhurried", "Colour is state",
                 "never changes while the world", "Captions ("):  # fmt: skip
        assert gone not in board, gone
    still = prompts.system("storyboard", "zack-d")
    for part in ("The best visual wins; the video's one set is home", "Colour marks the part",
                 "Graphics are objects, never overlays"):  # fmt: skip
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
