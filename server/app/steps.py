"""Saving what a script-flow step produced, once its job succeeds (called by the worker)."""

import logging

from sqlalchemy.orm import Session

from app.models.jobs import Job

log = logging.getLogger(__name__)


def save_step_result(db: Session, job: Job) -> None:
    from app.breakdown import save_breakdown
    from app.enhance import save_suggestions
    from app.storyboard import save_frames

    handlers = {
        "enhance": save_suggestions,
        "breakdown": save_breakdown,
        "storyboard": save_frames,
    }
    handler = handlers.get(job.input.get("step", ""))
    if handler is None:
        return
    try:
        handler(db, job)
    except Exception:  # never lose the paid answer: it stays in job.output
        log.exception("job %s: saving the %s result failed", job.id, job.input["step"])
