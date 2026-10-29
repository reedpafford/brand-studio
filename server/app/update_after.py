"""Update everything after this (audit M14 part 2; flows "Out of date is viewable, never
locked"): one press on a held step brings the later work up to date in order, on the server,
so it carries on when the editor leaves the page. Today's presses and prices only:
1. the storyboard again, then every still drawn (its frames were made for older shots);
2. or only the out-of-date stills drawn again (another cast or look);
3. then the stale clip prompts rewritten, once the stills they show are drawn.
Takes stay out (each prompt needs Prompt OK first). The whole price is checked once, up
front, so nothing half-runs; a step that fails stops the rest, and that step shows its own
failure and press. Each job carries the run (RUN) and the steps after it (THEN)."""

import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clip_prompts, looks, storyboard
from app.credits import estimate
from app.models.accounts import User
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.prompts.schemas import Breakdown

RUN, THEN, STOP = "update_run", "update_then", "update_stopped"
FROM = {"plan": 0, "storyboard": 0, "clips": 2}  # where each held step's press starts
WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)
NOTHING = "Nothing after this is out of date."
STOPPED = "Stopped before the clip prompts: draw the stills that are left first."


def _frames(db: Session, project: Project) -> list[StoryboardFrame]:
    return list(db.scalars(select(StoryboardFrame).where(StoryboardFrame.project_id == project.id)
                           .order_by(StoryboardFrame.id)))  # fmt: skip


def _redraw(db: Session, project: Project) -> list[StoryboardFrame]:
    frames = _frames(db, project)
    return [f for f in frames if f.file_id and (f.still_stale or looks.frame_other(project, f))]


def _still(db: Session, project: Project) -> Decimal:
    job = storyboard.image_job_input(storyboard.image_model(), "", project.aspect_ratio)
    return estimate(db, project.workspace_id, "image", Decimal(1), job)


def _count(n: int, one: str) -> str:
    return f"1 {one}" if n == 1 else f"{n} {one}s"


def plan(db: Session, project: Project, start: str) -> list[dict]:
    """The steps the press would run, in order: {step, what, credits}."""
    from app.routes.storyboard import _stale

    bd = clip_prompts.newest(db, project)
    if bd is None:
        return []
    out, frames = [], _frames(db, project)
    if FROM[start] == 0 and frames and any(_stale(db, project, f) for f in frames):
        n = len(Breakdown.model_validate(bd.data).clips)  # one frame a clip (per_shot off)
        cost = estimate(db, project.workspace_id, "write-claude", Decimal(1))
        what = f"Make the storyboard again ({_count(n, 'frame')}, {_count(n, 'still')})"
        out.append({"step": "storyboard", "credits": cost + n * _still(db, project), "what": what})
    elif FROM[start] == 0 and (redraw := _redraw(db, project)):
        out.append({"step": "stills", "credits": len(redraw) * _still(db, project),
                    "what": f"Draw {_count(len(redraw), 'still')} again"})  # fmt: skip
    if ids := clip_prompts.to_rewrite(db, project):
        out.append({"step": "clip_prompts", "credits": clip_prompts.rewrite_price(db, project, ids),
                    "what": f"Rewrite {_count(len(ids), 'clip prompt')}"})  # fmt: skip
    return out


def start(db: Session, user: User, project: Project, start_from: str) -> list[dict]:
    """Start the first step, checked with the whole price; the rest follow on the server."""
    from app.routes.jobs import enqueue

    steps = plan(db, project, start_from)
    if not steps:
        raise HTTPException(409, NOTHING)
    then = [s["step"] for s in steps[1:]]
    if steps[0]["step"] == "storyboard":  # its stills are drawn once its frames are in
        then = ["stills", *then]
    tag = {RUN: uuid.uuid4().hex, THEN: then}
    total = sum((s["credits"] for s in steps), Decimal(0))
    if steps[0]["step"] == "storyboard":
        from app.breakdown import would_show
        from app.sheets import require_looks

        bd = clip_prompts.newest(db, project)
        require_looks(would_show(db, project, bd.data), storyboard.assets(db, project), 409)
        if any(j.input.get("step") == "storyboard" for j in _waiting(db, project)):
            raise HTTPException(409, "A storyboard is already being written for this project.")
        call = estimate(db, project.workspace_id, "write-claude", Decimal(1))
        enqueue(db, user, "write-claude", {**storyboard.job_input(db, project, bd, False), **tag},
                project=project, provider="claude", hold=total - call)  # fmt: skip
    elif steps[0]["step"] == "stills":
        _draw(db, user, project, _redraw(db, project), tag, hold=total - steps[0]["credits"])
    else:
        _prompts(db, user, project, tag, prepaid=False)
    return [{**s, "status": "started" if n == 0 else "waiting"} for n, s in enumerate(steps)]


def _waiting(db: Session, project: Project) -> list[Job]:
    rows = select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING))
    return list(db.scalars(rows))


def _draw(db, user, project, frames, tag, hold=Decimal(0), prepaid=False) -> None:
    """Each frame's still, every input made first so a refusal starts none; the first is
    checked with `hold` too (the price of the stills and steps after it)."""
    from app.routes.jobs import enqueue

    inputs = [{**storyboard.render_input(db, project, f), **tag} for f in frames]
    later = (len(inputs) - 1) * _still(db, project)
    for n, job_input in enumerate(inputs):
        enqueue(db, user, "image", job_input, project=project, provider="replicate",
                prepaid=prepaid or n > 0, hold=hold + later if n == 0 else Decimal(0))  # fmt: skip


def _prompts(db, user, project, tag, prepaid=True) -> None:
    ids = clip_prompts.to_rewrite(db, project)
    if ids:
        clip_prompts.queue_rewrite(db, user, project, ids, extra=tag, prepaid=prepaid)


def _stop(job: Job, step: str, reason: str) -> None:
    """The run stops here: `step` (the next one) didn't start, and why."""
    job.input = {**job.input, STOP: {"at": step, "reason": reason}}


def follow(db: Session, job: Job) -> None:
    """After a step of a run saved: start the next one (already paid for in the press). A
    refusal now (the video's budget, a take being made) stops the run with why."""
    if not (run := job.input.get(RUN)) or not (then := job.input.get(THEN)):
        return
    project, user = db.get(Project, job.project_id), db.get(User, job.created_by_id)
    tag = {RUN: run, THEN: then[1:]}
    db.commit()  # a refusal rolls back: never take the step that just saved with it
    try:
        if then[0] == "stills":
            from app import advice

            frames = [f for f in _frames(db, project) if not advice.blocking(f.problems)]
            if len(frames) < len(_frames(db, project)):
                tag = {RUN: run, THEN: []}  # a frame to fix first: no clip prompts after
                _stop(job, "clip_prompts", STOPPED)
            _draw(db, user, project, frames, tag, prepaid=True)
        elif then[0] == "clip_prompts" and not _others(db, job, run):
            _prompts(db, user, project, tag)
    except HTTPException as exc:
        _stop(job, then[0], exc.detail)


def _others(db: Session, job: Job, run: str) -> bool:
    """Not yet, or never: another still of this run is being drawn or didn't finish, or the
    run's clip prompts are already asked for."""
    rows = db.scalars(select(Job).where(Job.project_id == job.project_id, Job.id != job.id))
    mine = [j for j in rows if j.input.get(RUN) == run]
    return any(j.input.get("step") == "clip_prompts" for j in mine) or any(
        j.input.get("step") == "frame" and j.status != JobStatus.succeeded for j in mine
    )


NAMES = {"storyboard": "storyboard", "frame": "stills", "clip_prompts": "clip_prompts"}


def last_run(db: Session, project: Project) -> dict:
    """The newest run's state, for the banner: running, or where it stopped and why. A stop
    the editor has since put right with that step's own press (the same still, or the step
    that didn't start, made since) is over: nothing is said."""
    rows = list(db.scalars(select(Job).where(Job.project_id == project.id)
                           .order_by(Job.id.desc()).limit(200)))  # fmt: skip
    run = next((j.input[RUN] for j in rows if j.input.get(RUN)), None)
    mine = [j for j in rows if run and j.input.get(RUN) == run]
    failed = next((j for j in mine if j.status == JobStatus.failed), None)
    stopped = next((j for j in mine if j.input.get(STOP)), None)
    stop, at = (stopped.input[STOP], stopped) if stopped else (None, None)
    if failed:
        stop, at = {"at": NAMES.get(failed.input.get("step", "")), "reason": failed.error}, failed
    if stop and _put_right(rows, at, failed is not None, stop["at"]):
        stop = None
    return {"running": any(j.status in WAITING for j in mine),
            "stopped_at": stop and stop["at"], "reason": stop and stop["reason"]}  # fmt: skip


def _put_right(rows: list[Job], at: Job, failed: bool, step: str) -> bool:
    """A job for the same work succeeded after the stop: the failed still's own frame, or
    the failed or unstarted step."""
    kind = {v: k for k, v in NAMES.items()}[step]
    frame = at.input.get("frame_id") if failed and kind == "frame" else None

    def same(j: Job) -> bool:
        return j.input.get("step") == kind and (frame is None or j.input.get("frame_id") == frame)

    return any(j.id > at.id and j.status == JobStatus.succeeded and same(j) for j in rows)
