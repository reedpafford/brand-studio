"""In production (owner only): each video made from a script version until it's done, with its
step, last activity, credits and one flag (failed, stuck, idle), attention first."""

from datetime import timedelta

from app.db import utcnow
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from tests.test_breakdown import BREAKDOWN
from tests.test_script_produce import _published


def _video(owner, editor, db) -> int:
    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    return editor.post(f"{base}/drafts/0/produce").json()["project_id"]


def _job(db, pid: int, status: JobStatus, minutes_ago: int = 0, step: str = "clip_take") -> None:
    at = utcnow() - timedelta(minutes=minutes_ago)
    project = db.get(Project, pid)
    db.add(
        Job(workspace_id=project.workspace_id, created_by_id=project.created_by_id, kind="video",
            provider="fake", input={"step": step}, project_id=pid, brand_id=project.brand_id,
            credits=4, status=status, created_at=at, finished_at=at, error="It didn't finish.")
    )  # fmt: skip
    db.commit()


def _row(owner, pid: int) -> dict:
    return next(r for r in owner.get("/production").json() if r["project_id"] == pid)


def test_only_the_owner_sees_it(owner, editor, db):
    _video(owner, editor, db)
    assert editor.get("/production").status_code == 404
    assert editor.get("/production/summary").status_code == 404
    (row,) = owner.get("/production").json()
    editor_id = db.query(User).filter_by(role="editor").one().id
    assert (row["letter"], row["editor"]["id"], row["script"]["title"]) == ("A", editor_id, "Dip")
    assert (row["credits_used"], row["budget_credits"], row["flag"]) == (0, 10, None)


def test_the_step_follows_what_the_video_has(owner, editor, db):
    pid = _video(owner, editor, db)
    assert _row(owner, pid)["step"] == "assets"  # Reed's saved breakdown came with it
    bd = db.query(BreakdownVersion).filter_by(project_id=pid).one()
    db.add(
        StoryboardFrame(project_id=pid, breakdown_id=bd.id, clip_id="c1", shot_id="s1", prompt="p")
    )
    db.commit()
    assert _row(owner, pid)["step"] == "storyboard"
    clip = ProjectClip(project_id=pid, breakdown_id=bd.id, clip_id="c1", seconds=5, prompt="p")
    db.add(clip)
    db.commit()
    assert _row(owner, pid)["step"] == "clips"
    clip.approved = True
    db.commit()
    assert _row(owner, pid)["step"] == "downloads"
    db.get(Project, pid).finished_at = utcnow()
    db.commit()
    assert owner.get("/production").json() == []  # Video done: off the list


def test_flags_and_the_attention_order(owner, editor, db):
    calm, failed, stuck, idle = (_video(owner, editor, db) for _ in range(4))
    _job(db, failed, JobStatus.failed)
    _job(db, stuck, JobStatus.queued, minutes_ago=31)
    old = utcnow() - timedelta(hours=49)
    db.get(Project, idle).created_at = old
    db.query(BreakdownVersion).filter_by(project_id=idle).update({"created_at": old})
    db.commit()
    rows = owner.get("/production").json()
    assert [(r["project_id"], r["flag"]) for r in rows] == [
        (failed, "failed"), (stuck, "stuck"), (idle, "idle"), (calm, None)
    ]  # fmt: skip
    assert (rows[0]["flag_job"], rows[0]["flag_problem"]) == (
        "Making the takes",
        "It didn't finish.",
    )
    assert [r["project_id"] for r in owner.get("/production?attention=true").json()] == [
        failed, stuck, idle
    ]  # fmt: skip
    assert owner.get("/production/summary").json() == {"in_production": 4, "needs_attention": 3}
    page = owner.get("/production", params={"limit": 2, "offset": 1})
    assert [r["project_id"] for r in page.json()] == [stuck, idle]
    assert page.headers["x-total-count"] == "4"


def test_a_job_that_ran_after_a_failure_clears_it(owner, editor, db):
    pid = _video(owner, editor, db)
    _job(db, pid, JobStatus.failed)
    _job(db, pid, JobStatus.succeeded)
    assert _row(owner, pid)["flag"] is None
    assert _row(owner, pid)["credits_used"] == 4  # the failed job was refunded, as for the gate
