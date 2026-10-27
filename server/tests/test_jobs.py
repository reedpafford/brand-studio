from app.models.accounts import User
from app.models.jobs import JobStatus
from app.providers.fake import FakeProvider
from app.routes.jobs import enqueue
from app.worker import run_once
from tests.helpers import assert_hidden, assert_no_dollars


def test_team_sees_jobs_and_can_cancel_queued(editor, db):
    job = enqueue(db, db.query(User).first(), "video-480p", {"seconds": 2})
    assert [j["id"] for j in editor.get("/jobs").json()] == [job.id]
    assert editor.post(f"/jobs/{job.id}/cancel").json()["status"] == "cancelled"
    assert editor.post(f"/jobs/{job.id}/cancel").status_code == 409


def test_started_job_cannot_be_cancelled(owner, db):
    job = enqueue(db, db.query(User).one(), "video-480p", {})
    run_once(db, {"fake": FakeProvider()})
    assert owner.get(f"/jobs/{job.id}").json()["status"] == JobStatus.running
    assert owner.post(f"/jobs/{job.id}/cancel").status_code == 409


def test_other_workspace_cannot_see_job(owner, outsider, db):
    job = enqueue(db, db.query(User).first(), "video-480p", {})
    assert_hidden(outsider, [("GET", f"/jobs/{job.id}"), ("POST", f"/jobs/{job.id}/cancel")])
    assert outsider.get("/jobs").json() == []


def test_editor_sees_no_dollars_on_finished_jobs(editor, db):
    job = enqueue(db, db.query(User).first(), "video-480p", {"seconds": 3})
    fake = FakeProvider()
    run_once(db, {"fake": fake})
    run_once(db, {"fake": fake})
    assert_no_dollars(editor, ["/jobs", f"/jobs/{job.id}"])
    text = (editor.get("/jobs").text + editor.get(f"/jobs/{job.id}").text).lower()
    assert editor.get(f"/jobs/{job.id}").json()["status"] == "succeeded"
    assert "usd" not in text and "cost" not in text


def test_editor_never_sees_raw_provider_errors(owner, editor, db):
    job = enqueue(db, db.query(User).first(), "video-480p", {})
    fake = FakeProvider()
    fake.submit_error = RuntimeError("insufficient credit, balance $987.65 key=zq7x")
    run_once(db, {"fake": fake})
    text = editor.get(f"/jobs/{job.id}").text + editor.get("/jobs").text
    assert "987.65" not in text and "zq7x" not in text and "usd" not in text.lower()
    assert editor.get(f"/jobs/{job.id}/detail").status_code == 403
    assert "$987.65" in owner.get(f"/jobs/{job.id}/detail").json()["error_detail"]


def test_owner_sees_who_asked_and_what_it_costs(owner, editor, db):
    """For the owner's Approvals list: the asker's name on jobs and projects, dollars owner-only."""
    ed = db.query(User).filter_by(name="Ed").one()
    job = enqueue(db, ed, "video-480p", {"seconds": 5}, units=5)
    row = owner.get("/jobs").json()[0]
    assert (row["created_by_id"], row["created_by_name"]) == (ed.id, "Ed")
    detail = owner.get(f"/jobs/{job.id}/detail").json()
    assert detail["cost_usd"] == round(float(job.credits) * 0.1028, 4)  # not run yet: its worth
    fake = FakeProvider()
    run_once(db, {"fake": fake})
    run_once(db, {"fake": fake})
    assert owner.get(f"/jobs/{job.id}/detail").json()["cost_usd"] == 0.514  # what was spent
    assert editor.get(f"/jobs/{job.id}/detail").status_code == 403
    assert_no_dollars(editor, ["/jobs", f"/jobs/{job.id}"])

    fomo = owner.get("/brands").json()[0]["id"]
    made = editor.post("/projects", json={"brand_id": fomo, "name": "Dip", "planned_seconds": 30})
    assert made.json()["created_by_name"] == "Ed"
    assert owner.get("/projects").json()[0]["created_by_id"] == ed.id


def test_times_in_responses_say_utc(owner, db):
    # Stored as naive UTC; without a "Z" a browser in New York reads them as 5 hours ahead.
    enqueue(db, db.query(User).first(), "video-480p", {})
    created = owner.get("/jobs").json()[0]["created_at"]
    assert created.endswith("Z") or created[-6] in "+-"


def test_every_response_time_uses_utc_time(app):
    from datetime import datetime
    from typing import Annotated, get_args, get_origin

    from fastapi.routing import APIRoute
    from pydantic import BaseModel

    from app.schemas import UtcTime

    bare, seen = [], set()

    def walk(tp, where):
        if tp in seen:
            return
        if get_origin(tp) is Annotated:
            if not set(tp.__metadata__) & set(UtcTime.__metadata__):
                walk(get_args(tp)[0], where)
        elif tp is datetime:
            bare.append(where)
        elif isinstance(tp, type) and issubclass(tp, BaseModel):
            seen.add(tp)
            for name, f in tp.model_fields.items():
                walk(
                    Annotated[(f.annotation, *f.metadata)] if f.metadata else f.annotation,
                    f"{tp.__name__}.{name}",
                )
        else:
            for arg in get_args(tp):
                walk(arg, where)

    for route in app.routes:
        if isinstance(route, APIRoute) and route.response_model is not None:
            walk(route.response_model, route.path)
    assert bare == []
