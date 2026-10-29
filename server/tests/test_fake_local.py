"""Local runs with stand-in providers (BS_FAKE_PROVIDERS): a project goes from script to a
clip take without any real call, and with generation switched off."""

from sqlalchemy import select

from app.models.files import StoredFile
from app.models.jobs import Job, JobStatus
from app.providers import get_providers
from app.providers.replicate import ReplicateProvider
from app.settings import Settings
from app.worker import run_once
from tests.test_enhance import setup  # noqa: F401 - fixture


def _drain(app, db, providers):
    for _ in range(5):
        run_once(db, providers, app.state.storage)
    waiting = db.scalars(select(Job).where(Job.status != JobStatus.succeeded)).all()
    assert not waiting, [(j.id, j.status, j.error_detail) for j in waiting]


def test_script_to_clip_take_with_stand_ins(app, db, editor, setup):  # noqa: F811
    app.state.settings.generation_enabled = False
    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings)
    assert not (providers["replicate"].paid or providers["claude"].paid)
    url = f"/projects/{setup['project']}"

    assert editor.post(f"{url}/breakdown").status_code == 201
    _drain(app, db, providers)
    bd = editor.get(f"{url}/breakdown").json()
    assert bd["breakdown"]["clips"] and not [p for p in bd["problems"] if "last line" not in p]

    assert editor.post(f"{url}/storyboard", json={"per_shot": False}).status_code == 201
    _drain(app, db, providers)
    for frame in editor.get(f"{url}/storyboard").json():
        assert editor.post(f"{url}/storyboard/frames/{frame['id']}/render").status_code == 201
        _drain(app, db, providers)
        assert editor.post(f"{url}/storyboard/frames/{frame['id']}/approve").status_code == 200

    assert editor.post(f"{url}/clips/prompts").status_code == 201
    _drain(app, db, providers)
    clips = editor.get(f"{url}/clips").json()
    assert clips and all(c["problems"] == [] for c in clips), clips
    assert '"Nate, where is all your money?"' in clips[0]["prompt"]
    take = editor.post(f"{url}/clips/{clips[0]['id']}/generate")
    assert take.status_code == 201, take.text
    _drain(app, db, providers)
    job = db.get(Job, take.json()["id"])
    video = db.get(StoredFile, job.output["file_ids"][0])
    assert video.content_type == "video/mp4" and video.size > 1000
    assert job.credits > 0  # the estimate stands; no fake dollars are recorded


def test_real_providers_unless_switched_on():
    assert isinstance(get_providers(Settings())["replicate"], ReplicateProvider)
