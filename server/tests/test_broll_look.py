"""A hosted video's B-roll look (n31, v6 S-gaps-01 option 1): the B-roll is drawn, checked and
modelled in another style's look while the host, voice and cast keep the video's own; the
briefed steps get both guides as Reed wrote them. Stand-ins only."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import guides, host, looks, prompts
from app.breakdown import video_model
from app.models.accounts import User
from app.models.jobs import Job
from app.models.looks import LookSwitch
from app.models.storyboards import StoryboardFrame
from tests.conftest import first_brand
from tests.test_freestyle_dialogue import BODY, _run
from tests.test_freestyle_song import NARRATION, _sent
from tests.test_host import _jobs, _video


@pytest.fixture(autouse=True)
def songs_on(monkeypatch, app):
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)


def test_the_brief_carries_both_guides_and_the_shots_are_drawn_in_the_b_roll_look():
    plain = guides.brief("presenter", "house", "storyboard")
    both = guides.brief("presenter", "house", "storyboard", "skeleton")
    assert "## Style: House\n" in plain and "B-roll look" not in plain
    assert "## Style: House (the host, the voice and the cast)" in both
    assert "## B-roll look: Skeleton" in both
    for _, text in guides.guidance(guides.style("skeleton")["sections"]):
        assert text in both  # Skeleton's guide as Reed wrote it
    for _, text in guides.guidance(guides.style("house")["sections"]):
        assert text in both  # and House's, for the host and what it must keep
    shots = prompts.system("storyboard", "house", "narrated", "presenter", "skeleton")
    assert guides.tokens("skeleton")["still_look"] in shots
    assert prompts.system("script_draft", "house", broll="skeleton") == prompts.system(
        "script_draft", "house")  # a script step has no B-roll  # fmt: skip


def test_a_presenters_b_roll_is_made_in_its_b_roll_look_and_the_host_in_its_style(app, db, owner):
    fs = _sent(owner, "presenter", NARRATION)
    video = _video(db, fs)
    url = f"/projects/{video.id}/settings"
    assert owner.post(url, json={"broll_look": "nope"}).status_code == 422
    seen = owner.post(f"{url}/preview", json={"broll_look": "skeleton"})
    assert seen.status_code == 200, seen.text
    switched = owner.post(url, json={"broll_look": "skeleton"})
    assert switched.status_code == 200, switched.text
    assert switched.json()["settings"]["broll_look"] == "skeleton"
    assert switched.json()["was"] == {"broll_look": None}
    db.expire_all()
    video = _video(db, fs)
    assert looks.drawn(video) == "skeleton" and video.look == "house"
    assert video_model(video).id == guides.style("skeleton")["video_model"]  # B-roll's model
    _run(app, db, ticks=160)
    out = owner.get(f"/freestyles/{fs['id']}").json()
    assert out["status"] == "delivered", [t["text"] for t in out["thread"]]
    frames = db.query(StoryboardFrame).filter_by(project_id=video.id).all()
    assert frames and {f.look for f in frames} == {"skeleton"}
    (still,) = _jobs(db, video, host.STILL)
    assert guides.tokens("house")["sheet_look"] in still.input["input"]["prompt"]  # the host
    briefed = [j for j in db.query(Job).filter(Job.project_id == video.id)
               if j.input.get("step") == "storyboard"]  # fmt: skip
    for job in briefed:
        assert "## B-roll look: Skeleton" in "".join(job.input["system"])
    assert briefed
    refused = owner.post(url, json={"broll_look": None})  # every still and take again
    assert refused.status_code == 409 and "budget" in refused.text
    back = owner.post(url, json={"broll_look": None, "undo": True}).json()
    assert back["settings"]["broll_look"] is None  # "Back to the style's own"
    db.expire_all()
    assert _video(db, fs).broll_look is None
    seen = owner.post(f"{url}/preview", json={"broll_look": "skeleton"}).json()
    assert seen["stills_out_of_date"] == 0  # the skeleton stills are current again in it


def test_only_a_video_with_a_host_has_a_b_roll_look_and_an_editor_picks_one_thats_on(
    db, owner, editor
):
    fs = owner.post("/freestyles", json={**BODY, "brand_id": first_brand(owner)}).json()
    refused = owner.post(f"/projects/{fs['project_id']}/settings", json={"broll_look": "skeleton"})
    assert refused.status_code == 409 and refused.json()["detail"] == looks.BROLL_HOSTED
    video = _video(db, _sent(owner, "presenter", NARRATION))
    same = owner.post(f"/projects/{video.id}/settings", json={"broll_look": "house"}).json()
    assert same["settings"]["broll_look"] is None  # the style's own reads as none
    kel = db.query(User).filter(User.name == "Ed").one()
    with pytest.raises(HTTPException) as off:  # Skeleton is off for editors until switched on
        looks.pick_broll(db, kel, video, "skeleton")
    assert off.value.status_code == 409


def test_a_talkers_clip_keeps_the_style_and_a_b_roll_look_the_style_became_is_its_own():
    video = SimpleNamespace(look="house", broll_look="skeleton", video_model=None)
    assert looks.take_look(video, SimpleNamespace(made_with={"talker": 7})) == "house"  # the host
    assert looks.take_look(video, SimpleNamespace(made_with={})) == "skeleton"  # B-roll
    assert looks.drawn(SimpleNamespace(look="skeleton-bare", broll_look="skeleton")) == (
        "skeleton-bare")  # the style is now Skeleton (its plan's lane): its own again  # fmt: skip
    assert (
        video_model(video, "house", "story").id == guides.style("skeleton")["video_model"]
    )  # quotes too


def test_an_editor_picks_a_b_roll_look_thats_on_never_a_lane(db, owner, editor):
    video = _video(db, _sent(owner, "presenter", NARRATION))
    kel = db.query(User).filter(User.name == "Ed").one()
    db.add(LookSwitch(workspace_id=kel.workspace_id, look_id="skeleton", on=True))
    db.flush()
    assert looks.pick_broll(db, kel, video, "skeleton") == "skeleton"
    with pytest.raises(HTTPException) as lane:
        looks.pick_broll(db, kel, video, "claymation-goofy")
    assert lane.value.status_code == 422
