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


def step_failed(db: Session, job: Job, again: bool = True) -> None:
    """A step's job failed: what waits on it is told (a check, a take's watch, a voice); and
    when the provider said so (`again`), the reel watch retries, then falls back, and a
    refused or busy take, a presenter's host and a take's added sound are tried again once on
    their own (P3)."""
    from app.clip_takes import retry
    from app.reel_read import watch_failed

    explain(db, job)
    if job.input.get("step") == "footage_describe":  # the owner types it instead
        from app.footage import describe_failed

        describe_failed(db, job)
    if job.input.get("step") in ("item_check", "take_words"):
        from app.item_checks import failed

        failed(db, job)
    if job.input.get("step") == "take_watch" or job.input.get("watch"):  # its listen or look
        from app.take_watch import failed as unwatched

        unwatched(db, job)
    if job.input.get("step") == "clip_take" and again:
        try:
            retry(db, job)
        except Exception:  # never let a retry break the worker
            log.exception("job %s: retrying the take failed", job.id)
    if job.input.get("step") in ("host_still", "host_piece", "take_sound") and again:  # once
        from app.clip_takes import once_more

        try:
            once_more(db, job)
        except Exception:  # never let a retry break the worker
            log.exception("job %s: trying it again failed", job.id)
    if job.input.get("step") == "song_timing":  # a take's timing: read once more, free and local
        from app.song_takes import time_again

        try:
            time_again(db, job)
        except Exception:  # never let a retry break the worker
            log.exception("job %s: reading the timing again failed", job.id)
    if job.input.get("saved_voice"):  # a narration in a clone MiniMax no longer has
        from app.voices import failed as voice_failed

        voice_failed(db, job)
    if job.input.get("step") == "reel_watch" and again:
        try:
            watch_failed(db, job)
        except Exception:  # never let a retry break the worker
            log.exception("job %s: retrying the reel watch failed", job.id)


def recheck(job_input: dict, result, ask):
    """Song directions, a narration's music prompt and the scene plan: the Director's check
    on the answer; with fixes, the one rewrite inside the same job (`ask` runs it; charged
    once: credits never pass the shown price), and if that still needs fixing the job fails,
    so nothing is shown or charged (rule 22)."""
    from app import narration_music as nm
    from app import one_pass, plans
    from app import song_directions as sd
    from app.providers import Result

    if result.state != "succeeded":
        return result
    if job_input.get("plan") or job_input.get("step") == "breakdown":  # from a plan (P2), timed
        return _shots_follow(job_input, result, ask)
    still = sd.STILL
    if job_input.get("step") == sd.STEP:
        check, again = (lambda out: sd.checked(job_input, out)), sd.again
    elif job_input.get("step") == nm.STEP:
        check, again = nm.checked, nm.again
    elif job_input.get("step") == plans.STEP:
        check, again = (lambda out: plans.checked(job_input, out)), plans.again
        still = plans.STILL
    elif job_input.get("step") == plans.SCENE_STEP:
        check, again = (lambda out: plans.scene_checked(job_input, out)), plans.scene_again
        still = plans.STILL
    elif job_input.get("step") == one_pass.STEP:  # every spoken line once, in order, by number
        check, again = (lambda out: one_pass.checked(job_input, out)), one_pass.again
        still = one_pass.STILL
    else:
        return result
    output, fixes = check(result.output)
    if fixes:
        second = ask(again(job_input, fixes))
        second.usage = [*result.usage, *second.usage]  # both calls' dollars are listed
        if second.state != "succeeded":
            return second
        result, (output, fixes) = second, check(second.output)
    if fixes:
        return Result("failed", error=still + "; ".join(fixes), usage=result.usage)
    result.output = output
    return result


def _shots_follow(job_input: dict, result, ask):
    """Shots made from an approved plan or timed to a style's pace: the Director's check
    (plans.shots_checked), the one rewrite inside the same job (charged once), and what it
    still finds is kept as Advice on the breakdown, never a failed job (rule 22: the shots
    are there, with a free fix)."""
    from app import plans
    from app.prompts.check import ADVICE

    output, found = plans.shots_checked(job_input, result.output)
    if fixes := [f for f in found if not f.startswith(ADVICE)]:
        second = ask(plans.shots_again(job_input, fixes))
        second.usage = [*result.usage, *second.usage]
        result.usage = second.usage
        if second.state == "succeeded":
            output, found = plans.shots_checked(job_input, second.output)
    advice = [f if f.startswith(ADVICE) else f"{ADVICE}{f}" for f in found]
    result.output = {**output, "plan_advice": advice} if advice else output
    return result


def save_step_result(db: Session, job: Job) -> None:
    from app import footage, footage_shot
    from app.breakdown import save_breakdown
    from app.change import save_changed
    from app.clip_prompts import save_clip_prompts
    from app.clip_takes import save_take
    from app.cut import saved as save_cut
    from app.enhance import save_suggestions
    from app.host import saved as save_host
    from app.item_checks import save as save_check
    from app.look_samples import save_clip as save_sample_clip
    from app.look_samples import save_still as save_sample_still
    from app.narration_music import save_bed
    from app.narration_music import save_prompt as save_music_prompt
    from app.one_pass import save as save_shooting_plan
    from app.plans import save as save_plan
    from app.plans import save_scene
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
    from app.take_sound import saved as save_sound
    from app.take_watch import save as save_take_watch
    from app.take_words import save as save_words
    from app.talker_sound import saved as save_voice_split
    from app.video_variations import save as save_video_variations
    from app.voices import saved as save_voice
    from app.watch_cut import heard_cut
    from app.watch_cut import save as save_watch_cut

    handlers = {
        "enhance": save_suggestions,
        "breakdown": save_breakdown,
        "plan": save_plan,
        "plan_scene": save_scene,
        "one_pass": save_shooting_plan,
        "song_breakdown": save_breakdown,
        "narrated_breakdown": save_breakdown,
        "storyboard": save_frames,
        "improve": save_improved,
        "change": save_changed,
        "sheet": save_sheet,
        "look_fit": save_fit,
        "frame": save_still,
        "item_check": save_check,
        "take_words": save_words,
        "cut_make": save_cut,
        "take_watch": save_take_watch,
        "cut_listen": heard_cut,
        "watch_cut": save_watch_cut,
        "look_sample": save_sample_still,
        "look_sample_clip": save_sample_clip,
        "clip_prompts": save_clip_prompts,
        "clip_take": save_take,
        footage_shot.TAKE: footage_shot.save_take,
        footage.STEP: footage.save_description,
        "take_sound": save_sound,
        "voice_split": save_voice_split,
        "voice_clone": save_voice,
        "host_still": save_host,
        "host_piece": save_host,
        "variations": save_variations,
        "video_variations": save_video_variations,
        "script_draft": save_written,
        "cast_slots": save_cast_slots,
        "reel_prepare": save_prepared,
        "reel_watch": save_watch,
        "song_take": save_song,
        "song_directions": save_directions,
        "narration_music": save_music_prompt,
        "narration_bed": save_bed,
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
        if job.input.get("step") in ("clip_prompts", "change", "one_pass"):  # not charged: said
            job.status, job.error = JobStatus.failed, "Its answer couldn't be saved."
            explain(db, job)
    if job.input.get("reel_step"):  # a step of reading an imported reel: queue the next
        follow_on(db, job, saved)
    if saved and "idea_send" in job.input:  # New video's idea is written: its video starts
        from app.routes.freestyles import written

        db.commit()  # the paid script first: a start that fails never loses it
        written(db, job)
    if saved and job.input.get("update_run"):  # Update everything after this: the next step
        from app import update_after

        update_after.follow(db, job)
    elif saved and job.input.get("then_cast"):  # Write or variations: the cast read next
        from app.script_cast_read import after

        try:
            after(db, job)
        except Exception:  # never lose the saved words over it
            log.exception("job %s: queueing the cast read failed", job.id)
