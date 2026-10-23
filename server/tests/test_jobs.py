from app.models.accounts import User
from app.models.jobs import JobStatus
from app.providers.fake import FakeProvider
from app.routes.jobs import enqueue
from app.worker import run_once
from tests.helpers import assert_hidden, assert_no_dollars


def test_team_sees_jobs_and_can_cancel_queued(editor, db):
    job = enqueue(db, db.query(User).first(), "video", {"seconds": 2})
    assert [j["id"] for j in editor.get("/jobs").json()] == [job.id]
    assert editor.post(f"/jobs/{job.id}/cancel").json()["status"] == "cancelled"
    assert editor.post(f"/jobs/{job.id}/cancel").status_code == 409


def test_started_job_cannot_be_cancelled(owner, db):
    job = enqueue(db, db.query(User).one(), "video", {})
    run_once(db, {"fake": FakeProvider()})
    assert owner.get(f"/jobs/{job.id}").json()["status"] == JobStatus.running
    assert owner.post(f"/jobs/{job.id}/cancel").status_code == 409


def test_other_workspace_cannot_see_job(owner, outsider, db):
    job = enqueue(db, db.query(User).first(), "video", {})
    assert_hidden(outsider, [("GET", f"/jobs/{job.id}"), ("POST", f"/jobs/{job.id}/cancel")])
    assert outsider.get("/jobs").json() == []


def test_editor_sees_no_dollars_on_finished_jobs(editor, db):
    job = enqueue(db, db.query(User).first(), "video", {"seconds": 3})
    fake = FakeProvider()
    run_once(db, {"fake": fake})
    run_once(db, {"fake": fake})
    assert_no_dollars(editor, ["/jobs", f"/jobs/{job.id}"])


def test_usage_dollars_are_owner_only(owner, editor, db):
    enqueue(db, db.query(User).first(), "video", {"seconds": 10})
    fake = FakeProvider()
    run_once(db, {"fake": fake})
    run_once(db, {"fake": fake})
    assert editor.get("/usage").status_code == 403
    assert owner.get("/usage").json()[0]["cost_usd"] == "1.0280"
