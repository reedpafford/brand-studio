"""Redo this frame (audit LW3, flows.md): a still out of date because the breakdown changed is
written again from the new breakdown, for that one frame (its neighbours as context), then
drawn, at one price. The earlier still stays (pick it back to undo). Only when its clip still
has the same shots; otherwise the whole storyboard is redone. Never a bare redraw."""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import advice, storyboard
from app.credits import estimate, own_script
from app.enhance import escape
from app.images import image_job_input
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.prompts.schemas import Breakdown, StoryboardFrames

WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)
CHANGED = "This clip changed in the breakdown, so its frames are planned again: Redo storyboard."
NOTE = "Redo this frame"
STILL_UNFINISHED = ("The frame was written again, but its still didn't finish, so the still "
                    "wasn't charged. Press Make still to draw it.")  # fmt: skip


def _shots(data: dict, clip_id: str) -> list[str] | None:
    return next((c["shot_ids"] for c in data["clips"] if c["id"] == clip_id), None)


def blocked(db: Session, frame: StoryboardFrame, newest: BreakdownVersion) -> str:
    """Why this out-of-date frame can't be redone on its own ("" when it can): its clip was
    split, joined or renumbered in the new breakdown."""
    old = _shots(db.get(BreakdownVersion, frame.breakdown_id).data, frame.clip_id)
    new = _shots(newest.data, frame.clip_id)
    return "" if new and new == old and frame.shot_id in new else CHANGED


def price(db: Session, project: Project) -> Decimal:
    """Writing the one frame, plus its still."""
    still = image_job_input(storyboard.image_model(), "", project.aspect_ratio)
    return estimate(db, project.workspace_id, "write-claude", Decimal(1)) + estimate(
        db, project.workspace_id, "image", Decimal(1), still
    )


def start(
    db: Session, user: User, project: Project, frame: StoryboardFrame, newest: BreakdownVersion
) -> Job:
    from app.routes.jobs import enqueue

    if reason := blocked(db, frame, newest):
        raise HTTPException(409, reason)
    pending = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING)))
    if any(j.input.get("step") == "storyboard" or j.input.get("frame_id") == frame.id
           or j.input.get("redo_frame_id") == frame.id for j in pending):  # fmt: skip
        raise HTTPException(409, "This one is still being made.")
    others = db.scalars(select(StoryboardFrame).where(StoryboardFrame.project_id == project.id,
                                                      StoryboardFrame.id != frame.id)
                        .order_by(StoryboardFrame.id))  # fmt: skip
    around = "\n".join(f"{f.clip_id} / {f.shot_id}: {f.prompt}" for f in others)
    data = storyboard.job_input(db, project, newest, per_shot=False)
    data["prompt"] += (
        f"\n<redo_frame>\nWrite only the frame for shot {frame.shot_id} of clip {frame.clip_id}, "
        "from this breakdown, and return it alone. The video's other frames, for its look and "
        f"continuity:\n{escape(around)}\n</redo_frame>"
    )
    then = price(db, project) - estimate(db, project.workspace_id, "write-claude", Decimal(1))
    data.update(redo_frame_id=frame.id, max_tokens=8000)
    if own_script(db, project, user):  # the still is held on the editor's week, as Change it
        data["then_credits"] = str(then)
    job = enqueue(db, user, "write-claude", data, project=project, provider="claude", hold=then)
    frame.change = {"note": NOTE, "job_id": job.id, "status": "changing",
                    "was_file_id": frame.file_id}  # fmt: skip
    db.commit()
    return job


def save(db: Session, job: Job) -> None:
    """The one frame is back: it moves to the new breakdown, then its still is drawn (prepaid:
    held at the press). The earlier still stays with the prompt it was drawn from."""
    from app.routes.jobs import enqueue

    frame = db.get(StoryboardFrame, job.input["redo_frame_id"], populate_existing=True)
    if frame is None:
        return
    found = StoryboardFrames.model_validate(job.output).frames
    new = next((f for f in found if f.shot_id == frame.shot_id), found[0] if found else None)
    if new is None:
        frame.change = {**(frame.change or {}), "status": "failed", "error": "The frame came "
                        "back empty, so nothing was charged for its still. Try again."}  # fmt: skip
        return
    project = db.get(Project, frame.project_id)
    bd = Breakdown.model_validate(db.get(BreakdownVersion, job.input["breakdown_id"]).data)
    new = new.model_copy(update={"clip_id": frame.clip_id, "shot_id": frame.shot_id})
    new = storyboard.with_cast(db, project, new, bd)
    soft = storyboard.softened(new.prompt)  # a word the image model refuses never blocks
    new = new.model_copy(update={"prompt": soft["after"]}) if soft else new
    before = frame.prompt
    frame.breakdown_id, frame.prompt = job.input["breakdown_id"], new.prompt
    frame.reference_ids = new.reference_ids
    frame.problems = storyboard.frame_problems(db, project, new, frame.breakdown_id)
    frame.approved = False
    # Still "changing" until its still is drawn (save_still says done; a failed still, failed).
    frame.change = {**(frame.change or {}), "before": before, "after": new.prompt,
                    "unchanged": False}  # fmt: skip
    if stops := advice.blocking(frame.problems):
        fix = stops[0].rstrip(".")
        said = (
            f"The new frame has a problem to fix first ({fix}). Nothing was charged for its still."
        )
        frame.change = {**frame.change, "status": "failed", "error": said}
        return
    db.commit()  # the rewrite is a paid answer: a refused still (it rolls back) keeps it
    try:
        data = {**storyboard.render_input(db, project, frame), "was_prompt": before}
        made = enqueue(db, db.get(User, job.created_by_id), "image", data, project=project,
                       provider="replicate", prepaid=True)  # fmt: skip
        frame.change = {**frame.change, "made_job_id": made.id}
    except HTTPException as e:
        frame.change = {**frame.change, "status": "failed", "error": e.detail}
