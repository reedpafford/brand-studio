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
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import event, func, or_, select, update
from sqlalchemy.orm import Session

from app import (
    advice,
    asks,
    breakdown_fix,
    cast_gate,
    cut_edits,
    director_song,
    director_tools,
    live,
    locked_line,
    take_mute,
    take_sound,
    talker_sound,
    told_look,
    video_variations,
    word_splice,
)
from app.clip_takes import NOTE_MAX
from app.credits import COUNTED, FREE_LANES, FREESTYLE, lock, uncapped
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
CITE_WORDS = {"why", "made", "unsure", "needs", "ask", "left_out"}  # words people read
OLD_TAKE = (
    "Refused: clip {c}'s picked take holds the cut out of date however often it's made "
    "again ({why}). Make another take of clip {c}, or pick one that's current."
)
RUNNING = "The director is already building this video."
NOTE = re.compile(r"\bnote (\d+)\b", re.I)  # how a move's why names the note it answers
OPEN = "Refused: note {0} is still open. Make it, or say why it can't; write Note {0} in that move."
READ = "chat_read"  # in a turn's input: how many of its run's messages it read
GAP, PER_RUN = timedelta(seconds=3), 30  # one note a person every 3 s; notes a run at most
TOO_MANY = "Too many messages; wait a moment."
IDLE = "Waiting, with nothing being made: it reads the video again."
WATCHED_AGAIN = "Refused: it already watched this cut; fix something or deliver."
REDO_NEEDS = ("needs a reason: a flagged take, a watch of this cut that saw it (a lip-sync "
              "doubt both watches saw counts), or a person's note")  # fmt: skip
ON_FACE = ("lipsync", "timing")  # a take's line on the wrong face, or run onto the next one
DOUBT = "Refused: {} has only a doubt, which is the owner's to judge; say so in the delivery note."
TURN_FAILED = "A turn failed; nothing more was done. Start it again to go on."
START = asks.START  # in its held first paid turn: the start card (S3-02)
START_HELD = "Ready to start: it waits for Make it."  # the start card's hold
START_FIRST = "Waiting for Make it: nothing more runs before it."  # a move before the OK
NOT_MADE = "Not made yet: it waits for Make it, and is made once it's pressed."  # START_FIRST,
# as <last_actions> shows it: the step still to make, not one done
TREATMENT_FIRST = "Refused: the treatment comes first, before Make it."
PLAN_FIRST = "Changing the plan first."  # a note while the start card waited
PRE_OK = ("treatment", "ask", "wait", "stop", "locked_line",
          "find_footage")  # fmt: skip  # before Make it: nothing made
# The direction card (Reed, 8 Nov: "before any paid stills or takes, the director presents one
# card: concept, beats, the look, the clip plan and the estimate"): on a first run not held for
# the owner, the director plans up to its cast and places OK before Make it, and the card comes
# when it asks for that OK or reaches a still or a take. Make it is then the go and the OK.
PLANNING = ("song", "narration", "plan", "split_clip", "make_looks", "add_place", "change_look",
            "outfit", "ask_cast_ok", "settings", "clip_model")  # fmt: skip
# A revision (a run on a video that has delivered): its free changes to the cut it has, and the
# watch and delivery they lead to, need no Make it (Reed: a revision charges only the affected
# work). Anything that makes something new still waits on its start card.
REVISION = "revision"  # in a run: started after a delivery, it reuses the video's story
REVISE_FREE = ("edit_cut", "final_cut", "mute", "unmute", "pick_take", "splice_word",
               "watch_cut", "deliver")  # fmt: skip
ON_YOU = "Waiting on your answer; everything else is made."  # parked on open questions
CAST_WAIT = "Waiting for the cast and places OK."  # its run waits on that point only


def start(db: Session, user: User, project: Project, *, hold: str = "",
          extra: dict | None = None, frozen: bool = True, fresh: bool = False,
          approved: dict | None = None) -> Job:  # fmt: skip
    """A run on a video made from a published script (its words are locked): its first turn.
    Every way in starts the same (S3-02): its plan (the treatment) first, charged at its real
    cost on the video's planning allowance (`asks.past_planning`), then the run waits on its
    start card, "Make it · up to $X", before any generation (`ok` in the run). `hold`: why
    that card waits for the owner (an editor's pasted words or New video send, or a script
    past what's left of its budget); "" lets the video's own editor press it (S2-06).
    `extra`: more of its input (the freestyle it's for), carried to the start card.
    `frozen=False`: a freestyle's, whose version is frozen and published when its run starts
    (`freestyles.freeze`). `fresh`: "Start the plan again" (S3-08): after Make it the run
    plans the whole video again instead of carrying on from its shots (`fresh`). `approved`:
    the owner's own priced press is its OK (line_change: "Change the line"), so no start card:
    its price, the clips it may make, and where its charges start (`PRICED`)."""
    if why := blocked(db, project) if frozen else (RUNNING if active(db, project) else ""):
        raise HTTPException(409, why)
    _close_carry(db, project)  # a Carry on still waiting for the owner isn't needed now
    again = {FRESH: utcnow().isoformat()} if fresh else _replanning(db, project)
    lock(db, Project, project.id)  # the notes it takes can't change under it
    db.refresh(project)
    left = set(leftover(db, project))  # every note no run has read: this run reads them
    after = delivered(turns(db, project)) or video_variations.source(db, project)
    if left and not fresh and after:  # notes after a delivery, or on a variation of one: a
        again = {**again, REVISION: True}  # revision, whose story stands
    run = {"id": uuid.uuid4().hex, "turn": 0, "redos": {}, "by": user.id,
           "ok": bool(approved) and user.is_owner, "hold": hold, **again,
           **({PRICED: approved} if approved else {})}  # fmt: skip
    if left:
        project.director_chat = [{**m, "run": run["id"]} if n in left else m
                                 for n, m in enumerate(project.director_chat)]  # fmt: skip
    return _turn(db, user, project, run, extra=extra)


CARRIES = asks.CARRIES  # in a carried-on run's held turn: the run's own approved price
CARRY_HOLD = "Waiting for the owner's OK to carry on after their Stop."
WAS_STOPPED = "was_stopped"  # on a turn a Stop (or a fault) ended, once the run carried on


CARRY_WAITING = "Waiting for the owner's OK to carry on."


def carry_on(db: Session, user: User, project: Project) -> Job:
    """Carry on (S3-08): the run a person stopped, or that stopped itself at a fault, goes on
    where it left off (its treatment, plan and Make it stand: video 240), the same run
    (rule 34: its price, holds, counts, notes and the director's own limits are its own), under
    the owner's existing OK and with no new start card, while its own approved price has
    something left (`run_progress.carry_left`); a step past it waits for the owner as any does
    (`asks.past_run`). A Stop the owner made holds an editor's Carry on for the owner, on a
    card for the rest of that price: the run stays stopped until the owner says yes
    (`resume`, as its turn starts), and a decline or withdraw leaves it as it was. With
    nothing of it left, or the run stopped before its Make it, it's a new run with its own
    start card. Checked under the video's lock, and the Stop lifted with its turn queued in
    one commit (a failed turn takes it all back)."""
    from app import run_progress

    lock(db, Project, project.id)
    db.refresh(project)
    if why := blocked(db, project):
        db.rollback()
        raise HTTPException(409, why)
    if _carry_waiting(db, project):
        db.rollback()
        raise HTTPException(409, CARRY_WAITING)
    rows = turns(db, project)  # the run's own starter decides, not who presses (QA on #1396)
    starter = db.get(User, (rows[-1].input[RUN].get("by") if rows else None) or 0)
    left = run_progress.carry_left(
        db, project, whole=uncapped(starter)
    )  # uncapped: whatever's left
    if left is None:
        db.rollback()
        return start(db, user, project, hold=asks.start_hold(db, user, project))
    rows = turns(db, project)  # a person's Stop, or none: it stopped itself (video 240)
    stopped = next((j for j in reversed(rows) if j.input.get(run_progress.STOPPED_BY)), None)
    by = db.get(User, stopped.input[run_progress.STOPPED_BY]) if stopped else None
    run = dict(rows[-1].input[RUN])
    if notes := set(leftover(db, project)):  # what was said since the Stop: it reads them
        project.director_chat = [{**m, "run": run["id"]} if n in notes else m
                                 for n, m in enumerate(project.director_chat)]  # fmt: skip
    held = CARRY_HOLD if by and by.is_owner and not user.is_owner else ""
    if not held:
        resume(db, project, run["id"])  # it goes on now
    try:
        return _turn(db, user, project, run, carry=(held, left) if held else None)
    except Exception:
        db.rollback()  # the Stop, the notes and the turn: none of it happened
        raise


def resume(db: Session, project: Project, run_id: str) -> None:
    """The Stop stays on record on its turn (`WAS_STOPPED`, with when it carried on), no
    longer the run's end: the run goes on. Not committed here."""
    now = utcnow().isoformat()
    for j in turns(db, project):
        if j.input[RUN]["id"] == run_id and j.input.get("ended"):
            was = {k: j.input.get(k) for k in ("ended", "stopped_by", "stopped_at")}
            j.input = {**{k: v for k, v in j.input.items() if k not in was},
                       WAS_STOPPED: {**was, "carried_at": now}}  # fmt: skip


NEW_RUN = "A new run started, so this isn't needed."


def _close_carry(db: Session, project: Project) -> None:
    """A new run on the video: an editor's Carry on still waiting for the owner's OK goes, its
    card no longer needed (never a press that does nothing). Nothing was charged for it."""
    held = _carry_waiting(db, project)
    if held is None:
        return
    held.status, held.finished_at = JobStatus.cancelled, utcnow()
    for ask in db.scalars(select(Ask).where(Ask.project_id == project.id, Ask.kind == "start")):
        if held.id in (ask.job_ids or []):
            ask.state, ask.closed = "not_needed", NEW_RUN


def _carry_waiting(db: Session, project: Project) -> Job | None:
    """A Carry on held for the owner's OK on this video, if any."""
    return db.scalar(select(Job).where(Job.project_id == project.id,
                                       Job.input["step"].as_string() == STEP,
                                       Job.input[CARRIES].as_string().is_not(None),
                                       Job.status == JobStatus.needs_owner_approval)
                     .limit(1))  # fmt: skip


def say(db: Session, user: User, project: Project, text: str, files: list[int] = (),
        revise: bool = False) -> Ask | None:  # fmt: skip
    """A person's note to the director (director-chat.md §1 item 4), kept in the thread with
    any pictures or clips sent with it (for this video only, rule 12; the director looks at
    them). While a run goes on, its next turn reads it (a turn already in flight, the one
    after); a run waiting on an answer wakes to read it, and one waiting on its start card
    reads it before Make it ("Change the plan first", S3-02). A note that asks only to change
    a locked line is answered at once (S3-14): that reply card is returned, and no run needs to
    read the note. `revise`: after a delivery, any other note starts the next run, as the
    boards draw revisions (S3-12: by talking, then its start card; the chat's note, from the
    video's maker or the owner), and one that asks both gets the reply and starts the run for
    its other half. After a Stop it waits, unread, for Carry on or the next run, which read
    every unread note. Nothing is charged for the note itself."""
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
    answered = instead = None
    if not going:
        try:  # a card that can't be made never loses the note (video 261: a 500 on a note)
            with db.begin_nested():
                instead = locked_line.offer(db, user, project, text)
        except Exception:
            log.exception("video %s: no locked-line card; the note goes on as it is", project.id)
    if instead and instead[1]:  # all it asked: answered at once (S3-14), no run reads it; a
        said["offer"], answered = instead[0].id, instead[0]  # note that asks more: Make it
    project.director_chat = [*every, said]
    db.commit()
    if going and going.status == JobStatus.needs_owner_approval and going.input.get(START):
        _plan_first(db, project, going)
    elif going:
        wake(db, project)
    elif (
        revise
        and not going
        and "offer" not in said
        and _delivered(db, project)
        and not blocked(db, project)
    ):  # a revision starts by talking (S3-12): the run, then its own start card
        start(db, user, project, hold=asks.start_hold(db, user, project))
    return answered


def _delivered(db: Session, project: Project) -> bool:
    return delivered(turns(db, project))


def delivered(rows: list[Job]) -> bool:
    """The run delivered: one of its turns says so. Never only its last turn (video 233: after
    a restart a duplicate turn, cancelled, came last, so a note never started the revision)."""
    return any(j.input.get("result") == DELIVERED for j in rows)


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
    live.note(db, held.project_id, JobStatus.cancelled)
    db.refresh(held)
    run = {**held.input[RUN], "ok": False}
    held.input = {**held.input, "result": PLAN_FIRST}
    db.commit()
    _turn(db, db.get(User, run["by"]), project, run)


def chat(project: Project, run_id: str) -> list[dict]:
    """What people asked of this run, oldest first."""
    return [{"text": m["text"]} for m in project.director_chat or [] if m.get("run") == run_id]


def answered(db: Session, run_id: str, project_id: int | None = None) -> set[int]:
    """The run's notes (numbered from 1) a move has answered: named "Note N" in the why of a
    move that wasn't refused, or in the delivery's note, or read by its treatment as it was
    written (`read_notes`). An ask stays open until then. With its video (`project_id`), only
    that video's jobs are read, not the whole table."""
    if project_id is not None:
        rows = [j for j in all_turns(db, project_id) if j.input[RUN]["id"] == run_id]
    else:
        mine = (Job.input["step"].as_string() == STEP, Job.input[RUN]["id"].as_string() == run_id)
        rows = db.scalars(select(Job).where(*mine)).all()
    return {int(n) for j in rows if not (j.input.get("result") or "").startswith("Refused")
            and j.input.get("result") != START_FIRST  # asked for, but it waits for Make it
            for n in NOTE.findall(move_words(j.output or {}))} | in_treatment(
        db, run_id, project_id)  # fmt: skip


def in_treatment(db: Session, run_id: str, project_id: int | None) -> set[int]:
    """The run's notes its treatment read as it was written (`read_notes`)."""
    return {n for j in db.scalars(select(Job).where(
        Job.input["step"].as_string() == "treatment", Job.input[RUN]["id"].as_string() == run_id,
        Job.status == JobStatus.succeeded,
        *((Job.project_id == project_id,) if project_id is not None else ())))
        for n in j.input.get(NOTES_READ) or []}  # fmt: skip


def move_words(decision: dict) -> str:
    """A move's words that can name a note: its why, and on a delivery its note's parts."""
    return " ".join(decision.get(k) or "" for k in ("why", "made", "unsure", "needs"))


def leftover(db: Session, project: Project) -> list[int]:
    """The notes (by place in the chat) that no run read and none will: sent with no run
    going, or while a run's last turn delivered or it stopped. The next Make it reads them."""
    rows = all_turns(db, project.id)
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

    runs_ = {m.get("run") for m in project.director_chat or []}
    done = {r: answered(db, r, project.id) for r in runs_ if r}
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
    shown = _shown(db, project) if written else None
    for n, j in enumerate(written):  # the treatment, posted in the chat as plain lines
        out.append({"id": f"s{j.id}", "kind": "move", "at": (j.finished_at or j.created_at
                    ).isoformat(), "who": "Director", "text": named(told(j.output or {}, n > 0)),
                    "status": "done", "why": "", "answered": None,
                    "treatment": shown(j.output or {})})  # fmt: skip
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
    cut saw in the frames or, for lip-sync, saw as its take's watch did (`_seen_twice`)."""
    clip = next((c for c in video_state(db, project)["clips"] if c["clip_id"] == clip_id), None)
    given = max((t.input.get(READ, 0) for t in turns(db, project)
                 if t.input[RUN]["id"] == run_id), default=0) if run_id else 0  # fmt: skip
    asked = any(1 <= int(n) <= given for n in NOTE.findall(why))  # a note this run was given
    if not clip or not clip["takes"] or asked:
        return False
    return not _confirmed(db, project, clip, _watch(db, project))


def _confirmed(db: Session, project: Project, clip: dict, watch: dict) -> bool:
    """A redo of this clip (as the director reads it) has a confirmed reason: its last take's
    watch flagged a fault, the clip is stale or was made from another prompt, or the current
    watch of the cut saw it in the frames, or saw again a lip-sync doubt its take's watch had."""
    last = clip["takes"][-1]
    row = db.scalar(select(ProjectClip).where(ProjectClip.project_id == project.id,
                                              ProjectClip.clip_id == clip["clip_id"]))  # fmt: skip
    newest = db.get(ClipTake, last["id"])
    if (
        last["verdict"] == "flagged"
        or clip["stale"]
        or clip.get("old_take")  # its take holds the cut out of date: the server's own reason
        or (newest.prompt or row.prompt) != row.prompt
    ):
        return True
    return bool(watch.get("current") and any(
        f.get("clip_id") == clip["clip_id"] and f.get("fix") == "redo"
        for f in watch.get("findings") or [])) or _seen_twice(db, clip, watch)  # fmt: skip


def _seen_twice(db: Session, clip: dict, watch: dict) -> bool:
    """A lip-sync doubt its take's own watch had (a line on the wrong face) that the current
    watch of the cut saw again on the same take and would have remade: two watches agreeing
    is a fault (276: both saw lines on the listener's face; the remake was refused). Only
    lip-sync: a voice, sound or words doubt stays the owner's (Reed, 4 Nov; MAIN, 8 Nov)."""
    take = db.get(ClipTake, clip["picked_take_id"]) if clip.get("picked_take_id") else None
    doubted = any(f.get("kind") in ON_FACE and not f.get("verified", True)
                  for f in ((take.watch if take else None) or {}).get("faults") or [])  # fmt: skip
    return bool(doubted and watch.get("current") and any(
        f.get("doubt") and f.get("clip_id") == clip["clip_id"] and f.get("kind") == "lipsync"
        for f in watch.get("findings") or []))  # fmt: skip


def _watched(db: Session, project: Project) -> list[dict]:
    """What its watch of each take and host piece found and did, said in the chat when it
    acted (rule 11): "Clip 7, take 1: cartoon eyes landed on the stomach … Remade it …"."""
    from app import watch_report

    out = []
    for x in watch_report.watched(db, project):
        w = x["watch"]
        if w.get("action") not in watch_report.ACTED or (x["item"].watch or {}).get("by") == "cut":
            continue  # a redo the watch of the cut asked for: its turn and the note say it
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


def clip_no(clip_id: str) -> str:
    """A clip as people read it: "1" for c1, "1b" for a split's c1b (the web's clipNo)."""
    return clip_id.removeprefix("c")


def named(text: str) -> str:
    """A move as people read it: clips as they see them ("clip 1", "clip 1b", never "c1"), and
    a note still open without what OPEN tells the director to do (QA-3)."""
    text = re.sub(r"^(Refused: note \d+ is still open\.).*", r"\1", text, flags=re.S)
    return re.sub(r"\bc(\d+[a-z]?)\b", r"clip \1", text)


def blocked(db: Session, project: Project) -> str:
    """Why a run can't start on this video now ("" when it can): the start's own refusal."""
    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    if not (draft and db.get(Script, draft.script_id).published):
        return NOT_PUBLISHED
    if video_variations.writing(db, project):  # they copy it as it is when they're written
        return video_variations.WRITING
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


READING = "director_reading"  # in a session's info while a page reads (`reading`)


@contextmanager
def reading(db: Session):
    """A page's read (GET /director, /progress): the video's turns are read once, not once a
    helper (video 240: each turn holds its whole prompt, and /director read them all some 30
    times, 11-30 s). Any write in the session reads them fresh again."""
    if READING in db.info:  # inside another read: its cache
        yield
        return
    db.info[READING] = {}
    try:
        yield
    finally:
        db.info.pop(READING, None)


@event.listens_for(Session, "after_flush")
@event.listens_for(Session, "after_commit")
@event.listens_for(Session, "after_rollback")
def _written_since(session, *_) -> None:
    if READING in session.info:
        session.info[READING] = {}


@event.listens_for(Session, "do_orm_execute")
def _bulk_write(state) -> None:
    if not state.is_select and READING in state.session.info:
        state.session.info[READING] = {}


def all_turns(db: Session, project_id: int) -> list[Job]:
    """Every director turn on the video, every run, in order; once a page read (`reading`)."""
    seen = db.info.get(READING)
    if seen is not None and project_id in seen:
        return seen[project_id]
    rows = list(db.scalars(select(Job).where(Job.project_id == project_id,
                                             Job.input["step"].as_string() == STEP)
                           .order_by(Job.id)).all())  # fmt: skip
    if seen is not None:
        seen[project_id] = rows
    return rows


def turns(db: Session, project: Project) -> list[Job]:
    """Every turn of the video's newest run, in order (its log)."""
    rows = all_turns(db, project.id)
    run = rows[-1].input[RUN]["id"] if rows else None
    return [j for j in rows if j.input[RUN]["id"] == run]


def active(db: Session, project: Project) -> Job | None:
    """The newest run's last turn while the run goes on (not delivered, stopped or ended)."""
    last = next(reversed(turns(db, project)), None)
    if last is None or last.status == JobStatus.cancelled:
        return None
    if over(db, last.input[RUN]["id"], project.id):
        return None
    return last


def over(db: Session, run_id: str, project_id: int | None) -> bool:
    """Whether a run has ended (delivered, stopped, failed): ANY of its turns says so, read
    fresh. A turn made while Stop landed (QA-7, round 3) never brings the run back. Read from
    its video's jobs only (video 240: the whole table, every call, made /director 11-30 s)."""
    return bool(db.scalar(select(func.count()).where(
        Job.project_id == project_id, Job.input["step"].as_string() == STEP,
        Job.input[RUN]["id"].as_string() == run_id,
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
        live.note(db, project.id, JobStatus.cancelled)
        db.refresh(last)
        _end(last, STOPPED)
        last.input = {**last.input, "stopped_by": by, "stopped_at": utcnow().isoformat()}
        asks.close_run(db, last.input[RUN]["id"], "The run was stopped.")
        db.commit()


def spent(db: Session, run_id: str, project_id: int | None) -> Decimal:
    """What the run's own Claude turns really cost (Usage), for the limit and to measure."""
    ids = select(Job.id).where(Job.project_id == project_id,
                               Job.input[RUN]["id"].as_string() == run_id)  # fmt: skip
    return Decimal(db.scalar(select(func.coalesce(func.sum(Usage.cost_usd), 0))
                             .where(Usage.job_id.in_(ids))))  # fmt: skip


OWN_LIMIT = "Waiting for the owner's OK: the director has used its own limit of {n} credits."
GRANT = "own_grant"  # in a run's job's input: held at the director's own limit (`past_own`)


def own_limit() -> Decimal:
    """The director's own limit a run, in credits, as the quote shows it: OWN_CREDITS (MAX_USD
    stays the real-cost backstop)."""
    return OWN_CREDITS


def own_charged(db: Session, run_id: str, project_id: int | None) -> tuple[Decimal, int]:
    """What the run's own jobs (its turns and its watches of the cut) were charged, at the
    flat price each was charged (not their real cost, `spent`), and how many OKs the owner
    gave at its limit."""
    mine = (
        Job.project_id == project_id,
        Job.input[RUN]["id"].as_string() == run_id,
        Job.status.in_(COUNTED),
        Job.input[asks.BEFORE].as_boolean().is_not(True),
    )  # its plan: its own allowance
    charged = db.scalar(select(func.coalesce(func.sum(Job.credits), 0)).where(*mine))
    oks = db.scalar(select(func.count()).where(*mine, Job.input[GRANT].as_boolean()))
    return Decimal(charged), oks


def own_usd(db: Session, run: dict, project_id: int | None) -> Decimal:
    """The real-cost backstop for this run: MAX_USD, and as much again for each OK the owner
    gave at its own limit, as that limit grows (audit 6 Nov: else it stops after the OK). None
    on the owner's own run with `owner_uncapped` (Reed, 6 Nov)."""
    if uncapped(db.get(User, run.get("by") or 0)):
        return Decimal("Infinity")
    return MAX_USD * (1 + own_charged(db, run["id"], project_id)[1])


def _limit_usd(most: Decimal) -> float | None:
    """<allowed>'s own_time_limit_usd: None when there's none (JSON has no infinity)."""
    return None if most.is_infinite() else float(most)


def past_own(db: Session, project: Project, run_id: str | None, credits: Decimal,
             user: User) -> str:  # fmt: skip
    """A run's next turn or watch that would take its charges past the director's own limit
    (the Producer): it waits for the owner, the owner's own run too, with a freestyle's
    reason for a step past its price, else OWN_LIMIT. Each OK grants another limit's worth,
    not one step. "" if it fits, and always on the owner's own run with `owner_uncapped`."""
    from app.credits import PAST_APPROVED, price

    if not run_id or uncapped(user):
        return ""
    charged, oks = own_charged(db, run_id, project.id)
    if charged + credits <= own_limit() * (1 + oks):
        return ""
    return PAST_APPROVED if project.hidden else OWN_LIMIT.format(n=price(own_limit()))


PRICED = "priced"  # in a run its press priced (line_change): {price, clips, since}
PRICED_ONLY = ("Refused: this run was priced for clip {} only (the owner's Change the line); "
               "it makes nothing else. Cut and watch what it made.")  # fmt: skip


def priced(db: Session, project: Project) -> dict | None:
    """The newest run's price when the owner's priced press started it (no start card): its
    OK, as a Make it's (`asks.approved_run`), held to on the uncapped site too."""
    if db.info.get(READING) is not None:  # a page read: its turns, read once (`all_turns`)
        last = next(reversed(all_turns(db, project.id)), None)
    else:  # else the newest turn only
        last = db.scalar(select(Job).where(Job.project_id == project.id,
                                           Job.input["step"].as_string() == STEP)
                         .order_by(Job.id.desc()).limit(1))  # fmt: skip
    return last.input[RUN].get(PRICED) if last else None


def _outside(db: Session, project: Project, run: dict, decision: dict) -> str:
    """A priced run's take or still of a clip its price didn't count (QA on #1437): refused,
    so its price holds (only its clips were priced)."""
    mine = (run.get(PRICED) or {}).get("clips")
    tool = decision.get("tool")
    if not mine or tool not in ("make_take", "redraw_still") or decision.get("redraws"):
        return ""
    if tool == "make_take":
        clip = decision.get("clip_id") or ""
    else:
        from app.clip_prompts import newest

        bd = newest(db, project)
        clip = next((c["id"] for c in (bd.data.get("clips", []) if bd else [])
                     if decision.get("shot_id") in c["shot_ids"]), "")  # fmt: skip
    if clip in mine:
        return ""
    return PRICED_ONLY.format(", ".join(c.removeprefix("c") for c in mine))


STORE: ContextVar = ContextVar("director_storage", default=None)  # the worker's, for `_auto`


def after(db: Session, job: Job, storage) -> None:
    """The worker finished `job`: a turn's answer is acted on; any other work on a video with
    a run going may wake the next turn."""
    kept = STORE.set(storage)
    try:
        _after(db, job, storage)
    finally:
        STORE.reset(kept)


def _after(db: Session, job: Job, storage) -> None:
    if job.input.get("step") == STEP:
        if _stopped(db, job) or over(db, job.input[RUN]["id"], job.project_id):  # Stop landed
            return
        if job.status == JobStatus.succeeded:
            _act(db, job, storage)
        elif not _again(db, job):
            _end(job, turn_failed(job))
        return
    run_id = (job.input.get(RUN) or {}).get("id")
    if job.input.get("step") == "treatment" and job.status == JobStatus.succeeded:
        if job.project_id and isinstance(job.output, dict):  # read in the chat: no citation
            named = _names_reed(db, db.get(Project, job.project_id))
            told = advice.uncited(job.output, "treatment", named)
            told["beats"] = [advice.uncited(b, "beat", named) for b in told.get("beats") or []]
            job.output = told
        if run_id and over(db, run_id, job.project_id):  # stopped meanwhile: nothing more
            return
        if _treatment_checked(db, job):  # one redo with its problems: the redo wakes the run
            return
    if job.project_id:
        wake(db, db.get(Project, job.project_id))


RETRIED = "retried"  # in a failed turn's input: the same turn was asked again (`_again`)
RETRIED_SAID = "My answer was cut off or unreadable; asked again."  # its line in <last_actions>


def _again(db: Session, job: Job) -> bool:
    """A turn whose answer came back cut off or unreadable is asked once more, on its own
    (audit 6 Nov: one bad answer ended the run): the same turn, needing no new OK; only its
    answer, if it comes, is charged. Whether it was asked again."""
    from app.claude import RAN_OUT, UNREADABLE

    if job.retry_of_id or (job.error_detail or "") not in (RAN_OUT, UNREADABLE):
        return False
    if not _write(db, job, {**job.input, RETRIED: True}):  # a Stop landed: no retry, kept
        db.refresh(job)
        return True
    db.refresh(job)
    db.add(Job(workspace_id=job.workspace_id, created_by_id=job.created_by_id, kind=job.kind,
               provider=job.provider, input={k: v for k, v in job.input.items() if k != RETRIED},
               project_id=job.project_id, brand_id=job.brand_id, credits=job.credits,
               approved_by_id=job.approved_by_id, status=JobStatus.queued,
               retry_of_id=job.id))  # fmt: skip
    return True


def turn_failed(job: Job) -> str:
    """Why a failed turn ended the run: the test site's real-AI budget in its own words (a Start
    again would only be refused again), else TURN_FAILED."""
    from app.run_progress import BUDGET

    return job.error if BUDGET in (job.error or "") else TURN_FAILED


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
    # The person's note stays with its fix (MAIN's run 276: the redo dropped "a barn wedding at
    # night", and the treatment kept went back to the first one's kitchen)
    fix = "\n".join(x for x in (job.input.get("note", ""), "Fix: " + " ".join(problems)) if x)
    write_treatment(db, db.get(User, job.created_by_id), project, job.input.get(RUN), fix,
                    redo=True, kept=job.input.get("note", ""))  # fmt: skip
    return True


def wake(db: Session, project: Project) -> None:
    """The next turn, once the last one was acted on and nothing on the video is waiting.
    Never twice (cost analysis A5: the worker's finish and its sweep both woke the same run,
    so a turn, and what it paid for, ran twice): `_turn` checks again under the lock."""
    if (last := _wakeable(db, project)) is None:
        return
    _turn(db, db.get(User, last.input[RUN]["by"]), project, dict(last.input[RUN]),
          after=last.id)  # fmt: skip


def _wakeable(db: Session, project: Project) -> Job | None:
    """The run's last turn when its next one should start now, else None."""
    last = active(db, project)
    if last is None or last.status != JobStatus.succeeded or "result" not in last.input:
        return None
    if _waiting(db, project) or _parked(db, project, last):
        return None
    if (
        last.input["result"] == CAST_WAIT
        and cast_gate.pending(db, project)
        and not (
            _unread(project, last)
            or asks.answered_since(db, project, (last.started_at or last.created_at).isoformat())
        )
    ):
        return None  # it goes on when the cast and places are approved, a question is
        # answered, or someone asks for more
    return last


def _parked(db: Session, project: Project, last: Job) -> bool:
    """A run that waits only on open questions (`ON_YOU`) sleeps until one is answered, a story
    choice's time passes or someone sends a note: then it reads them."""
    said = last.input.get("result") or ""
    if not (said == ON_YOU or said.startswith(told_look.WAITING)) or not asks.waiting(db, project):
        return False
    at = (last.started_at or last.created_at).isoformat()  # what it read was as of its start
    noted = any(m.get("run") == last.input[RUN]["id"] and m["at"] > at
                for m in project.director_chat or [])  # fmt: skip
    return not noted and not asks.answered_since(db, project, at)


def _unread(project: Project, last: Job) -> bool:
    """A note in the run that no turn has read yet."""
    return len(chat(project, last.input[RUN]["id"])) > last.input.get(READ, 0)


def sweep(db: Session, storage=None) -> None:
    """Each worker tick: every run whose last turn was acted on and has nothing left being
    made gets its next turn, however its work ended (failed, cancelled, released): a run
    never waits on work that is over (QA on #1087)."""
    kept = STORE.set(storage)
    try:
        _sweep(db)
    finally:
        STORE.reset(kept)


def _sweep(db: Session) -> None:
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
        if not job.input.get(RETRIED):  # unless it's being asked again (`_again`)
            _end(job, turn_failed(job))
    db.commit()
    for project_id in asks.overdue(db):  # a story choice's time passed: its pick (rule 37)
        wake(db, db.get(Project, project_id))


def _names_reed(db: Session, project: Project) -> bool:
    """A Reed in this video's own words: its script, its brand, or a look's or role's name."""
    from app import plans
    from app.models.brands import Brand
    from app.storyboard import assets

    version, brand = plans.script(db, project), db.get(Brand, project.brand_id)
    looks = [line for line, _ in assets(db, project).values()]
    return advice.names_reed(version.text if version else "", brand.name if brand else "", *looks)


def _planning(run: dict) -> bool:
    """A run that plans up to its direction card before Make it: not one held for the owner
    (an editor's send waits for Reed before anything is made, rule 33) nor a revision."""
    return not run.get("hold") and not run.get(REVISION)


def _own_plan(db: Session, run: dict, project: Project, seen: dict) -> bool:
    """Its story written, a run planning up to its card is on its own limit; a turn that
    first reads a person's note (refining it in the chat) stays on the planning allowance."""
    reads = any(m.get("new") for m in seen.get("chat") or [])
    return _planning(run) and not reads and _written(db, run, project.id)


def planning_now(db: Session, project: Project) -> bool:
    """The video's newest run plans before its own Make it: nothing it spends is held to an
    earlier run's price (its own card prices it, `asks.past_run`)."""
    last = next(reversed(turns(db, project)), None)
    return last is not None and not last.input[RUN].get("ok", True) and _planning(
        last.input[RUN])  # fmt: skip


def _unlooked(db: Session, project: Project, run: dict) -> str:
    """Before the direction card: why it can't come yet, or "". Every person and place the
    shots need is cast (free, as the storyboard would) and has a drawn look, unless a question
    to the person about them waits (QA on #1482: grey boxes on the card, then the cast stop
    again after Make it). A look that didn't draw is missing until it's drawn again once
    (make_looks); after that, or for a role nothing describes, the card comes with it marked
    as not drawn."""
    if asks.waiting(db, project):
        return ""
    me = {"project_id": project.id, "user": db.get(User, run["by"]), "db": db}
    director_tools._cast_in_shots(db, project, me)
    if missing := director_tools.missing_looks(db, project):
        return f"Refused: make the missing looks first ({', '.join(missing)}), then the card."
    items = cast_gate.current(db, project)
    if busy := [i for i in items if i["readiness"] in ("drawing", "waiting_for_owner")]:
        return f"Refused: {cast_gate.WHY[busy[0]['readiness']].format(busy[0]['name'])}; wait."
    return ""


def _before_ok(db: Session, project: Project, run: dict, tool: str | None) -> bool:
    """Whether a move runs before Make it. A wait with nothing being made and no question
    open is the plan done: the direction card comes instead."""
    if tool == "wait" and _planning(run) and _written(db, run, project.id):
        return bool(_waiting(db, project) or asks.waiting(db, project))
    return tool in PRE_OK or tool in PLANNING and _planning(run)


def _act(db: Session, job: Job, storage) -> None:
    project = db.get(Project, job.project_id)
    decision = dict(job.output or {})
    if CITE_WORDS.intersection(k for k, v in decision.items() if v):  # what people read
        named = _names_reed(db, project)
        decision = advice.uncited(decision, "move", named)
        if isinstance(decision.get("ask"), dict):
            decision["ask"] = advice.uncited(decision["ask"], "ask", named)
    job.output = decision
    run = _refund(db, project, dict(job.input[RUN]))
    tool = decision.get("tool")
    free = tool in REVISE_FREE and _free_revision(db, run, project.id)
    if not run.get("ok", True) and not free and not _before_ok(db, project, run, tool):
        written = _written(db, run, project.id)  # nothing made before Make it but the plan
        if written and _planning(run) and (why := _unlooked(db, project, run)):
            last = next((t for t in reversed(turns(db, project)) if t.id < job.id), None)
            if last is not None and last.input.get("result") == why:  # the same, again: stop
                no = why.removeprefix("Refused: ")
                return _end(job, f"It stopped: {no}", result=f"Refused again: {no}")
            return _record(db, job, run, why)  # the card shows drawn looks, never grey boxes
        return _record(db, job, run, START_FIRST if written else TREATMENT_FIRST)
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
        if old := next((c for c in state["clips"] if c.get("old_take")), None):
            return _record(db, job, run, OLD_TAKE.format(c=old["clip_id"].removeprefix("c"),
                                                         why=old["old_take"]))  # fmt: skip
        if (state.get("timeline") or {}).get("changes") or state["cut"] == "out of date":
            return _record(db, job, run, REBUILD)  # rebuilt (and watched) before it's shown
        if (state["cut"] != "none" and run.get("watches", 0) < MAX_WATCHES
                and not watched):  # a watch still going isn't one (QA-10)  # fmt: skip
            return _record(db, job, run, UNWATCHED)  # the Director: it watches what it delivers
        named = {int(n) for n in NOTE.findall(move_words(decision))}  # its note answers "Note N"
        given = max((t.input.get(READ, 0) for t in turns(db, project)
                     if t.input[RUN]["id"] == run["id"]), default=0)  # fmt: skip
        # a note no turn was given yet isn't its to answer: it waits for the next Make it
        if left := [n for n in range(1, given + 1)
                    if n not in answered(db, run["id"], project.id) | named]:  # fmt: skip
            return _record(db, job, run, OPEN.format(left[0]))
        from app import delivery

        why = decision.get("why") or "Delivered."
        job.output = {**decision, "note": delivery.note(db, project, job, decision)}
        asks.close_run(db, run["id"], "Delivered without it.")
        return _end(job, why, result=DELIVERED)  # a note it didn't read waits for Make it
    if tool == "stop":  # it can't go on (a story choice, a step that keeps refusing): says why
        return _end(job, decision.get("why") or "It stopped.", result="Stopped.")
    if outside := _outside(db, project, run, decision):
        return _record(db, job, run, outside)
    if tool == "make_take" and decision.get("clip_id"):
        clip = decision["clip_id"]
        if _redos(db, project, run).get(clip, 0) >= MAX_REDOS and _has_take(db, project, clip):
            return _record(db, job, run, f"Refused: {clip} was made again {MAX_REDOS} times.")
        if _only_a_doubt(db, project, clip, decision.get("why") or "", run["id"]):
            return _record(db, job, run, DOUBT.format(clip))
    redo = tool == "make_take" and decision.get("clip_id") and _has_take(db, project, clip)
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
    if tool == "make_looks" and (no := told_look.held(db, project, run, decision)):
        if no.startswith(told_look.WAITING):  # asked about them: it sleeps until answered
            return _record(db, job, run, no)
        return _end(job, f"It stopped: {no}", result=f"Refused again: {no}")
    if (refused := _refused_again(db, job, decision)) is not None:
        if tool == "make_looks" and (card := told_look.again(db, project, run, decision, refused)):
            return _record(db, job, run, card)  # its one retry: the owner's card, not a stop
        return _end(job, f"It stopped: {refused}", result=f"Refused again: {refused}")
    replan = tool == "plan" and bool((decision.get("note") or "").strip())
    if replan and run.get("replans", 0) >= MAX_REPLANS:  # the watch's "Re-plan:", once a run
        return _record(db, job, run, f"Refused: it planned again {MAX_REPLANS} time this run.")
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
    counted, mark = _counts(run), _newest_id(db, project)
    if tool == "redraw_still":
        result = _redraw(db, user, project, decision, storage, run)
    else:
        result = director_tools.run(db, user, project, decision, storage, run)
    if tool == "locked_line" and _answered_at_once(db, project, run, job, result):
        return _end(job, result, result=DELIVERED)  # its card is the answer: no re-delivery
    if tool == "watch_cut" and not result.startswith("Refused"):
        run["watches"] = run.get("watches", 0) + 1
    if redo and not result.startswith(("Refused", "Fixing")):  # nothing made (video 271)
        run["redos"] = {**run["redos"], clip: run["redos"].get(clip, 0) + 1}
    if replan and not result.startswith("Refused"):
        run["replans"] = run.get("replans", 0) + 1
    _spent_on(db, project, run, counted, mark)
    _record(db, job, run, result)


def _redraw(db: Session, user: User, project: Project, decision: dict, storage,
            run: dict) -> str:  # fmt: skip
    """`redraw_still`: every still it names (`redraws`, or one `shot_id`) drawn again at once,
    each with its own note, in parallel (video 261: four redraws one turn after another took
    3 min). Twice a still a run; the talker's one still once a move."""
    from app.still_review import REDRAWS

    asked = decision.get("redraws") or [{"shot_id": decision.get("shot_id"),
                                         "note": decision.get("note")}]  # fmt: skip
    said, keys = [], set()
    for one in asked:
        move = {**decision, "redraws": None, "shot_id": one.get("shot_id"),
                "note": one.get("note") or ""}  # fmt: skip
        sid = _still_key(db, project, move)
        what = "the talker's still" if sid == TALKER else f"shot {sid}"
        if sid in keys:
            continue  # the talker's still, asked from two of their shots: once
        keys.add(sid)
        if run.get("redraws", {}).get(sid, 0) >= REDRAWS:
            said.append(f"Refused: {what} was drawn again {REDRAWS} times.")
        elif outside := _outside(db, project, run, move):
            said.append(outside)
        else:
            done = director_tools.run(db, user, project, move, storage, run)
            if not done.startswith("Refused"):
                run["redraws"] = {**run.get("redraws", {}), sid: run.get("redraws", {}).get(
                    sid, 0) + 1}  # fmt: skip
            said.append(done)
    made = [x for x in said if not x.startswith("Refused")]
    if not made:  # nothing drawn: one refusal, all its reasons
        return "Refused: " + " ".join(x.removeprefix("Refused: ") for x in said)
    return " ".join([*made, *(x for x in said if x not in made)])


COUNTERS = ("redos", "watches", "replans", "redraws", director_song.REMADE)  # used up a run
SPENDS = "spends"  # in a run: its counted moves' work, until it runs (`_refund`)


def _counts(run: dict) -> dict[str, int]:
    """The run's counted work, flat: {"redos/c3": 1, "watches": 2}."""
    out = {}
    for k in COUNTERS:
        v = run.get(k)
        out.update({f"{k}/{i}": n for i, n in v.items()} if isinstance(v, dict) else
                   {k: v} if v else {})  # fmt: skip
    return out


def _newest_id(db: Session, project: Project) -> int:
    return db.scalar(select(func.coalesce(func.max(Job.id), 0)).where(
        Job.project_id == project.id)) or 0  # fmt: skip


def _spent_on(db: Session, project: Project, run: dict, before: dict, mark: int) -> None:
    """A move that used some of the run's counts keeps the jobs it made beside them, so that
    work which never runs is given back (`_refund`)."""
    now = _counts(run)
    used = {k: n - before.get(k, 0) for k, n in now.items() if n > before.get(k, 0)}
    if not used:
        return
    step = Job.input["step"].as_string()
    made = db.scalars(
        select(Job.id).where(
            Job.project_id == project.id, Job.id > mark, or_(step.is_(None), step != STEP)
        )
    ).all()
    if run.get("watches", 0) > before.get("watches", 0):
        from app import watch_cut

        cut = watch_cut._cut(db, project)
        run[SPENDS] = [*run.get(SPENDS, []), {"used": {"watches": 1}, "cut": cut.id if cut else 0}]
        used.pop("watches")
    if used and made:
        run[SPENDS] = [*run.get(SPENDS, []), {"used": used, "jobs": list(made)}]


def _refund(db: Session, project: Project, run: dict) -> dict:
    """Refused or never-run work never counts as used (Reed, 8 Nov): a counted move (a redo, a
    redraw, a re-plan, a narration or song remade, a watch) whose work all failed or was
    cancelled (declined, withdrawn) gives its count back; once it ran, it's spent."""
    from app import watch_cut

    if not run.get(SPENDS):
        return run
    run, keep = {**run}, []
    for s in run[SPENDS]:
        if "cut" in s:  # a watch: its listen, then its look, as <video>.watch reads it
            w = watch_cut.state(db, project)
            ran = None if w.get("for_cut") == s["cut"] and w["state"] == "watching" else not (
                w.get("for_cut") == s["cut"] and w["state"] == "failed")  # fmt: skip
        else:
            ran = _ran(db, s["jobs"])
        if ran is None:
            keep.append(s)
        elif not ran:
            for key, n in s["used"].items():
                name, _, item = key.partition("/")
                if item:
                    run[name] = {**run[name], item: max(0, run[name].get(item, 0) - n)}
                else:
                    run[name] = max(0, run.get(name, 0) - n)
    run[SPENDS] = keep
    return run


def _ran(db: Session, ids: list[int]) -> bool | None:
    """Whether a move's work ran (QA on #1468): True once any of its jobs, or their automatic
    retries (`retry_of_id`), succeeded or was billed by its provider; None while one is still
    queued, running or held; False when every one failed or was cancelled, unbilled."""
    states, seen, todo = set(), set(), list(ids)
    while todo:
        if (i := todo.pop()) in seen or (job := db.get(Job, i)) is None:
            continue
        seen.add(i)
        billed = db.scalar(select(Usage.id).where(Usage.job_id == i, Usage.cost_usd > 0).limit(1))
        states.add(JobStatus.succeeded if billed else job.status)
        todo += db.scalars(select(Job.id).where(Job.retry_of_id == i)).all()
    if JobStatus.succeeded in states:
        return True
    return False if states <= {JobStatus.failed, JobStatus.cancelled} else None


TALKER = "talker"  # a run's redraws of the talker's one still, whichever of their shots asked


def _still_key(db: Session, project: Project, decision: dict) -> str:
    """What a redraw counts against: its shot's still, or for any of a talker's shots their one
    still, which makes a whole HeyGen take again each time (QA on #1457: twice a run in all)."""
    from app import talker

    sid = decision.get("shot_id") or ""
    return TALKER if sid and talker.shot(db, project, sid) else sid


def _answered_at_once(db: Session, project: Project, run: dict, job: Job, result: str) -> bool:
    """A run whose notes S3-14's cards answer (`locked_line`) ends there, delivered with the
    cut it had, only when all of it holds (QA on #1429, twice): every note of the run is
    answered by a card and asks nothing more; no other move of the run did anything; and the
    cut is as it was delivered: made, with no edit waiting, nothing being made. Otherwise the
    card stands and the run goes on (a pause to tighten, a free edit to cut in)."""
    from app import locked_line

    if result != locked_line.POSTED or not delivered(_earlier(db, project, run)):
        return False  # a video never delivered goes on to make it
    notes = [m for m in project.director_chat or [] if m.get("run") == run["id"]]
    words = {a.id: a.subject for a in db.scalars(select(Ask).where(
        Ask.project_id == project.id, Ask.kind == locked_line.KIND))}  # fmt: skip
    if not notes or not all(m.get("offer") in words and locked_line.only_words(
            m["text"], words[m["offer"]]) for m in notes):  # fmt: skip
        return False  # a note asks more than its words (or isn't answered by a card)
    quiet = ("wait", "locked_line", "ask")
    if any((t.output or {}).get("tool") not in quiet and t.id != job.id
           and not (t.input.get("result") or "Refused").startswith(("Refused", "Waiting"))
           for t in turns(db, project) if t.input[RUN]["id"] == run["id"]):  # fmt: skip
        return False  # another move of this run did something
    state = video_state(db, project)
    return (state["cut"] == "made" and not (state.get("timeline") or {}).get("changes")
            and not state["being_made"])  # fmt: skip


def _earlier(db: Session, project: Project, run: dict) -> list[Job]:
    """The turns of the runs before this one (has the video delivered before?)."""
    return [j for j in all_turns(db, project.id) if j.input[RUN]["id"] != run["id"]]


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
    said = word_splice._heard(db, take)[0]  # every word heard in the take, with its times
    spans += [f.mute for f in (heard.findings if heard else [])
              if f.kind in ("extra", "voiced") and f.mute
              and not _over_others(f.text, f.mute, said)]  # fmt: skip
    done = {tuple(s) for s in take_mute.spans(take)}
    out = []
    for s in spans:
        span = [round(float(s[0]), 2), round(float(s[1]), 2)]
        if tuple(span) not in done and span not in out:
            if not take_mute.lost_line(db, row, take, *span):  # never a line's only copy
                out.append(span)
    return out


QUOTED = re.compile(r"“([^”]+)”")


def _over_others(text: str, span: list[float], said: list[dict]) -> bool:
    """A words-check span that would also silence a word it doesn't name (a script word, the
    brand, a figure: QA on #1428): its finding quotes the words it's about, and any other
    word heard inside it keeps the span from being muted."""
    from app.take_words import _bare

    own = set(_bare(m[1]).split()) if (m := QUOTED.search(text or "")) else set()
    a, b = float(span[0]), float(span[1])
    return any(w["start"] < b - 0.02 and w["end"] > a + 0.02
               and not set(_bare(w["word"]).split()) <= own for w in said)  # fmt: skip


def _refused_again(db: Session, job: Job, decision: dict) -> str | None:
    """The same tool, as it was, right after it was refused, or after one other refused step
    in between (video 281: redraw_still and host, each refused pointing at the other), with
    nothing of the video being made or done since: the refusal (else None). Nothing changed,
    so it would be refused again; the run stops and says why. Asking to watch the same cut
    again never stops it: it's told to fix something or deliver (QA on #1145)."""
    project = db.get(Project, job.project_id)
    rows = [j for j in turns(db, project) if j.id < job.id]
    keys = ("tool", "clip_id", "take_id", "shot_id", "note", "edit", "redraws", "look")
    said = []
    for before in rows[-2:][::-1]:  # the last turn, then the one before it
        result = before.input.get("result") or ""
        if result == WATCHED_AGAIN or not result.startswith("Refused: "):
            return None  # something went between: not a loop
        said.append(result.removeprefix("Refused: "))
        if all((before.output or {}).get(k) == decision.get(k) for k in keys):
            if "being rewritten to fit" in result or _moved(db, project, before):
                return None  # (video 271: its take never followed the rewrite)
            return " Then: ".join(reversed(said))
    return None


def _moved(db: Session, project: Project, since: Job) -> bool:
    """Something of the video is being made, or was made or asked for, since `since` (a
    refused turn): a refusal that waited ("The host is being made") may go now (QA on #1457)."""
    if _waiting(db, project):
        return True
    step = Job.input["step"].as_string()
    return bool(db.scalar(select(Job.id).where(
        Job.project_id == project.id, or_(step.is_(None), step != STEP),
        or_(Job.id > since.id, Job.finished_at >= since.created_at)).limit(1)))  # fmt: skip


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
    if kept and not over(db, run["id"], job.project_id):
        wake(db, db.get(Project, job.project_id))


def _write(db: Session, job: Job, data: dict) -> bool:
    """A turn's input written only while its run hasn't ended, in one statement, so a Stop
    that lands meanwhile is never overwritten (QA-7); whether it was written."""
    done = db.execute(update(Job).where(Job.id == job.id,
                                        Job.input["ended"].as_string().is_(None))
                      .values(input=data).execution_options(synchronize_session=False))  # fmt: skip
    if done.rowcount == 1:
        live.note(db, job.project_id)  # its open page reads the turn's words at once
    return done.rowcount == 1


def _stopped(db: Session, job: Job) -> bool:
    """Whether the run ended (Stop) since `job` was read: a fresh read, so what the worker
    writes next keeps the stop instead of overwriting it with what it read before."""
    db.refresh(job)
    return bool(job.input.get("ended"))


def _end(job: Job, why: str, result: str = "") -> None:
    job.input = {**job.input, "ended": why, **({"result": result} if result else {})}


def _turn(db: Session, user: User, project: Project, run: dict, *,
          extra: dict | None = None, carry: tuple[str, Decimal] | None = None,
          after: int | None = None) -> Job:  # fmt: skip
    from app.routes.jobs import enqueue

    last = next(reversed(turns(db, project)), None)
    if last is not None and (gave_up := _failed_too_often(db, project, run)):
        made = video_state(db, project)["cut"] == "made"  # what it has: a cut, or nothing
        last = db.get(Job, last.id)
        _end(last, f"{gave_up}; delivered without it." if made else f"It stopped: {gave_up}.",
             result=DELIVERED if made else "")  # fmt: skip
        db.commit()
        return last
    most = own_usd(db, run, project.id)
    if run["turn"] >= MAX_TURNS or spent(db, run["id"], project.id) >= most:
        why = (f"It stopped after {MAX_TURNS} turns." if run["turn"] >= MAX_TURNS
               else f"It stopped at ${most} of its own time.")  # fmt: skip
        if last is not None:
            _end(last, why)
            db.commit()
        return last
    before = not run.get("ok", True)  # before Make it: planning, on its allowance
    card = (before and last is not None and last.input[RUN]["id"] == run["id"]
            and _ready(db, project, run, last))  # its own turn moved it there  # fmt: skip
    run = _refund(db, project, {**run, "turn": run["turn"] + 1, **({"ok": True} if card else {})})
    seen: dict = {}
    prompt = turn_input(db, project, run, seen=seen)
    prompt.pop(READ)  # a note counts as given only once its turn starts (`refresh`)
    free = before and _free_revision(db, run, project.id)  # a revision's free cut changes
    if (not (card or carry) and (not before or _planning(run) or free) and last is not None
            and last.input[RUN]["id"] == run["id"]
            and (step := _auto(db, project, run, {**seen, "started": True}, last))):  # fmt: skip
        if not before or step["tool"] in (REVISE_FREE if free else PLANNING):  # the plan, say
            return _by_server(db, user, project, run, step, after)
        if not free and not _unlooked(db, project, run):  # the plan done, every look drawn: the
            card, run = True, {**run, "ok": True}  # direction card, with no call to reach it
    data = {"step": STEP, RUN: run, **prompt, **(extra or {})}
    wait = ""
    if card:  # the start card: its first generating turn, held for Make it (S3-02)
        hold = run.get("hold") or ""
        data = {**data, **_carried(db, project, run), START: True, asks.HOLD: hold}
        wait = hold or START_HELD
    elif carry:  # carrying on after the owner's Stop: their OK first, for the rest of its price
        from app.routes.jobs import PRICE

        price = asks.approved_run(db, project)[0]  # its own, with its OKs at its own limit
        data = {**data, START: True, asks.HOLD: carry[0], PRICE: str(carry[1]),
                CARRIES: str(price)}  # fmt: skip
        wait = carry[0]
    elif before and not (_free_revision(db, run, project.id) or _own_plan(db, run, project, seen)):
        # its plan: charged as it costs; past the allowance, the owner's OK first. A
        # revision's free changes to its cut aren't planning: its turns are the director's
        # own, on its own limit, below
        from app.credits import estimate

        turn = estimate(db, project.workspace_id, "write-claude", Decimal(1), data)
        data = {**data, asks.BEFORE: True}
        if not uncapped(user) and asks.past_planning(db, project, turn, plan=False):
            data, wait = {**data, asks.PLAN_OK: True}, asks.PLANNING
    else:  # past its own limit, or a freestyle's price, the run pauses for an OK
        from app.credits import estimate, past_approved

        turn = estimate(db, project.workspace_id, "write-claude", Decimal(1), data)
        wait = past_own(db, project, run["id"], turn, user)
        data = {**data, GRANT: True} if wait else data  # an OK here grants another limit
        wait = wait or past_approved(db, project, user, turn)
    if (newer := _taken(db, project, run, after)) is not None:
        return newer
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
        db.refresh(fs)  # its chat as it is now: a change may have landed since it was read
        mine = {t.id for t in turns(db, project) if t.input[RUN]["id"] == run["id"]}
        fs.chat = [{**m, "job": job.id} if m.get("job") in mine - {job.id} else m
                   for m in fs.chat]  # fmt: skip
        db.commit()
    return job


def _taken(db: Session, project: Project, run: dict, after: int | None) -> Job | None:
    """Woken (`after`): under the video's lock, the turn another waker got in first, if any;
    a second waker waits on the lock, then sees the first's turn."""
    if after is None:
        return None
    lock(db, Project, project.id)
    return db.scalar(select(Job).where(Job.project_id == project.id,
                                       Job.input["step"].as_string() == STEP,
                                       Job.input[RUN]["id"].as_string() == run["id"],
                                       Job.id > after).limit(1))  # fmt: skip


def _auto(db: Session, project: Project, run: dict, seen: dict, last: Job) -> dict | None:
    """The server's own next step (`director_auto`), when it's mechanical: never right after
    a refusal (the director reads it), and a take or a cut only with the worker's storage."""
    from app import director_auto

    if (last.input.get("result") or "").startswith("Refused"):
        return None
    at = (last.started_at or last.created_at).isoformat()
    questions = bool(asks.waiting(db, project)) or asks.answered_since(db, project, at)
    reviews = db.scalar(select(func.count(Job.id)).where(
        Job.project_id == project.id, Job.input["step"].as_string() == "review_stills",
        Job.input[RUN]["id"].as_string() == run["id"],
        Job.status == JobStatus.succeeded))  # fmt: skip
    cut = db.scalar(select(FinalVideo).where(FinalVideo.project_id == project.id)
                    .order_by(FinalVideo.id.desc()).limit(1))  # fmt: skip
    step = director_auto.move({**seen, "questions": questions, "tried": _tried(db, project, run),
                               "reviews": reviews, "fixed": _fixed(db, project, run),
                               "in_cut": (cut.take_ids or []) if cut else []})  # fmt: skip
    if step and step["tool"] in ("make_take", "final_cut") and STORE.get() is None:
        return None
    if step and step["tool"] == "ask_cast_ok" and any(
            i["look_fit"] for i in cast_gate.current(db, project)):  # fmt: skip
        return None  # the look check says one is wrong: the director's to change or keep
    if step and last.input.get(director_auto.SAID) and (last.output or {}).get("tool") == step[
            "tool"]:  # fmt: skip
        return None  # its own step again (a clip prompt's part that failed): the director's
    if step and any(t.input[RUN]["id"] == run["id"] and t.input.get(director_auto.SAID)
                    and (t.output or {}).get("tool") == step["tool"]
                    and (t.input.get("result") or "").startswith("Refused")
                    for t in turns(db, project)):  # fmt: skip
        return None  # refused before (video 299's first takes, four times): the director's
    if step and step["tool"] == "make_take" and run.get(PRICED):
        return None  # a priced run makes only its own clips' takes, named by the director
    return step


FIXES = ("make_take", "pick_take", "mute", "unmute", "splice_word")  # a fix on its clip_id


def _fixed(db: Session, project: Project, run: dict) -> bool:
    """Each fault this run's newest watch of the cut found (not a keep or a doubt) has had its
    own move on its clip since, not refused: the cut may be made again with no turn to say so.
    A split alone isn't a fix (its trim comes next). True with no watch of this run: a
    revision's changes are its notes', answered by the director."""
    from collections import Counter

    from app import watch_cut

    job = watch_cut._newest(db, project)
    if job is None or (job.input.get(RUN) or {}).get("id") != run["id"]:
        return True
    done: Counter = Counter()
    for t in turns(db, project):
        said, d = t.input.get("result") or "", t.output or {}
        if (t.id < job.id or t.input[RUN]["id"] != run["id"] or said == START_FIRST
                or said.startswith("Refused")):  # fmt: skip
            continue
        edit = d.get("edit") or {} if d.get("tool") == "edit_cut" else {}
        if edit and edit.get("kind") != "split":
            done.update([None, (edit.get("piece") or "").partition(".")[0]])
        elif d.get("tool") in FIXES:
            done.update([d.get("clip_id")])
    found = Counter(f.get("clip_id") for f in (job.output or {}).get("checked") or []
                    if f.get("fix") != "keep" and not f.get("doubt"))  # fmt: skip
    return all(done[c] >= n for c, n in found.items())


def _tried(db: Session, project: Project, run: dict) -> bool:
    """A still or a take of this run failed (trying again or going on without it is the
    director's call)."""
    first = next((t for t in turns(db, project) if t.input[RUN]["id"] == run["id"]), None)
    return bool(first) and any(
        j.input.get("frame_id") or j.input.get("project_clip_id")
        for j in db.scalars(select(Job).where(Job.project_id == project.id,
                                              Job.status == JobStatus.failed,
                                              Job.created_at >= first.created_at))
    )  # fmt: skip


def _by_server(db: Session, user: User, project: Project, run: dict, step: dict,
               after: int | None) -> Job:  # fmt: skip
    """A mechanical step the server takes itself: logged as the run's turn (no Claude call,
    nothing charged for it) and acted on as the director's own move."""
    from app import director_auto

    if (newer := _taken(db, project, run, after)) is not None:
        return newer
    now = utcnow()
    job = Job(workspace_id=project.workspace_id, created_by_id=user.id, kind="director_step",
              provider="server", input={"step": STEP, RUN: run, director_auto.SAID: True},
              output=step, project_id=project.id, brand_id=project.brand_id, credits=0,
              status=JobStatus.succeeded, started_at=now, finished_at=now)  # fmt: skip
    db.add(job)
    db.commit()
    if _stopped(db, job) or over(db, run["id"], project.id):  # Stop landed meanwhile
        return job
    _act(db, job, STORE.get())
    return job


def _own_story(db: Session, run: dict, project_id: int | None):
    """When this run itself last wrote a treatment, or None."""
    return db.scalar(select(func.max(Job.created_at)).where(
        Job.project_id == project_id, Job.input["step"].as_string() == "treatment",
        Job.input[RUN]["id"].as_string() == run["id"],
        Job.status == JobStatus.succeeded))  # fmt: skip


def _free_revision(db: Session, run: dict, project_id: int | None) -> bool:
    """A revision's free changes to the cut it has: none once its own story changed, or when
    the run is held for the owner's OK (an editor past their budget: the start card first)."""
    return bool(run.get(REVISION) and not run.get("hold")
                and not _own_story(db, run, project_id))  # fmt: skip


def _written(db: Session, run: dict, project_id: int | None) -> bool:
    """Whether the run's treatment is written (the start card waits for it)."""
    return bool(_treatment_at(db, run, project_id))


def _treatment_at(db: Session, run: dict, project_id: int | None):
    """When the run's newest written treatment was asked (what it read was as of then); a
    revision's (`REVISION`) is the video's own when the run wrote none: its story stands."""
    own = _own_story(db, run, project_id)
    if own or not run.get(REVISION) or project_id is None:
        return own
    return db.scalar(select(func.max(Job.created_at)).where(
        Job.project_id == project_id, Job.input["step"].as_string() == "treatment",
        Job.status == JobStatus.succeeded))  # fmt: skip


def _ready(db: Session, project: Project, run: dict, last: Job) -> bool:
    """Before Make it, the start card (the direction card) comes once the director moved
    past what may run before it (a still, a take, or nothing left to plan), or asked for the
    cast and places OK; on a run held for the owner, once the treatment is written and every
    note sent before Make it was read into it; or when the owner kept the plan as it is on a
    planning card past its allowance."""
    from app.routes.jobs import DECLINE

    at = _treatment_at(db, run, project.id)
    if at is None:
        return False
    said = last.input.get("result") or ""
    if said == START_FIRST or said.startswith(cast_gate.ASKED):
        return True
    kept = db.scalar(select(func.max(Job.finished_at)).where(
        Job.project_id == project.id, Job.input[RUN]["id"].as_string() == run["id"],
        Job.input[asks.PLAN_OK].as_boolean(),
        Job.input[DECLINE].as_boolean()))  # fmt: skip
    notes = [m["at"] for m in project.director_chat or [] if m.get("run") == run["id"]]
    if kept and (not notes or max(notes) <= kept.isoformat()):
        return True
    if _planning(run):  # it plans on, up to the cast and places OK
        return False
    if not notes:
        return True
    # every note was given to a turn (run 287: a brief sent while the first turn was being
    # answered was never read, and the card showed the plan from before it), and a treatment
    # asked since that turn is written: one that reads a note and changes nothing (a wait, a
    # question) gets its card too
    if not _own_story(db, run, project.id):  # a revision's story stands: its free changes,
        return False  # or Make it once it moves past them (START_FIRST)
    mine = [t for t in turns(db, project) if t.input[RUN]["id"] == run["id"]]
    reader = next((t for t in mine if t.input.get(READ, 0) >= len(notes)), None)
    if reader is None:
        return False
    newest = db.scalar(select(Job).where(
        Job.project_id == project.id, Job.input["step"].as_string() == "treatment",
        Job.input[RUN]["id"].as_string() == run["id"],
    ).order_by(Job.id.desc()).limit(1))  # fmt: skip
    return (newest is None or newest.status == JobStatus.succeeded
            or newest.id < reader.id and newest.status not in WAITING)  # fmt: skip


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
    db.refresh(project)  # its notes as they are now (a note may have landed since it was read)
    db.refresh(job)
    if job.input.get(CARRIES) and not job.input.get("ended"):  # a Carry on the owner OK'd:
        lock(db, Project, project.id)  # the stopped run goes on from here
        resume(db, project, job.input[RUN]["id"])
        db.commit()
        db.refresh(job)
    if job.input.get("ended") or over(db, job.input[RUN]["id"], job.project_id):
        return False
    seen: dict = {}
    asked = turn_input(db, project, job.input[RUN], job.id, seen=seen)  # as this turn starts
    db.refresh(job)  # Stop may land while the prompt is built: checked as it's written
    kept = _write(db, job, {**job.input, **asked})
    db.commit()
    db.refresh(job)
    if kept and not over(db, job.input[RUN]["id"], job.project_id) and _go_step(db, job, seen):
        return False  # the server took the step after Make it: no call
    return kept and not over(db, job.input[RUN]["id"], job.project_id)  # the last check


def _go_step(db: Session, job: Job, seen: dict) -> bool:
    """Make it on the direction card: when the step after it needs no judgment (the
    storyboard, say), or is the director's own move that waited for it, the server takes it
    as this turn, as `_by_server` does: no Claude call, nothing charged for it."""
    from app import director_auto

    project, run = db.get(Project, job.project_id), job.input[RUN]
    if not job.input.get(START) or job.input.get(CARRIES):
        return False
    # read as of this turn's own start: the Make it just pressed is no question answered
    if not (step := _auto(db, project, run, seen, job) or _held(db, project, run, job, seen)):
        return False
    job.kind, job.provider, job.credits, job.output = "director_step", "server", 0, step
    job.input = {**job.input, director_auto.SAID: True}
    job.status, job.finished_at = JobStatus.succeeded, utcnow()
    db.commit()
    _act(db, job, STORE.get())
    db.commit()
    return True


def _held(db: Session, project: Project, run: dict, job: Job, seen: dict) -> dict | None:
    """The director's move that waited for Make it ("Waiting for Make it"), made as it asked
    once Make it is pressed (video 294's revision paid a turn to ask for the same plan again);
    None when a note came since or a question waits: the director reads it first."""
    last = next((t for t in reversed(turns(db, project))
                 if t.id < job.id and t.input[RUN]["id"] == run["id"]), None)  # fmt: skip
    if (last is None or last.input.get("result") != START_FIRST or asks.waiting(db, project)
            or any(m.get("new") for m in seen.get("chat") or [])):  # fmt: skip
        return None
    return dict(last.output or {})


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
    if not rows or delivered(rows):
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


def _listed(result: str | None) -> str | None:
    """A move's result as <last_actions> shows it: one held for Make it is still to make."""
    return NOT_MADE if result == START_FIRST else result


def turn_input(db: Session, project: Project, run: dict, job_id: int | None = None,
               seen: dict | None = None) -> dict:  # fmt: skip
    """The director's prompt (app/prompts/director.md, the Director's) and the brand, then the
    video's state, its run's last actions and what it still may do; `seen` gets what it read
    (<video> with its chat, allowed and actions), for the server's own steps (`_auto`). Its
    turns are read once (`reading`), not once a helper."""
    with reading(db):
        return _turn_input(db, project, run, job_id, seen if seen is not None else {})


def _turn_input(db: Session, project: Project, run: dict, job_id: int | None,
                seen: dict) -> dict:  # fmt: skip
    from app.enhance import project_context

    system, brief = project_context(db, project, STEP)
    done = [{"tool": (j.output or {}).get("tool"), "why": (j.output or {}).get("why"),
             "result": RETRIED_SAID if j.input.get(RETRIED) else _listed(j.input.get("result"))}
            for j in turns(db, project)
            if j.input[RUN]["id"] == run["id"] and j.id != job_id]  # the whole run  # fmt: skip
    allowed = {"turns_left": MAX_TURNS - run["turn"], "redos_per_clip": MAX_REDOS,
               "watches_left": MAX_WATCHES - run.get("watches", 0),
               "redos_used": _redos(db, project, run),
               "own_time_usd": float(spent(db, run["id"], project.id)),
               "own_time_limit_usd": _limit_usd(own_usd(db, run, project.id)),
               "replans_left": MAX_REPLANS - run.get("replans", 0),
               "songs_left": director_song.REMAKES - run.get(director_song.REMADE, 0),
               "narrations_left": director_song.REMAKES - run.get(director_song.REMADE, 0),
               "redraws_per_still": 2, "redraws_used": run.get("redraws", {})}  # fmt: skip
    given = max((t.input.get(READ, 0) for t in turns(db, project)
                 if t.input[RUN]["id"] == run["id"] and t.id != job_id), default=0)  # fmt: skip
    closed, read = answered(db, run["id"], project.id), in_treatment(db, run["id"], project.id)
    asked = [{"note": n + 1, **m, "new": n >= given, "answered": n + 1 in closed,
              **({"in_treatment": True} if n + 1 in read else {})}
             for n, m in enumerate(chat(project, run["id"]))]  # fmt: skip
    # new: no earlier turn was given it. answered: a move named it ("Note N"), or the treatment
    # read it as it was written (in_treatment); else still open
    own = db.scalar(select(Job.id).where(Job.project_id == project.id,
                                         Job.input["step"].as_string() == "treatment",
                                         Job.input[RUN]["id"].as_string() == run["id"],
                                         Job.status.in_(COUNTED)).limit(1))  # fmt: skip
    if not own and run.get(REVISION):  # a revision reuses the video's story (its treatment)
        own = _treatment_at(db, run, project.id)
    video = {
        **video_state(db, project),
        "treatment": "written" if own else "none",
        "started": run.get("ok", True),
        "revision": bool(run.get(REVISION)),
    }  # this run's; started: Make it was pressed; revision: after a delivery
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
    seen.update(video, chat=asked, allowed=allowed, done=done)
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
    return "\n".join(parts) + "\n" + treatment_block(db, project, notes=False)


def treatment(db: Session, project: Project) -> dict | None:
    """The video's newest treatment (the Director's step: hook, logline, why it holds, beats,
    ending, voices), or None; its voices are the words set for the video (`voices.as_set`)."""
    from app import voices

    job = db.scalar(select(Job).where(Job.project_id == project.id,
                                      Job.input["step"].as_string() == "treatment",
                                      Job.status == JobStatus.succeeded)
                    .order_by(Job.id.desc()).limit(1))  # fmt: skip
    return voices.as_set(db, project, job.output or None) if job else None


def write_treatment(db: Session, user: User, project: Project, run: dict | None, note: str = "",
                    redo: bool = False, kept: str | None = None) -> str:  # fmt: skip
    """Queue the treatment (the Director's step: hook, logline, why it holds, beats, ending),
    on the director's own limit like a watch; its words in plain lines."""
    from app import omni_talker, plans, prompts
    from app.credits import estimate, past_approved
    from app.enhance import project_context
    from app.routes.jobs import enqueue

    version = plans.script(db, project)
    system, context = project_context(db, project, "treatment")  # its look's skill and craft
    text = f"{context}\n{prompts.treatment_input(version.text, note)}"
    if omni_talker.on(db, project):  # the presenter speaks on camera: `voices` names them
        text += f"\n{omni_talker.treatment_block(db, project)}"
    said = note.strip() if kept is None else kept  # the person's own note, for a check's redo
    data = {"step": "treatment", "project_id": project.id, RUN: run, "system": system,
            "prompt": text, "max_tokens": 6000, **({"redo": True} if redo else {}),
            **({"note": said} if said else {})}  # fmt: skip
    from app import footage

    data = footage.with_frames(db, project, data)  # how the brand's product really works
    again = treatment(db, project) is not None
    before = not (run or {}).get("ok", True)  # before Make it: on the planning allowance
    price = estimate(db, project.workspace_id, "write-claude", Decimal(1), data)
    if before:  # a check's own fix of the plan always runs: it's the same plan, counted
        data, wait = {**data, asks.BEFORE: True}, ""
        if not redo and not uncapped(user) and asks.past_planning(db, project, price, plan=True):
            data, wait = {**data, asks.PLAN_OK: True}, asks.PLANNING
    else:
        wait = past_own(db, project, (run or {}).get("id"), price, user)
        data = {**data, GRANT: True} if wait else data  # an OK here grants another limit
        wait = wait or past_approved(db, project, user, price)
    enqueue(db, user, "write-claude", data, project=project, provider="claude",
            prepaid=not wait, wait=wait)  # fmt: skip
    return "Changing the treatment." if again else "Writing the treatment."


NOTES_READ = "notes_read"  # in a treatment's input: the run's notes it read as it started


def read_notes(db: Session, job: Job) -> None:
    """Before Make it, a treatment about to be written reads the run's notes nothing read yet
    (a brief sent while the turn that asked for it was being answered: videos 293 and 315 paid
    for a second treatment and turn for it). It answers them (the director still reads them,
    marked `in_treatment`); a check's redo keeps them in its note. A revision's or a started
    run's notes may ask for more than the story: those stay the director's."""
    from html import escape

    run = job.input.get(RUN) or {}
    if job.input.get("redo") or not run.get("id") or run.get("ok", True) or run.get(REVISION):
        return
    project = db.get(Project, job.project_id)
    db.refresh(project)
    read = [t.input.get(READ, 0) for t in turns(db, project) if t.input[RUN]["id"] == run["id"]]
    read += [max(j.input.get(NOTES_READ) or [0]) for j in db.scalars(select(Job).where(
        Job.project_id == project.id, Job.input["step"].as_string() == "treatment",
        Job.input[RUN]["id"].as_string() == run["id"], Job.id != job.id))]  # fmt: skip
    given = max(read, default=0)
    if not (notes := chat(project, run["id"])[given:]):
        return
    said = "\n".join(f"Note {n}: {m['text']}" for n, m in enumerate(notes, given + 1))
    job.input = {**job.input, "prompt": f"{job.input['prompt']}\n<note>{escape(said)}</note>",
                 "note": "\n".join(x for x in (job.input.get("note"), said) if x),
                 NOTES_READ: list(range(given + 1, given + len(notes) + 1))}  # fmt: skip
    db.commit()


def _shown(db: Session, project: Project):
    """A treatment as its card draws it (board S3-02): its style and format named, and each
    beat's time in the video, from the words of the lines it covers (spoken at 4.8 words a
    second, as a script's length is guessed before any plan)."""
    from app import guides, ideas, narration, plans
    from app.script_library import WORDS_PER_SECOND, format_id

    version, script = plans.script(db, project), narration.video_script(db, project)
    lines = (version.text if version else "").splitlines()
    try:
        kind = guides.format_(format_id(script))["name"] if script else ""
    except ValueError:  # a format since taken out of the guides
        kind = ""
    heading = re.compile(r"^\s*(SCENE\b|INT\.|EXT\.)", re.I)

    def words(n: int) -> int:
        line = lines[n - 1] if 0 < n <= len(lines) else ""
        if heading.match(line):
            return 0
        said = re.match(r"^[A-Z][A-Z .'()-]*:(.*)$", line.strip())
        return len((said.group(1) if said else line).split())

    def shown(made: dict) -> dict:
        beats, at = [], 0
        for b in made.get("beats") or []:
            end = at + max(1, round(sum(words(n) for n in b.get("lines") or []) / WORDS_PER_SECOND))
            beats.append({**b, "start": at, "end": end})
            at = end
        return {**made, "beats": beats, "style": ideas._style(project.look), "format": kind}

    return shown


def told(made: dict, again: bool) -> str:
    """A treatment as plain lines in the thread (the Director: the delivery note's style)."""
    beats = " ".join(f"{b.get('id', '')}: {b.get('purpose', '')}, {b.get('picture', '')}."
                     for b in made.get("beats") or [])  # fmt: skip
    head = "Changed the treatment:" if again else "The treatment:"
    still = " ".join(made.get("problems") or [])
    return (f"{head} {made.get('logline', '')} Hook: {made.get('hook', '')} {beats} "
            f"Ending: {made.get('ending', '')}" + (f" Still to fix: {still}" if still else "")
            ).strip()  # fmt: skip


def treatment_block(db: Session, project: Project, notes: bool = True) -> str:
    """<treatment> for a step's user message (plan, breakdown, clip prompts, the watch, the
    director), or "" before one is made (the Director's prompts.treatment_block); then the
    run's notes from people (<notes>), so the steps that write the pictures never stage what
    a note takes away (226: "no phone", and clip 4's prompt still asked for the phone). The
    director reads them in its own <chat> (`notes` False)."""
    from app import prompts

    told = prompts.treatment_block(treatment(db, project))
    asked = run_notes(db, project) if notes else []
    said = "\n".join(f"Note {n}: {text}" for n, text in asked)
    return (f"{told}\n" if told else "") + (f"<notes>\n{said}\n</notes>\n" if said else "")


def run_notes(db: Session, project: Project) -> list[tuple[int, str]]:
    """The going run's notes from people, numbered as the director reads them ("Note 1")."""
    going = active(db, project)
    return list(enumerate((m["text"] for m in chat(project, going.input[RUN]["id"])), 1)) if (
        going) else []  # fmt: skip


def against_notes(row: ProjectClip, notes: list[tuple[int, str]]) -> dict:
    """The run's notes that take away something this clip's prompt still shows ("no phone"
    and a phone in the prompt), for the director to check before its take: {} with none."""
    from app.clip_takes import contradicts

    said = [f"Note {n}" for n, text in notes if contradicts(row.prompt, text)]
    return {"against_notes": said} if said else {}


def old_take(row: ProjectClip) -> dict:
    """Why the clip's picked take holds the cut out of date however often it's made again (its
    take shows an older sheet, still or prompt: `clip_prompts.take_stale`), or {}."""
    from app.clip_prompts import OLDER_PROMPT, OLDER_STILL, OLDER_TAKE, take_stale

    if not take_stale(row):
        return {}
    why = next(p for p in row.problems or [] if p.startswith((OLDER_TAKE, OLDER_STILL,
                                                              OLDER_PROMPT)))  # fmt: skip
    return {"old_take": why.removeprefix("Advice: ")}


def cut_findings(db: Session, project: Project) -> dict[int, list[str]]:
    """What the watches of this video's cuts found on each take, by take id (each finding is
    about the take its clip played in that cut): picking a take back brings these back (233:
    clip 2's take 2 came back with the wordless frown its redo was paid to remove)."""
    from app import watch_cut

    out: dict[int, list[str]] = {}
    rows = db.scalars(
        select(Job)
        .where(
            Job.project_id == project.id,
            Job.input["step"].as_string() == watch_cut.STEP,
            Job.status == JobStatus.succeeded,
        )
        .order_by(Job.id)
    )
    for job in rows:  # fmt: skip
        played = {c["clip_id"]: c.get("take_id") for c in job.input.get("cut") or []}
        for f in (job.output or {}).get("checked") or []:
            if (take := played.get(f.get("clip_id"))) and (says := f.get("says")):
                out.setdefault(take, [])
                out[take] += [] if says in out[take] else [says]
    return out


def _audio_key(db: Session, project: Project) -> str:
    return "song" if director_song.kind(db, project) == "song" else "narration"


def video_state(db: Session, project: Project) -> dict:
    """Where the video is, as the director reads it (and `choose` on the stand-ins)."""
    from app.clip_prompts import newest
    from app.clip_takes import take_credits
    from app.item_checks import latest, shown, verdict
    from app.routes.project_clips import out_of_date

    bd = newest(db, project)
    frames = [f for f in db.scalars(select(StoryboardFrame).where(
        StoryboardFrame.project_id == project.id)) if bd and f.breakdown_id == bd.id]  # fmt: skip
    data = bd.data if bd else {}  # what each clip shows and says (the Director: not only verdicts)
    shots = {x["id"]: x for sc in data.get("scenes", []) for x in sc.get("shots", [])}
    ids_of = {c["id"]: c["shot_ids"] for c in data.get("clips", [])}
    from app import footage, model_map, talker

    clips, said = [], talker.clips(db, project)  # a talker's clips come from its take, at the cut
    reals = footage.uses(data)  # the brand's real footage clips (UGC B-roll)
    cut_seen, notes_now = cut_findings(db, project), run_notes(db, project)
    for row in db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)
                          .order_by(ProjectClip.id)):  # fmt: skip
        takes = db.scalars(select(ClipTake).where(ClipTake.clip_id == row.id)
                           .order_by(ClipTake.number)).all()  # fmt: skip
        ids = [t.id for t in takes]
        seen, heard = latest(db, "take", ids), latest(db, "words", ids)
        out = []
        for t in takes:
            look = shown(db, seen.get(t.id))
            checks = [look, words := shown(db, heard.get(t.id))]
            notes = [f.note for f in look.findings if f.verified] if look else []
            extra = [f.text for f in words.findings if f.kind in ("extra", "voiced")] if (
                words) else []  # fmt: skip  # 245's "Come on.": mute it or pick another take
            watched = {k: (t.watch or {}).get(k) for k in ("found", "did", "action")}
            mark = verdict(checks)  # a transcript's finding alone is a doubt, as an unsure watch:
            doubt = watched["action"] == "unsure" or (mark == "flagged" and not notes)
            real = footage.is_footage(t)  # the brand's real clip: never watched or remade
            out.append({"id": t.id, "number": t.number,  # the owner's, never a paid redo
                        "verdict": "clean" if real else "unsure" if doubt else mark,
                        "notes": [] if doubt else notes, "watch": watched,
                        **({"cut_watch": cut_seen[t.id]} if t.id in cut_seen else {}),
                        **({"unscripted": extra} if extra else {}),
                        "set_aside": False})  # Start the plan again: `set_aside`  # fmt: skip
        clips.append({"clip_id": row.clip_id, "stale": bool(bd and row.breakdown_id != bd.id),
                      **old_take(row), **against_notes(row, notes_now),
                      "shots": [{"id": i, "action": shots[i].get("action", ""),
                                 "line": shots[i].get("line")}
                                for i in ids_of.get(row.clip_id, []) if i in shots],
                      "picked_take_id": row.picked_take_id, "takes": out,
                      "redo_credits": float(take_credits(db, project, row)),  # its "up to"
                      "muted": take_mute.spans(picked := db.get(ClipTake, row.picked_take_id)
                                               if row.picked_take_id else None),
                      "sound": {k: v for k, v in (take_sound.state(db, picked) or {}).items()
                                if k in ("state", "how")},
                      **({"own_sound": True} if take_sound.own(db, picked) else {}),
                      **word_splice.state(db, row),  # splice_word
                      **model_map.state(db, project, row),  # clip_model
                      **({"footage": reals[row.clip_id]["id"]} if row.clip_id in reals else {}),
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
        Job.finished_at >= acted[-1].created_at,
        Job.kind != talker_sound.STEP)) if acted else []  # a voice's falls back  # fmt: skip
    from app.breakdown import extras as breakdown_extras
    from app.cut import making as cut_making
    from app.plans import status

    cast = _cast_ok(db, project) if bd else {"state": "none"}
    watch = _watch(db, project)
    for c in clips:  # A6: a redo it would be refused says so before a paid turn (301, 294)
        if c["takes"] and not _confirmed(db, project, c, watch):
            c["redo"] = REDO_NEEDS
    held = set(cast.get("paused_clips") or [])
    for c in clips:
        c["waits_for_cast"] = c["clip_id"] in held and not c["takes"]
    audio = director_song.state(db, project)  # a song or narrated video's song or narration
    from app import host

    hosted = {"host": host.state(db, project)} if host.on(db, project) else {}
    return {
        **hosted,
        "plan": status(db, project),  # none, ready (waits for approval) or approved
        **({_audio_key(db, project): audio} if audio else {}),  # the clock its shots follow
        # choices fixed for it (director-chat.md §1), kept as is; a person's own look pick isn't
        "locked": {k: v for k, v in (project.locks or {}).items() if k != "look_picked"},
        "outfits": project.outfits or {},  # this video's outfit per character ("char:12")
        "shots": "ready" if bd else "none",
        "too_long": _splittable(db, project, bd),  # split_clip
        "missing_looks": director_tools.missing_looks(db, project) if bd else [],
        # someone the shots show who isn't a role (an extra: "Crowd"), yours to cast or leave
        "no_role": breakdown_extras(bd.problems) if bd else [],
        "cast_ok": cast,  # the person's OK on the cast and places, and what waits for it
        "stills": {"frames": len(frames), "drawn": sum(1 for f in frames if f.file_id),
                   "waiting": sum(1 for f in frames if not f.file_id and f.clip_id in held)},
        "clips": clips,
        # a cut being made reads as such, never "out of date" (226 made it again: A6)
        "cut": "being made" if cut_making(db, project) else "none" if not video else
               ("out of date" if project.id in out_of_date(db, [project]) else "made"),
        "being_made": len([j for j in waiting if j.status != JobStatus.needs_owner_approval]),
        "held_for_owner": [j.input.get("held", "") for j in waiting
                           if j.status == JobStatus.needs_owner_approval],
        "failed_since_last_turn": [j.error or "It didn't finish." for j in failed],
        "timeline": cut_edits.for_director(db, project),  # the cut's pieces, for edit_cut
        "cut_failed": _cut_failed(db, project),  # the newest cut couldn't be made: why, fixes
        "watch": watch,  # its last watch of the cut, and its findings (doubts say so)
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


STORY = re.compile(r"\b(story|plot|rewrite|new (?:scene|idea|angle|hook|ending)|different "
                   r"(?:hook|ending)|change (?:the )?(?:hook|ending))\b", re.I)  # fmt: skip
# a revision's note that asks to change what happens (its treatment again, before Make it);
# "Slow the ending down." is pacing


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
    if state.get("started") is False and state.get("revision"):  # after a delivery: the story
        m = next((m for m in notes if not m.get("answered") and STORY.search(m["text"])), None)
        if m is not None:  # stands unless a note asks to change it; else what it asks, below
            return go("treatment", f"Note {m['note']}: {m['text']}"[:300], note=m["text"])
        if "treatment" in state.get("done", []):  # its story changed: all of it, after Make it
            return go("wait", "The new treatment is ready: it waits for Make it.")
    elif state.get("started") is False:  # before Make it: a note changes the treatment, then
        m = next((m for m in notes if not m.get("answered")), None)  # it plans up to its card
        if m is not None:
            return go("treatment", f"Note {m['note']}: {m['text']}"[:300], note=m["text"])
    if audio := _audio_move(state, go):  # a song or narrated video: its audio is the clock
        return audio
    if state["shots"] == "none":
        return go("plan", "There are no shots yet.")
    if long := state.get("too_long"):  # before its stills: the split makes new shots
        return go("split_clip", f"{long[0]} is longer than the video model makes: split it.",
                  clip_id=long[0])  # fmt: skip
    if state["missing_looks"]:  # the first one in words, should nothing describe it
        return go(
            "make_looks",
            "Some roles have no look yet.",
            look={"name": state["missing_looks"][0], "description": "A practice look."},
        )
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
    if redraw := [{"shot_id": f["shot_id"], "note": f["note"]} for f in (
            review.get("findings") or [] if review.get("current") else [])
            if not used.get(f["shot_id"])]:  # fmt: skip
        return go(
            "redraw_still",
            "The review found stills off the treatment: drawn again.",
            redraws=redraw,
        )  # every one at once
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
    """For the delivery note: the brand's name the narration in use still says wrong, or the
    words it says that the script doesn't have, once its remakes are used (director.md: say
    what's off)."""
    audio = state.get("narration") or {}
    used = next((t for t in audio.get("takes") or [] if t["used"]), None)
    said = []
    if used and used.get("misheard"):
        w = used["misheard"][0]
        said.append(f"The narration still says “{w['heard']}” for {w['word']} at {w['at']:.1f} s")
    if used and used.get("extras"):
        x = used["extras"][0]
        said.append(f"The narration says “{x['text']}” at {x['start']:.1f} s, which the "
                    "script doesn't have")  # fmt: skip
    return (f"{'. '.join(said)}: it was read again as often as allowed, so listen before you "
            "share it.") if said else ""  # fmt: skip


STAND_IN_STYLE = "bright pop, warm female vocal, 110 bpm"  # a song version with no style line
STAND_IN_VOICES = ("English_DecentYoungMan", "English_Jovialman", "English_Trustworth_Man")


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
    if heard := audio.get("audition"):  # the presenter's voice first: the person picks it
        if heard["state"] == "asked":
            return go("wait", f"{heard['who']}'s voice is being auditioned.")
        who = heard["who"]
        return go(
            "ask",
            f"{who}'s voice first: everything is timed to it.",
            ask={
                "kind": "voice",
                "subject": who,
                "topic": f"{who}'s voice"[:80],
                "question": f"Which voice is {who}?",
                "voices": list(STAND_IN_VOICES),
                "why": "Each reads the script's opening. The one you pick is saved on them.",
            },
        )
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
                    "note": m["text"]}  # fmt: skip
        if (
            m.get("answered")
            or WORDS.search(m["text"])
            or clip not in clips
            or clips[clip]["stale"]
            or len(m["text"]) > NOTE_MAX  # never cut: the delivery note names it (`_answers`)
        ):
            continue
        if used.get(clip, 0) >= MAX_REDOS:
            continue  # it can't be made again: the delivery note says so
        return {"tool": "make_take", "why": f"Note {m['note']}: you asked: {m['text']}"[:300],
                "clip_id": clip, "take_id": None, "note": m["text"]}  # fmt: skip
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
        if len(text) > NOTE_MAX:
            return None  # never cut: the delivery note names it (`_answers`)
        return {"tool": "make_take", "why": why, "clip_id": p["clip_id"], "take_id": None,
                "note": text}  # fmt: skip
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
        elif len(m["text"]) > NOTE_MAX:  # the stand-in can't say it shorter; it never cuts it
            out.append(f"Note {n}: it's longer than one redo note carries ({NOTE_MAX} characters),"
                       f" so clip {clip[1:]} wasn't made again. Send it shorter.")  # fmt: skip
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
    times"; else "". The run then delivers what it has or stops, never spending turns on it.
    A free check that failed (video 240: the takes' words, on an overloaded server) never
    counts: its take reads "wasn't checked" in the delivery note (delivery.open_items).
    Counted since its last Carry on, which is a press to try again."""
    own = [j for j in turns(db, project) if j.input[RUN]["id"] == run["id"]]
    if not own:
        return ""
    since = max([own[0].created_at, *(datetime.fromisoformat(w["carried_at"]) for j in own
                 if (w := j.input.get(WAS_STOPPED)) and w.get("carried_at"))])  # fmt: skip
    counts: dict[str, int] = {}  # since its last Carry on: a press to try again
    for job in db.scalars(select(Job).where(Job.project_id == project.id,
                                            Job.status == JobStatus.failed,
                                            Job.created_at >= since)):  # fmt: skip
        if job.input.get(RETRIED):  # asked again on its own (`_again`): not a failure
            continue
        if job.provider in FREE_LANES:  # a check on our own server that couldn't run (a take's
            continue  # words, the cut's sound): never the run's end; the note says so
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
    if step == "song_timing":  # a narration's timing reads as one (its own job kind)
        return "The narration's timing" if job.kind == "narration_timing" else "The song's timing"
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
    jobs = db.scalars(select(Job).where(or_(Job.project_id == project.id, audio),
                                        Job.status.in_(WAITING),
                                        or_(step.is_(None), step != STEP)))  # fmt: skip
    # a talker's voice separation given up on isn't waited for: the cut uses the take's sound
    return [j for j in jobs if not (j.kind == talker_sound.STEP and talker_sound.given_up(j))]


def _has_take(db: Session, project: Project, clip_id: str) -> bool:
    row = db.scalar(select(ProjectClip).where(ProjectClip.project_id == project.id,
                                              ProjectClip.clip_id == clip_id))  # fmt: skip
    return bool(row and row.picked_take_id)
