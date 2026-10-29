"""Saving what a script-flow step produced, once its job succeeds (called by the worker)."""

import logging

from sqlalchemy.orm import Session

from app.models.jobs import Job, JobStatus

log = logging.getLogger(__name__)


def explain(db: Session, job: Job) -> None:
    """A failed clip-prompts run, take or still names its cause in plain words."""
    from app.change import change_failed
    from app.clip_prompts import failed
    from app.clip_takes import refused
    from app.storyboard import still_refused

    said = {"clip_prompts": failed, "clip_take": refused, "frame": still_refused,
            "change": change_failed}  # fmt: skip
    if (step := job.input.get("step")) in said:
        try:
            said[step](db, job)
        except Exception:  # never let the explanation break the worker
            log.exception("job %s: explaining the failure failed", job.id)


def step_failed(db: Session, job: Job) -> None:
    """A step's job failed at the provider: the reel watch retries, then falls back; a
    refused or busy take is tried again once on its own (P3)."""
    from app.clip_takes import retry
    from app.reel_read import watch_failed

    explain(db, job)
    if job.input.get("step") == "item_check":
        from app.item_checks import failed

        failed(db, job)
    if job.input.get("step") == "clip_take":
        try:
            retry(db, job)
        except Exception:  # never let a retry break the worker
            log.exception("job %s: retrying the take failed", job.id)
    if job.input.get("step") == "reel_watch":
        try:
            watch_failed(db, job)
        except Exception:  # never let a retry break the worker
            log.exception("job %s: retrying the reel watch failed", job.id)


def recheck(job_input: dict, result, ask):
    """Song directions: the Director's check on the answer; with fixes, the one rewrite
    inside the same job (`ask` runs it; charged once: credits never pass the shown price),
    and if that still needs fixing the job fails, so nothing is shown or charged (rule 22)."""
    from app import song_directions as sd
    from app.providers import Result

    if job_input.get("step") != sd.STEP or result.state != "succeeded":
        return result
    output, fixes = sd.checked(job_input, result.output)
    if fixes:
        second = ask(sd.again(job_input, fixes))
        second.usage = [*result.usage, *second.usage]  # both calls' dollars are listed
        if second.state != "succeeded":
            return second
        result, (output, fixes) = second, sd.checked(job_input, second.output)
    if fixes:
        return Result("failed", error=sd.STILL + "; ".join(fixes), usage=result.usage)
    result.output = output
    return result


def save_step_result(db: Session, job: Job) -> None:
    from app.breakdown import save_breakdown
    from app.change import save_changed
    from app.clip_prompts import save_clip_prompts
    from app.clip_takes import save_take
    from app.enhance import save_suggestions
    from app.item_checks import save as save_check
    from app.reel_read import follow_on, save_watch
    from app.routes.improve import save_improved
    from app.routes.script_import import save_prepared
    from app.routes.sheets import save_fit, save_sheet
    from app.script_cast_read import save_cast_slots
    from app.script_variations import save_variations
    from app.script_write import save_written
    from app.song_directions import save as save_directions
    from app.song_study import save as save_study
    from app.song_takes import save_take as save_song
    from app.song_takes import save_timing
    from app.storyboard import save_frames, save_still

    handlers = {
        "enhance": save_suggestions,
        "breakdown": save_breakdown,
        "song_breakdown": save_breakdown,
        "narrated_breakdown": save_breakdown,
        "storyboard": save_frames,
        "improve": save_improved,
        "change": save_changed,
        "sheet": save_sheet,
        "look_fit": save_fit,
        "frame": save_still,
        "item_check": save_check,
        "clip_prompts": save_clip_prompts,
        "clip_take": save_take,
        "variations": save_variations,
        "script_draft": save_written,
        "cast_slots": save_cast_slots,
        "reel_prepare": save_prepared,
        "reel_watch": save_watch,
        "song_take": save_song,
        "song_directions": save_directions,
        "song_timing": save_timing,
        "song_study": save_study,
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
        if job.input.get("step") in ("clip_prompts", "change"):  # not charged, and says so
            job.status, job.error = JobStatus.failed, "Its answer couldn't be saved."
            explain(db, job)
    if job.input.get("reel_step"):  # a step of reading an imported reel: queue the next
        follow_on(db, job, saved)
    elif saved and job.input.get("then_cast"):  # Write or variations: the cast read next
        from app.script_cast_read import after

        try:
            after(db, job)
        except Exception:  # never lose the saved words over it
            log.exception("job %s: queueing the cast read failed", job.id)
