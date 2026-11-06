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

from app import (
    asks,
    breakdown_fix,
    cast_gate,
    cut_edits,
    director_song,
    director_tools,
    locked_line,
    take_mute,
    take_sound,
    word_splice,
)
from app.credits import COUNTED, FREESTYLE, lock
from app.db import utcnow
from app.models.accounts import User
from app.models.asks import Ask
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.jobs import WAITING, Job, JobStatus, Usage
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft
from app.models.storyboards import StoryboardFrame

log = logging.getLogger(__name__)
STEP = "director"
RUN = "director_run"
MAX_TURNS = 40  # a run's turns at most
MAX_REDOS = 2  # takes made again for one clip a run, its watch's remakes too (rule 34)
MAX_REPLANS = 1  # plans made again from the watch ("Re-plan: …"), a run
MAX_WATCHES = 3  # watches of the cut a run (watch_cut, Reed 1 Nov: "watch and make those fixes")
MAX_USD = Decimal(5)  # its own Claude time a video (Reed: "ideally less"); measured per run
OWN_CREDITS = Decimal(75)  # its turns and watches a run, as charged and quoted (the Producer)
NOT_PUBLISHED = "The director builds from a published script. Publish it first."
UNWATCHED = "Refused: watch the cut first."
REBUILD = "Refused: make the cut again first: it isn't up to date."
NO_WATCH_LEFT = ("Refused: no watches are left this run to check an edit. Say in the delivery note "
                 "what you would change.")  # fmt: skip
RUNNING = "The director is already building this video."
NOTE = re.compile(r"\bnote (\d+)\b", re.I)  # how a move's why names the note it answers
OPEN = "Refused: note {0} is still open. Make it, or say why it can't; write Note {0} in that move."
READ = "chat_read"  # in a turn's input: how many of its run's messages it read
GAP, PER_RUN = timedelta(seconds=3), 30  # one note a person every 3 s; notes a run at most
TOO_MANY = "Too many messages; wait a moment."
IDLE = "Waiting, with nothing being made: it reads the video again."
WATCHED_AGAIN = "Refused: it already watched this cut; fix something or deliver."
DOUBT = "Refused: {} has only a doubt, which is the owner's to judge; say so in the delivery note."
TURN_FAILED = "A turn failed; nothing more was done. Start it again to go on."
START = asks.START  # in its held first paid turn: the start card (S3-02)
START_HELD = "Ready to start: it waits for Make it."  # the start card's hold
START_FIRST = "Waiting for Make it: nothing more runs before it."  # a move before the OK
TREATMENT_FIRST = "Refused: the treatment comes first, before Make it."
PLAN_FIRST = "Changing the plan first."  # a note while the start card waited
PRE_OK = ("treatment", "ask", "wait", "stop")  # what runs before Make it: planning only
ON_YOU = "Waiting on your answer; everything else is made."  # parked on open questions
CAST_WAIT = "Waiting for the cast and places OK."  # its run waits on that point only


def start(db: Session, user: User, project: Project, *, hold: str = "",
          extra: dict | None = None, frozen: bool = True, fresh: bool = False) -> Job:  # fmt: skip
    """A run on a video made from a published script (its words are locked): its first turn.
    Every way in starts the same (S3-02): its plan (the treatment) first, charged at its real
    cost on the video's planning allowance (`asks.past_planning`), then the run waits on its
    start card, "Make it · up to $X", before any generation (`ok` in the run). `hold`: why
    that card waits for the owner (an editor's pasted words or New video send, or a script
    past what's left of its budget); "" lets the video's own editor press it (S2-06).
    `extra`: more of its input (the freestyle it's for), carried to the start card.
    `frozen=False`: a freestyle's, whose version is frozen and published when its run starts
    (`freestyles.freeze`). `fresh`: "Start the plan again" (S3-08): after Make it the run
    plans the whole video again instead of carrying on from its shots (`fresh`)."""
    if why := blocked(db, project) if frozen else (RUNNING if active(db, project) else ""):
        raise HTTPException(409, why)
    again = {FRESH: utcnow().isoformat()} if fresh else _replanning(db, project)
    run = {"id": uuid.uuid4().hex, "turn": 0, "redos": {}, "by": user.id, "ok": False,
           "hold": hold, **again}  # fmt: skip
    lock(db, Project, project.id)  # the notes it takes can't change under it
    db.refresh(project)
    left = set(leftover(db, project))  # every note no run has read: this run reads them
    if left:
        project.director_chat = [{**m, "run": run["id"]} if n in left else m
                                 for n, m in enumerate(project.director_chat)]  # fmt: skip
    return _turn(db, user, project, run, extra=extra)


CARRIED = "carried"  # in a run carried on after a person's Stop: the run it goes on from
KEPT = ("turn", "redos", "watches", "replans", "redraws", director_song.REMADE)  # its counts


def carry_on(db: Session, user: User, project: Project) -> Job:
    """Carry on (S3-08): a run a person stopped goes on where it left off under the owner's
    existing OK, with no new start card, while its own approved price has something left
    (`run_progress.carry_left`). It is the same run (rule 34: its holds and counts are its
    own): what it charges counts against that price, and a step past it waits for the owner as
    any does (`asks.past_run`). A stopped "Start the plan again" press is kept. With nothing
    left of that price, or no Make it before the Stop, it's a new run with its own start card."""
    from app import run_progress

    if why := blocked(db, project):
        raise HTTPException(409, why)
    if run_progress.carry_left(db, project) is None:
        return start(db, user, project, hold=asks.start_hold(db, user, project))
    old = dict(turns(db, project)[-1].input[RUN])
    run = {**{k: old[k] for k in KEPT if k in old}, **_replanning(db, project),
           "id": uuid.uuid4().hex, "by": user.id, "ok": True, "hold": "",
           CARRIED: old.get(CARRIED) or old["id"]}  # fmt: skip
    lock(db, Project, project.id)
    db.refresh(project)
    if notes := set(leftover(db, project)):  # what was said since the Stop: it reads them
        project.director_chat = [{**m, "run": run["id"]} if n in notes else m
                                 for n, m in enumerate(project.director_chat)]  # fmt: skip
    return _turn(db, user, project, run)


def say(db: Session, user: User, project: Project, text: str, files: list[int] = ()) -> None:
    """A person's note to the director (director-chat.md §1 item 4), kept in the thread with
    any pictures or clips sent with it (for this video only, rule 12; the director looks at
    them). While a run goes on, its next turn reads it (a turn already in flight, the one
    after); a run waiting on an answer wakes to read it, and one waiting on its start card
    reads it before Make it ("Change the plan first", S3-02). It never starts a run: after
    Stop or a delivery it waits, unread, for the next Make it, which reads every unread note.
    Nothing is charged for it."""
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
    said = {"by": user.id, "text": text, "at": now.isoformat(), "run": run_id,
            **({"files": list(files)} if files else {})}  # fmt: skip
    if not going and (instead := locked_line.offer(db, user, project, text)):
        if instead[1]:  # all it asked: answered at once (S3-14), no run reads it; a note that
            said["offer"] = instead[0].id  # asks more stays for the director's next Make it
    project.director_chat = [*every, said]
    db.commit()
    if going and going.status == JobStatus.needs_owner_approval and going.input.get(START):
        _plan_first(db, project, going)
    elif going:
        wake(db, project)


def _plan_first(db: Session, project: Project, held: Job) -> None:
    """A note while the start card waits: the card goes (nothing was charged) and a turn
    before Make it reads the note and changes the treatment; then the card comes back with
    the new price."""
    from app.db import utcnow

    done = db.execute(update(Job).where(Job.id == held.id,
                                        Job.status == JobStatus.needs_owner_approval)
                      .values(status=JobStatus.cancelled, finished_at=utcnow()))  # fmt: skip
    if done.rowcount != 1:
        return
    db.refresh(held)
    run = {**held.input[RUN], "ok": False}
    held.input = {**held.input, "result": PLAN_FIRST}
    db.commit()
    _turn(db, db.get(User, run["by"]), project, run)


def chat(project: Project, run_id: str) -> list[dict]:
    """What people asked of this run, oldest first."""
    return [{"text": m["text"]} for m in project.director_chat or [] if m.get("run") == run_id]


def answered(db: Session, run_id: str) -> set[int]:
    """The run's notes (numbered from 1) a move has answered: named "Note N" in the why of a
    move that wasn't refused, or in the delivery's note. An ask stays open until then."""
    mine = Job.input[RUN]["id"].as_string() == run_id
    rows = db.scalars(select(Job).where(Job.input["step"].as_string() == STEP, mine)).all()
    return {int(n) for j in rows if not (j.input.get("result") or "").startswith("Refused")
            for n in NOTE.findall(move_words(j.output or {}))}  # fmt: skip


def move_words(decision: dict) -> str:
    """A move's words that can name a note: its why, and on a delivery its note's parts."""
    return " ".join(decision.get(k) or "" for k in ("why", "made", "unsure", "needs"))


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
        if run is not None and run == live or m.get("offer"):
            continue  # its next turn reads it; or answered at once with what can change (S3-14)
        seen[run] = seen.get(run, 0) + 1
        if run is None or seen[run] > read.get(run, 0):
            out.append(n)
    return out


def thread(db: Session, project: Project, viewer: User | None = None) -> list[dict]:
    """The whole conversation on the video, oldest first: what people said, the treatment,
    and for each run its progress card and its delivery note (app/run_progress)."""
    from app import run_progress
    from app.auth import user_name

    done = {r: answered(db, r) for r in {m.get("run") for m in project.director_chat or []} if r}
    place: dict[str | None, int] = {}  # a note's number in its run ("Note N"), as `answered` reads
    out = []
    for n, m in enumerate(project.director_chat or []):
        place[m.get("run")] = place.get(m.get("run"), 0) + 1
        out.append({"id": f"m{n}", "kind": "message", "at": m["at"],
                    "who": user_name(db, m["by"]), "text": m["text"], "status": None, "why": "",
                    "answered": bool(m.get("offer"))
                    or place[m.get("run")] in done.get(m.get("run"), set()),
                    "files": m.get("files", [])})  # fmt: skip
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
    out += run_progress.thread_items(db, project, viewer)
    for a in db.scalars(select(Ask).where(Ask.project_id == project.id)):
        if a.kind != "start" or asks.state(db, a) != "not_needed":  # a card in the chat
            out.append({"id": f"a{a.id}", "kind": "ask", "at": a.created_at.isoformat(),
                        "who": "Director", "text": a.question, "status": None, "why": "",
                        "answered": None, "ask_id": a.id})  # fmt: skip
    out += _watched(db, project)
    return sorted(out, key=lambda m: m["at"])


def _cut_failed(db: Session, project: Project) -> dict | None:
    """{why, fixes} when the newest cut couldn't be made (a cut's problem is a job that
    finished with plain words, not a failed job), else None."""
    from app import cut
    from app.routes.cut import _failed, _newest_job

    failed = _failed(db, project, cut.newest(db, project))
    if not failed:
        return None
    tried = _newest_job(db, project).input.get("edit_ids") or []
    changed = tried != [e.id for e in cut.active(db, project)]  # an edit since it failed
    return {"why": failed.why, "fixes": failed.fixes, "changed": changed}


def _edit_of(db: Session, turn: Job, tool: str | None, status: str) -> dict | None:
    """An edit_cut move's edit, for its Undo in the chat (S7-03: "Clip 9 re-timed · Undo")."""
    from app.models.clips import CutEdit

    edit_id = turn.input.get(RUN, {}).get("edit_id")
    row = db.get(CutEdit, edit_id) if tool == "edit_cut" and status == "done" and edit_id else None
    return {"id": row.id, "at": row.at, "undone": row.undone_at is not None} if row else None


def _only_a_doubt(db: Session, project: Project, clip_id: str, why: str,
                  run_id: str | None = None) -> bool:  # fmt: skip
    """A redo with no confirmed reason behind it: the owner's to judge, never paid for (Reed,
    4 Nov). It goes ahead on a person's note, a take its watch confirmed a fault in (flagged),
    a take made from another prompt than the clip's now, or a redo the current watch of the
    cut saw in the frames."""
    from app.models.clips import ClipTake

    clip = next((c for c in video_state(db, project)["clips"] if c["clip_id"] == clip_id), None)
    given = max((t.input.get(READ, 0) for t in turns(db, project)
                 if t.input[RUN]["id"] == run_id), default=0) if run_id else 0  # fmt: skip
    asked = any(1 <= int(n) <= given for n in NOTE.findall(why))  # a note this run was given
    if not clip or not clip["takes"] or asked:
        return False
    last = clip["takes"][-1]
    row = db.scalar(select(ProjectClip).where(ProjectClip.project_id == project.id,
                                              ProjectClip.clip_id == clip_id))  # fmt: skip
    newest = db.get(ClipTake, last["id"])
    if last["verdict"] == "flagged" or clip["stale"] or (newest.prompt or row.prompt) != row.prompt:
        return False
    watch = _watch(db, project)
    return not (watch.get("current") and any(
        f.get("clip_id") == clip_id and f.get("fix") == "redo"
        for f in watch.get("findings") or []))  # fmt: skip


def _watched(db: Session, project: Project) -> list[dict]:
    """What its watch of each take and host piece found and did, said in the chat when it
    acted (rule 11): "Clip 7, take 1: cartoon eyes landed on the stomach … Remade it …"."""
    from app import watch_report

    out = []
    for x in watch_report.watched(db, project):
        w = x["watch"]
        if w.get("action") not in watch_report.ACTED:
            continue
        what = (f"The host's piece {x['number']}" if x["clip_id"] == "host" else
                f"Clip {x['clip_id'].removeprefix('c')}, take {x['number']}")  # fmt: skip
        out.append({"id": f"w-{x['clip_id']}-{x['item'].id}", "kind": "move", "at": w["at"],
                    "who": "Director", "text": f"{what}: {w['found']} {w['did']}",
                    "status": "held" if w["waiting"] else "done", "why": "",
                    "answered": None})  # fmt: skip
    return out


def _redos(db: Session, project: Project, run: dict) -> dict[str, int]:
    """Takes made again for each clip this run: by the director's own moves and by its watch
    of each take (app/take_watch), MAX_REDOS a clip in all."""
    from app import take_watch, watch_report

    out = dict(run["redos"])
    for row, _ in watch_report.clip_takes_of(db, project):
        if n := take_watch.remakes(db, row):
            out[row.clip_id] = out.get(row.clip_id, 0) + n
    return out


def named(text: str) -> str:
    """A move as people read it: clips as they see them ("clip 1", never "c1"), and a note
    still open without what OPEN tells the director to do (QA-3)."""
    text = re.sub(r"^(Refused: note \d+ is still open\.).*", r"\1", text, flags=re.S)
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


def charged(db: Session, project: Project) -> Decimal:
    """What the newest run has charged so far (made or being made): `credits` less what's
    held for an OK."""
    rows = turns(db, project)
    if not rows:
        return Decimal(0)
    return Decimal(db.scalar(select(func.coalesce(func.sum(Job.credits), 0)).where(
        Job.project_id == project.id, Job.id >= rows[0].id,
        Job.status.in_(COUNTED))))  # fmt: skip


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


DELIVERED = "Delivered."  # a run's last turn's result once it delivered
STOPPED = "Stopped."  # a person pressed Stop: the run's `ended`, with who and when (S-gaps-01)


def stop(db: Session, project: Project, by: int) -> None:
    """A person's Stop (`by`): no more turns. A turn not yet asked is cancelled (only if the
    worker hasn't taken it); one being asked finishes, and what its call cost is recorded and
    charged as ever (a paid call is always logged), but nothing more is done. Its own work
    held for an OK (its plan past the allowance, a watch past its limit) goes with it."""
    if last := active(db, project):
        db.execute(update(Job).where(Job.id == last.id, Job.status.in_(
            (JobStatus.queued, JobStatus.needs_owner_approval))).values(
            status=JobStatus.cancelled))  # fmt: skip
        db.execute(update(Job).where(
            Job.project_id == project.id, Job.status == JobStatus.needs_owner_approval,
            Job.input[RUN]["id"].as_string() == last.input[RUN]["id"])
            .values(status=JobStatus.cancelled, finished_at=utcnow())
            .execution_options(synchronize_session=False))  # fmt: skip
        db.refresh(last)
        _end(last, STOPPED)
        last.input = {**last.input, "stopped_by": by, "stopped_at": utcnow().isoformat()}
        asks.close_run(db, last.input[RUN]["id"], "The run was stopped.")
        db.commit()


def spent(db: Session, run_id: str) -> Decimal:
    """What the run's own Claude turns really cost (Usage), for the limit and to measure."""
    ids = select(Job.id).where(Job.input[RUN]["id"].as_string() == run_id)
    return Decimal(db.scalar(select(func.coalesce(func.sum(Usage.cost_usd), 0))
                             .where(Usage.job_id.in_(ids))))  # fmt: skip


OWN_LIMIT = "Waiting for the owner's OK: the director has used its own limit of {n} credits."
GRANT = "own_grant"  # in a run's job's input: held at the director's own limit (`past_own`)


def own_limit() -> Decimal:
    """The director's own limit a run, in credits, as the quote shows it: OWN_CREDITS (MAX_USD
    stays the real-cost backstop)."""
    return OWN_CREDITS


def own_charged(db: Session, run_id: str) -> tuple[Decimal, int]:
    """What the run's own jobs (its turns and its watches of the cut) were charged, at the
    flat price each was charged (not their real cost, `spent`), and how many OKs the owner
    gave at its limit."""
    mine = (
        Job.input[RUN]["id"].as_string() == run_id,
        Job.status.in_(COUNTED),
        Job.input[asks.BEFORE].as_boolean().is_not(True),
    )  # its plan: its own allowance
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
    if _waiting(db, project) or _parked(db, project, last):
        return
    if (
        last.input["result"] == CAST_WAIT
        and cast_gate.pending(db, project)
        and not (
            _unread(project, last)
            or asks.answered_since(db, project, (last.started_at or last.created_at).isoformat())
        )
    ):
        return  # it goes on when the cast and places are approved, a question is answered, or
        # someone asks for more
    _turn(db, db.get(User, last.input[RUN]["by"]), project, dict(last.input[RUN]))


def _parked(db: Session, project: Project, last: Job) -> bool:
    """A run that waits only on open questions (`ON_YOU`) sleeps until one is answered, a story
    choice's time passes or someone sends a note: then it reads them."""
    if last.input.get("result") != ON_YOU or not asks.waiting(db, project):
        return False
    at = (last.started_at or last.created_at).isoformat()  # what it read was as of its start
    noted = any(m.get("run") == last.input[RUN]["id"] and m["at"] > at
                for m in project.director_chat or [])  # fmt: skip
    return not noted and not asks.answered_since(db, project, at)


def _unread(project: Project, last: Job) -> bool:
    """A note in the run that no turn has read yet."""
    return len(chat(project, last.input[RUN]["id"])) > last.input.get(READ, 0)


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
    for project_id in asks.overdue(db):  # a story choice's time passed: its pick (rule 37)
        wake(db, db.get(Project, project_id))


def _act(db: Session, job: Job, storage) -> None:
    project, decision = db.get(Project, job.project_id), dict(job.output or {})
    run = dict(job.input[RUN])
    tool = decision.get("tool")
    if not run.get("ok", True) and tool not in PRE_OK:  # nothing is spent before Make it
        return _record(db, job, run, START_FIRST if _written(db, run) else TREATMENT_FIRST)
    unpick_old_takes(db, project, run)  # "Start the plan again": its new shots are made
    if tool == "pick_take" and (aside := _aside(db, project, run, decision)):
        return _record(db, job, run, aside)
    swap = decision.get("edit") or {} if tool == "edit_cut" else {}
    if swap.get("kind") == "swap" and (aside := _aside(db, project, run, swap)):
        return _record(db, job, run, aside)  # a swap to a set-aside take: refused as a pick is
    if tool == "deliver":
        watch = _watch(db, project)
        watched = watch.get("current") and watch.get("state") in ("done", "failed")
        state = video_state(db, project)
        if (state.get("timeline") or {}).get("changes") or state["cut"] == "out of date":
            return _record(db, job, run, REBUILD)  # rebuilt (and watched) before it's shown
        if (state["cut"] != "none" and run.get("watches", 0) < MAX_WATCHES
                and not watched):  # a watch still going isn't one (QA-10)  # fmt: skip
            return _record(db, job, run, UNWATCHED)  # the Director: it watches what it delivers
        named = {int(n) for n in NOTE.findall(move_words(decision))}  # its note answers "Note N"
        given = max((t.input.get(READ, 0) for t in turns(db, project)
                     if t.input[RUN]["id"] == run["id"]), default=0)  # fmt: skip
        # a note no turn was given yet isn't its to answer: it waits for the next Make it
        if left := [n for n in range(1, given + 1) if n not in answered(db, run["id"]) | named]:
            return _record(db, job, run, OPEN.format(left[0]))
        from app import delivery

        why = decision.get("why") or "Delivered."
        job.output = {**decision, "note": delivery.note(db, project, job, decision)}
        asks.close_run(db, run["id"], "Delivered without it.")
        return _end(job, why, result=DELIVERED)  # a note it didn't read waits for Make it
    if tool == "stop":  # it can't go on (a story choice, a step that keeps refusing): says why
        return _end(job, decision.get("why") or "It stopped.", result="Stopped.")
    if tool == "make_take" and decision.get("clip_id"):
        clip = decision["clip_id"]
        if _redos(db, project, run).get(clip, 0) >= MAX_REDOS and _has_take(db, project, clip):
            return _record(db, job, run, f"Refused: {clip} was made again {MAX_REDOS} times.")
        if _only_a_doubt(db, project, clip, decision.get("why") or "", run["id"]):
            return _record(db, job, run, DOUBT.format(clip))
        if _has_take(db, project, clip):
            run["redos"] = {**run["redos"], clip: run["redos"].get(clip, 0) + 1}
    if tool == "wait":  # with nothing being made (it read the video before a step saved), the
        idle = not _waiting(db, project)  # next turn reads it again now (`wake`), once
        if idle and cast_gate.state(db, project)["asked"]:  # what's left waits for their OK
            return _record(db, job, run, CAST_WAIT)  # (an answer to a question wakes it too)
        if idle and asks.waiting(db, project):  # only questions left: it sleeps until answered
            return _record(db, job, run, ON_YOU)
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
    if tool == "edit_cut" and run.get("watches", 0) >= MAX_WATCHES:  # it watches what it edits
        return _record(db, job, run, NO_WATCH_LEFT)
    if tool == "watch_cut" and (cut_edits.for_director(db, project) or {}).get("changes"):
        return _record(db, job, run, REBUILD)  # a watch is for the cut with the edits in it
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


def _aside(db: Session, project: Project, run: dict, decision: dict) -> str:
    """A pick of a take that's set aside (`set_aside`): refused, saying what to do."""
    clips = video_state(db, project)["clips"]
    set_aside(db, project, run, clips)
    for c in clips:
        for t in c["takes"]:
            if t["id"] == decision.get("take_id") and t["set_aside"]:
                return SET_ASIDE.format(t["number"], c["clip_id"])
    return ""


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
    keys = ("tool", "clip_id", "take_id", "note", "edit")
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


def _turn(db: Session, user: User, project: Project, run: dict, *,
          extra: dict | None = None) -> Job:  # fmt: skip
    from app.routes.jobs import enqueue

    last = next(reversed(turns(db, project)), None)
    if last is not None and (gave_up := _failed_too_often(db, project, run)):
        made = video_state(db, project)["cut"] == "made"  # what it has: a cut, or nothing
        last = db.get(Job, last.id)
        _end(last, f"{gave_up}; delivered without it." if made else f"It stopped: {gave_up}.",
             result=DELIVERED if made else "")  # fmt: skip
        db.commit()
        return last
    if run["turn"] >= MAX_TURNS or spent(db, run["id"]) >= MAX_USD:
        why = (f"It stopped after {MAX_TURNS} turns." if run["turn"] >= MAX_TURNS
               else f"It stopped at ${MAX_USD} of its own time.")  # fmt: skip
        if last is not None:
            _end(last, why)
            db.commit()
        return last
    before = not run.get("ok", True)  # before Make it: planning, on its allowance
    card = before and last is not None and _ready(db, project, run, last)
    run = {**run, "turn": run["turn"] + 1, **({"ok": True} if card else {})}
    prompt = turn_input(db, project, run)
    prompt.pop(READ)  # a note counts as given only once its turn starts (`refresh`)
    data = {"step": STEP, RUN: run, **prompt, **(extra or {})}
    wait = ""
    if card:  # the start card: its first generating turn, held for Make it (S3-02)
        hold = run.get("hold") or ""
        data = {**data, **_carried(db, project, run), START: True, asks.HOLD: hold}
        wait = hold or START_HELD
    elif before:  # its plan: charged as it costs; past the allowance, the owner's OK first
        from app.credits import estimate

        turn = estimate(db, project.workspace_id, "write-claude", Decimal(1), data)
        data = {**data, asks.BEFORE: True}
        if asks.past_planning(db, project, turn, plan=False):
            data, wait = {**data, asks.PLAN_OK: True}, asks.PLANNING
    else:  # past its own limit, or a freestyle's price, the run pauses for an OK
        from app.credits import estimate, past_approved

        turn = estimate(db, project.workspace_id, "write-claude", Decimal(1), data)
        wait = past_own(db, project, run["id"], turn)
        data = {**data, GRANT: True} if wait else data  # an OK here grants another limit
        wait = wait or past_approved(db, project, user, turn)
    try:
        job = enqueue(db, user, "write-claude", data, project=project, provider="claude",
                      prepaid=not wait, wait=wait)  # fmt: skip
        # its own limit (MAX_USD), never the video's budget (director-chat.md §2, DECISIONS #1066)
    except HTTPException as no:  # e.g. the video was archived: the run ends, saying why
        if last is None or run["turn"] == 1:  # its first turn: the start itself is refused
            raise
        last = db.get(Job, last.id)
        _end(last, f"It stopped: {no.detail}")
        db.commit()
        return last
    if card and FREESTYLE in data:  # the freestyle's send is this card from now on
        from app.models.freestyles import Freestyle

        fs = db.get(Freestyle, data[FREESTYLE])
        mine = {t.id for t in turns(db, project) if t.input[RUN]["id"] == run["id"]}
        fs.chat = [{**m, "job": job.id} if m.get("job") in mine - {job.id} else m
                   for m in fs.chat]  # fmt: skip
        db.commit()
    return job


def _written(db: Session, run: dict) -> bool:
    """Whether the run's treatment is written (the start card waits for it)."""
    return bool(_treatment_at(db, run))


def _treatment_at(db: Session, run: dict):
    """When the run's newest written treatment was asked (what it read was as of then)."""
    return db.scalar(select(func.max(Job.created_at)).where(
        Job.input["step"].as_string() == "treatment", Job.input[RUN]["id"].as_string() == run["id"],
        Job.status == JobStatus.succeeded))  # fmt: skip


def _ready(db: Session, project: Project, run: dict, last: Job) -> bool:
    """Before Make it, the start card comes once the treatment is written and every note
    sent before Make it was read into it, or the director moved past it, or the owner kept
    the plan as it is on a planning card past its allowance."""
    from app.routes.jobs import DECLINE

    at = _treatment_at(db, run)
    if at is None:
        return False
    if last.input.get("result") == START_FIRST:
        return True
    kept = db.scalar(select(func.max(Job.finished_at)).where(
        Job.input[RUN]["id"].as_string() == run["id"], Job.input[asks.PLAN_OK].as_boolean(),
        Job.input[DECLINE].as_boolean()))  # fmt: skip
    seen = max(at, kept) if kept else at
    notes = [m["at"] for m in project.director_chat or [] if m.get("run") == run["id"]]
    return not notes or max(notes) <= seen.isoformat()


def keep_plan(db: Session, project: Project, job: Job) -> None:
    """The owner kept the plan as it is on a planning card: its start card comes back for
    the plan it has (a held planning turn was the run's last: the run goes on from it)."""
    if active(db, project) is None and job.input.get("step") == STEP:
        run = dict(job.input[RUN])
        _turn(db, db.get(User, run["by"]), project, run)
    else:
        wake(db, project)


def _carried(db: Session, project: Project, run: dict) -> dict:
    """What the run's first turn carried (a freestyle's send, its price, what its OK makes
    real) goes on its start card, with the price the card shows ("up to", rule 36)."""
    from app.routes.jobs import CHANGE, PRICE, SAID

    first = next(t for t in turns(db, project) if t.input[RUN]["id"] == run["id"])
    keys = (FREESTYLE, SAID, CHANGE, PRICE, "freeze")
    out = {k: first.input[k] for k in keys if k in first.input}
    return {PRICE: str(asks.run_price(db, project)), **out}


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


FRESH = "fresh"  # in a run: when "Start the plan again" was pressed (S3-08)


def fresh(db: Session, project: Project, run: dict | None) -> tuple[bool, bool]:
    """A run started with "Start the plan again": (it still needs its own new plan, it still
    needs the shots from it). The video's plan and shots from before it don't count."""
    from datetime import datetime

    from app import plans
    from app.models.breakdowns import BreakdownVersion

    if not (at := (run or {}).get(FRESH)):
        return False, False
    at, plan = datetime.fromisoformat(at), plans.current(db, project)
    made = datetime.fromisoformat(plan["made_at"]) if plan and plan.get("made_at") else None
    newest = db.scalar(select(func.max(BreakdownVersion.created_at)).where(
        BreakdownVersion.project_id == project.id))  # fmt: skip
    return made is None or made < at, newest is None or newest < at


def unpick_old_takes(db: Session, project: Project, run: dict | None) -> None:
    """ "Start the plan again" (S3-08): once its new shots are made, every clip's take from
    before the press stays only as an earlier take (`set_aside`), so each clip is made again
    for the new plan. A UGC talker's clips are cut from its take at the cut, so they keep
    theirs. Once a run (`UNPICKED`)."""
    from app import talker

    if not (at := _pressed(run)) or run.get(UNPICKED) or any(fresh(db, project, run)):
        return
    said = talker.clips(db, project)
    for row in db.scalars(
        select(ProjectClip).where(
            ProjectClip.project_id == project.id, ProjectClip.picked_take_id.is_not(None)
        )
    ):
        if row.clip_id not in said and db.get(ClipTake, row.picked_take_id).created_at < at:
            row.picked_take_id = None
    run[UNPICKED] = True
    db.commit()


UNPICKED = "unpicked"  # in a fresh run: its takes from before the press were set aside


def _replanning(db: Session, project: Project) -> dict:
    """A new run after a "Start the plan again" run that ended before it delivered (Stop, or a
    step that failed) carries on that press: the same press time and unpicked mark, so its old
    takes stay set aside and every clip is still made again. After that run delivered, the next
    run is a normal one (its earlier takes can be picked back as on any video)."""
    rows = turns(db, project)
    if not rows or rows[-1].input.get("result") == DELIVERED:
        return {}
    last = rows[-1].input[RUN]
    return {k: last[k] for k in (FRESH, UNPICKED) if last.get(k)}


def _pressed(run: dict | None):
    from datetime import datetime

    at = (run or {}).get(FRESH)
    return datetime.fromisoformat(at) if at else None


def set_aside(db: Session, project: Project, run: dict | None, clips: list[dict]) -> None:
    """Only in a run started with "Start the plan again", once its new shots are made: each
    clip's takes made before the press are `set_aside` (a talker's clips keep theirs). One a
    person picked again after they were set aside (`UNPICKED`) is theirs and stays."""
    if not (at := _pressed(run)) or any(fresh(db, project, run)):
        return
    for c in clips:
        if c.get("talker"):
            continue
        old = {t.id for t in db.scalars(select(ClipTake).where(
            ClipTake.id.in_([t["id"] for t in c["takes"]] or [0]),
            ClipTake.created_at < at))}  # fmt: skip
        for t in c["takes"]:
            theirs = run.get(UNPICKED) and t["id"] == c["picked_take_id"]
            t["set_aside"] = t["id"] in old and not theirs
    held = set(_cast_ok(db, project).get("paused_clips") or [])  # a set-aside take isn't one:
    for c in clips:  # a clip with only those waits for the cast and places OK like one with none
        now = [t for t in c["takes"] if not t["set_aside"]]
        c["waits_for_cast"] = c["clip_id"] in held and not now


SET_ASIDE = ("Refused: take {} of {} was made before the plan was started again, so it's set "
             "aside. Make a new take of it.")  # fmt: skip


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
               "redos_used": _redos(db, project, run), "own_time_usd": float(spent(db, run["id"])),
               "own_time_limit_usd": float(MAX_USD),
               "replans_left": MAX_REPLANS - run.get("replans", 0),
               "songs_left": director_song.REMAKES - run.get(director_song.REMADE, 0),
               "narrations_left": director_song.REMAKES - run.get(director_song.REMADE, 0),
               "redraws_per_still": 2, "redraws_used": run.get("redraws", {})}  # fmt: skip
    given = max((t.input.get(READ, 0) for t in turns(db, project)
                 if t.input[RUN]["id"] == run["id"] and t.id != job_id), default=0)  # fmt: skip
    closed = answered(db, run["id"])
    asked = [{"note": n + 1, **m, "new": n >= given, "answered": n + 1 in closed}
             for n, m in enumerate(chat(project, run["id"]))]  # fmt: skip
    # new: no earlier turn was given it. answered: a move named it ("Note N"); else still open
    mine = [run["id"], *([run[CARRIED]] if run.get(CARRIED) else [])]  # carried on: its run's
    own = db.scalar(select(Job.id).where(Job.input["step"].as_string() == "treatment",
                                         Job.input[RUN]["id"].as_string().in_(mine),
                                         Job.status.in_(COUNTED)).limit(1))  # fmt: skip
    video = {
        **video_state(db, project),
        "treatment": "written" if own else "none",
        "started": run.get("ok", True),
    }  # this run's; started: Make it was pressed
    plan, shots = fresh(db, project, run)  # "Start the plan again": no plan or shots of its own yet
    if plan:
        video["plan"] = "none"
    if shots:
        video["shots"], video["missing_looks"] = "none", []
    set_aside(db, project, run, video["clips"])  # its takes from before the press
    from app.routes.reel_video import look_reference

    questions, reel = asks.for_director(db, project), look_reference(db, project)
    looked, eyes = _eyes(db, project)  # its answers', the chat's and New video's pictures
    parts = (("video", video), ("last_actions", done), ("allowed", allowed),
             *((("chat", asked),) if asked else ()), *((("asks", questions),) if questions else ()),
             *((("seen", looked),) if looked else ()),
             *((("look_reference", reel),) if reel else ()))  # fmt: skip
    tagged = "\n".join(f"<{tag}>\n{json.dumps(value, indent=1)}\n</{tag}>" for tag, value in parts)
    return {"system": system, "prompt": f"{brief}\n{story(db, project)}{tagged}",
            READ: len(asked), **eyes}  # fmt: skip


FRAMES = 3  # a clip it's given is seen as this many frames (app/worker.video_frames)


def _eyes(db: Session, project: Project) -> tuple[list[str], dict]:
    """The pictures and clips given for this video (answers, the chat's uploads, New video's
    attachments) as images in its turn, pictures first, then each clip's frames: <seen> says
    which image is which, so it can judge them (the director brief: it gets eyes)."""
    given = asks.seen(db, project)
    stills = [(label, f) for label, f, clip in given if not clip]
    clips = [(label, f) for label, f, clip in given if clip]
    said = [f"Image {n}: {label}" for n, (label, _) in enumerate(stills, 1)]
    for n, (label, _) in enumerate(clips):
        first = len(stills) + n * FRAMES + 1
        said.append(f"Images {first}-{first + FRAMES - 1}: frames of a clip, {label}")
    if not given:  # none now (an answer changed): none given, not the last turn's
        return [], {"files": {}, "clip_frames": []}
    return said, {"files": {"reference_images": [f for _, f in stills]}, "fit_images_to": 1024,
                  "clip_frames": [f for _, f in clips]}  # fmt: skip


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
    before = not (run or {}).get("ok", True)  # before Make it: on the planning allowance
    price = estimate(db, project.workspace_id, "write-claude", Decimal(1), data)
    if before:  # a check's own fix of the plan always runs: it's the same plan, counted
        data, wait = {**data, asks.BEFORE: True}, ""
        if not redo and asks.past_planning(db, project, price, plan=True):
            data, wait = {**data, asks.PLAN_OK: True}, asks.PLANNING
    else:
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
    from app.clip_takes import take_credits
    from app.item_checks import latest, shown, verdict
    from app.routes.project_assets import _missing, missing_places
    from app.routes.project_clips import out_of_date

    bd = newest(db, project)
    frames = [f for f in db.scalars(select(StoryboardFrame).where(
        StoryboardFrame.project_id == project.id)) if bd and f.breakdown_id == bd.id]  # fmt: skip
    data = bd.data if bd else {}  # what each clip shows and says (the Director: not only verdicts)
    shots = {x["id"]: x for sc in data.get("scenes", []) for x in sc.get("shots", [])}
    ids_of = {c["id"]: c["shot_ids"] for c in data.get("clips", [])}
    from app import model_map, talker

    clips, said = [], talker.clips(db, project)  # a talker's clips come from its take, at the cut
    for row in db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)
                          .order_by(ProjectClip.id)):  # fmt: skip
        takes = db.scalars(select(ClipTake).where(ClipTake.clip_id == row.id)
                           .order_by(ClipTake.number)).all()  # fmt: skip
        ids = [t.id for t in takes]
        seen, heard = latest(db, "take", ids), latest(db, "words", ids)
        out = []
        for t in takes:
            look = shown(db, seen.get(t.id))
            checks = [look, shown(db, heard.get(t.id))]
            notes = [f.note for f in look.findings if f.verified] if look else []
            watched = {k: (t.watch or {}).get(k) for k in ("found", "did", "action")}
            mark = verdict(checks)  # a transcript's finding alone is a doubt, as an unsure watch:
            doubt = watched["action"] == "unsure" or (mark == "flagged" and not notes)
            out.append({"id": t.id, "number": t.number,  # the owner's, never a paid redo
                        "verdict": "unsure" if doubt else mark,
                        "notes": [] if doubt else notes, "watch": watched,
                        "set_aside": False})  # Start the plan again: `set_aside`  # fmt: skip
        clips.append({"clip_id": row.clip_id, "stale": bool(bd and row.breakdown_id != bd.id),
                      "shots": [{"id": i, "action": shots[i].get("action", ""),
                                 "line": shots[i].get("line")}
                                for i in ids_of.get(row.clip_id, []) if i in shots],
                      "picked_take_id": row.picked_take_id, "takes": out,
                      "redo_credits": float(take_credits(db, project, row)),  # its "up to"
                      "muted": take_mute.spans(picked := db.get(ClipTake, row.picked_take_id)
                                               if row.picked_take_id else None),
                      "sound": {k: v for k, v in (take_sound.state(db, picked) or {}).items()
                                if k in ("state", "how")},
                      **word_splice.state(db, row),  # splice_word
                      **model_map.state(db, project, row),  # clip_model
                      **({"talker": True} if row.clip_id in said else {})})  # fmt: skip
    have = {c["clip_id"] for c in clips}  # a planned clip with no prompt yet (after a split)
    clips += [{"clip_id": c["id"], "stale": True, "picked_take_id": None,
               "shots": [{"id": i, "action": shots[i].get("action", ""), "line": shots[i].get(
                   "line")} for i in c["shot_ids"] if i in shots],
               "takes": [], "muted": [], "sound": {}} for c in data.get("clips", [])
              if c["id"] not in have]  # fmt: skip
    video = db.scalar(select(FinalVideo).where(FinalVideo.project_id == project.id).limit(1))
    waiting = _waiting(db, project)
    acted = [j for j in turns(db, project) if "result" in j.input]
    failed = db.scalars(select(Job).where(
        Job.project_id == project.id, Job.status == JobStatus.failed,
        Job.finished_at >= acted[-1].created_at)) if acted else []  # fmt: skip
    from app.plans import status

    cast = _cast_ok(db, project) if bd else {"state": "none"}
    held = set(cast.get("paused_clips") or [])
    for c in clips:
        c["waits_for_cast"] = c["clip_id"] in held and not c["takes"]
    audio = director_song.state(db, project)  # a song or narrated video's song or narration
    from app import host

    hosted = {"host": host.state(db, project)} if host.on(db, project) else {}  # a presenter's
    return {
        **hosted,
        "plan": status(db, project),  # none, ready (waits for approval) or approved
        **({_audio_key(db, project): audio} if audio else {}),  # the clock its shots follow
        # choices fixed for it (director-chat.md §1), kept as is; a person's own look pick isn't
        "locked": {k: v for k, v in (project.locks or {}).items() if k != "look_picked"},
        "outfits": project.outfits or {},  # this video's outfit per character ("char:12")
        "shots": "ready" if bd else "none",
        "too_long": _splittable(db, project, bd),  # split_clip
        "missing_looks": [*(s.role for s in _missing(db, project)),
                          *(p.name for p in missing_places(db, project))] if bd else [],
        "cast_ok": cast,  # the person's OK on the cast and places, and what waits for it
        "stills": {"frames": len(frames), "drawn": sum(1 for f in frames if f.file_id),
                   "waiting": sum(1 for f in frames if not f.file_id and f.clip_id in held)},
        "clips": clips,
        "cut": "none" if not video else
               ("out of date" if project.id in out_of_date(db, [project]) else "made"),
        "being_made": len([j for j in waiting if j.status != JobStatus.needs_owner_approval]),
        "held_for_owner": [j.input.get("held", "") for j in waiting
                           if j.status == JobStatus.needs_owner_approval],
        "failed_since_last_turn": [j.error or "It didn't finish." for j in failed],
        "timeline": cut_edits.for_director(db, project),  # the cut's pieces, for edit_cut
        "cut_failed": _cut_failed(db, project),  # the newest cut couldn't be made: why, fixes
        "watch": _watch(db, project),  # its last watch of the cut, and its findings
        "stills_review": _stills_review(db, project),  # its last look at the stills
    }  # fmt: skip


def _cast_ok(db: Session, project: Project) -> dict:
    """The cast and places checkpoint as the director reads it: its state, whether it asked,
    each item (name, kind, source, readiness, approval), what isn't ready and why, and the
    clips waiting for it."""
    said = cast_gate.state(db, project)
    keep = ("name", "kind", "source", "readiness", "approval", "changes")
    return {"state": said["state"], "asked": said["asked"],
            "items": [{k: i[k] for k in keep} for i in said["items"]],
            "not_ready": [n["why"] for n in said["not_ready"]],
            "paused_clips": said["paused_clips"],
            "update": {k: said["update"][k] for k in ("stills", "clips", "credits")}}  # fmt: skip


def _splittable(db: Session, project: Project, bd) -> list[str]:
    """The clips longer than the video model makes that split_clip can cut; one that can't
    (a sentence longer than the model makes) is refused at its take with what to do."""
    from app import plans
    from app.breakdown import video_model

    if bd is None:
        return []
    m, version = video_model(project), plans.script(db, project)
    text = version.text if version else ""
    return [
        c
        for c in breakdown_fix.too_long(bd.problems or [])
        if breakdown_fix.split_into(bd.data, text, c, m.duration.min, m.duration.max) > 1
    ]


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
    aside = {t["id"] for c in clips for t in c["takes"] if t.get("set_aside")}
    found = [f for f in found if not (f.get("fix") == "pick" and f.get("take_id") in aside)]
    picked_by_watch = {f["clip_id"]: f.get("take_id") for f in found if f.get("fix") == "pick"}
    if state["being_made"] or state["held_for_owner"]:
        return go("wait", "Something is still being made or waits for the owner.")
    if state.get("treatment") == "none":  # the story first, on every run (the Director)
        return go("treatment", "The story first: what holds a viewer, beat by beat.")
    if state.get("started") is False:  # before Make it: a note changes the treatment only
        m = next((m for m in notes if not m.get("answered")), None)
        if m is None:
            return go("wait", "The treatment is ready: it waits for Make it.")
        return go("treatment", f"Note {m['note']}: {m['text']}"[:300], note=m["text"][:500])
    if audio := _audio_move(state, go):  # a song or narrated video: its audio is the clock
        return audio
    if state["shots"] == "none":
        return go("plan", "There are no shots yet.")
    if long := state.get("too_long"):  # before its stills: the split makes new shots
        return go("split_clip", f"{long[0]} is longer than the video model makes: split it.",
                  clip_id=long[0])  # fmt: skip
    if state["missing_looks"]:
        return go("make_looks", "Some roles have no look yet.")
    cast = state.get("cast_ok") or {}
    if cast.get("state") == "ready" and not cast.get("asked"):  # each drawn: the person's OK
        return go("ask_cast_ok", "all: the cast and places are drawn; they're the person's OK.")
    if not state["stills"]["frames"]:
        return go("storyboard", "The shots are ready; the storyboard is next.")
    stills = state["stills"]
    if stills["drawn"] + stills.get("waiting", 0) < stills["frames"]:
        return go("stills", "Some frames have no still yet.")
    if stills.get("waiting"):
        return go("wait", "The other stills wait for the cast and places OK.")
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
    # a take that's set aside (an earlier prompt, or before Start the plan again) is never picked
    now = {c["clip_id"]: [t for t in c["takes"] if not t.get("set_aside")] for c in clips}
    if bare := [c for c in clips if not now[c["clip_id"]] and not c.get("talker")
                and not c.get("waits_for_cast")]:  # fmt: skip
        if all(c["picked_take_id"] is None for c in bare):
            return go("make_take", "Some clips have no take yet.")
        return go("make_take", f"{bare[0]['clip_id']} has no take from its prompt now.",
                  clip_id=bare[0]["clip_id"])  # fmt: skip
    if any(c.get("waits_for_cast") for c in clips):
        return go("wait", "The other takes wait for the cast and places OK.")
    clips = [c for c in clips if c["takes"]]  # a talker's are cut from its take at the cut
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
            note = "; ".join(last["notes"]) or "Fix what the watch found."
            return go("make_take", f"The watch flagged {c['clip_id']}.",
                      clip_id=c["clip_id"], note=note[:500])  # fmt: skip
    for c in clips:  # the newest clean take (Builder-Server-8's best-take function to come)
        if not now[c["clip_id"]]:
            continue  # a talker's, cut from its take at the cut
        clean = next((t for t in reversed(now[c["clip_id"]]) if t["verdict"] == "clean"), None)
        best = clean or now[c["clip_id"]][-1]
        by_watch = picked_by_watch.get(c["clip_id"])  # none picked yet: never the watch's pick
        if c["picked_take_id"] != best["id"] and (
            c["picked_take_id"] is None or c["picked_take_id"] != by_watch
        ):
            why = (f"Take {best['number']} is {c['clip_id']}'s newest clean take." if clean
                   else f"No take of {c['clip_id']} is clean: using the newest, take "
                   f"{best['number']}.")  # fmt: skip
            return go("pick_take", why, clip_id=c["clip_id"], take_id=best["id"])
    if (host := state.get("host")) and host["state"] != "ready":  # a presenter: before the cut
        if host["state"] == "making":
            return go("wait", "The host is being made.")
        return go("host", "all: the host says the narration on camera over the B-roll.")
    if state["cut"] != "none" and (fix := _next_fix(found, {c["clip_id"]: c for c in clips})):
        return fix  # every fix the watch of this cut found, then one cut again
    failed = state.get("cut_failed")
    edited = failed and failed.get("changed")  # an edit since it failed: cut again to see
    if failed and not edited and "loop_music" in failed["fixes"]:
        return go("edit_cut", f"{failed['why']} Looping the music to fit.",
                  edit={"kind": "music", "loop": True})  # fmt: skip
    if failed and not edited:  # nothing a cut again would change: say so
        return go("stop", failed["why"])
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
    made = f"The cut is made with each clip's best take. {done}".strip()
    unsure = " ".join(x for x in (keep, _still_wrong(state)) if x)
    return go(
        "deliver",
        "The cut is made and watched."
        if watch.get("state") == "done" and watch.get("current")
        else "The cut is made.",
        made=made,
        unsure=unsure,
        needs=noticed,
    )  # its questions are for the owner


def _still_wrong(state: dict) -> str:
    """For the delivery note: the brand's name the narration in use still says wrong, once
    its remakes are used (director.md: say what's off)."""
    audio = state.get("narration") or {}
    used = next((t for t in audio.get("takes") or [] if t["used"]), None)
    if not used or not used.get("misheard"):
        return ""
    w = used["misheard"][0]
    return (f"The narration still says “{w['heard']}” for {w['word']} at {w['at']:.1f} s: it "
            "was read again as often as allowed, so listen before you share it.")  # fmt: skip


STAND_IN_STYLE = "bright pop, warm female vocal, 110 bpm"  # a song version with no style line


def _audio_move(state: dict, go) -> dict | None:
    """The stand-in's song or narration: make it, wait for it, then use its best take; a
    failed one is tried again (free when the service failed; refused, it says so). A narration
    that says the brand's name wrong is read again with the pronunciation note (while
    narrations are left), and the plan follows one that says it right."""
    tool = "song" if "song" in state else "narration" if "narration" in state else None
    audio = state.get(tool) if tool else None
    if audio is None:
        return None
    if tool == "narration" and (said := _say_it_right(audio, state, go)):
        return said
    if audio.get("used_take_id"):
        return None
    what = "song" if tool == "song" else "narration"
    if audio["state"] == "none":
        style = {} if audio.get("style", True) else {"note": STAND_IN_STYLE}  # a song's first
        return go(tool, f"The {what} first: its timing is what the shots follow.", **style)
    if audio["state"] == "making":
        return go("wait", f"The {what} is being made.")
    if audio["state"] == "ready":
        return go(tool, f"The {what} is made and timed: use its best take.")
    return go(tool, f"The {what} didn't come out: try it again.")  # free once; then a note


def _say_it_right(audio: dict, state: dict, go) -> dict | None:
    """A narration that says the brand's name wrong, before the plan: read again with the
    pronunciation note while narrations are left, then the one that says it right is used."""
    if audio["state"] not in ("ready", "making") or state["shots"] != "none":
        return None
    timed = [t for t in audio["takes"] if t["state"] == "ready" and t["timed"]]
    used = next((t for t in timed if t["used"]), None)
    good = [t for t in timed if not t.get("misheard")]
    if used and not used.get("misheard") or not timed:
        return None
    if audio["state"] == "making":
        return go("wait", "The narration is being read again.")
    if good:
        return go("narration", "This narration says the brand's name right: use it.",
                  take_id=good[-1]["id"])  # fmt: skip
    wrong = timed[-1]["misheard"][0]
    if state.get("allowed", {}).get("narrations_left", 0) > 0:
        return go("narration", f"The narration says “{wrong['heard']}” for {wrong['word']} at "
                  f"{wrong['at']:.1f} s: read it again.", note=audio["say"])  # fmt: skip
    return None


# Rule 19, not here: an ask to change the script's words ("change the line to ...", "make her
# say 'Buy now'", "rewrite clip 2"), never a note that only mentions what someone says or said.
WORDS = re.compile(
    r"\b(?:rename|re-?word|rewrite|(?:change|edit|replace|swap|cut|drop)\b[^.]{0,30}?\b"
    r"(?:words?|lines?|script|dialogue|wording)\b|say\s+['\"“‘])",
    re.I,
)


SOUND = re.compile(r"\bsound effects?\b|\bsfx\b|\badd\b[^.]{0,30}\bsounds?\b", re.I)
# Notes the cut's own edits answer (free; the stand-in's reading, the real director decides)
TIGHTEN = re.compile(r"\btighten\b|\bdrags?\b|\btoo slow\b", re.I)
SHORTER_END = re.compile(r"\bshorter (?:end|ending)\b|\b(?:end|ending) shorter\b", re.I)
SWAP_AT = re.compile(r"\bswap\b.*?\bat (\d+):(\d\d)\b", re.I)
SIDE = re.compile(r"\b(?:presenter|host|him|her|them)\b.*?\b(left|right)\b", re.I)


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
        if not m.get("answered") and (move := _cut_move(state, m)):
            return move
        if not m.get("answered") and SOUND.search(m["text"]):  # sound effects, asked for once
            ready = clips and all(c["picked_take_id"] for c in clips.values())
            if "add_sound" in state.get("done", []) or not ready:
                continue  # tried this run (a refusal is said in the delivery note), or no takes
            return {"tool": "add_sound", "why": f"Note {m['note']}: you asked: {m['text']}"[:300],
                    "clip_id": clip if clip in clips else None, "take_id": None,
                    "note": m["text"][:300]}  # fmt: skip
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


def _cut_move(state: dict, m: dict) -> dict | None:
    """A note the cut's own edits answer, as one free edit (or a redo when the B-roll at a
    time has no other take to swap to)."""
    tl, text = state.get("timeline"), m["text"]
    if (
        not tl
        or not tl["pieces"]
        or not (
            TIGHTEN.search(text)
            or SHORTER_END.search(text)
            or SWAP_AT.search(text)
            or SIDE.search(text)
        )
    ):
        return None
    why = f"Note {m['note']}: you asked: {text}"[:300]

    def go(**edit) -> dict:
        return {"tool": "edit_cut", "why": why, "clip_id": None, "take_id": None, "note": "",
                "edit": edit}  # fmt: skip

    pieces = tl["pieces"]
    if at := SWAP_AT.search(text):
        t = int(at[1]) * 60 + int(at[2])
        p = next((p for p in pieces if p["start"] <= t < p["end"]), pieces[-1])
        clip = next((c for c in state["clips"] if c["clip_id"] == p["clip_id"]), None)
        other = next((x for x in reversed((clip or {}).get("takes") or [])
                      if x["id"] != p["take_id"]), None)  # fmt: skip
        if other:
            return go(kind="swap", piece=p["piece"], take_id=other["id"])
        return {"tool": "make_take", "why": why, "clip_id": p["clip_id"], "take_id": None,
                "note": text[:500]}  # fmt: skip
    if SHORTER_END.search(text):
        return go(kind="retime", piece=pieces[-1]["piece"])
    if TIGHTEN.search(text):
        return go(kind="retime", piece=pieces[len(pieces) // 2]["piece"])
    if tl.get("presenter"):
        side = SIDE.search(text)[1].lower()
        return go(kind="presenter", start=0, end=tl["length"], side=side)
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
        elif SOUND.search(m["text"]):
            out.append(f"Note {n}: {take_sound.ALL_HAVE}")
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
        if f.get("fix") == "redo" and len(c["takes"]) == 1 and not c.get("talker"):
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
    if piece := job.input.get("host_piece_id"):
        from app.models.clips import HostPiece

        row = db.get(HostPiece, piece)
        return f"The host's piece {row.number}" if row and row.number else "The host's still"
    step = str(job.input.get("step") or job.kind)
    return NAMED.get(step) or f"The {step.replace('_', ' ')}"


NAMED = {"watch_cut": "The watch of the cut", "cut_listen": "The watch of the cut",
         STEP: "The director's next step", "treatment": "The treatment",
         "take_watch": "The watch of a take", "review_stills": "The look at the stills",
         "write-claude": "The director's next step", "item_check": "A take's check",
         "ask_option": "The options for a question"}  # fmt: skip  # plain names, never a step's


def _waiting(db: Session, project: Project) -> list[Job]:
    """What's being made for the video: its own jobs, and its narration's (or song's) timing
    and music bed, which carry no video (the dry run: two waits through the timing ended it)."""
    from app.models.songs import SongTake

    step = Job.input["step"].as_string()
    takes = select(SongTake).where(SongTake.project_id == project.id)
    audio = or_(Job.id.in_(takes.with_only_columns(SongTake.timing_job_id)),
                Job.id.in_(takes.with_only_columns(SongTake.music_job_id)))  # fmt: skip
    return list(db.scalars(select(Job).where(or_(Job.project_id == project.id, audio),
                                             Job.status.in_(WAITING),
                                             or_(step.is_(None), step != STEP))))  # fmt: skip


def _has_take(db: Session, project: Project, clip_id: str) -> bool:
    row = db.scalar(select(ProjectClip).where(ProjectClip.project_id == project.id,
                                              ProjectClip.clip_id == clip_id))  # fmt: skip
    return bool(row and row.picked_take_id)
