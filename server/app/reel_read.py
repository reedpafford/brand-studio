"""Reading an imported reel (docs/design/reel-import-server.md §3): three paid steps after the
free prep, priced together and pressed once. Watch (Gemini) describes the shots and names the
speakers; the server builds the breakdown from it plus the transcript and cuts it measured;
then the existing Write (script_draft) and Cast read (cast_slots) steps run on it. Each step's
job queues the next with `prepaid`; a failed step stops the chain and a new press retries
from it."""

import logging
import re
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts, script_write
from app import script_cast_read as cast_read
from app.credits import estimate
from app.enhance import escape
from app.models.accounts import User
from app.models.jobs import WAITING, Job, JobStatus
from app.models.script_library import Script
from app.prompts import check
from app.prompts.schemas import ReelWatch
from app.reference import checked

log = logging.getLogger(__name__)
STEPS = ("watch", "write", "cast")
AGAIN = ("watch", "write")  # Read it again: the breakdown and the script; the cast stays
WATCH_MODEL = "gemini-3.5-flash"
KIND = {"watch": "watch-gemini", "write": "write-claude", "cast": "write-claude"}
NAMES = {"watch": "Finding the shots", "write": "Writing the script", "cast": "Reading the cast"}


def latest(db: Session, job: Job) -> Script | None:
    """The job's script as the database has it now (sessions keep objects across commits,
    and the web side may have moved it on, e.g. a new press)."""
    return db.get(Script, job.input["script_id"], populate_existing=True)


def state(db: Session, script: Script) -> tuple[str, str | None]:
    """(status, failed step): preparing | ready | reading | done | failed, worked out from the
    import's latest job and what the script holds; the step is prepare, watch, write or cast."""
    reel = script.reel or {}
    job = db.get(Job, script.reel_job_id) if script.reel_job_id else None
    step = (job.input.get("reel_step") if job else None) or "prepare"
    if job and job.status in WAITING:
        return ("preparing" if step == "prepare" else "reading"), None
    if reel.get("problem") or not job or job.status != JobStatus.succeeded:
        return "failed", step
    if reel.get("failed_step"):
        return "failed", reel["failed_step"]
    return ("ready" if remaining(script) else "done"), None


def needs_upload(script: Script) -> bool:
    """Prepared before watch copies existed, so it can't be watched: upload it again."""
    return "watch" in remaining(script) and not (script.reel or {}).get("watch_file_id")


def remaining(script: Script) -> list[str]:
    done = (script.reel or {}).get("done", [])
    return [s for s in STEPS if s not in done]


def price(db: Session, user: User, steps: list[str]) -> Decimal:
    model = {"watch": {"model": WATCH_MODEL}}
    return sum(
        (estimate(db, user.workspace_id, KIND[s], Decimal(1), model.get(s, {})) for s in steps),
        Decimal(0),
    )


def shots(reel: dict) -> list[dict]:
    """The measured shots, [{n, start, end}], from the cut times."""
    edges = [0.0, *reel.get("cuts", []), reel["seconds"]]
    pairs = [(a, b) for a, b in zip(edges, edges[1:], strict=False) if b > a]
    return [{"n": n, "start": a, "end": b} for n, (a, b) in enumerate(pairs, 1)]


VIDEO_TRIES = 2  # the video watch, then one retry, before watching from frames


def last_reading(db: Session, script: Script) -> str:
    """The last watch answer (the ReelWatch JSON) for this script, for Read it again."""
    jobs = db.scalars(
        select(Job)
        .where(Job.workspace_id == script.workspace_id, Job.kind == KIND["watch"],
               Job.status == JobStatus.succeeded)
        .order_by(Job.id.desc())
    )  # fmt: skip
    job = next((j for j in jobs if j.input.get("script_id") == script.id), None)
    return (
        re.sub(r"^\s*```(?:json)?|```\s*$", "", (job.output or {}).get("text", "")) if job else ""
    )


def watch_input(script: Script, mode: str = "video", attempt: int = 1) -> dict:
    """Gemini's input. "video": the small watch copy, inline as a data: URL (Replicate file
    URLs to Gemini failed on and off). "frames": when video won't go through at all (the
    model's own upload to Google fails too), the contact sheet and frame grids only."""
    reel = script.reel
    said = [{**x, "text": escape(x["text"])} for x in reel["transcript"]]
    prompt = prompts.reel_watch_input(said, shots(reel), frames_only=mode == "frames")
    if reel.get("last_reading"):  # Read it again: start from it, change only what the note says
        prompt += f"\n<last_reading>{escape(reel['last_reading'])}</last_reading>"
    if reel.get("note"):  # Read it again: what the last reading got wrong
        prompt += (
            "\n<correction>Someone checked the last reading of this reel and says: "
            f"{escape(reel['note'])}\nFix those points; keep the rest.</correction>"
        )
    files = {"images": [reel["contact_file_id"]], "videos": [reel["watch_file_id"]]}
    if mode == "frames":  # the watch prompt's rule 7 says how to read them
        files = {"images": [reel["contact_file_id"], *reel.get("grid_file_ids", [])][:10]}
    return {
        "step": "reel_watch",
        "script_id": script.id,
        "model": WATCH_MODEL,
        "input": {"prompt": prompt, "system_instruction": prompts.watch_system()},
        "files": files,
        "watch_mode": mode,
        "attempt": attempt,
    }


def _job_input(db: Session, script: Script, step: str, **watch) -> dict:
    if step == "watch":
        data = watch_input(script, **watch)
    elif step == "write":
        data = script_write.job_input(db, script, script.reference_breakdown)
    else:
        versions = {0: script_write.original(db, script).text}
        data = cast_read.job_input(db, script, script.reference_breakdown, versions)
    return {**data, "reel_step": step}


def queue(
    db: Session, user: User, script: Script, step: str, prepaid: bool = False, **watch
) -> Job:
    """Queue one step and point the script at it (the import's latest job)."""
    from app.routes.jobs import enqueue

    provider = "replicate" if step == "watch" else "claude"
    data = _job_input(db, script, step, **watch)
    job = enqueue(db, user, KIND[step], data, provider=provider, prepaid=prepaid)
    tries = {**script.reel.get("tries", {}), step: script.reel.get("tries", {}).get(step, 0) + 1}
    script.reel = {k: v for k, v in script.reel.items() if k != "failed_step"} | {"tries": tries}
    script.reel_job_id = job.id
    db.commit()
    return job


def save_watch(db: Session, job: Job) -> None:
    """Gemini's answer, checked against the cuts, becomes the script's own reel breakdown
    (`prompts.watch_breakdown`; the length is the one ffprobe measured). A shot list that
    doesn't match the cuts fails the step, and the next press retries from it."""
    script = latest(db, job)
    if script is None or script.reel_job_id != job.id:
        return
    text = re.sub(r"^\s*```(?:json)?|```\s*$", "", job.output.get("text") or "")
    watch = ReelWatch.model_validate_json(text)
    reel = script.reel
    problems = check.reel_watch(watch, shots(reel), reel["transcript"])
    if fixes := [p for p in problems if not p.startswith(check.ADVICE)]:
        raise ValueError(f"The watch answer doesn't fit the cuts: {fixes[0]}")
    made = prompts.watch_breakdown(watch, reel["transcript"], shots(reel))
    script.reference_breakdown = checked({**made, "duration_seconds": reel["seconds"]})
    script.reel = {**reel, "watched_from": job.input.get("watch_mode", "video")}
    if not script.description:
        script.description = watch.logline


def watch_failed(db: Session, job: Job) -> None:
    """The watch call failed at the provider (nothing charged: failed jobs aren't counted).
    Try the video once more, then watch from frames; already paid for, so prepaid."""
    script = latest(db, job)
    if script is None or script.reel_job_id != job.id:
        return
    mode, attempt = job.input.get("watch_mode", "video"), job.input.get("attempt", 1)
    if mode == "video" and attempt < VIDEO_TRIES:
        nxt = {"mode": "video", "attempt": attempt + 1}
    elif mode == "video" and script.reel.get("grid_file_ids"):
        nxt = {"mode": "frames", "attempt": 1}
    else:
        return  # the chain stops here; a new press retries the watch
    try:
        queue(db, db.get(User, job.created_by_id), script, "watch", prepaid=True, **nxt)
    except HTTPException as exc:
        log.warning("job %s: couldn't retry the reel watch: %s", job.id, exc)


def follow_on(db: Session, job: Job, saved: bool) -> None:
    """After a chain step's job succeeds: mark it done and queue the next, already paid for.
    If saving its answer failed, the chain stops at this step."""
    script = latest(db, job)
    if script is None or script.reel_job_id != job.id:
        return
    step = job.input["reel_step"]
    if not saved:
        script.reel = {**script.reel, "failed_step": step}
        return
    script.reel = {**script.reel, "done": [*script.reel.get("done", []), step]}
    if left := remaining(script):
        try:
            queue(db, db.get(User, job.created_by_id), script, left[0], prepaid=True)
        except HTTPException as exc:  # e.g. a cap reached meanwhile: stop here, say why
            log.warning("job %s: couldn't queue the reel's %s step: %s", job.id, left[0], exc)
            script.reel = {**script.reel, "failed_step": left[0]}
