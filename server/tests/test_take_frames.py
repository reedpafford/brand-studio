"""Take check slice 2, frames (take-review checklist B3–B5): the take's picture check looks at
a strip of frames for eyes, the brand's screens and the cast, on the free stand-in writer."""

from decimal import Decimal

import pytest
from sqlalchemy.orm.attributes import flag_modified

from app.models.brands import Brand, BrandScreen
from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job
from app.models.projects import Project
from tests.conftest import run_writer
from tests.test_clip_takes import FakeSeedance, _mp4, _work, clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture


@pytest.fixture(autouse=True)
def checks_on(monkeypatch):
    monkeypatch.setattr("app.item_checks.on", lambda: True)  # as on the test site's stand-ins


def _shot(db, **change):
    """Change the first shot of the video's breakdown (what the take shows)."""
    row = db.query(BreakdownVersion).one()
    row.data["scenes"][0]["shots"][0].update(change)
    flag_modified(row, "data")
    db.commit()


def _check(app, db, editor, setup, clip):  # noqa: F811
    clips = f"/projects/{setup['project']}/clips"
    editor.post(f"{clips}/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    return clips, db.query(Job).filter(Job.kind == "check-claude").one()


def test_a_take_is_a_strip_with_its_cast_at_its_price(app, db, editor, setup, clip):  # noqa: F811
    _, job = _check(app, db, editor, setup, clip)
    assert job.input["take_frames"]["count"] == 6
    assert "Images 1–6 are frames of one take" in job.input["prompt"]
    assert "<cast>Mom</cast>" in job.input["prompt"]
    assert job.credits == Decimal("0.6")  # three looks' worth, held as its "up to"
    assert "<screens>" not in job.input["prompt"]  # the shot shows no brand screen


def test_a_shown_screen_goes_with_its_rules(app, db, editor, setup, clip):  # noqa: F811
    project = db.get(Project, setup["project"])
    db.get(Brand, project.brand_id).tone_notes = "Fun.\nThe fomo screen only ever shows wins."
    screen = db.get(BrandScreen, setup["screen"])
    screen.product, screen.tags = "", ["app"]  # the brand's app, not a product
    _shot(db, screen_ids=[f"screen:{screen.id}"])
    _, job = _check(app, db, editor, setup, clip)
    prompt = job.input["prompt"]
    assert f'id="screen:{screen.id}"' in prompt and "<screens>" in prompt
    assert "<screen_rules>\nThe fomo screen only ever shows wins.\n</screen_rules>" in prompt
    assert f"screen:{screen.id}" in job.input["ref_ids"]  # so a screen finding is kept


def test_eyes_extra_people_and_screens_are_advice(app, db, editor, setup, clip):  # noqa: F811
    screen = db.get(BrandScreen, setup["screen"])
    screen.product, screen.tags = "", ["app"]
    _shot(db, action="They argue. fake:eyes fake:extra-person fake:screen",
          screen_ids=[f"screen:{screen.id}"])  # fmt: skip
    clips, _ = _check(app, db, editor, setup, clip)
    run_writer(app, db)
    (take,) = editor.get(clips).json()[0]["takes"]
    kinds = [f["kind"] for f in take["check"]["findings"]]
    assert kinds == ["face", "eyes", "cast", "screen"]
    eyes = take["check"]["findings"][1]
    assert eyes["note"] == "Keep normal human eyes the whole time, never glowing or red."
    assert take["verdict"] == "flagged"
