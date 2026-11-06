"""The director looks at each piece of a Presenter video's host as it lands (rule
11): the corner presenter's take on green, or a UGC talker's in their room, each one HeyGen take
(app/host.py). The same free listen and one look as a take (app/take_watch): lip-sync
on the sampled frames against the narration's words, the voice, glitches, the host kept as
their still. A weak piece is made again with the fix in its prompt when a fault is confirmed
(app/watch_report), within the budget and twice a piece a run at most; past the budget it
waits for the owner's OK. What it found and did is kept on the piece (`HostPiece.watch`); the
talker clips cut from a talker's take show their share of it."""

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts, take_watch, watch_report
from app.credits import WAIT_OK, fits
from app.models.accounts import User
from app.models.brands import Brand
from app.models.checks import ItemCheck
from app.models.clips import HostPiece
from app.models.files import StoredFile
from app.models.jobs import Job
from app.models.projects import Project
from app.prompts.schemas import TakeWatch

log = logging.getLogger(__name__)
TARGET = "piece"
REDO = "watch_redo_piece"  # in a piece's remake: the piece it makes again
SAID = "On-camera speech: the host says this piece of the narration; its sound is that."
SHOT = (
    "{who} says this piece of the narration straight to the camera, lip-synced to it: the "
    "mouth moves with every word in <over>, the voice stays the narration's own, and they "
    "stay exactly as their still (the reference): the same face, outfit and place."
)


def _words(db: Session, project: Project, row: HostPiece) -> list[dict]:
    """The narration's words this piece says, in its own seconds."""
    from app.models.songs import SongTake

    take = db.get(SongTake, row.take_id)
    return [{"word": w["word"], "start": round(w["start"] - row.start, 2),
             "end": round(w["end"] - row.start, 2)}
            for w in (take.timing or {}).get("words") or []
            if row.start <= w["start"] < row.end] if take else []  # fmt: skip


def queue(db: Session, job: Job, row: HostPiece) -> None:
    """A piece is made (in the worker): its free listen, then its look; skipped when the watch
    would leave no room to make it again ("skipped", never held)."""
    from app import host
    from app.take_words import KIND, STEP, say

    project = db.get(Project, job.project_id)
    if not take_watch.on() or not project or not row.number or not row.file_id:
        return
    check = ItemCheck(project_id=project.id, target=TARGET, target_id=row.id, status="checking")
    db.add(check)
    db.flush()
    user = db.get(User, job.created_by_id)
    room = host.price(db, project, row.number)  # making it again, its watch included
    if not user or fits(db, project, user, room):
        check.status = "skipped"
        row.watch = {"state": "skipped", "found": "", "did": take_watch.SKIPPED,
                     "at": take_watch._now()}  # fmt: skip
        return
    row.watch = {"state": "watching"}
    brand = db.get(Brand, project.brand_id)
    watch = {"item_check_id": check.id, "piece_id": row.id, "over": _words(db, project, row),
             "approved_by_id": job.approved_by_id, "dense": take_watch.DENSE,
             "overview": [take_watch.OVERVIEW, take_watch.FEWEST, take_watch.MOST]}  # fmt: skip
    data = {"step": STEP, "item_check_id": None, "project_id": project.id, "lines": [],
            "video_key": db.get(StoredFile, row.file_id).key, "prompt": "", "actions": [],
            "brand": brand.name, "said_as": say(brand), "silent": False,
            "watch": watch}  # fmt: skip
    listen = Job(workspace_id=project.workspace_id, created_by_id=job.created_by_id, kind=KIND,
                 provider="local", input=data, project_id=project.id, brand_id=project.brand_id,
                 credits=0, status="queued")  # fmt: skip
    db.add(listen)
    db.flush()
    check.job_id = listen.id


def queue_safely(db: Session, job: Job, row: HostPiece) -> None:
    """A watch never stops a piece from being kept."""
    try:
        with db.begin_nested():
            queue(db, job, row)
    except Exception:
        log.exception("couldn't queue the watch of the host's piece %s", row.id)


def _model(db: Session, project: Project) -> str:
    from app import talker
    from app.catalogue import get_model

    return get_model(talker.MODEL).name  # the corner presenter and the talker: HeyGen


def heard(db: Session, listen: Job) -> None:
    """The piece is heard and measured: its look is queued, on the piece's own price."""
    from app import host, talker
    from app.enhance import project_context

    w = listen.input["watch"]
    check, row = db.get(ItemCheck, w["item_check_id"]), db.get(HostPiece, w["piece_id"])
    if not check or not row:
        return
    out = listen.output or {}
    files, labels = out.get("file_ids") or [], out.get("strips") or []
    if not files:
        return _failed(check, row)
    project = db.get(Project, check.project_id)
    talks = talker.on(db, project)
    still = host.rows(db, project)[0]
    sheet = [("host:0", "The host's still: every piece keeps this face, outfit and place")]
    told = prompts.references(len(files), sheet if still.file_id else [])
    heard_words = [x for line in out.get("heard") or [] for x in line.get("words") or []]
    text = prompts.take_watch_input(
        f"the host's piece {row.number}, {row.start:.1f}–{row.end:.1f} s of the narration, made "
        f"on {_model(db, project)}", SHOT.format(who="The talker" if talks else "The host"),
        SAID, talker.MOTION if talks else host.TALK, heard_words, w.get("over", []),
        out.get("measured_text", ""), labels, told, max(take_watch.REMAKES - remakes(db, row), 0),
    )  # fmt: skip
    system, _ = project_context(db, project, take_watch.STEP)
    data = {"step": take_watch.STEP, "item_check_id": check.id, "piece_id": row.id,
            "project_id": project.id, "system": system, "prompt": text, "effort": "medium",
            "max_tokens": 8000, "fit_images_to": 1024, "ref_ids": ["host:0"],
            "known": watch_report.facts(out.get("measured")),
            "files": {"reference_images": [*files, *([still.file_id] if still.file_id else [])]}}  # fmt: skip  # noqa: E501
    look = Job(workspace_id=project.workspace_id, created_by_id=listen.created_by_id,
               kind=take_watch.KIND, provider="claude", input=data, project_id=project.id,
               brand_id=project.brand_id, status="queued", approved_by_id=w.get("approved_by_id"),
               credits=take_watch.per_take(db, project.workspace_id, always=True))  # fmt: skip
    db.add(look)
    db.flush()
    check.job_id = look.id


def save(db: Session, job: Job) -> None:
    """The look's answer, kept on the piece, and the piece made again when it's weak."""
    check = db.get(ItemCheck, job.input["item_check_id"])
    row = db.get(HostPiece, job.input["piece_id"])
    if not check or not row:
        return
    answer = TakeWatch.model_validate(job.output)
    faults = watch_report.faults(answer, [], job.input.get("known", {}))
    sure = [f for f in faults if f["verified"]]
    redo = answer.verdict == "redo" and bool(faults)
    doubts = len(sure) < len(faults)  # the model's note may cover a doubt: the sure ones only
    note = ("; ".join(f["says"] for f in sure) if doubts and sure
            else answer.note.strip() or "; ".join(f["says"] for f in faults))  # fmt: skip
    if redo and sure:  # only confirmed faults pay for making it again
        did, action, made, credits = act(db, row, note)
    elif doubts:  # shown to the owner, never paid for
        unsure = [f for f in faults if not f["verified"]]
        did, action, made, credits = watch_report.unsure(unsure), "unsure", None, None
    else:
        did, action, made, credits = take_watch.KEPT, "keep", None, None
    check.findings = [{"kind": f["kind"], "role": "", "text": f["says"], "at": f["at"],
                     "change_note": note if f["verified"] else "", "verified": f["verified"]}
                    for f in faults if redo or not f["verified"]]  # fmt: skip
    check.status = "done"
    row.watch = {"state": "done", "found": answer.seen.strip(), "faults": faults, "did": did,
                 "action": action, "note": note if redo else "", "at": take_watch._now(),
                 "job_id": job.id, "remake_job_id": made.id if made else None,
                 "remake_credits": float(credits) if credits else None}  # fmt: skip


def failed(db: Session, job: Job) -> None:
    w = job.input.get("watch") or job.input
    check = db.get(ItemCheck, w.get("item_check_id") or 0)
    row = db.get(HostPiece, w.get("piece_id") or 0)
    if check and row:
        _failed(check, row)


def _failed(check: ItemCheck, row: HostPiece) -> None:
    check.status = "failed"
    row.watch = {"state": "failed", "found": "", "did": take_watch.UNWATCHED,
                 "at": take_watch._now()}  # fmt: skip


def remakes(db: Session, row: HostPiece) -> int:
    """This piece's remakes by its watch this run: made, being made or waiting for the owner."""
    since = take_watch.run_start(db, db.get(Project, row.project_id))
    jobs = db.scalars(select(Job).where(Job.project_id == row.project_id, Job.kind == "video",
                                        Job.status.in_(take_watch.MADE)))  # fmt: skip
    return sum(1 for j in jobs if j.input.get(REDO) == row.id
               and (since is None or j.created_at >= since))  # fmt: skip


def act(db: Session, row: HostPiece, note: str) -> tuple[str, str, Job | None, Decimal | None]:
    """A weak piece made again with the fix in its prompt, or why not (as take_watch.act)."""
    from fastapi import HTTPException

    from app import host
    from app.routes.jobs import DIRECTOR_TOOL

    project = db.get(Project, row.project_id)
    name = f"the host's piece {row.number}"
    jobs = host._jobs(db, project)
    if any(host._state(r, jobs.get(r.id)) == "making" for r in host.rows(db, project)):
        return "Nothing done: the host is still being made.", "superseded", None, None
    if remakes(db, row) >= take_watch.REMAKES:
        return (f"Flagged for you: {name} was made again {take_watch.REMAKES} times already, the "
                "most a run allows. Make it again or keep it.", "flagged", None, None)  # fmt: skip
    user = db.get(User, jobs[row.id].created_by_id)
    credits = host.price(db, project, row.number)  # its watch included
    wait = f"{WAIT_OK}making {name} again goes past the video's budget." if fits(
        db, project, user, credits) else ""  # fmt: skip
    from app import cast_gate

    try:  # the host's look changed since the cast and places OK: the person's OK first
        host._cast(db, project, check=True)
    except cast_gate.Waiting as no:
        return cast_gate.not_yet(no), "flagged", None, None
    marked = DIRECTOR_TOOL.set(True)
    try:
        made = host._piece(db, user, project, row, host.rows(db, project)[0].file_id,
                           note=note, mark={REDO: row.id}, prepaid=not wait, wait=wait)  # fmt: skip
    except HTTPException:  # its reason can name dollars
        return ("Flagged for you: it couldn't be made again here. Make it again from the host.",
                "flagged", None, None)  # fmt: skip
    finally:
        DIRECTOR_TOOL.reset(marked)
    how = f"on {_model(db, project)} with “{note}” in the prompt"
    if wait:
        return (f"Asked the owner: making it again {how} goes past the video's budget.", "held",
                made, credits)  # fmt: skip
    return f"Made it again {how}.", "redo", made, credits
