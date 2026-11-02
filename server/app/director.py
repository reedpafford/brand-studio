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
import re
import uuid
from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app import director_song, director_tools, take_mute, word_splice
from app.credits import COUNTED, lock
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
MAX_REPLANS = 1  # plans made again from the watch ("Re-plan: …"), a run
MAX_WATCHES = 3  # watches of the cut a run (watch_cut, Reed 1 Nov: "watch and make those fixes")
MAX_USD = Decimal(5)  # its own Claude time a video (Reed: "ideally less"); measured per run
OWN_CREDITS = Decimal(75)  # its turns and watches a run, as charged and quoted (the Producer)
NOT_PUBLISHED = "The director builds from a published script. Publish it first."
UNWATCHED = "Refused: watch the cut first."
RUNNING = "The director is already building this video."
NOTE = re.compile(r"\bnote (\d+)\b", re.I)  # how a move's why names the note it answers
OPEN = "Refused: note {0} is still open. Make it, or say why it can't; write Note {0} in that move."
READ = "chat_read"  # in a turn's input: how many of its run's messages it read
GAP, PER_RUN = timedelta(seconds=3), 30  # one note a person every 3 s; notes a run at most
TOO_MANY = "Too many messages; wait a moment."
IDLE = "Waiting, with nothing being made: it reads the video again."
WATCHED_AGAIN = "Refused: it already watched this cut; fix something or deliver."
PENDING = {JobStatus.queued: "Deciding what to do next.",
           JobStatus.running: "Deciding what to do next.",
           JobStatus.needs_owner_approval: "Waiting for the owner's OK."}  # fmt: skip
TURN_FAILED = "A turn failed; nothing more was done. Start it again to go on."


def start(db: Session, user: User, project: Project, *, wait: str = "", extra: dict | None = None,
          frozen: bool = True) -> Job:  # fmt: skip
    """A run on a video made from a published script (its words are locked): its first turn.
    `wait`: the turn waits for the owner with that reason (a freestyle's editor send);
    `extra`: more of its input (the freestyle it's for). `frozen=False`: a freestyle's, whose
    version is frozen and published when its run starts (`freestyles.freeze`)."""
    if why := blocked(db, project) if frozen else (RUNNING if active(db, project) else ""):
        raise HTTPException(409, why)
    run = {"id": uuid.uuid4().hex, "turn": 0, "redos": {}, "by": user.id}
    lock(db, Project, project.id)  # the notes it takes can't change under it
    db.refresh(project)
    left = set(leftover(db, project))  # every note no run has read: this run reads them
    if left:
        project.director_chat = [{**m, "run": run["id"]} if n in left else m
                                 for n, m in enumerate(project.director_chat)]  # fmt: skip
    return _turn(db, user, project, run, wait=wait, extra=extra)


def say(db: Session, user: User, project: Project, text: str) -> None:
    """A person's note to the director (director-chat.md §1 item 4), kept in the thread. While
    a run goes on, its next turn reads it (a turn already in flight, the one after). It never
    starts a run: after Stop or a delivery it waits, unread, for the next Make it, which reads
    every unread note. Nothing is charged for it."""
    from app.db import utcnow

    lock(db, Project, project.id)  # never lost to a run starting or ending as it lands
    db.refresh(project)
    going = active(db, project)
    run_id = going.input[RUN]["id"] if going else None
    every = project.director_chat or []
    now = utcnow()
    last = next((m["at"] for m in reversed(every) if m["by"] == user.id), "")
    waiting = ([m for m in every if m.get("run") == run_id] if going
               else [every[n] for n in leftover(db, project)])  # fmt: skip
    if last > (now - GAP).isoformat() or len(waiting) >= PER_RUN:
        db.rollback()
        raise HTTPException(429, TOO_MANY)
    said = {"by": user.id, "text": text, "at": now.isoformat(), "run": run_id}
    project.director_chat = [*every, said]
    db.commit()


def chat(project: Project, run_id: str) -> list[dict]:
    """What people asked of this run, oldest first."""
    return [{"text": m["text"]} for m in project.director_chat or [] if m.get("run") == run_id]


def answered(db: Session, run_id: str) -> set[int]:
    """The run's notes (numbered from 1) a move has answered: named "Note N" in the why of a
    move that wasn't refused, or of the delivery. An ask stays open until then."""
    mine = Job.input[RUN]["id"].as_string() == run_id
    rows = db.scalars(select(Job).where(Job.input["step"].as_string() == STEP, mine)).all()
    return {int(n) for j in rows if not (j.input.get("result") or "").startswith("Refused")
            for n in NOTE.findall((j.output or {}).get("why") or "")}  # fmt: skip


def leftover(db: Session, project: Project) -> list[int]:
    """The notes (by place in the chat) that no run read and none will: sent with no run
    going, or while a run's last turn delivered or it stopped. The next Make it reads them."""
    rows = db.scalars(select(Job).where(Job.project_id == project.id,
                                        Job.input["step"].as_string() == STEP)).all()  # fmt: skip
    read: dict[str, int] = {}
    for j in rows:
        run = j.input[RUN]["id"]
        read[run] = max(read.get(run, 0), j.input.get(READ, 0))
    going = active(db, project)
    live = going.input[RUN]["id"] if going else None
    seen: dict[str | None, int] = {}
    out = []
    for n, m in enumerate(project.director_chat or []):
        run = m.get("run")
        if run is not None and run == live:
            continue  # its next turn reads it
        seen[run] = seen.get(run, 0) + 1
        if run is None or seen[run] > read.get(run, 0):
            out.append(n)
    return out


def thread(db: Session, project: Project) -> list[dict]:
    """The whole conversation on the video, oldest first: what people said and each of the
    director's moves, as plain lines (a held move says so)."""
    from app.auth import user_name

    rows = db.scalars(select(Job).where(Job.project_id == project.id,
                                        Job.input["step"].as_string() == STEP)
                      .order_by(Job.id)).all()  # fmt: skip
    done = {r: answered(db, r) for r in {m.get("run") for m in project.director_chat or []} if r}
    place: dict[str | None, int] = {}  # a note's number in its run ("Note N"), as `answered` reads
    out = []
    for n, m in enumerate(project.director_chat or []):
        place[m.get("run")] = place.get(m.get("run"), 0) + 1
        out.append({"id": f"m{n}", "kind": "message", "at": m["at"],
                    "who": user_name(db, m["by"]), "text": m["text"], "status": None, "why": "",
                    "answered": place[m.get("run")] in done.get(m.get("run"), set())})  # fmt: skip
    from app.credits import price

    written = db.scalars(select(Job).where(Job.project_id == project.id,
                                           Job.input["step"].as_string() == "treatment",
                                           Job.status == JobStatus.succeeded)
                         .order_by(Job.id)).all()  # fmt: skip
    written = [j for j in written if not j.input.get("redone")]  # its check's one redo replaced it
    for n, j in enumerate(written):  # the treatment, posted in the chat as plain lines
        out.append({"id": f"s{j.id}", "kind": "move", "at": (j.finished_at or j.created_at
                    ).isoformat(), "who": "Director", "text": named(told(j.output or {}, n > 0)),
                    "status": "done", "why": "", "answered": None,
                    "treatment": j.output})  # fmt: skip
    for j in rows:
        if j.input.get(GRANT) and j.status in COUNTED:  # the owner's OK at the director's limit
            out.append({"id": f"g{j.id}", "kind": "move", "at": j.created_at.isoformat(),
                        "who": "Director", "text": GRANTED.format(n=price(own_limit())),
                        "status": "done", "why": "", "answered": None})  # fmt: skip
        result = j.input.get("result") or ""
        tool = (j.output or {}).get("tool")
        text = (
            ((j.output or {}).get("why") if tool == "deliver" else result)
            or (
                j.input.get("held")  # a held turn says why it waits
                if j.status == JobStatus.needs_owner_approval
                else ""
            )
            or PENDING.get(j.status, TURN_FAILED if j.status == JobStatus.failed else "Stopped.")
        )
        why = "" if tool == "deliver" else (j.output or {}).get("why") or ""  # deliver's is text
        text, why = named(text), named(why)
        status = ("held" if j.status == JobStatus.needs_owner_approval
                  else str(j.status) if j.status in (JobStatus.queued, JobStatus.running)
                  else "refused" if result.startswith("Refused") else "done")  # fmt: skip
        out.append({"id": f"t{j.id}", "kind": "move", "at": j.created_at.isoformat(),
                    "who": "Director",
                    "text": text, "status": status, "why": why, "answered": None})  # fmt: skip
    return sorted(out, key=lambda m: m["at"])


def named(text: str) -> str:
    """Clips as people see them ("clip 1"), never their ids ("c1")."""
    return re.sub(r"\bc(\d+)\b", r"clip \1", text)


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
    if last is None or last.status == JobStatus.cancelled or over(db, last.input[RUN]["id"]):
        return None
    return last


def over(db: Session, run_id: str) -> bool:
    """Whether a run has ended (delivered, stopped, failed): ANY of its turns says so, read
    fresh. A turn made while Stop landed (QA-7, round 3) never brings the run back."""
    return bool(db.scalar(select(func.count()).where(
        Job.input["step"].as_string() == STEP, Job.input[RUN]["id"].as_string() == run_id,
        Job.input["ended"].as_string().is_not(None))))  # fmt: skip


def ended(db: Session, project: Project) -> str:
    """Why the newest run ended, in plain words, from whichever of its turns says ("")."""
    return next((j.input["ended"] for j in reversed(turns(db, project))
                 if j.input.get("ended")), "")  # fmt: skip


def stop(db: Session, project: Project, why: str = "Stopped.") -> None:
    """No more turns. A turn not yet asked is cancelled (only if the worker hasn't taken it);
    one being asked finishes, and what its call cost is recorded and charged as ever (a paid
    call is always logged), but nothing more is done."""
    if last := active(db, project):
        db.execute(update(Job).where(Job.id == last.id, Job.status.in_(
            (JobStatus.queued, JobStatus.needs_owner_approval))).values(
            status=JobStatus.cancelled))  # fmt: skip
        db.refresh(last)
        _end(last, why)
        db.commit()


def spent(db: Session, run_id: str) -> Decimal:
    """What the run's own Claude turns really cost (Usage), for the limit and to measure."""
    ids = select(Job.id).where(Job.input[RUN]["id"].as_string() == run_id)
    return Decimal(db.scalar(select(func.coalesce(func.sum(Usage.cost_usd), 0))
                             .where(Usage.job_id.in_(ids))))  # fmt: skip


OWN_LIMIT = "Waiting for the owner's OK: the director has used its own limit of {n} credits."
GRANTED = "OK'd: up to {n} more credits of the director's time."
GRANT = "own_grant"  # in a run's job's input: held at the director's own limit (`past_own`)


def own_limit() -> Decimal:
    """The director's own limit a run, in credits, as the quote shows it: OWN_CREDITS (MAX_USD
    stays the real-cost backstop)."""
    return OWN_CREDITS


def own_charged(db: Session, run_id: str) -> tuple[Decimal, int]:
    """What the run's own jobs (its turns and its watches of the cut) were charged, at the
    flat price each was charged (not their real cost, `spent`), and how many OKs the owner
    gave at its limit."""
    mine = (Job.input[RUN]["id"].as_string() == run_id, Job.status.in_(COUNTED))
    charged = db.scalar(select(func.coalesce(func.sum(Job.credits), 0)).where(*mine))
    oks = db.scalar(select(func.count()).where(*mine, Job.input[GRANT].as_boolean()))
    return Decimal(charged), oks


def past_own(db: Session, project: Project, run_id: str | None, credits: Decimal) -> str:
    """A run's next turn or watch that would take its charges past the director's own limit
    (the Producer): it waits for the owner, the owner's own run too, with a freestyle's
    reason for a step past its price, else OWN_LIMIT. Each OK grants another limit's worth,
    not one step. "" if it fits."""
    from app.credits import PAST_APPROVED, price

    if not run_id:
        return ""
    charged, oks = own_charged(db, run_id)
    if charged + credits <= own_limit() * (1 + oks):
        return ""
    return PAST_APPROVED if project.hidden else OWN_LIMIT.format(n=price(own_limit()))


def after(db: Session, job: Job, storage) -> None:
    """The worker finished `job`: a turn's answer is acted on; any other work on a video with
    a run going may wake the next turn."""
    if job.input.get("step") == STEP:
        if _stopped(db, job) or over(db, job.input[RUN]["id"]):  # Stop landed while it ran
            return
        if job.status == JobStatus.succeeded:
            _act(db, job, storage)
        else:
            _end(job, TURN_FAILED)
        return
    run_id = (job.input.get(RUN) or {}).get("id")
    if job.input.get("step") == "treatment" and job.status == JobStatus.succeeded:
        if run_id and over(db, run_id):  # stopped meanwhile: nothing more runs for it
            return
        if _treatment_checked(db, job):  # one redo with its problems: the redo wakes the run
            return
    if job.project_id:
        wake(db, db.get(Project, job.project_id))


def _treatment_checked(db: Session, job: Job) -> bool:
    """The Director's free check on a saved treatment (check.treatment: every line once, in
    order, word for word): problems mean one redo with them as its note; a redo's problems
    are kept and shown. Whether a redo was queued."""
    from app import plans
    from app.prompts import check

    project = db.get(Project, job.project_id)
    version = plans.script(db, project)
    problems = check.treatment(job.output or {}, version.text if version else "")
    if not problems:
        return False
    if job.input.get("redo"):  # kept as it is, its problems shown in the thread
        job.output = {**(job.output or {}), "problems": problems}
        db.commit()
        return False
    job.input = {**job.input, "redone": True}  # the thread shows the one it kept
    write_treatment(db, db.get(User, job.created_by_id), project, job.input.get(RUN),
                    "Fix: " + " ".join(problems), redo=True)  # fmt: skip
    return True


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
    failed = select(Job).where(step == STEP, Job.status == JobStatus.failed,
                               Job.input["ended"].as_string().is_(None))  # fmt: skip
    for job in db.scalars(failed).all():  # failed before its finish (a bad answer): it ends
        _end(job, TURN_FAILED)
    db.commit()


def _act(db: Session, job: Job, storage) -> None:
    project, decision = db.get(Project, job.project_id), dict(job.output or {})
    run = dict(job.input[RUN])
    tool = decision.get("tool")
    if tool == "deliver":
        watch = _watch(db, project)
        watched = watch.get("current") and watch.get("state") in ("done", "failed")
        if (video_state(db, project)["cut"] != "none" and run.get("watches", 0) < MAX_WATCHES
                and not watched):  # a watch still going isn't one (QA-10)  # fmt: skip
            return _record(db, job, run, UNWATCHED)  # the Director: it watches what it delivers
        named = {int(n) for n in NOTE.findall(decision.get("why") or "")}
        given = max((t.input.get(READ, 0) for t in turns(db, project)
                     if t.input[RUN]["id"] == run["id"]), default=0)  # fmt: skip
        # a note no turn was given yet isn't its to answer: it waits for the next Make it
        if left := [n for n in range(1, given + 1) if n not in answered(db, run["id"]) | named]:
            return _record(db, job, run, OPEN.format(left[0]))
        why = " ".join([decision.get("why") or "Delivered.", *_mutes(db, job, run)])
        job.output = {**decision, "why": why}  # the note the video page shows names the mutes
        return _end(job, why, result="Delivered.")  # a note it didn't read waits for Make it
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
    if tool == "redraw_still":  # the review's redraws: twice a still, a run
        from app.still_review import REDRAWS

        sid = decision.get("shot_id") or ""
        if run.get("redraws", {}).get(sid, 0) >= REDRAWS:
            return _record(db, job, run, f"Refused: shot {sid} was drawn again {REDRAWS} times.")
    replan = tool == "plan" and bool((decision.get("note") or "").strip())
    if replan and run.get("replans", 0) >= MAX_REPLANS:  # the watch's "Re-plan:", once a run
        return _record(db, job, run, f"Refused: it planned again {MAX_REPLANS} time this run.")
    if tool == "watch_cut":  # its own eyes on the cut: 3 a run, never the same cut twice
        watch = _watch(db, project)
        if run.get("watches", 0) >= MAX_WATCHES:
            return _record(db, job, run, f"Refused: it watched {MAX_WATCHES} times this run.")
        if watch.get("state") in ("watching", "done") and watch.get("current"):
            return _record(db, job, run, WATCHED_AGAIN)  # not a watch; it goes on
    db.commit()  # the turn's answer is kept whatever the tool does
    user = db.get(User, run["by"])
    result = director_tools.run(db, user, project, decision, storage, run)
    if tool == "watch_cut" and not result.startswith("Refused"):
        run["watches"] = run.get("watches", 0) + 1
    if replan and not result.startswith("Refused"):
        run["replans"] = run.get("replans", 0) + 1
    if tool == "redraw_still" and not result.startswith("Refused"):
        sid = decision.get("shot_id") or ""
        run["redraws"] = {**run.get("redraws", {}), sid: run.get("redraws", {}).get(sid, 0) + 1}
    _record(db, job, run, result)


def _mutes(db: Session, job: Job, run: dict) -> list[str]:
    """What this run muted instead of remaking, for the delivery note."""
    rows = turns(db, db.get(Project, job.project_id))
    return [j.input["result"] for j in rows if j.input[RUN]["id"] == run["id"]
            and (j.output or {}).get("tool") == "mute"
            and j.input.get("result", "").startswith("Muted")]  # fmt: skip


def _stills_review(db: Session, project: Project) -> dict:
    from app import still_review

    return still_review.state(db, project)


def _watch(db: Session, project: Project) -> dict:
    """The newest watch of the cut (watch_cut, Builder-Server-8's): {"state": "none"} before."""
    from app import watch_cut

    return watch_cut.state(db, project)


def to_mute(db: Session, row: ProjectClip) -> list[list[float]]:
    """The stretches the director's mute silences on a clip's picked take, in its seconds:
    the current watch's mute findings for that clip and the words check's unscripted lines,
    less any already muted. Never a time the model gives: so never a script word."""
    from app.item_checks import latest, shown

    take = db.get(ClipTake, row.picked_take_id) if row.picked_take_id else None
    if take is None:
        return []
    watch = _watch(db, db.get(Project, row.project_id))
    spans = [
        f["mute"]
        for f in watch.get("findings") or []
        if watch.get("current")
        and f.get("fix") == "mute"
        and f.get("clip_id") == row.clip_id
        and f.get("mute")
    ]
    heard = shown(db, latest(db, "words", [take.id]).get(take.id))
    spans += [f.mute for f in (heard.findings if heard else [])
              if f.kind in ("extra", "voiced") and f.mute]  # fmt: skip
    done = {tuple(s) for s in take_mute.spans(take)}
    out = []
    for s in spans:
        span = [round(float(s[0]), 2), round(float(s[1]), 2)]
        if tuple(span) not in done and span not in out:
            out.append(span)
    return out


def _refused_again(db: Session, job: Job, decision: dict) -> str | None:
    """The same tool, as it was, right after it was refused: the refusal (else None). Nothing
    changed, so it would be refused again; the run stops and says why. Asking to watch the
    same cut again never stops it: it's told to fix something or deliver (QA on #1145)."""
    rows = turns(db, db.get(Project, job.project_id))
    before = next((j for j in reversed(rows) if j.id < job.id), None)
    said = (before.input.get("result") or "") if before else ""
    keys = ("tool", "clip_id", "take_id", "note")
    same = before is not None and all((before.output or {}).get(k) == decision.get(k) for k in keys)
    if said == WATCHED_AGAIN or not (same and said.startswith("Refused: ")):
        return None
    return said.removeprefix("Refused: ")


def _record(db: Session, job: Job, run: dict, result: str) -> None:
    """The turn's result on its log line; the next turn starts now if nothing it started is
    being made (else when that's done: `wake`)."""
    job = db.get(Job, job.id)
    _stopped(db, job)
    kept = _write(db, job, {**job.input, RUN: run, "result": result})
    if not kept:  # pressed while the tool ran: its result is kept beside the stop, no more
        db.refresh(job)
        job.input = {**job.input, "result": result}
    db.commit()
    if kept and not over(db, run["id"]):
        wake(db, db.get(Project, job.project_id))


def _write(db: Session, job: Job, data: dict) -> bool:
    """A turn's input written only while its run hasn't ended, in one statement, so a Stop
    that lands meanwhile is never overwritten (QA-7); whether it was written."""
    done = db.execute(update(Job).where(Job.id == job.id,
                                        Job.input["ended"].as_string().is_(None))
                      .values(input=data).execution_options(synchronize_session=False))  # fmt: skip
    return done.rowcount == 1


def _stopped(db: Session, job: Job) -> bool:
    """Whether the run ended (Stop) since `job` was read: a fresh read, so what the worker
    writes next keeps the stop instead of overwriting it with what it read before."""
    db.refresh(job)
    return bool(job.input.get("ended"))


def _end(job: Job, why: str, result: str = "") -> None:
    job.input = {**job.input, "ended": why, **({"result": result} if result else {})}


def _turn(db: Session, user: User, project: Project, run: dict, *, wait: str = "",
          extra: dict | None = None) -> Job:  # fmt: skip
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
    prompt = turn_input(db, project, run)
    prompt.pop(READ)  # a note counts as given only once its turn starts (`refresh`)
    data = {"step": STEP, RUN: run, **prompt, **(extra or {})}
    if not wait:  # past its own limit, or a freestyle's price, the run pauses for an OK
        from app.credits import estimate, past_approved

        turn = estimate(db, project.workspace_id, "write-claude", Decimal(1), data)
        wait = past_own(db, project, run["id"], turn)
        data = {**data, GRANT: True} if wait else data  # an OK here grants another limit
        wait = wait or past_approved(db, project, user, turn)
    try:
        return enqueue(db, user, "write-claude", data, project=project, provider="claude",
                       prepaid=not wait, wait=wait)  # fmt: skip
        # its own limit (MAX_USD), never the video's budget; the per-video cap still counts
        # it (director-chat.md §2, DECISIONS #1066)
    except HTTPException as no:  # e.g. the per-video cap: the run ends, saying why
        if last is None or run["turn"] == 1:  # its first turn: the start itself is refused
            raise
        last = db.get(Job, last.id)
        _end(last, f"It stopped: {no.detail}")
        db.commit()
        return last


def refresh(db: Session, job: Job) -> bool:
    """A turn about to be asked reads the video as it is now, not as it was when queued (a
    step saved since, or the turn waited for the owner). False when its run was stopped
    before the call: the worker then makes no call (nothing is charged)."""
    project = db.get(Project, job.project_id)
    db.refresh(job)
    if job.input.get("ended") or over(db, job.input[RUN]["id"]):
        return False
    asked = turn_input(db, project, job.input[RUN], job.id)  # given to this turn as it starts
    db.refresh(job)  # Stop may land while the prompt is built: checked as it's written
    kept = _write(db, job, {**job.input, **asked})
    db.commit()
    db.refresh(job)
    return kept and not over(db, job.input[RUN]["id"])  # the last check, right before the call


def turn_input(db: Session, project: Project, run: dict, job_id: int | None = None) -> dict:
    """The director's prompt (app/prompts/director.md, the Director's) and the brand, then the
    video's state, its run's last actions and what it still may do."""
    from app.enhance import project_context

    system, brief = project_context(db, project, STEP)
    done = [{"tool": (j.output or {}).get("tool"), "why": (j.output or {}).get("why"),
             "result": j.input.get("result")} for j in turns(db, project)
            if j.input[RUN]["id"] == run["id"] and j.id != job_id]  # the whole run  # fmt: skip
    allowed = {"turns_left": MAX_TURNS - run["turn"], "redos_per_clip": MAX_REDOS,
               "watches_left": MAX_WATCHES - run.get("watches", 0),
               "redos_used": run["redos"], "own_time_usd": float(spent(db, run["id"])),
               "own_time_limit_usd": float(MAX_USD),
               "replans_left": MAX_REPLANS - run.get("replans", 0),
               "songs_left": director_song.REMAKES - run.get("songs", 0),
               "narrations_left": director_song.REMAKES - run.get("songs", 0),
               "redraws_per_still": 2, "redraws_used": run.get("redraws", {})}  # fmt: skip
    given = max((t.input.get(READ, 0) for t in turns(db, project)
                 if t.input[RUN]["id"] == run["id"] and t.id != job_id), default=0)  # fmt: skip
    closed = answered(db, run["id"])
    asked = [{"note": n + 1, **m, "new": n >= given, "answered": n + 1 in closed}
             for n, m in enumerate(chat(project, run["id"]))]  # fmt: skip
    # new: no earlier turn was given it. answered: a move named it ("Note N"); else still open
    own = db.scalar(select(Job.id).where(Job.input["step"].as_string() == "treatment",
                                         Job.input[RUN]["id"].as_string() == run["id"],
                                         Job.status.in_(COUNTED)).limit(1))  # fmt: skip
    video = {**video_state(db, project), "treatment": "written" if own else "none"}  # this run's
    parts = (("video", video), ("last_actions", done), ("allowed", allowed),
             *((("chat", asked),) if asked else ()))  # fmt: skip
    tagged = "\n".join(f"<{tag}>\n{json.dumps(value, indent=1)}\n</{tag}>" for tag, value in parts)
    return {"system": system, "prompt": f"{brief}\n{story(db, project)}{tagged}",
            READ: len(asked)}  # fmt: skip


def story(db: Session, project: Project) -> str:
    """What the video is (the Director, on Reed's first real run: it never read the words):
    its script, numbered; its plan's beats; its treatment, when there is one."""
    from app import plans, prompts
    from app.watch_cut import _plan

    version = plans.script(db, project)
    if version is None:
        return ""
    parts = [f"<script>\n{prompts.number_lines(version.text)}\n</script>"]
    if beats := _plan(plans.current(db, project), version):
        parts.append(f"<plan>\n{beats}\n</plan>")
    return "\n".join(parts) + "\n" + treatment_block(db, project)


def treatment(db: Session, project: Project) -> dict | None:
    """The video's newest treatment (the Director's step: hook, logline, why it holds, beats,
    ending), or None."""
    job = db.scalar(select(Job).where(Job.project_id == project.id,
                                      Job.input["step"].as_string() == "treatment",
                                      Job.status == JobStatus.succeeded)
                    .order_by(Job.id.desc()).limit(1))  # fmt: skip
    return (job.output or None) if job else None


def write_treatment(db: Session, user: User, project: Project, run: dict | None,
                    note: str = "", redo: bool = False) -> str:  # fmt: skip
    """Queue the treatment (the Director's step: hook, logline, why it holds, beats, ending),
    on the director's own limit like a watch; its words in plain lines."""
    from app import plans, prompts
    from app.credits import estimate, past_approved
    from app.enhance import project_context
    from app.routes.jobs import enqueue

    version = plans.script(db, project)
    system, context = project_context(db, project, "treatment")  # its look's skill and craft
    text = f"{context}\n{prompts.treatment_input(version.text, note)}"
    data = {"step": "treatment", "project_id": project.id, RUN: run, "system": system,
            "prompt": text, "max_tokens": 6000, **({"redo": True} if redo else {})}  # fmt: skip
    again = treatment(db, project) is not None
    price = estimate(db, project.workspace_id, "write-claude", Decimal(1), data)
    wait = past_own(db, project, (run or {}).get("id"), price)
    data = {**data, GRANT: True} if wait else data  # an OK here grants another limit
    wait = wait or past_approved(db, project, user, price)
    enqueue(db, user, "write-claude", data, project=project, provider="claude",
            prepaid=not wait, wait=wait)  # fmt: skip
    return "Changing the treatment." if again else "Writing the treatment."


def told(made: dict, again: bool) -> str:
    """A treatment as plain lines in the thread (the Director: the delivery note's style)."""
    beats = " ".join(f"{b.get('id', '')}: {b.get('purpose', '')}, {b.get('picture', '')}."
                     for b in made.get("beats") or [])  # fmt: skip
    head = "Changed the treatment:" if again else "The treatment:"
    still = " ".join(made.get("problems") or [])
    return (f"{head} {made.get('logline', '')} Hook: {made.get('hook', '')} {beats} "
            f"Ending: {made.get('ending', '')}" + (f" Still to fix: {still}" if still else "")
            ).strip()  # fmt: skip


def treatment_block(db: Session, project: Project) -> str:
    """<treatment> for a step's user message (plan, breakdown, clip prompts, the watch, the
    director), or "" before one is made (the Director's prompts.treatment_block)."""
    from app import prompts

    told = prompts.treatment_block(treatment(db, project))
    return f"{told}\n" if told else ""


def _audio_key(db: Session, project: Project) -> str:
    return "song" if director_song.kind(db, project) == "song" else "narration"


def video_state(db: Session, project: Project) -> dict:
    """Where the video is, as the director reads it (and `choose` on the stand-ins)."""
    from app.clip_prompts import newest
    from app.item_checks import latest, shown, verdict
    from app.routes.project_assets import _missing
    from app.routes.project_clips import out_of_date

    bd = newest(db, project)
    frames = [f for f in db.scalars(select(StoryboardFrame).where(
        StoryboardFrame.project_id == project.id)) if bd and f.breakdown_id == bd.id]  # fmt: skip
    data = bd.data if bd else {}  # what each clip shows and says (the Director: not only verdicts)
    shots = {x["id"]: x for sc in data.get("scenes", []) for x in sc.get("shots", [])}
    ids_of = {c["id"]: c["shot_ids"] for c in data.get("clips", [])}
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
                      "shots": [{"id": i, "action": shots[i].get("action", ""),
                                 "line": shots[i].get("line")}
                                for i in ids_of.get(row.clip_id, []) if i in shots],
                      "picked_take_id": row.picked_take_id, "takes": out,
                      "muted": take_mute.spans(db.get(ClipTake, row.picked_take_id)
                                               if row.picked_take_id else None),
                      **word_splice.state(db, row)})  # splice_word  # fmt: skip
    video = db.scalar(select(FinalVideo).where(FinalVideo.project_id == project.id).limit(1))
    waiting = _waiting(db, project)
    acted = [j for j in turns(db, project) if "result" in j.input]
    failed = db.scalars(select(Job).where(
        Job.project_id == project.id, Job.status == JobStatus.failed,
        Job.finished_at >= acted[-1].created_at)) if acted else []  # fmt: skip
    from app.plans import status

    audio = director_song.state(db, project)  # a song or narrated video's song or narration
    return {
        "plan": status(db, project),  # none, ready (waits for approval) or approved
        **({_audio_key(db, project): audio} if audio else {}),  # the clock its shots follow
        # choices fixed for it (director-chat.md §1), kept as is; a person's own look pick isn't
        "locked": {k: v for k, v in (project.locks or {}).items() if k != "look_picked"},
        "outfits": project.outfits or {},  # this video's outfit per character ("char:12")
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
        "watch": _watch(db, project),  # its last watch of the cut, and its findings
        "stills_review": _stills_review(db, project),  # its last look at the stills
    }  # fmt: skip


def choose(state: dict) -> dict:
    """The stand-in director (no paid call): the agents' order, step by step. A flagged take
    is made again with the take check's notes (the server counts the redos). Once cut, it
    watches the cut (while watches are left), fixes what that watch found (a clip remade once,
    a pick, a mute), then cuts again and watches again (`allowed`: what its turn may still
    do). Kept short: the browser test walks it in real time."""

    def go(tool: str, why: str, **extra) -> dict:
        return {"tool": tool, "why": why, "clip_id": None, "take_id": None, "note": "", **extra}

    clips, watch = state["clips"], state.get("watch") or {"state": "none"}
    found = watch.get("findings") or [] if watch.get("current") else []
    notes = state.get("chat") or []  # a run with notes: only what was asked
    wanted = {f"c{n}" for m in notes for n in re.findall(r"\bclip (\d+)\b", m["text"], re.I)}
    # It can't tell whether the change caused a fault, so it fixes none: each is mentioned
    older = [f for f in found if notes and f.get("fix") != "keep"]
    found = [f for f in found if f not in older]
    picked_by_watch = {f["clip_id"]: f.get("take_id") for f in found if f.get("fix") == "pick"}
    if state["being_made"] or state["held_for_owner"]:
        return go("wait", "Something is still being made or waits for the owner.")
    if state.get("treatment") == "none":  # the story first, on every run (the Director)
        return go("treatment", "The story first: what holds a viewer, beat by beat.")
    if audio := _audio_move(state, go):  # a song or narrated video: its audio is the clock
        return audio
    if state["shots"] == "none":
        return go("plan", "There are no shots yet.")
    if state["missing_looks"]:
        return go("make_looks", "Some roles have no look yet.")
    if not state["stills"]["frames"]:
        return go("storyboard", "The shots are ready; the storyboard is next.")
    if state["stills"]["drawn"] < state["stills"]["frames"]:
        return go("stills", "Some frames have no still yet.")
    review = state.get("stills_review") or {"state": "done"}  # (a hand-made state: none asked)
    if review["state"] == "none":  # its own look at the stills before any take
        return go("review_stills", "The stills are drawn: check them against the treatment.")
    if review["state"] == "reviewing":
        return go("wait", "It's looking at the stills.")
    used = state.get("allowed", {}).get("redraws_used", {})
    for f in review.get("findings") or [] if review.get("current") else []:
        if not used.get(f["shot_id"]):
            return go("redraw_still", f"{f['problem']} Drawing it again.",
                      shot_id=f["shot_id"], note=f["note"])  # fmt: skip
    if asked := _asked(state):
        return asked  # a new note: what the person asked, once; then cut and deliver again
    if not clips or any(c["stale"] for c in clips):
        return go("clip_prompts", "The clips need their prompts.")
    if any(not c["takes"] for c in clips):
        return go("make_take", "Some clips have no take yet.")
    for c in clips:  # the brand said wrong, with a clean copy in the same voice (word_splice)
        if c.get("can_splice"):
            word = c["can_splice"][0]["word"]
            return go("splice_word", f"{c['clip_id']} says “{word}” wrong; a clean copy is "
                      "spliced in.", clip_id=c["clip_id"], word=word)  # fmt: skip
    for c in clips:
        last = c["takes"][-1]
        if last["verdict"] == "checking":
            return go("wait", f"{c['clip_id']}'s take is being checked.")
        mine = not notes or c["clip_id"] in wanted
        spliced = c.get("splices")  # the wrong word is covered: no take made again for it
        if last["verdict"] == "flagged" and len(c["takes"]) <= MAX_REDOS and mine and not spliced:
            note = "; ".join(last["notes"]) or "Fix what the take check found."
            return go("make_take", f"The take check flagged {c['clip_id']}.",
                      clip_id=c["clip_id"], note=note[:500])  # fmt: skip
    for c in clips:  # the newest clean take (Builder-Server-8's best-take function to come)
        clean = next((t for t in reversed(c["takes"]) if t["verdict"] == "clean"), None)
        best = clean or c["takes"][-1]
        if c["picked_take_id"] != best["id"] and c["picked_take_id"] != picked_by_watch.get(
            c["clip_id"]
        ):
            why = (f"Take {best['number']} is {c['clip_id']}'s newest clean take." if clean
                   else f"No take of {c['clip_id']} is clean: using the newest, take "
                   f"{best['number']}.")  # fmt: skip
            return go("pick_take", why, clip_id=c["clip_id"], take_id=best["id"])
    if state["cut"] != "none" and (fix := _next_fix(found, {c["clip_id"]: c for c in clips})):
        return fix  # every fix the watch of this cut found, then one cut again
    if state["cut"] != "made":
        unclean = [c["clip_id"] for c in clips
                   if not any(t["verdict"] == "clean" for t in c["takes"])]  # fmt: skip
        said = f" No take of {', '.join(unclean)} is clean: its newest is used." if unclean else ""
        return go("final_cut", f"Every clip has its take.{said}")
    if watch.get("state") == "watching":
        return go("wait", "It's watching the cut.")
    left = state.get("allowed", {}).get("watches_left", 0)
    if not watch.get("current") and left > 0:  # it delivers only a cut it watched (UNWATCHED)
        return go("watch_cut", "The cut is made: it watches it as a viewer would.")
    keep = " ".join(f"Kept: {f['says']}" for f in found if f.get("fix") == "keep")
    done = _answers(state)
    noticed = " ".join(
        f"I also noticed: {f['says'].rstrip('.')}. Want me to fix it?" for f in older
    )
    said = " ".join(x for x in (done, keep, noticed) if x)
    return go("deliver", f"The cut is made with each clip's best take. {said}".strip())


def _audio_move(state: dict, go) -> dict | None:
    """The stand-in's song or narration: make it, wait for it, then use its best take; a
    failed one is tried again (free when the service failed; refused, it says so)."""
    tool = "song" if "song" in state else "narration" if "narration" in state else None
    audio = state.get(tool) if tool else None
    if audio is None or audio.get("used_take_id"):
        return None
    what = "song" if tool == "song" else "narration"
    if audio["state"] == "none":
        return go(tool, f"The {what} first: its timing is what the shots follow.")
    if audio["state"] == "making":
        return go("wait", f"The {what} is being made.")
    if audio["state"] == "ready":
        return go(tool, f"The {what} is made and timed: use its best take.")
    return go(tool, f"The {what} didn't come out: try it again.")  # free once; then a note


# Rule 19, not here: an ask to change the script's words ("change the line to ...", "make her
# say 'Buy now'", "rewrite clip 2"), never a note that only mentions what someone says or said.
WORDS = re.compile(
    r"\b(?:rename|re-?word|rewrite|(?:change|edit|replace|swap|cut|drop)\b[^.]{0,30}?\b"
    r"(?:words?|lines?|script|dialogue|wording)\b|say\s+['\"“‘])",
    re.I,
)


def _clip_of(note: dict) -> str | None:
    named = re.search(r"\bclip (\d+)\b", note["text"], re.I)
    return f"c{named[1]}" if named else None


def _asked(state: dict) -> dict | None:
    """The stand-in's next open note it can make: the clip it names made again, with the note
    as its note and "Note N" in the why (that answers it, so it's made once). A note whose
    clip isn't ready yet (its prompt is stale) is carried until it is; one it can't make is
    answered in the delivery note (`_answers`)."""
    clips = {c["clip_id"]: c for c in state["clips"]}
    used = state.get("allowed", {}).get("redos_used", {})
    for m in state.get("chat") or []:
        clip = _clip_of(m)
        if (
            m.get("answered")
            or WORDS.search(m["text"])
            or clip not in clips
            or clips[clip]["stale"]
        ):
            continue
        if used.get(clip, 0) >= MAX_REDOS:
            continue  # it can't be made again: the delivery note says so
        return {"tool": "make_take", "why": f"Note {m['note']}: you asked: {m['text']}"[:300],
                "clip_id": clip, "take_id": None, "note": m["text"][:500]}  # fmt: skip
    return None


def _answers(state: dict) -> str:
    """The delivery note's line for each of the run's notes: what was made, or plainly why not."""
    clips = {c["clip_id"] for c in state["clips"]}
    used = state.get("allowed", {}).get("redos_used", {})
    out = []
    for m in state.get("chat") or []:
        clip, n = _clip_of(m), m["note"]
        if m.get("answered"):
            out.append(f"Note {n}: done, as you asked ({m['text']}).")
        elif WORDS.search(m["text"]):
            out.append(f"Note {n}: the script's words stay as written here. I can change how a "
                       "line is delivered, the pictures or the pacing instead.")  # fmt: skip
        elif clip is None:
            out.append(f"Note {n}: I couldn't tell which clip you meant. Name the clip "
                       "(for example \"clip 2\") and send it again.")  # fmt: skip
        elif clip not in clips:
            out.append(f"Note {n}: there's no clip {clip[1:]} in this video.")
        elif used.get(clip, 0) >= MAX_REDOS:
            out.append(f"Note {n}: clip {clip[1:]} was already made again {MAX_REDOS} times, "
                       "the most a run may.")  # fmt: skip
        else:
            out.append(f"Note {n}: not made yet.")
    return " ".join(out)


def _next_fix(found: list[dict], clips: dict) -> dict | None:
    """The stand-in's next fix from the watch of this cut: a clip is remade once at most."""
    base = {"clip_id": None, "take_id": None, "note": ""}
    for f in found:
        c = clips.get(f.get("clip_id"))
        if c is None:
            continue
        if f.get("fix") == "redo" and len(c["takes"]) == 1:
            return {
                **base,
                "tool": "make_take",
                "why": f"The watch found: {f['says']}",
                "clip_id": c["clip_id"],
                "note": (f.get("note") or f["says"])[:500],
            }
        if f.get("fix") == "pick" and f.get("take_id") not in (None, c["picked_take_id"]):
            return {
                **base,
                "tool": "pick_take",
                "why": f"The watch found: {f['says']}",
                "clip_id": c["clip_id"],
                "take_id": f["take_id"],
            }
        if f.get("fix") == "mute" and f.get("mute") and not _muted(c, f["mute"]):
            return {
                **base,
                "tool": "mute",
                "why": f"The watch found: {f['says']}",
                "clip_id": c["clip_id"],
            }
    return None


def _muted(clip: dict, span: list[float]) -> bool:
    return [round(x, 2) for x in span] in (clip.get("muted") or [])


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
