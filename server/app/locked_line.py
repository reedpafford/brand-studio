"""An editor asks to change a locked line (S3-14): a published script's words are set, so a
note that quotes the script's words and asks to change them is answered at once, free and
without a model call, with what can change instead, each priced as its press charges ("up to";
an editor reads credits). Only what this video can really make is offered; with nothing, the
note waits for the director as any note does.

The card is an `Ask` of kind "instead": never a question the run waits on, never in Needs you
(its state is "offered"). A press makes its choice at once: "Say it softer" is a new take of the
clip that says the words, through Make a take's own price and holds, and once it's in the cut
is made again (free). The other choices stay pressable."""

import re
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accounts import User
from app.models.asks import Ask
from app.models.clips import ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project

KIND = "instead"
OFFERED = "offered"  # its state: answered by the server; never a question that waits
FOR = "instead_for"  # in a take job's input: the card whose choice made it
SET = "The script’s words are set for this script, so I can’t change “{}”. Here’s what I can change instead:"  # noqa: E501
SOFTER_NOTE = "Say it more softly and warmly, with less edge. Every word stays as written."
QUOTE = re.compile(r"[“\"]([^”\"]{2,80})[”\"]|(?:^|(?<=\s))[‘']([^’']{2,80})[’'](?=[\s?.!,]|$)")
CHANGE = re.compile(
    r"\b(change|swap|replace|reword|rewrite|instead|cut|drop|remove|lose|say|use|call)\b", re.I
)


def _plain(text: str) -> str:
    return " ".join(text.replace("’", "'").replace("‘", "'").lower().split())


def offer(db: Session, user: User, project: Project, text: str) -> Ask | None:
    """The reply to a note asking to change the script's words, or None (not such a note, or
    nothing here can be made instead)."""
    from app import plans

    version = plans.script(db, project)
    quoted = [a or b for a, b in QUOTE.findall(text)]
    script = _plain(version.text) if version else ""
    words = next((q.strip() for q in quoted if _plain(q) and _plain(q) in script), None)
    others = [q for q in quoted if q.strip() != words]
    if not words or not (others or CHANGE.search(text)):
        return None
    shot = _said_in(db, project, words)
    choices = [c for c in (_softer(db, project, shot),) if c]
    if not choices:
        return None
    ask = Ask(workspace_id=project.workspace_id, project_id=project.id, kind=KIND,
              subject=words[:120], question=SET.format(words), state=OFFERED,
              choices=[{"key": chr(65 + n), **c} for n, c in enumerate(choices)])  # fmt: skip
    db.add(ask)
    db.flush()
    return ask


def _said_in(db: Session, project: Project, words: str) -> dict | None:
    """The newest shots' shot that says these words: {clip, speaker}, or None."""
    from app.clip_prompts import newest

    bd = newest(db, project)
    if bd is None:
        return None
    clip_of = {s: c["id"] for c in bd.data.get("clips", []) for s in c["shot_ids"]}
    for scene in bd.data.get("scenes", []):
        for shot in scene.get("shots", []):
            if shot.get("line") and _plain(words) in _plain(shot["line"]):
                if shot["id"] in clip_of:
                    return {"clip": clip_of[shot["id"]], "speaker": shot.get("speaker") or ""}
    return None


def _softer(db: Session, project: Project, shot: dict | None) -> dict | None:
    """ "Say it softer": a new take of the clip that says it, its voice with it. Only where the
    clip's take carries the voice: a dialogue video's clip with a take in the cut (a narration,
    a song or a presenter is said elsewhere, and a UGC talker's clips come from its one take)."""
    from app import director_song, host, talker

    if shot is None or director_song.kind(db, project):  # a song or narrated video
        return None
    if host.on(db, project) or shot["clip"] in talker.clips(db, project):
        return None
    row = _row(db, project, shot["clip"])
    if row is None or row.picked_take_id is None:
        return None
    who = _name(shot["speaker"])
    said = f"{who} says it more softly" if who else "It's said more softly"
    n = shot["clip"].removeprefix("c")
    return {"title": "Say it softer", "why": f"{said}. Redo the voice line and clip {n}",
            "do": "softer", "clip": shot["clip"]}  # fmt: skip


def _name(speaker: str) -> str:
    """ "DR. PICKLE" as people write it: "Dr. Pickle"."""
    return " ".join(w.capitalize() for w in speaker.split()) if speaker.isupper() else speaker


def _row(db: Session, project: Project, clip: str) -> ProjectClip | None:
    return db.scalar(select(ProjectClip).where(ProjectClip.project_id == project.id,
                                               ProjectClip.clip_id == clip))  # fmt: skip


def price(db: Session, project: Project, choice: dict) -> Decimal:
    """What a choice's press can charge, as that press quotes it (0: free)."""
    from app.clip_takes import take_credits

    row = _row(db, project, choice.get("clip") or "")
    if choice.get("do") == "softer" and row is not None:
        return take_credits(db, project, row)
    return Decimal(0)


def state(db: Session, ask: Ask, key: str) -> str:
    """A choice's state: "" not pressed (or its take failed: press it again), "held" waiting
    for the owner's OK, "making", or "done"."""
    job = db.get(Job, ((ask.answer or {}).get("chosen") or {}).get(key) or 0)
    if job is None or job.status in (JobStatus.failed, JobStatus.cancelled):
        return ""
    if job.status == JobStatus.needs_owner_approval:
        return "held"
    return "done" if job.status == JobStatus.succeeded else "making"


def choose(db: Session, user: User, ask: Ask, key: str, storage) -> None:
    """A press on one of the card's choices: made at once, through its own route."""
    from app.routes import project_clips

    found = next((c for c in ask.choices if c["key"] == key), None)
    if found is None:
        raise HTTPException(422, "Pick one of the choices on the card.")
    if state(db, ask, key):
        raise HTTPException(409, "That's already being made.")
    project = db.get(Project, ask.project_id)
    row = _row(db, project, found.get("clip") or "")
    if row is None:
        raise HTTPException(409, "That clip isn't in this video any more.")
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(storage=storage)))
    made = project_clips.generate(project_id=project.id, clip_id=row.id, request=request,
                                  body=project_clips.TakeIn(note=SOFTER_NOTE), user=user,
                                  db=db)  # fmt: skip
    job = db.get(Job, made.id)
    job.input = {**job.input, FOR: ask.id}
    chosen = {**((ask.answer or {}).get("chosen") or {}), key: job.id}
    ask.answer = {"how": KIND, "choice": key, "name": found["title"], "chosen": chosen}
    ask.answered_by_id = user.id
    from app.db import utcnow

    ask.answered_at = utcnow()
    db.commit()


def after(db: Session, job: Job, storage) -> None:
    """A take a choice made is in: the cut is made again with it (free)."""
    from app.routes import project_clips

    if not job.input.get(FOR) or job.status != JobStatus.succeeded or not job.project_id:
        return
    project = db.get(Project, job.project_id)
    user = db.get(User, job.created_by_id)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(storage=storage)))
    me = {"project_id": project.id, "user": user, "db": db}
    try:
        project_clips.approve_all(**me)  # the picked takes it cuts with
        project_clips.make_video(request=request, **me)
    except HTTPException:
        db.rollback()  # another clip isn't ready: the cut is made again with the next one
