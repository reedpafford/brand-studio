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


def test_a_saved_false_blocker_is_said_again_on_deploy(app, db, editor, setup):  # noqa: F811
    editor.post(f"/projects/{setup['project']}/breakdown")
    _run(app, db, FakeClaude(BREAKDOWN))
    row = db.query(BreakdownVersion).filter_by(project_id=setup["project"]).one()
    data = json.loads(json.dumps(BREAKDOWN))
    data["scenes"][0]["shots"][0]["moment"] = "trading"  # the Buy screen's moment, not shown
    row.data, row.problems = data, ["shot 1.1: 'trading' moment without its screen"]
    db.commit()
    assert moment_problems(db) == (1, 0) and moment_problems(db) == (0, 0)  # once, then nothing
    assert db.get(BreakdownVersion, row.id).problems == [
        "Advice: shot 1.1: 'trading' moment without its screen"
    ]


def test_a_deleted_plan_is_skipped_on_deploy(db, owner):
    """A version whose plan was deleted holds JSON null, which SQL's is_not(None) lets through
    (#565's deploy crashed on it): the repair skips it."""
    from sqlalchemy import text

    from app.models.script_library import ScriptDraft
    from tests.test_script_library import SCRIPT, _make

    made = _make(owner, text=SCRIPT)
    draft = db.query(ScriptDraft).filter_by(script_id=made["id"]).first()
    draft.breakdown_problems = ["shot 1.1: 'trading' moment without its screen"]
    db.commit()
    db.execute(text("UPDATE script_drafts SET breakdown = 'null' WHERE id = :id"), {"id": draft.id})
    db.commit()
    assert moment_problems(db) == (0, 0)


def test_the_repair_finds_the_check_in_its_said_form(app, db, editor, setup):  # noqa: F811
    """As people read it, a check can start "Shot 6.11" (a clip id dropped, then capitalised):
    the repair still finds it. One it can't read is counted as still blocking, for the log."""
    editor.post(f"/projects/{setup['project']}/breakdown")
    _run(app, db, FakeClaude(BREAKDOWN))
    row = db.query(BreakdownVersion).filter_by(project_id=setup["project"]).one()
    data = json.loads(json.dumps(BREAKDOWN))
    data["scenes"][0]["shots"][0]["moment"] = "trading"
    row.data, row.problems = data, ["Shot 1.1: 'trading' moment without its screen"]
    db.commit()
    assert moment_problems(db) == (1, 0)
    assert db.get(BreakdownVersion, row.id).problems == [
        "Advice: shot 1.1: 'trading' moment without its screen"
    ]
    row.problems = ["shot 9.9 (deleted): 'win' moment without its screen"]  # unreadable
    db.commit()
    assert moment_problems(db) == (0, 1)
