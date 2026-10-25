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
from app.models.jobs import Job, JobStatus
from app.models.script_library import Script
from app.prompts import check
from app.prompts.schemas import ReelWatch
from app.reference import checked

log = logging.getLogger(__name__)
STEPS = ("watch", "write", "cast")
WATCH_MODEL = "gemini-3.5-flash"
KIND = {"watch": "watch-gemini", "write": "write-claude", "cast": "write-claude"}
NAMES = {"watch": "Finding the shots", "write": "Writing the script", "cast": "Reading the cast"}


def latest(db: Session, job: Job) -> Script | None:
    """The job's script as the database has it now (sessions keep objects across commits,
    and the web side may have moved it on, e.g. a new press)."""
    return db.get(Script, job.input["script_id"], populate_existing=True)


WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)


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


def held(db: Session, user: User) -> Decimal:
    """Credits held for the reel-read steps this person already paid for that aren't queued
    yet: while a chain step runs, the steps after it. A chain that fails or stops holds
    nothing, so nothing has to be given back."""
    running = (
        select(Script)
        .join(Job, Job.id == Script.reel_job_id)
        .where(Job.created_by_id == user.id, Job.status.in_(WAITING), Job.kind != "reel_prepare")
    )
    total = Decimal(0)
    for script in db.scalars(running):
        job = db.get(Job, script.reel_job_id)
        later = [s for s in remaining(script) if s != job.input.get("reel_step")]
        total += price(db, user, later)
    return total


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


def watch_input(script: Script) -> dict:
    reel = script.reel
    said = [{**x, "text": escape(x["text"])} for x in reel["transcript"]]
    return {
        "step": "reel_watch",
        "script_id": script.id,
        "model": WATCH_MODEL,
        "input": {
            "prompt": prompts.reel_watch_input(said, shots(reel)),
            "system_instruction": prompts.watch_system(),
        },
        "files": {"images": [reel["contact_file_id"]]},
        "uploads": {"videos": [reel["video_file_id"]]},
    }


def _job_input(db: Session, script: Script, step: str) -> dict:
    if step == "watch":
        data = watch_input(script)
    elif step == "write":
        data = script_write.job_input(db, script, script.reference_breakdown)
    else:
        versions = {0: script_write.original(db, script).text}
        data = cast_read.job_input(db, script, script.reference_breakdown, versions)
    return {**data, "reel_step": step}


def queue(db: Session, user: User, script: Script, step: str, prepaid: bool = False) -> Job:
    """Queue one step and point the script at it (the import's latest job)."""
    from app.routes.jobs import enqueue

    provider = "replicate" if step == "watch" else "claude"
    data = _job_input(db, script, step)
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
    if not script.description:
        script.description = watch.logline


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
