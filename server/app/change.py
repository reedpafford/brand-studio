"""Change it in plain English (change-notes.md §1): a note rewrites a still's or a clip's
prompt (a small Claude call), then the still, or a new take, is made from the new prompt. The
note never changes what's said (`check.redo_note`, before anything is charged). If the prompt
comes back the same, nothing is made and nothing is charged. The old still or take stays with
the prompt it was made from, so picking it back is the Undo."""

import math
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import clip_prompts, clip_takes, prompts, storyboard
from app.credits import estimate, over_allowance
from app.enhance import escape
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.prompts import check
from app.prompts.schemas import Breakdown, ChangedPrompt, ClipPrompt, Frame, Reference

WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)
Row = StoryboardFrame | ProjectClip


def _target(row: Row) -> str:
    return "frame" if isinstance(row, StoryboardFrame) else "clip"


def _has_take(db: Session, row: ProjectClip) -> bool:
    return bool(db.scalar(select(func.count(ClipTake.id)).where(ClipTake.clip_id == row.id)))


def _draw(db: Session, project: Project, row: Row, before: str = "") -> tuple[str, dict, int]:
    """The job that makes the still or the new take: (kind, input, units)."""
    if isinstance(row, StoryboardFrame):
        data = storyboard.render_input(db, project, row)
        return "image", {**data, "was_prompt": before or row.prompt}, 1
    return "video", clip_takes.take_input(db, project, row), row.seconds


def credits(db: Session, project: Project, row: Row) -> Decimal:
    """Change it · N: rewriting the prompt, plus the still or the new take (a clip with no
    take yet only has its prompt rewritten)."""
    total = estimate(db, project.workspace_id, "write-claude", Decimal(1))
    if isinstance(row, StoryboardFrame) or _has_take(db, row):
        kind, data, units = _draw(db, project, row)
        total += estimate(db, project.workspace_id, kind, Decimal(units), data)
    return total


def shown(total: Decimal) -> int:
    return max(1, math.ceil(total))


def start(db: Session, user: User, project: Project, row: Row, note: str) -> Job:
    """Check the note, then queue the rewrite. 422 (nothing charged) for a note that changes
    the dialogue; 409 while this one is being made, or past an editor's week."""
    from app.routes.jobs import enqueue

    note = note.strip()
    if not note:
        raise HTTPException(422, "Say what should change.")
    bd = Breakdown.model_validate(db.get(BreakdownVersion, row.breakdown_id).data)
    if wrong := check.redo_note(note, bd, row.clip_id):
        raise HTTPException(422, " ".join(wrong))
    target = _target(row)
    key = "frame_id" if target == "frame" else "project_clip_id"
    pending = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING)))
    for job in pending:
        mine = job.input.get("step") == "change" and job.input.get("target_id") == row.id
        if job.input.get(key) == row.id or (mine and job.input.get("target") == target):
            raise HTTPException(409, "This one is still being made.")
    if declined := over_allowance(db, user, project, credits(db, project, row)):
        raise HTTPException(409, declined)  # the whole change is checked once, here
    data = {
        "step": "change",
        "project_id": project.id,
        "target": target,
        "target_id": row.id,
        "note": note,
        "before": row.prompt,
        "system": [prompts.system("change")],
        "prompt": (
            f"<kind>{'still' if target == 'frame' else 'clip'}</kind>\n"
            f"<prompt>\n{escape(row.prompt)}\n</prompt>\n<note>\n{escape(note)}\n</note>"
        ),
        "max_tokens": 4000,
    }
    job = enqueue(db, user, "write-claude", data, project=project, provider="claude")
    row.change = {"note": note, "job_id": job.id, "status": "changing"}
    db.commit()
    return job


def save_changed(db: Session, job: Job) -> None:
    """The rewrite is back: the same prompt makes nothing and costs nothing; a new one is
    saved (the old one stays with its still or take) and the still or a new take is made."""
    from app.routes.jobs import enqueue

    i = job.input
    model = StoryboardFrame if i["target"] == "frame" else ProjectClip
    row = db.get(model, i["target_id"])
    if row is None or row.project_id != i["project_id"]:
        return
    before, after = i["before"], ChangedPrompt.model_validate(job.output).prompt.strip()
    change = {"note": i["note"], "job_id": job.id, "before": before, "after": after}
    if row.prompt != before:  # edited by hand while the note was read: never overwrite it
        row.change = {**change, "status": "failed",
                      "error": "The prompt was edited meanwhile. Try the note again."}  # fmt: skip
        return
    if " ".join(after.split()) == " ".join(before.split()):
        job.credits = Decimal(0)  # nothing is made, so nothing is charged
        row.change = {**change, "status": "unchanged", "unchanged": True}
        return
    project = db.get(Project, row.project_id)
    if isinstance(row, ProjectClip) and row.picked_take_id:  # an older take: keep its prompt
        take = db.get(ClipTake, row.picked_take_id)
        take.prompt = take.prompt if take.prompt is not None else before
    row.prompt, row.approved = after, False
    row.change = {**change, "status": "done", "unchanged": False}
    bd = db.get(BreakdownVersion, row.breakdown_id)
    if isinstance(row, StoryboardFrame):
        frame = Frame(clip_id=row.clip_id, shot_id=row.shot_id, prompt=after,
                      reference_ids=row.reference_ids)  # fmt: skip
        row.problems = storyboard.frame_problems(db, project, frame, row.breakdown_id)
    else:
        row.prompt_ok = False  # a prompt written again needs reading again
        clip = ClipPrompt(clip_id=row.clip_id, seconds=row.seconds, prompt=after,
                          references=[Reference(**r) for r in row.references])  # fmt: skip
        row.problems = clip_prompts.clip_problems(
            db, project, Breakdown.model_validate(bd.data), clip
        )
        if not _has_take(db, row):
            return  # before any take, a change only rewrites the prompt
    try:
        kind, data, units = _draw(db, project, row, before)
        user = db.get(User, job.created_by_id)
        made = enqueue(db, user, kind, data, units=units, project=project,
                       provider="replicate", prepaid=True)  # fmt: skip
        row.change = {**row.change, "made_job_id": made.id}
    except HTTPException as e:  # e.g. a sheet unapproved meanwhile: the new prompt stays
        row.change = {**row.change, "status": "failed", "error": e.detail}
