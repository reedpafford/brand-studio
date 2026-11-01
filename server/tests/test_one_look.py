"""One look per style (Reed; the Director's plan): a style's lanes (Paper's Flat, Collage, …)
aren't cards; the plan picks the lane, and the video's look follows it while nothing is drawn
in the look yet and nobody picked the look themselves. A video on a lane id keeps working."""

import pytest
from fastapi import HTTPException

from app import looks, plans, prompts
from app.models.breakdowns import BreakdownVersion
from app.models.looks import LookSwitch
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from tests.test_enhance import setup  # noqa: F401 - fixture
from tests.test_looks import _a_file
from tests.test_storyboard import _with_breakdown

LANES = {s["id"] for s in prompts.styles() if s["kind"] == "lane"}


def test_a_lane_is_found_named_by_its_style_and_follows_its_switch(db, owner, editor):
    assert {"paper-flat", "claymation-goofy", "skeleton-xray"} <= LANES
    flat = looks.get("paper-flat")
    assert (flat["name"], flat["parent"]) == ("Paper · Flat Paper", "paper")
    assert looks.base("paper-flat") == "paper" and looks.base("paper") == "paper"
    with pytest.raises(HTTPException):
        looks.get("song")  # a format is neither
    cards = [c["id"] for c in editor.get("/looks").json()]
    assert not LANES & set(cards) and {"paper", "claymation", "skeleton"} <= set(cards)
    assert len(cards) == len(set(cards))  # one card per style
    paper = next(c for c in editor.get("/looks").json() if c["id"] == "paper")
    assert {"id": "paper-flat", "name": "Paper · Flat Paper"} in paper["lanes"]  # to name a video
    assert next(c for c in editor.get("/looks").json() if c["id"] == "house")["lanes"] == []
    ws = owner.get("/auth/me").json()["workspace_id"]
    assert not looks.is_on(db, ws, "paper-flat")
    db.add(LookSwitch(workspace_id=ws, look_id="paper", sample_still_id=_a_file(db),
                      sample_clip_id=_a_file(db), on=True))  # fmt: skip
    db.commit()
    assert looks.is_on(db, ws, "paper-flat")  # Paper's switch and sample are its lanes'


def _paper(db, setup, lane="paper-flat"):  # noqa: F811
    project = db.get(Project, setup["project"])
    project.look = "paper"
    db.commit()
    plan = {"structure": {"shape": "story", "lane": lane}, "cast": [], "scenes": []}
    return project, plan


def test_a_plans_lane_becomes_the_videos_look(db, setup):  # noqa: F811
    project, plan = _paper(db, setup)
    plans._set(project, plan, "by_hand", None, "")
    assert project.look == "paper-flat"
    other = {**plan, "structure": {"lane": "claymation-goofy"}}  # another style's lane
    project.look = "paper"
    plans._set(project, other, "by_hand", None, "")
    assert project.look == "paper"
    plans._set(project, {**plan, "structure": {"lane": ""}}, "by_hand", None, "")
    assert project.look == "paper"  # no lane: the look's own


def test_a_drawn_still_or_a_persons_pick_keeps_the_look(app, db, owner, editor, setup):  # noqa: F811
    _with_breakdown(app, db, editor, setup)
    project, plan = _paper(db, setup)
    bd = db.query(BreakdownVersion).filter_by(project_id=project.id).one()
    still = StoryboardFrame(
        project_id=project.id,
        breakdown_id=bd.id,
        clip_id="c1",
        shot_id="1.1",
        prompt="x",
        file_id=_a_file(db),
        look="paper",
    )
    db.add(still)
    db.commit()
    plans._set(project, plan, "by_hand", None, "")
    assert project.look == "paper"  # a still in the look: changing it would leave it out of date
    db.query(StoryboardFrame).delete()
    db.commit()
    picked = owner.patch(f"/projects/{project.id}", json={"look": "paper"})  # a person's pick
    assert picked.status_code == 200, picked.text
    db.expire_all()
    project = db.get(Project, setup["project"])
    plans._set(project, plan, "by_hand", None, "")
    assert project.look == "paper"
    assert editor.get(f"/projects/{project.id}/locks").status_code == 200  # still reads
