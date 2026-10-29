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


def test_a_preview_made_before_the_plan_never_starts_the_video(app, owner, editor, db):
    """Flow-QA on #934: preview → plan → approve → publish. The old preview is "Made for an
    older plan", and Make this version makes the shots again from the plan (paid), never the
    old ones; a preview made from the plan lands free and knows its plan."""
    from tests.test_breakdown import BREAKDOWN
    from tests.test_enhance import FakeClaude, _run

    base = f"/scripts/{_make(owner, text=SCRIPT)['id']}"
    url = f"{base}/drafts/0/plan"
    owner.put(f"{base}/drafts/0/breakdown", json=BREAKDOWN)  # the preview, before any plan
    owner.post(url, json={})
    _write(app, db)
    owner.post(f"{url}/approve")
    version = next(v for v in owner.get(base).json()["versions"] if v["slot"] == 0)
    assert version["preview_older_plan"] is True  # "Make the preview again"
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    made = editor.post(f"{base}/drafts/0/produce").json()
    shots = db.get(Job, made["breakdown_job_id"])  # paid, from Reed's plan
    assert "<plan>" in shots.input["prompt"] and shots.input["plan_version"] == 1

    again = f"/scripts/{_make(owner, text=SCRIPT)['id']}"
    plan = f"{again}/drafts/0/plan"
    owner.post(plan, json={})
    _write(app, db)
    owner.post(f"{plan}/approve")
    owner.post(f"{again}/drafts/0/breakdown")  # the preview films the approved plan
    _run(app, db, FakeClaude(BREAKDOWN))
    version = next(v for v in owner.get(again).json()["versions"] if v["slot"] == 0)
    assert version["has_breakdown"] and version["preview_older_plan"] is False
    owner.post(f"{again}/drafts/0/approve")
    owner.post(f"{again}/publish")
    made = editor.post(f"{again}/drafts/0/produce").json()
    assert made["breakdown_job_id"] is None  # free: the preview follows the plan
    landed = editor.get(f"/projects/{made['project_id']}/breakdown").json()
    assert landed["older_plan"] is False
    from app.models.breakdowns import BreakdownVersion

    row = db.query(BreakdownVersion).filter_by(project_id=made["project_id"]).one()
    assert row.data["plan_version"] == 1  # an edit to the video's plan makes it older
