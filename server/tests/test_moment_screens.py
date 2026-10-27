"""Reed's false blocker (2026-10-27): a CTA shot showing Home (rich) got "'fomo-mention' moment
without its screen". A moment now takes any screen of the same kind (any "home" screen), the
check is advice, never a block."""

import json
from pathlib import Path

from app.prompts import check
from app.prompts.schemas import Breakdown
from tests.test_breakdown import BREAKDOWN, _shot
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture

SCREENS = {"screen:1": ["fomo-mention", "app-open"], "screen:2": ["win"], "screen:3": ["trading"]}
KINDS = {"screen:1": {"mobile", "home"}, "screen:2": {"mobile", "home", "portfolio", check.BALANCE},
         "screen:3": {"mobile", "trading"}}  # fmt: skip


def _cta(screen: str, moment: str = "fomo-mention"):
    return (
        Breakdown.model_validate(
            {
                **BREAKDOWN,
                "scenes": [
                    {
                        **BREAKDOWN["scenes"][0],
                        "shots": [
                            _shot("1.1", [2, 3], "Mom", "Nate, where is all your money?", 2.5)
                            | {"moment": moment, "screen_ids": [screen]},
                            _shot("1.2", [4], "Nate", "I bought the dip.", 1.5),
                        ],
                    }
                ],
            }  # fmt: skip
        )
        .scenes[0]
        .shots[0]
    )


def test_a_moment_takes_any_screen_of_its_kind_and_never_blocks():
    assert check.moment_screen(_cta("screen:2"), SCREENS, KINDS) == ""  # Home (rich) is a home
    said = check.moment_screen(_cta("screen:3"), SCREENS, KINDS)  # a chart is not
    assert said == "Advice: shot 1.1: 'fomo-mention' moment without its screen"
    # QA: the win needs the balance on screen, so plain Home (no balance) doesn't stand in.
    assert check.moment_screen(_cta("screen:1", "win"), SCREENS, KINDS).startswith("Advice: ")
    manifest = Path(__file__).parents[2] / "assets/brands/fomo/screens/screens.json"
    assert "fomo-mention" in json.loads(manifest.read_text())["home-rich.png"]["default_for"]


def test_the_brand_block_says_one_screen_is_enough_for_a_moment():
    from app.prompts import brand_block

    home = {"id": 1, "name": "Home", "tags": ["home"], "default_for": ["fomo-mention"]}
    rich = {
        "id": 2,
        "name": "Home (rich)",
        "tags": ["home"],
        "default_for": ["win", "fomo-mention"],
    }
    screens = [home, rich]
    block = brand_block({"name": "fomo"}, screens)
    assert "At fomo-mention, one of these is enough: Home or Home (rich)." in block
    assert "At win, one" not in block  # one screen: nothing to choose
