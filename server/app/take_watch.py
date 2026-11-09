"""The director looks at every take as it lands (rule 11). After a take is saved, one free pass
on our server (app/take_words: a speech model's transcript; app/deep_watch: sampled filmstrips,
motion and loudness measured, a spectrogram) and then one look (the same Claude check path as a
still's check, `check-claude`) at them, against the style's guide, the shot, the transcript and
the references.

What it found and did is kept on the take (`ClipTake.watch`) for the Clips tab and the
delivery note. A weak take is remade with its prompt rewritten for its model, within the
video's approved budget and never more than REMAKES times a clip a run (rule 34); past the
budget the remake waits for the owner's OK (a held job, as every hold does). Its findings are
also an ItemCheck ("take"), so a clean picked take approves itself (rule 21). Only confirmed
findings remake a take (app/watch_report: seen in the frames, or clipped samples); the rest
(the transcript, a silence, a jump, lip-sync, voice, music) go to the owner as unconfirmed
notes, never paid for."""

import logging
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import cast_gate, item_checks, plans, prompts, watch_report
from app.credits import WAIT_OK, estimate, fits
from app.db import utcnow
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.checks import ItemCheck
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.prompts.schemas import TakeWatch

log = logging.getLogger(__name__)
STEP, KIND, TARGET = "take_watch", "check-claude", "take"
LOOKS = 6  # a watch's "up to" in looks at one picture (0.2 credits each): 1.2 credits a take
REMAKES = 2  # remakes of one clip by its watch, a run (rule 34)
OVERVIEW, FEWEST, MOST = 2.5, 8, 24  # frames a second spread over the take, 8 to 24 of them
DENSE = 3  # windows sampled at 10 a second on its jumps, shot changes and first word
REDO = "watch_redo"  # in a remake's job input: the take it remakes
MADE = (JobStatus.queued, JobStatus.running, JobStatus.succeeded, JobStatus.needs_owner_approval)
SKIPPED = "Not watched: the video is at its budget."
KEPT = "Kept it."
UNWATCHED = watch_report.UNWATCHED
SUPERSEDED = "Nothing done: a newer take of this clip is on its way."
NOT_REMADE = "Flagged for you: it couldn't be remade here. Make another take from the clip."
TO_DIRECTOR = "Left for the director: {} A screen or a label is never remade on its own."
HANDED_BACK = ("Left for the director: it was remade on its own once already since the "
               "director's last look.")  # fmt: skip
ITS_CALL = ("screen", "product")  # a brand screen or label: the director's call, never a remake
# on its own (video 299: Seedance can't draw the real screen exactly, so every take "failed" and
# each check bought another, and the director never got a turn)
SPEAKS = "This clip is planned to speak or sing on camera: its lines are in <shot>."
SILENT = ("A {over} is heard over this clip, which isn't planned to speak: a voice or singing "
          "in the take works against it.")  # fmt: skip
QUIET = "Nobody is planned to speak in this clip."


def on() -> bool:
    """Watches run whenever checks do (item_checks.on: the stand-ins, or once turned on)."""
    return item_checks.on()


def per_take(db: Session, workspace_id: int, always: bool = False) -> Decimal:
    """What watching one take adds to it while watches are on: every shown price that makes a
    take includes it, so a price shown is never below what the press charges (QA-3 on #1170)."""
    if not (always or on()):
        return Decimal(0)
    return estimate(db, workspace_id, KIND, Decimal(LOOKS), {})


def rides(db: Session, project: Project, clip: ProjectClip | None = None) -> Decimal:
    """The watch one more take of a clip brings with it."""
    return per_take(db, project.workspace_id)


def speaks(db: Session, project: Project, clip: ProjectClip, shots: list[dict]) -> bool:
    """This clip is planned to speak or sing on camera: a dialogue or movie video's spoken
    lines, or a song's sung shots. A narrated video keeps its narration throughout: nobody on
    screen speaks (Reed, 4 Nov)."""
    from app.clip_takes import on_camera_speech

    return on_camera_speech(db, project, clip, shots)


def said(db: Session, project: Project, clip: ProjectClip, shots: list[dict]) -> str:
    """<format>: who is planned to be heard in this clip."""
    if speaks(db, project, clip, shots):
        return SPEAKS
    fmt = plans.fmt(db, project)
    return QUIET if fmt == "dialogue" else SILENT.format(over="narrator" if fmt == "narrated"
                                                         else "song")  # fmt: skip


def _shots(db: Session, clip: ProjectClip) -> list[dict]:
    data = db.get(BreakdownVersion, clip.breakdown_id).data
    ids = next((c["shot_ids"] for c in data.get("clips", []) if c["id"] == clip.clip_id), [])
    by_id = {s["id"]: s for sc in data.get("scenes", []) for s in sc.get("shots", [])}
    return [by_id[i] for i in ids if i in by_id]


def over(db: Session, project: Project, clip: ProjectClip) -> list[dict]:
    """A narration's or song's words heard over this clip, in its take's seconds."""
    from app.models.songs import SongTake

    piece = clip.song_slice or {}
    take = db.get(SongTake, project.song_take_id) if project.song_take_id else None
    if not piece or not take or not take.timing:
        return []
    return [{"word": w["word"], "start": round(w["start"] - piece["start"], 2),
             "end": round(w["end"] - piece["start"], 2)}
            for w in take.timing.get("words") or []
            if piece["start"] <= w["start"] < piece["end"]]  # fmt: skip


def queue(db: Session, job: Job, take: ClipTake, clip: ProjectClip) -> None:
    """After a take is saved (in the worker): its free listen, then its look; skipped when the
    watch would leave no room for one more take of the clip ("skipped", never held). The
    words check rides on the same listen."""
    from app import take_words
    from app.clip_takes import take_credits

    project = db.get(Project, job.project_id) if job.project_id else None
    if not project or not on():
        return
    shots = _shots(db, clip)
    row = ItemCheck(project_id=project.id, target=TARGET, target_id=take.id, status="checking")
    db.add(row)
    db.flush()
    user = db.get(User, job.created_by_id)
    room = per_take(db, project.workspace_id) + take_credits(db, project, clip)
    watch = None
    if not user or fits(db, project, user, room):
        row.status = "skipped"
        take.watch = {"state": "skipped", "found": "", "did": SKIPPED, "at": _now()}
    else:
        take.watch = {"state": "watching"}
        watch = {"item_check_id": row.id, "take_id": take.id, "over": over(db, project, clip),
                 "approved_by_id": job.approved_by_id, "overview": [OVERVIEW, FEWEST, MOST],
                 "dense": DENSE}  # fmt: skip
    listen = take_words.queue(db, job, take.id, take.file_id, shots, take.prompt or "", watch,
                              speaks(db, project, clip, shots))  # fmt: skip
    row.job_id = listen.id if listen and watch else None


def queue_safely(db: Session, job: Job, take: ClipTake, clip: ProjectClip) -> None:
    """A watch never stops a take from being saved."""
    try:
        with db.begin_nested():
            queue(db, job, take, clip)
    except Exception:
        log.exception("couldn't queue the watch of take %s", take.id)


def heard(db: Session, listen: Job) -> None:
    """The listen is done (its words, measurements, strips and spectrogram): the look at them
    is queued, on the take's own price (checked when it was queued)."""
    from app import model_map
    from app.enhance import project_context

    w = listen.input["watch"]
    row, take = db.get(ItemCheck, w["item_check_id"]), db.get(ClipTake, w["take_id"])
    if not row or not take:
        return
    out = listen.output or {}
    files, labels = out.get("file_ids") or [], out.get("strips") or []
    if not files:
        return _failed(row, take)
    clip, project = db.get(ProjectClip, take.clip_id), db.get(Project, row.project_id)
    shots = _shots(db, clip)
    refs = [r["id"] for r in clip.references or [] if r["kind"] == "image"]
    seen = item_checks.compared(db, project, refs, shots) or {}
    told = prompts.references(len(files), seen.get("sheets", []), seen.get("product"),
                              seen.get("cast"), seen.get("screens"),
                              seen.get("screen_rules"))  # fmt: skip
    model = model_map.of_clip(project, clip)  # the clip's own model
    lines = [f"{s.get('speaker') or 'Someone'}: “{s['line']}”" for s in shots if s.get("line")]
    shot = " ".join([seen.get("said") or " ".join(s.get("action", "") for s in shots), *lines])
    heard_words = [x for line in out.get("heard") or [] for x in line.get("words") or []]
    text = prompts.take_watch_input(
        f"{clip.clip_id}, {clip.seconds} s, made on {model.name}", shot,
        said(db, project, clip, shots), take.prompt or clip.prompt, heard_words,
        w.get("over", []),
        out.get("measured_text", ""), labels, told,
        max(REMAKES - remakes(db, clip) - directors(db, project, clip.clip_id), 0),
    )  # fmt: skip
    system, _ = project_context(db, project, STEP)  # the style's guide: its must-keeps
    known = watch_report.facts(out.get("measured"))
    data = {"step": STEP, "item_check_id": row.id, "take_id": take.id, "project_id": project.id,
            "system": system, "prompt": text, "effort": "medium", "max_tokens": 8000,
            "known": known,
            "fit_images_to": 1024, "ref_ids": seen.get("ref_ids", []),
            "files": {"reference_images": [*files, *seen.get("images", [])]}}  # fmt: skip
    look = Job(workspace_id=project.workspace_id, created_by_id=listen.created_by_id, kind=KIND,
               provider="claude", input=data, project_id=project.id, brand_id=project.brand_id,
               credits=per_take(db, project.workspace_id, always=True), status="queued",
               approved_by_id=w.get("approved_by_id"))  # fmt: skip
    db.add(look)
    db.flush()
    row.job_id = look.id


def save(db: Session, job: Job) -> None:
    """The look's answer: what it found, kept on the take, and what it did about it."""
    if job.input.get("piece_id"):  # a presenter's host (app/host_watch)
        from app import host_watch

        return host_watch.save(db, job)
    row = db.get(ItemCheck, job.input["item_check_id"])
    take = db.get(ClipTake, job.input["take_id"])
    if not row or not take:
        return
    answer = TakeWatch.model_validate(job.output)
    found = watch_report.faults(answer, job.input.get("ref_ids", []), job.input.get("known", {}))
    sure = [f for f in found if f["verified"]]
    redo = answer.verdict == "redo" and bool(found)
    doubts = len(sure) < len(found)  # the model's note may cover a doubt: the sure ones only
    note = ("; ".join(f["says"] for f in sure) if doubts and sure
            else answer.note.strip() or "; ".join(f["says"] for f in found))  # fmt: skip
    if redo and sure and all(f["kind"] in ITS_CALL for f in sure):
        did, action, made, credits = TO_DIRECTOR.format(note), "flagged", None, None
    elif redo and sure:  # only confirmed faults pay for a remake
        prompt = "" if doubts else answer.prompt.strip()
        did, action, made, credits = act(db, take, note, prompt)
    elif doubts:  # shown to the owner, never paid for
        unsure = [f for f in found if not f["verified"]]
        did, action, made, credits = watch_report.unsure(unsure), "unsure", None, None
    else:
        did, action, made, credits = KEPT, "keep", None, None
    row.findings = [{"kind": f["kind"], "role": f["who"], "text": f["says"], "at": f["at"],
                     "change_note": note if f["verified"] else "", "verified": f["verified"]}
                    for f in found if redo or not f["verified"]]  # doubts stay visible  # fmt: skip
    row.status = "done"
    take.watch = {"state": "done", "found": answer.seen.strip(), "faults": found, "did": did,
                  "action": action, "note": note if redo else "", "at": _now(),
                  "job_id": job.id, "remake_job_id": made.id if made else None,
                  "remake_credits": float(credits) if credits else None}  # fmt: skip
    from app.clip_prompts import repair
    from app.take_approval import after_check

    db.flush()
    repair(db, db.get(Project, row.project_id))  # its clip's notes as Clips would show them now
    after_check(db, take.id)  # a clean picked take approves itself (rule 21)


def failed(db: Session, job: Job) -> None:
    """The listen or the look failed: "Couldn't watch this one." Nothing is charged."""
    w = job.input.get("watch") or job.input
    if w.get("piece_id"):
        from app import host_watch

        return host_watch.failed(db, job)
    row = db.get(ItemCheck, w.get("item_check_id") or 0)
    take = db.get(ClipTake, w.get("take_id") or 0)
    if row and take and row.target == TARGET:
        _failed(row, take)


def _failed(row: ItemCheck, take: ClipTake) -> None:
    row.status = "failed"
    take.watch = {"state": "failed", "found": "", "did": UNWATCHED, "at": _now()}


def _now() -> str:
    return utcnow().isoformat()


def run_start(db: Session, project: Project):
    """When the video's newest director run began (its first turn), or None before any run."""
    from app.director import RUN
    from app.director import STEP as TURN

    newest = db.scalar(select(Job).where(Job.project_id == project.id,
                                         Job.input["step"].as_string() == TURN)
                       .order_by(Job.id.desc()).limit(1))  # fmt: skip
    if newest is None:
        return None
    run = newest.input[RUN]["id"]
    return db.scalar(select(Job.created_at).where(
        Job.project_id == project.id, Job.input[RUN]["id"].as_string() == run,
        Job.input["step"].as_string() == TURN).order_by(Job.id).limit(1))  # fmt: skip


def remakes(db: Session, clip: ProjectClip) -> int:
    """This clip's remakes by its watch this run: made, being made or waiting for the owner."""
    project = db.get(Project, clip.project_id)
    since = run_start(db, project)
    jobs = db.scalars(select(Job).where(Job.project_id == clip.project_id, Job.kind == "video",
                                        Job.status.in_(MADE)))  # fmt: skip
    return sum(1 for j in jobs if j.input.get(REDO) and j.input.get("project_clip_id") == clip.id
               and (since is None or j.created_at >= since))  # fmt: skip


LOOKS_SET = ("char:", "slot:", "place:", "prop:", "screen:")  # approved pictures: their look


def keeps_looks(db: Session, project: Project, clip: ProjectClip, fitted, note: str) -> bool:
    """A rewritten prompt keeps every approved picture the prompt in hand attaches (a
    character's, place's, product's or screen's look is never rewritten: Reed, 4 Nov); else
    the note goes into the take instead."""
    from app import change

    have, _ = change.fit(db, project, clip, clip.prompt, note)
    kept = {r.id for r in fitted.references}
    return all(r.id in kept for r in have.references if r.id.startswith(LOOKS_SET))


def _since_director(db: Session, project: Project, clip: ProjectClip) -> bool:
    """This clip was remade on its own since the director's last turn: the next fault goes to
    the director, so automatic remakes never keep the run busy without it."""
    from app.director import STEP as TURN

    last = db.scalar(select(func.max(Job.created_at)).where(
        Job.project_id == project.id, Job.input["step"].as_string() == TURN))  # fmt: skip
    if last is None:  # no director on this video: its own limit (REMAKES) only
        return False
    jobs = db.scalars(select(Job).where(Job.project_id == project.id, Job.kind == "video",
                                        Job.status.in_(MADE), Job.created_at > last))  # fmt: skip
    return any(j.input.get(REDO) and j.input.get("project_clip_id") == clip.id for j in jobs)


def directors(db: Session, project: Project, clip_id: str) -> int:
    """The director's own remakes of this clip this run (its run's `redos`), so the watch's
    and its own come to REMAKES a clip in all (rule 34)."""
    from app.director import RUN
    from app.director import STEP as TURN

    newest = db.scalar(select(Job).where(Job.project_id == project.id,
                                         Job.input["step"].as_string() == TURN)
                       .order_by(Job.id.desc()).limit(1))  # fmt: skip
    return int((newest.input[RUN].get("redos") or {}).get(clip_id, 0)) if newest else 0


def _for(job: Job, clip: ProjectClip) -> bool:
    """A job making this clip's next take: the take itself, or a Change it… rewriting its
    prompt first (its take follows)."""
    return job.input.get("project_clip_id") == clip.id or (
        job.input.get("target") == "clip" and job.input.get("target_id") == clip.id
    )


def _redone_since(db: Session, project: Project, clip: ProjectClip, take: ClipTake) -> bool:
    """The director remade this clip since this take was made: only its newest take is judged,
    so the watch never remakes the older one too (run 287's clip 3: two remakes, +$1.54)."""
    from sqlalchemy import or_

    from app.director import STEP as TURN

    turns = db.scalars(select(Job).where(
        Job.project_id == project.id, Job.input["step"].as_string() == TURN,
        or_(Job.created_at >= take.created_at, Job.finished_at >= take.created_at)))  # fmt: skip
    return any((j.output or {}).get("tool") == "make_take"
               and (j.output or {}).get("clip_id") == clip.clip_id
               and not (j.input.get("result") or "Refused").startswith("Refused")
               for j in turns)  # fmt: skip


def act(db: Session, take: ClipTake, note: str,
        prompt: str) -> tuple[str, str, Job | None, Decimal | None]:  # fmt: skip
    """A weak take remade, or why not: (what it did, the action, the remake's job, its "up
    to"). The action: redo (being made), held (past the budget: the owner's OK first) or
    flagged (it can't be remade here: the owner sees it). The prompt in hand is rewritten
    only when the take was made from it and the rewrite has no problem to fix first; else
    the note goes into this take only, as a Redo note does."""
    from fastapi import HTTPException

    from app import advice, change, clip_takes, model_map
    from app.models.jobs import WAITING
    from app.prompts import check
    from app.prompts.schemas import Breakdown
    from app.routes.jobs import DIRECTOR_TOOL, enqueue

    clip = db.get(ProjectClip, take.clip_id)
    project = db.get(Project, clip.project_id)
    name = f"clip {clip.clip_id.removeprefix('c')}"
    newest = db.scalar(select(func.max(ClipTake.number)).where(ClipTake.clip_id == clip.id))
    pending = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING)))
    if (take.number != newest or any(_for(j, clip) for j in pending)
            or _redone_since(db, project, clip, take)):  # fmt: skip
        return SUPERSEDED, "superseded", None, None
    if _since_director(db, project, clip):  # a turn runs between: never starved (video 299)
        return HANDED_BACK, "flagged", None, None
    if remakes(db, clip) + directors(db, project, clip.clip_id) >= REMAKES:
        return (f"Flagged for you: {name} was remade {REMAKES} times already, the most a run "
                "allows. Remake it or keep it.", "flagged", None, None)  # fmt: skip
    bd = Breakdown.model_validate(db.get(BreakdownVersion, clip.breakdown_id).data)
    if check.redo_note(note, bd, clip.clip_id):  # the fix would change the words (rule 19)
        return ("Flagged for you: the fix would change what's said, so it wasn't remade.",
                "flagged", None, None)  # fmt: skip
    user = db.get(User, db.get(Job, take.job_id).created_by_id)
    credits = clip_takes.take_credits(db, project, clip)
    over = fits(db, project, user, credits)
    wait = f"{WAIT_OK}remaking {name} goes past the video's budget." if over else ""
    rewritten = False  # held: the prompt in hand stays, the note rides in the held take
    before = {k: getattr(clip, k) for k in ("prompt", "references", "seconds", "problems",
                                            "prompt_ok", "approved", "prompt_history")}  # fmt: skip
    if prompt and not wait and clip.prompt == take.prompt:
        fitted, problems = change.fit(db, project, clip, prompt, note)
        if not advice.blocking(problems) and keeps_looks(db, project, clip, fitted, note):
            change.use(db, clip, fitted, problems, user.id)
            rewritten = True
    marked = DIRECTOR_TOOL.set(True)  # the director's own remake
    try:
        data = clip_takes.take_input(db, project, clip, "" if rewritten else note)
        data = {**data, REDO: take.id,
                "made_with": {**data["made_with"], "remade_from": take.number}}  # fmt: skip
        seconds = model_map.billed(model_map.of_clip(project, clip), clip.seconds)
        made = enqueue(db, user, "video", data, units=seconds, project=project,
                       provider="replicate", prepaid=not wait, wait=wait)  # fmt: skip
    except HTTPException as no:  # its reason can name dollars: the owner sees it on the clip
        for field, value in before.items():  # no take: the prompt in hand stays as it was
            setattr(clip, field, value)
        if isinstance(no, cast_gate.Waiting):  # a look in it changed: the person's OK first
            return cast_gate.not_yet(no), "flagged", None, None
        return NOT_REMADE, "flagged", None, None
    finally:
        DIRECTOR_TOOL.reset(marked)
    how = f"with “{note}” in the prompt" if rewritten else f"with the note “{note}”"
    model = model_map.of_clip(project, clip).name
    if wait:
        return (f"Asked the owner: remaking it on {model} {how} goes past the video's budget.",
                "held", made, credits)  # fmt: skip
    return f"Remade it on {model} {how}.", "redo", made, credits
