"""The site's director, first slice (docs/next/director-chat.md §1, §2, §6 items 3-4): builds
a video end to end from a published script, the editor path (its words locked), with the
site's own actions (`director_tools`). Each turn is one Claude call on the video (step
"director", paid from its budget like any press, so held for the owner past it): it reads the
video's state and its last actions and picks one tool; the server runs it. When the work it
started is all done, the next turn starts. The run's turns are its log, on the video.
Server-side limits whatever the answer: MAX_TURNS, MAX_REDOS a clip and MAX_USD of its own
Claude time. On the stand-ins (BS_FAKE_PROVIDERS) `choose` answers each turn: no paid call."""

import json
import logging
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import director_tools
from app.credits import COUNTED
from app.models.accounts import User
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.jobs import WAITING, Job, JobStatus, Usage
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft
from app.models.storyboards import StoryboardFrame

log = logging.getLogger(__name__)
STEP = "director"
RUN = "director_run"
MAX_TURNS = 40  # a run's turns at most
MAX_REDOS = 2  # takes made again for one clip after the take check flagged it
MAX_USD = Decimal(5)  # its own Claude time a video (Reed: "ideally less"); measured per run
NOT_PUBLISHED = "The director builds from a published script. Publish it first."
RUNNING = "The director is already building this video."
IDLE = "Waiting, with nothing being made: it reads the video again."


def start(db: Session, user: User, project: Project) -> Job:
    """A run on a video made from a published script (its words are locked): its first turn."""
    if why := blocked(db, project):
        raise HTTPException(409, why)
    run = {"id": uuid.uuid4().hex, "turn": 0, "redos": {}, "by": user.id}
    return _turn(db, user, project, run)


def blocked(db: Session, project: Project) -> str:
    """Why a run can't start on this video now ("" when it can): the start's own refusal."""
    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    if not (draft and db.get(Script, draft.script_id).published):
        return NOT_PUBLISHED
    return RUNNING if active(db, project) else ""


def credits(db: Session, project: Project) -> Decimal:
    """The newest run's cost "up to": every job on the video since its first turn (its turns
    and what its tools pressed), queued, running, held or done at their price; never a
    cancelled, declined or failed one (nothing charged)."""
    rows = turns(db, project)
    if not rows:
        return Decimal(0)
    counted = (*COUNTED, JobStatus.needs_owner_approval)
    return Decimal(db.scalar(select(func.coalesce(func.sum(Job.credits), 0)).where(
        Job.project_id == project.id, Job.id >= rows[0].id, Job.status.in_(counted))))  # fmt: skip


def turns(db: Session, project: Project) -> list[Job]:
    """Every turn of the video's newest run, in order (its log)."""
    rows = db.scalars(select(Job).where(Job.project_id == project.id,
                                        Job.input["step"].as_string() == STEP)
                      .order_by(Job.id)).all()  # fmt: skip
    run = rows[-1].input[RUN]["id"] if rows else None
    return [j for j in rows if j.input[RUN]["id"] == run]


def active(db: Session, project: Project) -> Job | None:
    """The newest run's last turn while the run goes on (not delivered, stopped or ended)."""
    last = next(reversed(turns(db, project)), None)
    if last is None or last.input.get("ended") or last.status in (JobStatus.cancelled,):
        return None
    return last


def stop(db: Session, project: Project, why: str = "Stopped.") -> None:
    if last := active(db, project):
        if last.status in WAITING:
            last.status = JobStatus.cancelled
        _end(last, why)
        db.commit()


def spent(db: Session, run_id: str) -> Decimal:
    """What the run's own Claude turns really cost (Usage), for the limit and to measure."""
    ids = select(Job.id).where(Job.input[RUN]["id"].as_string() == run_id)
    return Decimal(db.scalar(select(func.coalesce(func.sum(Usage.cost_usd), 0))
                             .where(Usage.job_id.in_(ids))))  # fmt: skip


def after(db: Session, job: Job, storage) -> None:
    """The worker finished `job`: a turn's answer is acted on; any other work on a video with
    a run going may wake the next turn."""
    if job.input.get("step") == STEP:
        if job.status == JobStatus.succeeded:
            _act(db, job, storage)
        else:
            _end(job, "A turn failed; nothing more was done. Start it again to go on.")
        return
    if job.project_id:
        wake(db, db.get(Project, job.project_id))


def wake(db: Session, project: Project) -> None:
    """The next turn, once the last one was acted on and nothing on the video is waiting."""
    last = active(db, project)
    if last is None or last.status != JobStatus.succeeded or "result" not in last.input:
        return
    if _waiting(db, project):
        return
    _turn(db, db.get(User, last.input[RUN]["by"]), project, dict(last.input[RUN]))


def sweep(db: Session) -> None:
    """Each worker tick: every run whose last turn was acted on and has nothing left being
    made gets its next turn, however its work ended (failed, cancelled, released): a run
    never waits on work that is over (QA on #1087)."""
    step = Job.input["step"].as_string()
    acted = select(Job.project_id).where(
        step == STEP, Job.status == JobStatus.succeeded,
        Job.input["result"].as_string().is_not(None), Job.input["ended"].as_string().is_(None),
    ).distinct()  # fmt: skip
    for project_id in db.scalars(acted).all():
        wake(db, db.get(Project, project_id))


def _act(db: Session, job: Job, storage) -> None:
    project, decision = db.get(Project, job.project_id), dict(job.output or {})
    run = dict(job.input[RUN])
    tool = decision.get("tool")
    if tool == "deliver":
        return _end(job, decision.get("why") or "Delivered.", result="Delivered.")
    if tool == "stop":  # it can't go on (a story choice, a step that keeps refusing): says why
        return _end(job, decision.get("why") or "It stopped.", result="Stopped.")
    if tool == "make_take" and decision.get("clip_id"):
        clip = decision["clip_id"]
        if run["redos"].get(clip, 0) >= MAX_REDOS and _has_take(db, project, clip):
            return _record(db, job, run, f"Refused: {clip} was made again {MAX_REDOS} times.")
        if _has_take(db, project, clip):
            run["redos"] = {**run["redos"], clip: run["redos"].get(clip, 0) + 1}
    if tool == "wait":  # with nothing being made (it read the video before a step saved), the
        idle = not _waiting(db, project)  # next turn reads it again now (`wake`), once
        rows = [j for j in turns(db, project) if j.id < job.id]
        if idle and rows and rows[-1].input.get("result") == IDLE:
            return _end(job, "It stopped: it waited twice with nothing being made.", result=IDLE)
        return _record(db, job, run, IDLE if idle else "Waiting.")
    if (refused := _refused_again(db, job, decision)) is not None:
        return _end(job, f"It stopped: {refused}", result=f"Refused again: {refused}")
    db.commit()  # the turn's answer is kept whatever the tool does
    user = db.get(User, run["by"])
    _record(db, job, run, director_tools.run(db, user, project, decision, storage))


def _refused_again(db: Session, job: Job, decision: dict) -> str | None:
    """The same tool, as it was, right after it was refused: the refusal (else None). Nothing
    changed, so it would be refused again; the run stops and says why."""
    rows = turns(db, db.get(Project, job.project_id))
    before = next((j for j in reversed(rows) if j.id < job.id), None)
    said = (before.input.get("result") or "") if before else ""
    keys = ("tool", "clip_id", "take_id", "note")
    same = before is not None and all((before.output or {}).get(k) == decision.get(k) for k in keys)
    return said.removeprefix("Refused: ") if same and said.startswith("Refused: ") else None


def _record(db: Session, job: Job, run: dict, result: str) -> None:
    """The turn's result on its log line; the next turn starts now if nothing it started is
    being made (else when that's done: `wake`)."""
    job = db.get(Job, job.id)
    job.input = {**job.input, RUN: run, "result": result}
    db.commit()
    wake(db, db.get(Project, job.project_id))


def _end(job: Job, why: str, result: str = "") -> None:
    job.input = {**job.input, "ended": why, **({"result": result} if result else {})}


def _turn(db: Session, user: User, project: Project, run: dict) -> Job:
    from app.routes.jobs import enqueue

    last = next(reversed(turns(db, project)), None)
    if last is not None and (gave_up := _failed_too_often(db, project, run)):
        made = video_state(db, project)["cut"] == "made"  # what it has: a cut, or nothing
        last = db.get(Job, last.id)
        _end(last, f"{gave_up}; delivered without it." if made else f"It stopped: {gave_up}.",
             result="Delivered." if made else "")  # fmt: skip
        db.commit()
        return last
    if run["turn"] >= MAX_TURNS or spent(db, run["id"]) >= MAX_USD:
        why = (f"It stopped after {MAX_TURNS} turns." if run["turn"] >= MAX_TURNS
               else f"It stopped at ${MAX_USD} of its own time.")  # fmt: skip
        if last is not None:
            _end(last, why)
            db.commit()
        return last
    run = {**run, "turn": run["turn"] + 1}
    data = {"step": STEP, RUN: run, **turn_input(db, project, run)}
    try:
        return enqueue(
            db, user, "write-claude", data, project=project, provider="claude", prepaid=True
        )  # its own limit (MAX_USD), never the video's budget; the
        # per-video cap still counts it (director-chat.md §2, DECISIONS #1066)
    except HTTPException as no:  # e.g. the per-video cap: the run ends, saying why
        if last is None or run["turn"] == 1:  # its first turn: the start itself is refused
            raise
        last = db.get(Job, last.id)
        _end(last, f"It stopped: {no.detail}")
        db.commit()
        return last


def refresh(db: Session, job: Job) -> None:
    """A turn about to be asked reads the video as it is now, not as it was when queued (a
    step saved since, or the turn waited for the owner)."""
    project = db.get(Project, job.project_id)
    job.input = {**job.input, **turn_input(db, project, job.input[RUN])}
    db.commit()


def turn_input(db: Session, project: Project, run: dict) -> dict:
    """The director's prompt (app/prompts/director.md, the Director's) and the brand, then the
    video's state, its run's last actions and what it still may do."""
    from app.enhance import project_context

    system, brief = project_context(db, project, STEP)
    done = [{"tool": (j.output or {}).get("tool"), "why": (j.output or {}).get("why"),
             "result": j.input.get("result")} for j in turns(db, project)[-8:]]  # fmt: skip
    allowed = {"turns_left": MAX_TURNS - run["turn"], "redos_per_clip": MAX_REDOS,
               "redos_used": run["redos"], "own_time_usd": float(spent(db, run["id"])),
               "own_time_limit_usd": float(MAX_USD)}  # fmt: skip
    parts = (("video", video_state(db, project)), ("last_actions", done), ("allowed", allowed))
    tagged = "\n".join(f"<{tag}>\n{json.dumps(value, indent=1)}\n</{tag}>" for tag, value in parts)
    return {"system": system, "prompt": f"{brief}\n{tagged}"}


def video_state(db: Session, project: Project) -> dict:
    """Where the video is, as the director reads it (and `choose` on the stand-ins)."""
    from app.clip_prompts import newest
    from app.item_checks import latest, shown, verdict
    from app.routes.project_assets import _missing
    from app.routes.project_clips import out_of_date

    bd = newest(db, project)
    frames = [f for f in db.scalars(select(StoryboardFrame).where(
        StoryboardFrame.project_id == project.id)) if bd and f.breakdown_id == bd.id]  # fmt: skip
    clips = []
    for row in db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)
                          .order_by(ProjectClip.id)):  # fmt: skip
        takes = db.scalars(select(ClipTake).where(ClipTake.clip_id == row.id)
                           .order_by(ClipTake.number)).all()  # fmt: skip
        ids = [t.id for t in takes]
        seen, heard = latest(db, "take", ids), latest(db, "words", ids)
        out = []
        for t in takes:
            checks = [shown(db, seen.get(t.id)), shown(db, heard.get(t.id))]
            notes = [f.note for c in checks if c for f in c.findings]
            out.append({"id": t.id, "number": t.number, "verdict": verdict(checks),
                        "notes": notes})  # fmt: skip
        clips.append({"clip_id": row.clip_id, "stale": bool(bd and row.breakdown_id != bd.id),
                      "picked_take_id": row.picked_take_id, "takes": out})  # fmt: skip
    video = db.scalar(select(FinalVideo).where(FinalVideo.project_id == project.id).limit(1))
    waiting = _waiting(db, project)
    acted = [j for j in turns(db, project) if "result" in j.input]
    failed = db.scalars(select(Job).where(
        Job.project_id == project.id, Job.status == JobStatus.failed,
        Job.finished_at >= acted[-1].created_at)) if acted else []  # fmt: skip
    from app.plans import status

    return {
        "plan": status(db, project),  # none, ready (waits for approval) or approved
        "shots": "ready" if bd else "none",
        "missing_looks": [s.role for s in _missing(db, project)] if bd else [],
        "stills": {"frames": len(frames), "drawn": sum(1 for f in frames if f.file_id)},
        "clips": clips,
        "cut": "none" if not video else
               ("out of date" if project.id in out_of_date(db, [project]) else "made"),
        "being_made": len([j for j in waiting if j.status != JobStatus.needs_owner_approval]),
        "held_for_owner": [j.input.get("held", "") for j in waiting
                           if j.status == JobStatus.needs_owner_approval],
        "failed_since_last_turn": [j.error or "It didn't finish." for j in failed],
    }  # fmt: skip


def choose(state: dict) -> dict:
    """The stand-in director (no paid call): the agents' order, step by step. A flagged take
    is made again with the take check's notes (the server counts the redos)."""

    def go(tool: str, why: str, **extra) -> dict:
        return {"tool": tool, "why": why, "clip_id": None, "take_id": None, "note": "", **extra}

    clips = state["clips"]
    if state["being_made"] or state["held_for_owner"]:
        return go("wait", "Something is still being made or waits for the owner.")
    if state["shots"] == "none":
        return go("plan", "There are no shots yet.")
    if state["missing_looks"]:
        return go("make_looks", "Some roles have no look yet.")
    if not state["stills"]["frames"]:
        return go("storyboard", "The shots are ready; the storyboard is next.")
    if state["stills"]["drawn"] < state["stills"]["frames"]:
        return go("stills", "Some frames have no still yet.")
    if not clips or any(c["stale"] for c in clips):
        return go("clip_prompts", "The clips need their prompts.")
    if any(not c["takes"] for c in clips):
        return go("make_take", "Some clips have no take yet.")
    for c in clips:
        last = c["takes"][-1]
        if last["verdict"] == "checking":
            return go("wait", f"{c['clip_id']}'s take is being checked.")
        if last["verdict"] == "flagged" and len(c["takes"]) <= MAX_REDOS:
            note = "; ".join(last["notes"]) or "Fix what the take check found."
            return go("make_take", f"The take check flagged {c['clip_id']}.",
                      clip_id=c["clip_id"], note=note[:500])  # fmt: skip
    for c in clips:  # the newest clean take (Builder-Server-8's best-take function to come)
        clean = next((t for t in reversed(c["takes"]) if t["verdict"] == "clean"), None)
        best = clean or c["takes"][-1]
        if c["picked_take_id"] != best["id"]:
            why = (f"Take {best['number']} is {c['clip_id']}'s newest clean take." if clean
                   else f"No take of {c['clip_id']} is clean: using the newest, take "
                   f"{best['number']}.")  # fmt: skip
            return go("pick_take", why, clip_id=c["clip_id"], take_id=best["id"])
    if state["cut"] != "made":
        unclean = [c["clip_id"] for c in clips
                   if not any(t["verdict"] == "clean" for t in c["takes"])]  # fmt: skip
        said = f" No take of {', '.join(unclean)} is clean: its newest is used." if unclean else ""
        return go("final_cut", f"Every clip has its take.{said}")
    return go("deliver", "The cut is made with each clip's best take.")


def _failed_too_often(db: Session, project: Project, run: dict) -> str:
    """Plain words for the first item of the run's work that failed more than MAX_REDOS
    times since the run began (tried, then retried twice), e.g. "Clip 3's still failed 3
    times"; else "". The run then delivers what it has or stops, never spending turns on it."""
    first = next((j for j in turns(db, project) if j.input[RUN]["id"] == run["id"]), None)
    if first is None:
        return ""
    counts: dict[str, int] = {}
    for job in db.scalars(select(Job).where(Job.project_id == project.id,
                                            Job.status == JobStatus.failed,
                                            Job.created_at >= first.created_at)):  # fmt: skip
        what = _item(db, job)
        counts[what] = counts.get(what, 0) + 1
        if counts[what] > MAX_REDOS:
            return f"{what} failed {counts[what]} times"
    return ""


def _item(db: Session, job: Job) -> str:
    """What a failed job was making, in plain words: "Clip 3's still", "Clip 3's take"."""
    if frame := job.input.get("frame_id"):
        row = db.get(StoryboardFrame, frame)
        return f"Clip {row.clip_id.removeprefix('c')}'s still" if row else "A still"
    if clip := job.input.get("project_clip_id"):
        row = db.get(ProjectClip, clip)
        return f"Clip {row.clip_id.removeprefix('c')}'s take" if row else "A take"
    return f"The {str(job.input.get('step') or job.kind).replace('_', ' ')}"


def _waiting(db: Session, project: Project) -> list[Job]:
    step = Job.input["step"].as_string()
    return list(db.scalars(select(Job).where(Job.project_id == project.id,
                                             Job.status.in_(WAITING),
                                             or_(step.is_(None), step != STEP))))  # fmt: skip


def _has_take(db: Session, project: Project, clip_id: str) -> bool:
    row = db.scalar(select(ProjectClip).where(ProjectClip.project_id == project.id,
                                              ProjectClip.clip_id == clip_id))  # fmt: skip
    return bool(row and row.picked_take_id)
