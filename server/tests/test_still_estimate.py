"""A still is priced the way its job charges (Next-Lead, after the price-check sweep): the
video's picture model and the still's size come from one place (storyboard.still_input and
still_credits), so the estimate's storyboard row, Update everything after this and a frame's
own price can't drift from the job. On the stand-ins (no paid calls)."""

import pytest

from app import update_after
from app.credits import price
from app.models.jobs import Job
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.providers import get_providers
from tests.test_enhance import setup  # noqa: F401 - fixture
from tests.test_fake_local import _drain


@pytest.mark.parametrize("model", ["nano-banana-2.1", "nano-banana-pro"])
@pytest.mark.parametrize("shape", ["9:16", "16:9"])
def test_a_stills_estimate_is_its_jobs_charge(app, db, editor, setup, model, shape):  # noqa: F811
    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings, app.state.storage)
    url = f"/projects/{setup['project']}"
    project = db.get(Project, setup["project"])
    project.image_model, project.aspect_ratio = model, shape  # the video's picks (VS1)
    db.commit()
    editor.post(f"{url}/breakdown")
    _drain(app, db, providers)
    editor.post(f"{url}/storyboard", json={"per_shot": False})
    _drain(app, db, providers)
    frames = editor.get(f"{url}/storyboard").json()
    stages = {s["stage"]: s for s in editor.get(f"{url}/estimate").json()["stages"]}
    per_still = stages["storyboard"]["credits"] / len(frames)  # its frames are written: stills

    since = db.query(Job.id).order_by(Job.id.desc()).limit(1).scalar()
    assert editor.post(f"{url}/storyboard/frames/{frames[0]['id']}/render").status_code == 201
    _drain(app, db, providers)
    (drawn,) = db.query(Job).filter(Job.id > since).all()
    assert drawn.input["model"] == model and drawn.input["input"]["aspect_ratio"] == shape
    assert per_still == pytest.approx(float(drawn.credits))  # the estimate is the charge
    db.expire_all()
    project = db.get(Project, setup["project"])
    assert update_after._still(db, project) == drawn.credits  # the video's model, not Auto's
    shown = next(f for f in editor.get(f"{url}/storyboard").json() if f["id"] == frames[0]["id"])
    assert shown["still_credits"] == price(drawn.credits)
    assert db.get(StoryboardFrame, frames[0]["id"]).file_id  # it was drawn
