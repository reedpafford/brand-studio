import threading
import time
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import credits as credits_module
from app.db import utcnow
from app.models.accounts import Role, User
from app.models.jobs import Job
from app.models.projects import Project
from app.providers.fake import FakeProvider
from app.routes.jobs import enqueue
from app.worker import run_once
from tests.conftest import PASSWORD
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


def _raise_video_cap(owner, credits=1000):
    """The approval paths need a per-video cap above 2x the editor length limit."""
    limits = {"weekly_quick_clip_credits": 150}
    owner.put("/credits/limits", json={**limits, "per_video_max_credits": credits})


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
    limits = {"weekly_quick_clip_credits": 200, "per_video_max_credits": 500}
    assert editor.put("/credits/limits", json=limits).status_code == 403
    saved = owner.put("/credits/limits", json=limits).json()
    assert saved == {**limits, "editors_can_save_looks": False}  # off unless Reed turns it on


def test_kind_without_rate_is_allowed_at_one_credit_per_unit(ed, db):
    job = enqueue(db, ed, "brand-new-model", {}, units=4)
    assert (job.status, job.credits) == ("queued", 4)


def test_budget_is_twice_planned_length(project, editor, ed, db):
    body, model = project
    enqueue(db, ed, "video-480p", {"seconds": 15}, units=15, project=model)
    got = editor.get(f"/projects/{body['id']}").json()
    assert (got["estimate_credits"], got["budget_credits"]) == (10, 20)
    assert (got["credits_used"], got["budget_pct"]) == (15, 75)


def _held(db, ed, model, credits):
    """A job held for the owner's OK, as editors' over-budget jobs were before #399."""
    from app.models.jobs import Job

    held = Job(workspace_id=ed.workspace_id, created_by_id=ed.id, kind="video-480p",
               provider="fake", input={}, project_id=model.id, credits=Decimal(credits),
               status="needs_owner_approval")  # fmt: skip
    db.add(held)
    db.commit()
    return held


def test_over_budget_job_is_refused_and_one_already_held_waits_for_owner(
    project, owner, editor, ed, db
):
    """Reed, 2026-10-26 (#399): past a library version's budget an editor is refused with the
    reason, never sent to Reed. A job held before that change still waits and can be OK'd."""
    import pytest
    from fastapi import HTTPException

    _, model = project
    enqueue(db, ed, "video-480p", {}, units=15, project=model)
    with pytest.raises(HTTPException) as refused:
        enqueue(db, ed, "video-480p", {}, units=10, project=model)
    assert (refused.value.status_code, refused.value.detail) == (
        409, "That's more than this video's budget."
    )  # fmt: skip
    held = _held(db, ed, model, 10)
    _run(db)
    db.refresh(held)
    assert held.status == "needs_owner_approval"  # the worker leaves it alone
    assert editor.post(f"/jobs/{held.id}/approve").status_code == 403
    assert owner.post(f"/jobs/{held.id}/approve").json()["status"] == "queued"
    assert owner.post(f"/jobs/{held.id}/approve").status_code == 409
    me = owner.get("/auth/me").json()["id"]
    assert owner.get(f"/jobs/{held.id}/detail").json()["approved_by_id"] == me


def test_editors_plan_any_length_up_to_the_cap(owner, editor):
    """Reed, 2026-10-23: no editor length limit; only the per-video cap (budget = 2x)."""
    fomo = owner.get("/brands").json()[0]["id"]
    body = {"brand_id": fomo, "name": "Epic", "planned_seconds": 364}  # 728 credits
    assert editor.post("/projects", json=body).json()["status"] == "active"
    r = editor.post("/projects", json={**body, "planned_seconds": 365})  # 730 > 729
    assert r.status_code == 422 and "Plan 364 seconds or less." in r.json()["detail"]


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
    """$15 a week (Reed): past it an editor's own work is declined, never sent to the owner."""
    assert enqueue(db, ed, "video-480p", {}, units=100).status == "queued"
    with pytest.raises(HTTPException) as err:
        enqueue(db, ed, "video-480p", {}, units=60)
    assert err.value.status_code == 409
    assert err.value.detail == (
        "That's more than this week's 145 free credits (100 used). It resets on Monday."
    )
    assert db.query(Job).count() == 1  # nothing queued or held
    assert enqueue(db, ed, "video-480p", {}, units=45).status == "queued"  # exactly 145
    me = editor.get("/credits/me").json()
    assert (me["quick_clip_credits_used"], me["quick_clip_credits_allowed"]) == (145, 145)
    resets = date.fromisoformat(me["resets_on"])
    assert resets.weekday() == 0 and resets > utcnow().date()  # next Monday: "It resets on…"
    with pytest.raises(HTTPException) as spent:
        enqueue(db, ed, "video-480p", {}, units=1)
    assert spent.value.detail == "You've used this week's 145 credits. It resets on Monday."
    assert not db.query(Job).filter_by(status="needs_owner_approval").count()  # never held


def test_last_weeks_quick_clips_do_not_count(ed, db):
    old = enqueue(db, ed, "video-480p", {}, units=145)
    old.created_at = credits_module.week_start().replace(year=2020)
    db.commit()
    assert enqueue(db, ed, "video-480p", {}, units=145).status == "queued"


def test_owner_jobs_are_never_held(owner, db):
    me = db.query(User).filter_by(role=Role.owner).one()
    assert enqueue(db, me, "video-480p", {}, units=300).status == "queued"  # no allowance
    assert owner.get("/credits/me").json()["resets_on"]


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
        try:
            return enqueue(
                s, s.get(User, ed.id), "video-480p", {}, units=5, project=s.get(Project, model.id)
            )
        except HTTPException as exc:
            return type("Declined", (), {"status": f"declined {exc.status_code}"})()

    assert _race(app, monkeypatch, make) == ["declined 409", "queued"]


def test_two_quick_clips_at_once_cannot_both_fit(app, ed, db, monkeypatch):
    enqueue(db, ed, "video-480p", {}, units=135)  # 135 of 145 used

    def make(s):
        try:
            return enqueue(s, s.get(User, ed.id), "video-480p", {}, units=10)
        except HTTPException as exc:
            return type("Declined", (), {"status": f"declined {exc.status_code}"})()

    assert _race(app, monkeypatch, make) == ["declined 409", "queued"]


def test_other_workspace_is_shut_out(project, ed, outsider, db):
    body, model = project
    held = _held(db, ed, model, 99)
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


def test_weekly_allowance_is_per_editor_and_owner_can_raise_it(app, owner, ed, db):
    token = owner.post("/team/invites", json={"email": "two@example.com"}).json()["token"]
    with TestClient(app) as c:
        c.post("/auth/accept-invite", json={"token": token, "name": "Two", "password": PASSWORD})
    second = db.query(User).filter_by(email="two@example.com").one()
    clips = [enqueue(db, ed, "video-480p", {}, units=60).status for _ in range(2)]
    assert clips == ["queued", "queued"]
    with pytest.raises(HTTPException):
        enqueue(db, ed, "video-480p", {}, units=60)  # 180 > 145: declined
    assert enqueue(db, second, "video-480p", {}, units=60).status == "queued"
    owner.put(
        "/credits/limits",
        json={"weekly_quick_clip_credits": 180, "per_video_max_credits": 340},
    )
    assert enqueue(db, ed, "video-480p", {}, units=60).status == "queued"


def test_approving_a_project_releases_its_held_jobs_within_budget(owner, editor, ed, db):
    _raise_video_cap(owner)
    fomo = owner.get("/brands").json()[0]["id"]
    body = {"brand_id": fomo, "name": "Epic", "planned_seconds": 200}  # budget 400
    created = editor.post("/projects", json=body).json()
    model = db.get(Project, created["id"])
    model.status = "needs_owner_approval"  # a project from before Reed dropped the length limit
    db.commit()
    with pytest.raises(HTTPException) as refused:  # nothing new waits for Reed any more
        enqueue(db, ed, "video-480p", {}, units=10, project=model)
    assert refused.value.detail == "This video's length isn't approved yet, so nothing can be made."
    assert "Reed" not in refused.value.detail  # editors are never sent to Reed (#397/#399)
    jobs = [_held(db, ed, model, c) for c in (150, 200, 100)]  # held before that change
    owner.post(f"/projects/{created['id']}/approve")
    for job in jobs:
        db.refresh(job)
    assert [j.status for j in jobs] == ["queued", "queued", "needs_owner_approval"]  # 450 > 400


def test_per_video_cap_holds_for_everyone(owner, editor, ed, db):
    fomo = owner.get("/brands").json()[0]["id"]
    body = {"brand_id": fomo, "name": "Big", "planned_seconds": 365}  # 730 credits > 729
    r = owner.post("/projects", json=body)
    assert (
        r.status_code == 422
        and "$75 limit" in r.json()["detail"]
        and "364 seconds" in r.json()["detail"]
    )
    r = editor.post("/projects", json=body)
    assert (
        r.status_code == 422
        and "$" not in r.json()["detail"]
        and "over its limit" in r.json()["detail"]
    )
    project = owner.post("/projects", json={**body, "planned_seconds": 364}).json()
    me = db.query(User).filter_by(role=Role.owner).one()
    model = db.get(Project, project["id"])
    enqueue(db, me, "video-480p", {}, units=700, project=model)
    with pytest.raises(HTTPException) as err:  # the owner too: 700 + 30 > 729
        enqueue(db, me, "video-480p", {}, units=30, project=model)
    assert "$75 limit" in err.value.detail
    with pytest.raises(HTTPException) as err:
        enqueue(db, ed, "video-480p", {}, units=30, project=model)
    assert err.value.detail == "This video would go over its limit."
    assert enqueue(db, me, "video-480p", {}, units=29, project=model).status == "queued"


def test_owner_cannot_approve_past_the_cap(owner, editor, ed, db):
    _raise_video_cap(owner)
    fomo = owner.get("/brands").json()[0]["id"]
    project = editor.post(
        "/projects", json={"brand_id": fomo, "name": "P", "planned_seconds": 100}
    ).json()
    model = db.get(Project, project["id"])
    enqueue(db, ed, "video-480p", {}, units=190, project=model)
    held = _held(db, ed, model, 100)  # 290 > 200 budget, held before #399
    _raise_video_cap(owner, 250)  # the owner lowers the cap meanwhile
    r = owner.post(f"/jobs/{held.id}/approve")
    assert r.status_code == 409 and "limit" in r.json()["detail"]


def test_limits_put_needs_the_cap_so_it_is_never_reset_by_omission(owner):
    r = owner.put("/credits/limits", json={"weekly_quick_clip_credits": 150})
    assert r.status_code == 422
    assert owner.get("/credits/limits").json()["per_video_max_credits"] == 729


def test_default_cap_is_75_dollars_and_no_editor_length_limit(editor):
    limits = editor.get("/credits/limits").json()
    assert limits == {
        "weekly_quick_clip_credits": 145,
        "per_video_max_credits": 729,
        "editors_can_save_looks": False,
    }
    assert 729 * 0.1028 <= 75  # floored: never more than $75


def test_a_single_quick_clip_cannot_pass_the_cap(owner, ed, db):
    _raise_video_cap(owner, 50)
    me = db.query(User).filter_by(role=Role.owner).one()
    with pytest.raises(HTTPException) as err:
        enqueue(db, me, "video-480p", {}, units=51)  # the owner too
    assert "$5 limit" in err.value.detail
    with pytest.raises(HTTPException) as err:
        enqueue(db, ed, "video-480p", {}, units=51)
    assert err.value.detail == "This video would go over its limit."
    assert enqueue(db, me, "video-480p", {}, units=50).status == "queued"


def test_videos_from_an_editors_own_script_use_their_allowance(owner, editor, ed, db):
    """Reed: editors' own scripts run on their $15 a week, declined past it; videos from the
    owner's scripts keep the 2x budget and wait for approval past it."""
    from app.models.script_library import ScriptDraft

    fomo = owner.get("/brands").json()[0]["id"]

    def video(client, planned):
        script = client.post("/scripts", json={"brand_id": fomo, "title": "S", "text": "A: hi"})
        draft = db.query(ScriptDraft).filter_by(script_id=script.json()["id"]).one()
        made = editor.post(
            "/projects", json={"brand_id": fomo, "name": "V", "planned_seconds": planned}
        )
        project = db.get(Project, made.json()["id"])
        project.script_draft_id = draft.id
        db.commit()
        return project

    own = video(editor, 100)  # budget 200, but the allowance (145) is the limit
    assert enqueue(db, ed, "video-480p", {}, units=100, project=own).status == "queued"
    with pytest.raises(HTTPException) as err:
        enqueue(db, ed, "video-480p", {}, units=50, project=own)
    assert err.value.status_code == 409
    with pytest.raises(HTTPException):
        enqueue(db, ed, "video-480p", {}, units=50)  # the same allowance as Quick clips
    reeds = video(owner, 10)  # budget 20
    with pytest.raises(HTTPException) as err:
        enqueue(db, ed, "video-480p", {}, units=30, project=reeds)
    assert err.value.detail == "That's more than this video's budget."  # #399: no Ask Reed


def test_owner_sees_each_editors_allowance(owner, editor, ed, db):
    enqueue(db, ed, "video-480p", {}, units=40)
    assert owner.get("/credits/allowances").json() == [
        {
            "user_id": ed.id,
            "name": "Ed",
            "quick_clip_credits_used": 40,
            "quick_clip_credits_allowed": 145,
        }
    ]
    assert editor.get("/credits/allowances").status_code == 403
    assert_no_dollars(owner, ["/credits/allowances"])
