"""Saving what a script-flow step produced, once its job succeeds (called by the worker)."""

import logging

from sqlalchemy.orm import Session

from app.models.jobs import Job

log = logging.getLogger(__name__)


def save_step_result(db: Session, job: Job) -> None:
    from app.breakdown import save_breakdown
    from app.clip_prompts import save_clip_prompts
    from app.clip_takes import save_take
    from app.enhance import save_suggestions
    from app.routes.sheets import save_sheet
    from app.storyboard import save_frames, save_still

    handlers = {
        "enhance": save_suggestions,
        "breakdown": save_breakdown,
        "storyboard": save_frames,
        "sheet": save_sheet,
        "frame": save_still,
        "clip_prompts": save_clip_prompts,
        "clip_take": save_take,
    }
    handler = handlers.get(job.input.get("step", ""))
    if handler is None:
        return
    try:
        handler(db, job)
    except Exception:  # never lose the paid answer: it stays in job.output
        log.exception("job %s: saving the %s result failed", job.id, job.input["step"])
