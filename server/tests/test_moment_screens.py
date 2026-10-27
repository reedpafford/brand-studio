"""Reed's false blocker (2026-10-27): a CTA shot showing Home (rich) got "'fomo-mention' moment
without its screen". A moment now takes any screen of the same kind (any "home" screen), the
check is advice, never a block, and saved checks are said again on deploy."""

import json
from pathlib import Path

from app.models.breakdowns import BreakdownVersion
from app.prompts import check
from app.prompts.schemas import Breakdown
from app.seed import moment_problems
from tests.test_breakdown import BREAKDOWN, _shot
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture

SCREENS = {"screen:1": ["fomo-mention", "app-open"], "screen:2": ["win"], "screen:3": ["trading"]}
KINDS = {"screen:1": {"mobile", "home"}, "screen:2": {"mobile", "home", "portfolio"},
         "screen:3": {"mobile", "trading"}}  # fmt: skip


def _cta(screen: str):
    return (
        Breakdown.model_validate(
            {
                **BREAKDOWN,
                "scenes": [
                    {
                        **BREAKDOWN["scenes"][0],
                        "shots": [
                            _shot("1.1", [2, 3], "Mom", "Nate, where is all your money?", 2.5)
                            | {"moment": "fomo-mention", "screen_ids": [screen]},
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
    manifest = Path(__file__).parents[2] / "assets/brands/fomo/screens/screens.json"
    assert "fomo-mention" in json.loads(manifest.read_text())["home-rich.png"]["default_for"]


def test_a_saved_false_blocker_is_said_again_on_deploy(app, db, editor, setup):  # noqa: F811
    editor.post(f"/projects/{setup['project']}/breakdown")
    _run(app, db, FakeClaude(BREAKDOWN))
    row = db.query(BreakdownVersion).filter_by(project_id=setup["project"]).one()
    data = json.loads(json.dumps(BREAKDOWN))
    data["scenes"][0]["shots"][0]["moment"] = "trading"  # the Buy screen's moment, not shown
    row.data, row.problems = data, ["shot 1.1: 'trading' moment without its screen"]
    db.commit()
    assert moment_problems(db) == 1 and moment_problems(db) == 0  # once, then nothing to do
    assert db.get(BreakdownVersion, row.id).problems == [
        "Advice: shot 1.1: 'trading' moment without its screen"
    ]
