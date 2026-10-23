import threading
import time
from decimal import Decimal

import pytest

from app import credits as credits_module
from app.models.accounts import Role, User
from app.models.credits import Project
from app.models.jobs import Job
from app.providers.fake import FakeProvider
from app.routes.jobs import enqueue
from app.worker import run_once
from tests.helpers import assert_hidden, assert_no_dollars


@pytest.fixture
def ed(editor, db):
    return db.query(User).filter_by(role=Role.editor).one()


@pytest.fixture
def project(owner, editor, db):
    """A fomo project an editor planned at 10 s: estimate 10 credits, budget 20."""
    fomo = owner.get("/brands").json()[0]["id"]
    body = editor.post(
        "/projects", json={"brand_id": fomo, "name": "Launch", "planned_seconds": 10}
    ).json()
    return body, db.get(Project, body["id"])


def _run(db, fake=None):
    fake = fake or FakeProvider()
    run_once(db, {"fake": fake})
    run_once(db, {"fake": fake})


def test_launch_rates_seeded(editor):
    rates = {r["kind"]: r["credits_per_unit"] for r in editor.get("/credits/rates").json()}
    assert rates["video-480p"] == 1 and rates["video-720p"] == 2.25
    assert rates["image-nano-banana-pro"] == 1.5


def test_only_owner_sets_rates_and_limits(owner, editor):
    rate = {"unit": "image", "credits_per_unit": 3}
    assert editor.put("/credits/rates/image-x", json=rate).status_code == 403
    assert owner.put("/credits/rates/image-x", json=rate).json()["credits_per_unit"] == 3
    limits = {"max_planned_seconds": 240, "weekly_quick_clip_credits": 200}
    assert editor.put("/credits/limits", json=limits).status_code == 403
    assert owner.put("/credits/limits", json=limits).json() == limits


def test_kind_without_rate_is_allowed_at_one_credit_per_unit(ed, db):
    job = enqueue(db, ed, "brand-new-model", {}, units=4)
    assert (job.status, job.credits) == ("queued", 4)


def test_budget_is_twice_planned_length(project, editor, ed, db):
    body, model = project
    enqueue(db, ed, "video-480p", {"seconds": 15}, units=15, project=model)
    got = editor.get(f"/projects/{body['id']}").json()
    assert (got["estimate_credits"], got["budget_credits"]) == (10, 20)
    assert (got["credits_used"], got["budget_pct"]) == (15, 75)


def test_over_budget_job_waits_for_owner(project, owner, editor, ed, db):
    _, model = project
    enqueue(db, ed, "video-480p", {}, units=15, project=model)
    held = enqueue(db, ed, "video-480p", {}, units=10, project=model)
    assert held.status == "needs_owner_approval"
    _run(db)
    db.refresh(held)
    assert held.status == "needs_owner_approval"  # the worker leaves it alone
    assert editor.post(f"/jobs/{held.id}/approve").status_code == 403
    assert owner.post(f"/jobs/{held.id}/approve").json()["status"] == "queued"
    assert owner.post(f"/jobs/{held.id}/approve").status_code == 409
    me = owner.get("/auth/me").json()["id"]
    assert owner.get(f"/jobs/{held.id}/detail").json()["approved_by_id"] == me


def test_long_project_from_editor_waits_and_holds_its_jobs(owner, editor, ed, db):
    fomo = owner.get("/brands").json()[0]["id"]
    body = {"brand_id": fomo, "name": "Epic", "planned_seconds": 181}
    created = editor.post("/projects", json=body).json()
    assert created["status"] == "needs_owner_approval"
    job = enqueue(db, ed, "video-480p", {}, units=1, project=db.get(Project, created["id"]))
    assert job.status == "needs_owner_approval"
    assert editor.post(f"/projects/{created['id']}/approve").status_code == 403
    assert owner.post(f"/projects/{created['id']}/approve").json()["status"] == "active"
    assert owner.post("/projects", json=body).json()["status"] == "active"


def test_editor_lengthening_past_limit_needs_owner_again(project, editor):
    body, _ = project
    url = f"/projects/{body['id']}"
    assert editor.patch(url, json={"planned_seconds": 180}).json()["status"] == "active"
    assert editor.patch(url, json={"planned_seconds": 200}).json()["status"] == (
        "needs_owner_approval"
    )


def test_real_cost_replaces_estimate(project, ed, db):
    _, model = project
    job = enqueue(db, ed, "video-480p", {"seconds": 6}, units=8, project=model)
    assert job.credits == 8
    _run(db)
    db.refresh(job)
    assert (job.status, job.credits) == ("succeeded", Decimal(6))  # 6 s x $0.1028 / $0.1028


def test_cancelled_and_failed_jobs_free_their_credits(project, editor, ed, db):
    body, model = project
    cancelled = enqueue(db, ed, "video-480p", {}, units=5, project=model)
    editor.post(f"/jobs/{cancelled.id}/cancel")
    enqueue(db, ed, "video-480p", {}, units=5, project=model)
    _run(db, FakeProvider(fail=True))
    assert editor.get(f"/projects/{body['id']}").json()["credits_used"] == 0


def test_quick_clips_use_a_weekly_allowance_per_editor(editor, ed, db):
    assert enqueue(db, ed, "video-480p", {}, units=100).status == "queued"
    assert enqueue(db, ed, "video-480p", {}, units=60).status == "needs_owner_approval"
    assert enqueue(db, ed, "video-480p", {}, units=50).status == "queued"  # exactly 150
    assert editor.get("/credits/me").json() == {
        "quick_clip_credits_used": 150,
        "quick_clip_credits_allowed": 150,
    }


def test_last_weeks_quick_clips_do_not_count(ed, db):
    old = enqueue(db, ed, "video-480p", {}, units=150)
    old.created_at = credits_module.week_start().replace(year=2020)
    db.commit()
    assert enqueue(db, ed, "video-480p", {}, units=150).status == "queued"


def test_owner_jobs_are_never_held(owner, db):
    me = db.query(User).filter_by(role=Role.owner).one()
    assert enqueue(db, me, "video-480p", {}, units=1000).status == "queued"


def _race(app, monkeypatch, make_job):
    real = credits_module.credits_used, credits_module.quick_clip_used

    def slow(fn):
        def wrapper(*args):  # widen the window between the check and the insert
            value = fn(*args)
            time.sleep(0.3)
            return value

        return wrapper

    monkeypatch.setattr(credits_module, "credits_used", slow(real[0]))
    monkeypatch.setattr(credits_module, "quick_clip_used", slow(real[1]))
    barrier, statuses = threading.Barrier(2), []

    def one():
        with app.state.sessionmaker() as s:
            barrier.wait()
            statuses.append(make_job(s).status)

    threads = [threading.Thread(target=one) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return sorted(statuses)


def test_two_project_jobs_at_once_cannot_both_fit(app, project, ed, db, monkeypatch):
    _, model = project
    enqueue(db, ed, "video-480p", {}, units=15, project=model)  # 15 of 20 used

    def make(s):
        return enqueue(
            s, s.get(User, ed.id), "video-480p", {}, units=5, project=s.get(Project, model.id)
        )

    assert _race(app, monkeypatch, make) == ["needs_owner_approval", "queued"]


def test_two_quick_clips_at_once_cannot_both_fit(app, ed, db, monkeypatch):
    enqueue(db, ed, "video-480p", {}, units=140)  # 140 of 150 used

    def make(s):
        return enqueue(s, s.get(User, ed.id), "video-480p", {}, units=10)

    assert _race(app, monkeypatch, make) == ["needs_owner_approval", "queued"]


def test_other_workspace_is_shut_out(project, ed, outsider, db):
    body, model = project
    held = enqueue(db, ed, "video-480p", {}, units=99, project=model)
    url = f"/projects/{body['id']}"
    assert outsider.get("/projects").json() == []
    assert outsider.get("/credits/rates").json() == []
    assert_hidden(
        outsider,
        [
            ("GET", url),
            ("PATCH", url, {"name": "x"}),
            ("POST", f"{url}/approve"),
            ("POST", f"/jobs/{held.id}/approve"),
        ],
    )
    other = {"brand_id": body["brand_id"], "name": "x", "planned_seconds": 1}
    assert outsider.post("/projects", json=other).status_code == 404


def test_editor_sees_no_dollars(project, editor, ed, db):
    body, model = project
    enqueue(db, ed, "video-480p", {"seconds": 3}, units=3, project=model)
    _run(db)
    assert db.query(Job).one().status == "succeeded"
    paths = ["/projects", f"/projects/{body['id']}", "/credits/rates", "/credits/limits"]
    assert_no_dollars(editor, [*paths, "/credits/me", "/jobs"])
