"""Take check slice 2, frames (take-review checklist B3–B5): the take's picture check looks at
a strip of frames for eyes, the brand's screens and the cast, on the free stand-in writer."""

import itertools
import re
import subprocess
from decimal import Decimal

import pytest
from sqlalchemy.orm.attributes import flag_modified

from app import take_frames
from app.item_checks import _cast
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
    assert re.search(r"<cast>Mom \(char:\d+\)</cast>", job.input["prompt"])  # a name, by id
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


def test_a_cast_name_thats_also_a_word_reads_as_a_person():
    line = "char:12 | character | date | plays the alien date | Sheet sets the look."
    assert _cast("char:12", line) == "date (char:12, the alien date)"  # not "his date"
    assert _cast("slot:3", "slot:3 | character | Omar | A rival") == "Omar (slot:3)"


def test_frames_sit_on_the_boundaries_spread_out_or_filled_in_evenly():
    assert take_frames.moments(6.0, [], 6) == [0.0, 1.14, 2.28, 3.42, 4.56, 5.7]  # none: even
    shown = take_frames.moments(6.0, [2.0, 2.05, 4.0], 6)  # a cut, a line just after, a cut
    assert [2.15, 2.2, 4.15] == [t for t in shown if t in (2.15, 2.2, 4.15)]
    assert len(shown) == 6 and shown == sorted(shown) and shown[-1] <= 5.7
    many = take_frames.moments(6.0, [n * 0.25 for n in range(24)], 6)  # more than 6: spread
    assert len(many) == 6 and min(b - a for a, b in itertools.pairwise(many)) >= 0.75


def test_a_quick_cut_and_a_line_after_a_pause_are_found(tmp_path):
    src = tmp_path / "take.mp4"
    args = ["-v", "error", "-f", "lavfi", "-i", "color=c=red:s=64x64:d=1.2", "-f", "lavfi",
            "-i", "color=c=blue:s=64x64:d=1.8", "-f", "lavfi", "-i",
            "sine=frequency=440:duration=3,volume=enable='lt(t,1.5)':volume=0",
            "-filter_complex", "[0:v][1:v]concat=n=2:v=1[v]", "-map", "[v]", "-map", "2:a",
            "-c:v", "libx264", "-c:a", "aac", str(src)]  # fmt: skip
    subprocess.run(["ffmpeg", *args], check=True)  # noqa: S603, S607
    assert [round(t, 1) for t in take_frames.cuts(src)] == [1.2]  # red to blue
    assert [round(t, 1) for t in take_frames.starts(None, None, src)] == [1.5]  # no words yet


def test_a_cast_finding_is_dropped_when_no_cast_was_sent(app, db, editor, setup, clip):  # noqa: F811
    _shot(db, character_ids=[], action="A bag on the counter. fake:extra-person")
    clips, job = _check(app, db, editor, setup, clip)
    assert job.input["cast"] is False and "<cast>" not in job.input["prompt"]
    run_writer(app, db)
    (take,) = editor.get(clips).json()[0]["takes"]
    assert "cast" not in [f["kind"] for f in (take["check"] or {}).get("findings", [])]
