from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounts import Role, User
from app.models.credits import Project
from app.models.jobs import Job
from app.providers.fake import FakeProvider
from app.routes.jobs import enqueue
from app.worker import run_once
from tests.helpers import assert_hidden, assert_no_dollars


@pytest.fixture
def setup(owner, editor, db):
    """An owner, an editor, and a fomo project with a 10-credit estimate (budget 20)."""
    fomo = owner.get("/brands").json()[0]["id"]
    project = editor.post(
        "/projects", json={"brand_id": fomo, "name": "Launch", "estimate_credits": 10}
    ).json()
    ed = db.query(User).filter_by(role=Role.editor).one()
    return project, db.get(Project, project["id"]), ed


def _run(db, fake):
    run_once(db, {"fake": fake})
    run_once(db, {"fake": fake})


def test_launch_rate_is_one_credit_per_480p_second(editor):
    rates = editor.get("/credits/rates").json()
    assert rates == [{"kind": "video-480p", "unit": "second", "credits_per_unit": 1.0}]


def test_only_owner_sets_rates(owner, editor):
    body = {"unit": "image", "credits_per_unit": 3}
    assert editor.put("/credits/rates/image", json=body).status_code == 403
    assert owner.put("/credits/rates/image", json=body).json()["credits_per_unit"] == 3.0


def test_unpriced_kind_is_refused(owner, db):
    with pytest.raises(HTTPException) as err:
        enqueue(db, db.query(User).first(), "video-4k", {}, units=5)
    assert err.value.status_code == 422


def test_budget_is_twice_estimate_and_editor_sees_credits_and_percent(setup, editor, db):
    project, model, ed = setup
    enqueue(db, ed, "video-480p", {"seconds": 15}, units=15, project=model)
    body = editor.get(f"/projects/{project['id']}").json()
    assert (body["budget_credits"], body["credits_used"], body["budget_pct"]) == (20, 15, 75)


def test_over_budget_job_waits_for_owner(setup, owner, editor, db):
    _, model, ed = setup
    enqueue(db, ed, "video-480p", {"seconds": 15}, units=15, project=model)
    held = enqueue(db, ed, "video-480p", {"seconds": 10}, units=10, project=model)
    assert held.status == "needs_owner_approval"
    _run(db, FakeProvider())
    db.refresh(held)
    assert held.status == "needs_owner_approval"  # the worker leaves it alone
    assert editor.post(f"/jobs/{held.id}/approve").status_code == 403
    assert owner.post(f"/jobs/{held.id}/approve").json()["status"] == "queued"
    assert owner.post(f"/jobs/{held.id}/approve").status_code == 409


def test_actual_usage_replaces_estimate(setup, db):
    _, model, ed = setup
    job = enqueue(db, ed, "video-480p", {"seconds": 6}, units=8, project=model)
    assert job.credits == 8
    _run(db, FakeProvider())
    db.refresh(job)
    assert (job.status, job.credits) == ("succeeded", Decimal(6))


def test_cancelled_and_failed_jobs_free_their_credits(setup, editor, db):
    project, model, ed = setup
    cancelled = enqueue(db, ed, "video-480p", {}, units=5, project=model)
    editor.post(f"/jobs/{cancelled.id}/cancel")
    enqueue(db, ed, "video-480p", {}, units=5, project=model)
    _run(db, FakeProvider(fail=True))
    assert editor.get(f"/projects/{project['id']}").json()["credits_used"] == 0


def test_only_owner_changes_estimate(setup, owner, editor):
    url = f"/projects/{setup[0]['id']}"
    assert editor.patch(url, json={"estimate_credits": 100}).status_code == 403
    assert editor.patch(url, json={"name": "Renamed"}).json()["name"] == "Renamed"
    assert owner.patch(url, json={"estimate_credits": 100}).json()["budget_credits"] == 200


def test_other_workspace_is_shut_out(setup, owner, outsider, db):
    project, model, ed = setup
    held = enqueue(db, ed, "video-480p", {}, units=99, project=model)
    url = f"/projects/{project['id']}"
    assert outsider.get("/projects").json() == []
    assert outsider.get("/credits/rates").json() == []
    assert_hidden(
        outsider,
        [("GET", url), ("PATCH", url, {"name": "x"}), ("POST", f"/jobs/{held.id}/approve")],
    )
    r = outsider.post(
        "/projects", json={"brand_id": project["brand_id"], "name": "x", "estimate_credits": 1}
    )
    assert r.status_code == 404


def test_editor_sees_no_dollars(setup, editor, db):
    project, model, ed = setup
    enqueue(db, ed, "video-480p", {"seconds": 3}, units=3, project=model)
    _run(db, FakeProvider())
    assert db.query(Job).one().status == "succeeded"
    assert_no_dollars(
        editor, ["/projects", f"/projects/{project['id']}", "/credits/rates", "/jobs"]
    )
