"""The director's look at its stills before any take (the director rework, PR B): one vision
call over every drawn still of the newest shots, against the treatment, the plan and the
look's skill (the Director's review_stills step). Its findings each carry a change note; the
director redraws a still with `redraw_still` (the Change it… route), twice at most a still."""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accounts import User
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame

STEP, KIND = "review_stills", "check-claude"
NO_STILLS = "Draw the stills first."
REDRAWS = 2  # a still redrawn for the review, a run


def frames(db: Session, project: Project) -> list[StoryboardFrame]:
    """The newest shots' drawn stills, in shot order."""
    from app.clip_prompts import newest

    bd = newest(db, project)
    if bd is None:
        return []
    order = [s["id"] for sc in bd.data.get("scenes", []) for s in sc.get("shots", [])]
    rows = [f for f in db.scalars(select(StoryboardFrame).where(
        StoryboardFrame.project_id == project.id, StoryboardFrame.breakdown_id == bd.id))
        if f.file_id]  # fmt: skip
    return sorted(rows, key=lambda f: order.index(f.shot_id) if f.shot_id in order else 999)


def start(db: Session, user: User, project: Project, run: dict | None) -> str:
    """Queue the review of every drawn still, on the director's own limit like a watch."""
    from app import plans, prompts
    from app.credits import estimate, past_approved
    from app.director import GRANT, past_own, treatment_block
    from app.enhance import project_context
    from app.routes.jobs import enqueue
    from app.watch_cut import _plan

    drawn = frames(db, project)
    if not drawn:
        raise HTTPException(409, NO_STILLS)
    from app.clip_prompts import newest

    shots = {s["id"]: s for sc in newest(db, project).data.get("scenes", [])
             for s in sc.get("shots", [])}  # fmt: skip
    version = plans.script(db, project)
    beats = _plan(plans.current(db, project), version) if version else ""
    told = [shots.get(f.shot_id, {}) for f in drawn]
    seen = [(n, f.shot_id, s.get("action", ""), s.get("line") or "")
            for n, (f, s) in enumerate(zip(drawn, told, strict=True), 1)]  # fmt: skip
    system, _ = project_context(db, project, STEP)  # its look's skill and craft
    text = treatment_block(db, project) + prompts.review_stills_input(beats, seen)
    data = {"step": STEP, "project_id": project.id, "director_run": run, "system": system,
            "prompt": text, "effort": "high", "max_tokens": 4000, "fit_images_to": 1024,
            "seen": {str(f.id): f.file_id for f in drawn},
            "files": {"reference_images": [f.file_id for f in drawn]}}  # fmt: skip
    units = len(drawn)
    look = estimate(db, project.workspace_id, KIND, Decimal(units), data)
    wait = past_own(db, project, (run or {}).get("id"), look, user)
    data = {**data, GRANT: True} if wait else data  # an OK here grants another limit
    wait = wait or past_approved(db, project, user, look)
    enqueue(db, user, KIND, data, units=units, project=project, provider="claude",
            prepaid=not wait, wait=wait)  # fmt: skip
    return f"Looking at the {units} still{'s' if units != 1 else ''} against the treatment."


def state(db: Session, project: Project) -> dict:
    """The newest review: {state none | reviewing | done | failed, ready, findings, current
    (no still it saw was redrawn since)}."""
    job = db.scalar(select(Job).where(Job.project_id == project.id,
                                      Job.input["step"].as_string() == STEP)
                    .order_by(Job.id.desc()).limit(1))  # fmt: skip
    if job is None or job.status == JobStatus.cancelled:
        return {"state": "none"}
    if job.status == JobStatus.failed:
        return {"state": "failed"}
    if job.status != JobStatus.succeeded:
        return {"state": "reviewing"}
    now = {str(f.id): f.file_id for f in frames(db, project)}
    out = job.output or {}
    return {
        "state": "done",
        "ready": bool(out.get("ready")),
        "findings": out.get("findings") or [],
        "current": now == job.input.get("seen"),
    }
