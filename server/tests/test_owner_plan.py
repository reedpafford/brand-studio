"""The owner's scene plan on a script version (flows S6, 1b), on the free stand-in writer."""

from app.models.jobs import Job
from app.providers.fake_local import FakeWriter
from app.worker import run_once
from tests.test_script_library import SCRIPT, _make


def _write(app, db):
    run_once(db, {"claude": FakeWriter()}, app.state.storage, only={"claude"})


def test_the_owners_plan_is_each_new_videos_start(app, owner, editor, db):
    base = f"/scripts/{_make(owner, text=SCRIPT)['id']}"
    url = f"{base}/drafts/0/plan"
    assert owner.get(url).status_code == 404  # no plan yet
    job = owner.post(url, json={}).json()
    assert db.get(Job, job["id"]).project_id is None  # the version's, from the author's week
    assert owner.get(url).json()["job"]["status"] == "queued"
    _write(app, db)
    plan = owner.get(url).json()
    assert plan["status"] == "ready" and plan["scenes"] and plan["earlier"] == []
    assert owner.post(f"{url}/approve").json()["status"] == "approved"

    preview = owner.post(f"{base}/drafts/0/breakdown").json()  # the preview films the plan
    queued = db.get(Job, preview["id"])
    assert "<plan>" in queued.input["prompt"] and queued.input["plan_version"] == plan["version"]
    db.delete(queued)
    db.commit()

    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    final = owner.put(url, json={"scenes": []})
    assert final.status_code == 409 and "published" in final.json()["detail"]  # rule 31
    assert editor.get(url).json()["status"] == "approved"  # read only, for everyone

    made = editor.post(f"{base}/drafts/0/produce").json()
    pid = made["project_id"]
    video = editor.get(f"/projects/{pid}/plan").json()
    assert (video["status"], video["source"]) == ("approved", "owner")  # "From Reed's plan"
    assert editor.get(f"/projects/{pid}").json()["plan_status"] == "approved"
    shots = db.get(Job, made["breakdown_job_id"])
    assert "<plan>" in shots.input["prompt"]  # its shots are made from the owner's plan
