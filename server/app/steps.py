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
    from app.reel_read import follow_on, save_watch
    from app.routes.improve import save_improved
    from app.routes.script_import import save_prepared
    from app.routes.sheets import save_sheet
    from app.script_cast_read import save_cast_slots
    from app.script_variations import save_variations
    from app.script_write import save_written
    from app.storyboard import save_frames, save_still

    handlers = {
        "enhance": save_suggestions,
        "breakdown": save_breakdown,
        "storyboard": save_frames,
        "improve": save_improved,
        "sheet": save_sheet,
        "frame": save_still,
        "clip_prompts": save_clip_prompts,
        "clip_take": save_take,
        "variations": save_variations,
        "script_draft": save_written,
        "cast_slots": save_cast_slots,
        "reel_prepare": save_prepared,
        "reel_watch": save_watch,
    }
    handler = handlers.get(job.input.get("step", ""))
    if handler is None:
        return
    try:
        handler(db, job)
        saved = True
    except Exception:  # never lose the paid answer: it stays in job.output
        log.exception("job %s: saving the %s result failed", job.id, job.input["step"])
        saved = False
    if job.input.get("reel_step"):  # a step of reading an imported reel: queue the next
        follow_on(db, job, saved)
