"""An editor asks to change a locked line (S3-14): a published script's words are set, so a
note that asks to replace or reword the script's own words is answered at once, free and with
no model call, with what can change instead, each priced as its press charges ("up to"; an
editor reads credits). Only what this video can really make is offered; with nothing, the note
waits for the director as any note does. A note that asks for more than the word change keeps
the rest for the director (it stays unread for the next Make it).

The card is an `Ask` of kind "instead": never a question a run waits on, never in Needs you
(its state is "offered"). A press makes its choice at once (`DOES`). "Say it softer" is a new
take of the clip that says the words, through Make a take's own price and holds; once its watch
comes back clean that clip is approved and the cut is made again (free, rule 35: never a cut
from a take nobody watched). Each choice keeps what happened to it on the card
(`answer.chosen`); the other choices stay pressable."""

import re
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accounts import User
from app.models.asks import Ask
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project

KIND = "instead"
OFFERED = "offered"  # its state: answered by the server; never a question that waits
FOR = "instead_for"  # in a take job's input: [the card, the choice] whose press made it
SET = "The script’s words are set for this script, so I can’t change “{}”. Here’s what I can change instead:"  # noqa: E501
SOFTER_NOTE = "Say it more softly and warmly, with less edge. Every word stays as written."
RUNNING = "The director is working on this video. Tell it in the chat instead."
QUOTE = re.compile(r"[“\"]([^”\"]{2,80})[”\"]|(?<![\w’'])[‘']([^’']{2,80})[’'](?![\w])")
# what a word change says around the quoted words ("Q" stands for them; "R" for a replacement)
ASKS = (
    r"\b(?:change|swap|replace|switch)\s+(?:the\s+)?(?:(?:word|words|line|phrase|bit)\s+)?Q"
    r"\s*(?:to|with|for|into|by)\b",
    r"\b(?:reword|rewrite|rephrase)\s+(?:the\s+)?(?:(?:word|words|line|phrase|bit)\s+)?Q",
    r"\b(?:say|use|write|put)\s+R\s+instead\s+of\s+Q",
    r"R\s+instead\s+of\s+Q",
    r"\binstead\s+of\s+Q\s*,?\s*(?:say|use|write|put)\s+R",
)
ASK_WORDS = re.compile(  # a clause that asks for something else as well
    r"\b(make|add|show|cut|swap|move|change|remove|drop|redo|fix|try|put|keep|use|lose|give|"
    r"brighter|darker|faster|slower|louder|quieter|longer|shorter|more|less)\b",
    re.I,
)


def _plain(text: str) -> str:
    return " ".join(text.replace("’", "'").replace("‘", "'").lower().split())


def _in(words: str, text: str) -> bool:
    """`words` said in `text` as whole words ("pin" isn't in "pint")."""
    return bool(re.search(rf"(?<!\w){re.escape(_plain(words))}(?!\w)", _plain(text)))


def asked(text: str, script: str) -> tuple[str, bool] | None:
    """The script's words a note asks to replace or reword, and whether that's all the note
    asks; None when it doesn't ask that."""
    quotes = [(m.group(0), (m.group(1) or m.group(2)).strip()) for m in QUOTE.finditer(text)]
    for raw, words in quotes:
        if not words or not _in(words, script):
            continue
        new = [re.escape(r) for r, w in quotes if w != words and not _in(w, script)]
        repl = f"(?:{'|'.join(new)})" if new else r"(?!x)x"
        for pattern in ASKS:
            found = re.search(pattern.replace("Q", re.escape(raw)).replace("R", repl), text, re.I)
            if found:
                rest = (text[: found.start()] + " " + text[found.end() :]).strip()
                for r in new:  # the replacement's own words aren't an ask
                    rest = re.sub(r, " ", rest)
                return words, not ASK_WORDS.search(rest)
    return None


def offer(db: Session, user: User, project: Project, text: str) -> tuple[Ask, bool] | None:
    """The reply to a note asking to change the script's words, and whether the note asked only
    that; None (not such a note, not a published script's video, or nothing can be made)."""
    from app import plans

    version = plans.script(db, project)
    if not project.script_draft_id or version is None:
        return None
    found = asked(text, version.text)
    if found is None:
        return None
    words, only = found
    shot = _said_in(db, project, words)
    choices = [c for c in (_softer(db, project, shot),) if c]
    if not choices:
        return None
    ask = Ask(workspace_id=project.workspace_id, project_id=project.id, kind=KIND,
              subject=words[:120], question=SET.format(words), state=OFFERED,
              choices=[{"key": chr(65 + n), **c} for n, c in enumerate(choices)])  # fmt: skip
    db.add(ask)
    db.flush()
    return ask, only


def _said_in(db: Session, project: Project, words: str) -> dict | None:
    """The newest shots' shot that says these words: {clip, speaker}, or None."""
    from app.clip_prompts import newest

    bd = newest(db, project)
    if bd is None:
        return None
    clip_of = {s: c["id"] for c in bd.data.get("clips", []) for s in c["shot_ids"]}
    for scene in bd.data.get("scenes", []):
        for shot in scene.get("shots", []):
            if shot.get("line") and _in(words, shot["line"]) and shot["id"] in clip_of:
                return {"clip": clip_of[shot["id"]], "speaker": shot.get("speaker") or ""}
    return None


def _softer(db: Session, project: Project, shot: dict | None) -> dict | None:
    """ "Say it softer": a new take of the clip that says it, its voice with it. Only where the
    clip's take carries the voice: a dialogue video's clip with a take in the cut (a narration,
    a song or a presenter is said elsewhere, and a UGC talker's clips come from its one take)."""
    if shot is None or _voiced(db, project, shot["clip"]):
        return None
    row = _row(db, project, shot["clip"])
    if row is None or row.picked_take_id is None:
        return None
    who = _name(shot["speaker"])
    said = f"{who} says it more softly" if who else "It's said more softly"
    n = shot["clip"].removeprefix("c")
    return {"title": "Say it softer", "why": f"{said}. Redo the voice line and clip {n}",
            "do": "softer", "clip": shot["clip"]}  # fmt: skip


def _voiced(db: Session, project: Project, clip: str) -> bool:
    """The line is said outside the clip's take: a song or narrated video (a presenter's
    narration too), or a UGC talker's clip."""
    from app import director_song, host, talker

    return bool(director_song.kind(db, project) or host.on(db, project)
                or clip in talker.clips(db, project))  # fmt: skip


def _name(speaker: str) -> str:
    """ "DR. PICKLE" as people write it: "Dr. Pickle"."""
    return " ".join(w.capitalize() for w in speaker.split()) if speaker.isupper() else speaker


def _row(db: Session, project: Project, clip: str) -> ProjectClip | None:
    return db.scalar(select(ProjectClip).where(ProjectClip.project_id == project.id,
                                               ProjectClip.clip_id == clip))  # fmt: skip


# --- A choice on the card: whether it can be made, its price, its press, what happened -------


def cannot(db: Session, project: Project, choice: dict) -> str:
    """Why this choice can't be made now ("" when it can), checked when shown and pressed."""
    from app import director

    if director.active(db, project):
        return RUNNING
    if choice.get("do") == "softer":
        row = _row(db, project, choice.get("clip") or "")
        n = (choice.get("clip") or "").removeprefix("c")
        if row is None:
            return f"Clip {n} isn't in this video any more."
        if row.picked_take_id is None or _voiced(db, project, row.clip_id):
            return f"Clip {n} has no take of its own in the cut now."
        return ""
    return "This can't be made here."


def price(db: Session, project: Project, choice: dict) -> Decimal | None:
    """What a choice's press can charge, as that press quotes it (0: free; None: it can't be
    made now, so it has no price)."""
    from app.clip_takes import take_credits

    if choice.get("do") == "softer":
        row = _row(db, project, choice.get("clip") or "")
        return take_credits(db, project, row) if row is not None else None
    return None


def made(db: Session, ask: Ask, key: str) -> tuple[str, str]:
    """A pressed choice's state and its words: ("", "") not pressed (or its take failed, so it
    can be pressed again: its words say so); held, making, watching, done or kept."""
    mine = ((ask.answer or {}).get("chosen") or {}).get(key)
    if not mine:
        return "", ""
    if "outcome" in mine:
        return ("done" if mine.get("cut") else "kept"), mine["outcome"]
    job = db.get(Job, mine.get("job") or 0)
    if job is None or job.status in (JobStatus.failed, JobStatus.cancelled):
        return "", "It wasn’t made, and nothing was charged. You can press it again."
    if job.status == JobStatus.needs_owner_approval:
        return "held", "Waiting for the owner’s OK."
    if job.status != JobStatus.succeeded:
        return "making", "Being made. Its watch looks at it before the cut is made again."
    return "watching", "Made. Being watched before the cut is made again."


def choose(db: Session, user: User, ask: Ask, key: str, storage) -> None:
    """A press on one of the card's choices: made at once, through its own route."""
    found = next((c for c in ask.choices if c["key"] == key), None)
    if found is None:
        raise HTTPException(422, "Pick one of the choices on the card.")
    if made(db, ask, key)[0]:
        raise HTTPException(409, "That's already being made.")
    project = db.get(Project, ask.project_id)
    if why := cannot(db, project, found):
        raise HTTPException(409, why)
    done = DOES[found["do"]](db, user, project, ask, found, storage)
    from app.db import utcnow

    chosen = {**((ask.answer or {}).get("chosen") or {}), key: done}
    ask.answer = {"how": KIND, "choice": key, "name": found["title"], "chosen": chosen}
    ask.answered_by_id, ask.answered_at = user.id, utcnow()
    db.commit()


def _say_softer(db: Session, user: User, project: Project, ask: Ask, choice: dict,
                storage) -> dict:  # fmt: skip
    """A new take of its clip through Make a take's own route (its price, its holds)."""
    from app.routes import project_clips

    row = _row(db, project, choice["clip"])
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(storage=storage)))
    out = project_clips.generate(project_id=project.id, clip_id=row.id, request=request,
                                 body=project_clips.TakeIn(note=SOFTER_NOTE), user=user,
                                 db=db)  # fmt: skip
    job = db.get(Job, out.id)
    job.input = {**job.input, FOR: [ask.id, choice["key"]]}
    return {"job": job.id}


DOES = {"softer": _say_softer}  # what each kind of choice does when pressed


def after(db: Session, job: Job, storage) -> None:
    """A choice's take, or its watch, finished: once the take's watch is back (and a remake its
    watch made is watched in turn), its clip is approved and the cut made again if it's clean;
    else the card says what was found and the cut stays as it was."""
    take = _take(db, job)
    if take is None:
        return
    root = _root(db, take)
    mark = (db.get(Job, root.job_id).input.get(FOR) if root and root.job_id else None) or []
    ask = db.get(Ask, mark[0]) if mark else None
    if ask is None or ask.kind != KIND:
        return
    watch = take.watch or {}
    if watch.get("state") == "watching" or watch.get("action") in ("redo", "held"):
        return  # its watch comes next, or its watch is remaking it: wait for that
    project = db.get(Project, ask.project_id)
    n = db.get(ProjectClip, take.clip_id).clip_id.removeprefix("c")
    if watch.get("state") != "done" or watch.get("action") != "keep":
        found = (watch.get("did") or "It wasn't watched.").rstrip(".")
        _outcome(db, ask, mark[1], f"Made. {found}. The cut stays as it was; look at clip "
                 f"{n} in Clips, then make the cut.", cut=False)  # fmt: skip
        return
    said, cut = _cut(db, project, take, storage)
    _outcome(db, ask, mark[1], said, cut=cut)


def _take(db: Session, job: Job) -> ClipTake | None:
    """The take a finished job is about: a take it made, or the take its watch looked at."""
    if job.kind == "video":
        return db.scalar(select(ClipTake).where(ClipTake.job_id == job.id))
    take_id = job.input.get("take_id") or (job.input.get("watch") or {}).get("take_id")
    return db.get(ClipTake, take_id) if take_id else None


def _root(db: Session, take: ClipTake) -> ClipTake | None:
    """The take a chain of the watch's remakes started from (each remake names the one before)."""
    from app.take_watch import REDO

    seen = set()
    while take is not None and take.id not in seen:
        seen.add(take.id)
        job = db.get(Job, take.job_id) if take.job_id else None
        if job is None or not job.input.get(REDO):
            return take
        take = db.get(ClipTake, job.input[REDO])
    return take


def _cut(db: Session, project: Project, take: ClipTake, storage) -> tuple[str, bool]:
    """That clip approved (only it) and the cut made again, free; or plainly why not."""
    from app.routes import project_clips

    row = db.get(ProjectClip, take.clip_id)
    user = db.get(User, db.get(Job, take.job_id).created_by_id)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(storage=storage)))
    me = {"project_id": project.id, "user": user, "db": db}
    try:
        if row.picked_take_id != take.id:
            project_clips.pick_take(clip_id=row.id, take_id=take.id, **me)
        row.approved = True  # this clip only: its watch came back clean
        db.flush()
        project_clips.make_video(request=request, **me)
    except HTTPException as no:
        db.rollback()
        return (f"Made and watched, but the cut wasn’t made again: {no.detail} Make the cut "
                "from the Cut tab once that’s done.", False)  # fmt: skip
    return "Made and watched. The cut is made again with it.", True


def _outcome(db: Session, ask: Ask, key: str, said: str, cut: bool) -> None:
    ask = db.get(Ask, ask.id)
    chosen = dict((ask.answer or {}).get("chosen") or {})
    chosen[key] = {**chosen.get(key, {}), "outcome": said, "cut": cut}
    ask.answer = {**(ask.answer or {}), "chosen": chosen}
    db.commit()
