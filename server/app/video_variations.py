"""Video variations (Reed, Runway #2: "on a finished video, 'Make 2–3 variations' with a
different hook or ending, keeping the locked cast, look and approved clips; only the changed
clips are made"). One director call proposes them (`ask`). Each becomes its own video beside
the source, "<title> · variation A", copied from it: its words, plan, cast and looks, voice,
stills, clips and takes (the same files: nothing is made again for them). Only the clips its
idea names lose their take, and its treatment carries the new hook or ending. Its run is a
revision (the source's story stands), so its direction card, before anything is made, prices
only those clips (`revision.revision`). The script's words never change, except for words the
owner quoted in the note for that line (a new version of the script for that video only). A
one-pass video's variation is one too (its engine is copied): its note is the run's note, so
its one plan call changes only the clips the note names (one_pass._kept)."""

import copy
import json
import logging

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import director
from app.db import utcnow
from app.models.accounts import User
from app.models.clips import ClipTake, HostPiece, ProjectClip
from app.models.jobs import WAITING, Job, JobStatus
from app.models.projects import Project
from app.models.scripts import ScriptVersion
from app.models.storyboards import StoryboardFrame
from app.prompts.schemas import VideoVariation, VideoVariations

log = logging.getLogger(__name__)
STEP = "video_variations"
SOURCE = "variation_of"  # in a variation's treatment: {id, letter, chain} of what it varies
NOT_DONE = "Make variations once the director has delivered this video."
WRITING = "Variations of this video are already being written."
ONE_CLIP = "This video has one clip: there's nothing to keep, so make a new video instead."
NOTE = (
    "This video is variation {letter} of {title}, with another {part}: {direction} The "
    "treatment already says it and stands, so don't write it again. Make {clips} again "
    "for it: {note} Keep every other clip and take, then make the cut and watch it."
)
FRESH = ("created_at", "name", "finished_at", "archived_at", "released_draft_id",
         "created_by_id", "director_chat", "forecast_credits", "forecast_basis", "score",
         "score_note", "hidden", "plan_history", "storyboard_history", "settings_log",
         "cast_redraw", "cast_ok")  # what a new video starts without  # fmt: skip


def refusal(db: Session, project: Project) -> str:
    """Why this video can't have variations now, or ""."""
    from app.clip_prompts import newest

    if director.active(db, project):
        return director.RUNNING
    if not director.delivered(director.turns(db, project)) or not director.treatment(db, project):
        return NOT_DONE
    if writing(db, project) is not None:
        return WRITING
    bd = newest(db, project)
    return "" if bd and len(bd.data.get("clips", [])) > 1 else ONE_CLIP


def writing(db: Session, project: Project) -> Job | None:
    return db.scalar(select(Job).where(Job.project_id == project.id,
                                       Job.input["step"].as_string() == STEP,
                                       Job.status.in_(WAITING)).limit(1))  # fmt: skip


def ask(db: Session, user: User, project: Project, count: int, part: str, note: str) -> Job:
    """The one director call that proposes them (on the video, as a director turn is); its
    answer makes them (`save`)."""
    from app import plans, prompts
    from app.clip_prompts import newest
    from app.credits import lock
    from app.enhance import escape, project_context
    from app.routes.jobs import enqueue

    lock(db, Project, project.id)  # two presses at once: the second finds the first's job
    db.refresh(project)
    if why := refusal(db, project):
        db.rollback()
        raise HTTPException(409, why)
    system, context = project_context(db, project, STEP)
    clips = [{"id": c["id"], "seconds": c["seconds"], "shots": [
        {k: s.get(k) for k in ("id", "script_lines", "line", "action")} for s in
        (shot for sc in newest(db, project).data["scenes"] for shot in sc["shots"])
        if s["id"] in c["shot_ids"]]} for c in newest(db, project).data["clips"]]  # fmt: skip
    text = "\n".join([
        context, f"<script>\n{escape(prompts.number_lines(plans.script(db, project).text))}\n"
        "</script>", prompts.treatment_block(director.treatment(db, project)),
        f"<clips>\n{escape(json.dumps(clips, ensure_ascii=False))}\n</clips>",
        f"<part>{part}</part>\n<count>{count}</count>",
        *([f"<note>{escape(note.strip())}</note>"] if note.strip() else [])])  # fmt: skip
    data = {"step": STEP, "project_id": project.id, "system": system, "prompt": text,
            "part": part, "count": count, "note": note.strip()}  # fmt: skip
    from app.routes.freestyles import held_for  # an editor's on a Freestyle video: the owner's

    wait = held_for(db, user, project)  # OK first, as any Freestyle send; then it runs
    return enqueue(db, user, "write-claude", data, project=project, provider="claude", wait=wait)


def save(db: Session, job: Job) -> None:
    """Each variation that fits (its clips are the opening or the closing ones, never all of
    them) becomes a video, and its run starts, waiting on its own direction card."""
    from app.clip_prompts import newest

    source, user = db.get(Project, job.input["project_id"]), db.get(User, job.created_by_id)
    order = [c["id"] for c in newest(db, source).data["clips"]]
    edge = order[0] if job.input["part"] == "hook" else order[-1]
    made = []
    for option in VideoVariations.model_validate(job.output).variations[: job.input["count"]]:
        clips = [c for c in order if c in option.clips]
        if edge in clips and len(clips) < len(order):
            made.append(_make(db, user, source, option, clips, job.input))
    job.output = {**job.output, "made": [v.id for v in made]}
    db.commit()
    for video in made:  # each waits on its own card; one that can't start starts on Make it
        try:
            from app.asks import start_hold

            director.start(db, user, video, hold=start_hold(db, user, video))
        except Exception:
            db.rollback()
            log.exception("variation %s: its run didn't start", video.id)


def source(db: Session, project: Project) -> dict | None:
    """A variation's {id, letter, chain} of the video it varies (`chain`: every video back to
    the first, oldest first), else None."""
    if project.id is None:
        return None
    return db.scalar(select(Job.input[SOURCE]).where(
        Job.project_id == project.id, Job.input["step"].as_string() == "treatment",
        Job.input[SOURCE]["id"].as_integer().is_not(None)).limit(1))  # fmt: skip


def own_ids(db: Session, project: Project) -> set[int]:
    """The videos whose own looks and places are this video's too: itself, and every video a
    variation comes from, back to the first (its cast and places are theirs, kept)."""
    return {project.id, *((source(db, project) or {}).get("chain") or [])}


def using(db: Session, project: Project) -> list[Project]:
    """This video and every live variation made from it, and from those: they all use its own
    looks."""
    rows = db.execute(select(Job.project_id, Job.input[SOURCE]).where(
        Job.workspace_id == project.workspace_id, Job.input["step"].as_string() == "treatment",
        Job.input[SOURCE]["id"].as_integer().is_not(None))).all()  # fmt: skip
    ids = {pid for pid, src in rows if project.id in (src.get("chain") or [])}
    return [project, *db.scalars(select(Project).where(Project.id.in_(ids or {0}),
                                                       Project.archived_at.is_(None)))]  # fmt: skip


def made(db: Session, project: Project) -> dict:
    """The newest proposal on this video: writing, done (the variations it made) or failed."""
    from app.ideas import titles

    job = db.scalar(select(Job).where(Job.project_id == project.id,
                                      Job.input["step"].as_string() == STEP)
                    .order_by(Job.id.desc()).limit(1))  # fmt: skip
    if job is None:
        return {"state": "none", "videos": []}
    said = {JobStatus.needs_owner_approval: "held", JobStatus.failed: "failed",
            JobStatus.cancelled: "declined"}  # fmt: skip
    if job.status != JobStatus.succeeded:
        return {"state": said.get(job.status, "writing"), "videos": []}
    ids = (job.output or {}).get("made") or []
    names = {p.id: p.name for p in db.scalars(select(Project).where(Project.id.in_(ids or [0])))}
    names |= titles(db, ids)
    videos = [{"id": i, "title": names[i]} for i in ids if i in names]
    return {"state": "done" if videos else "unfit", "videos": videos}


def _make(db: Session, user: User, source_: Project, option: VideoVariation, clips: list[str],
          asked: dict) -> Project:  # fmt: skip
    from app import line_change
    from app.ideas import titles

    taken = db.scalar(select(func.count(Job.id)).where(
        Job.input["step"].as_string() == "treatment",
        Job.input[SOURCE]["id"].as_integer() == source_.id)) or 0  # fmt: skip
    title = titles(db, [source_.id]).get(source_.id, source_.name)
    was = source(db, source_)  # a variation of a variation: "… · variation A1", A2, …
    letter = f"{was['letter']}{taken + 1}" if was else chr(ord("A") + taken % 26)
    base = title.rsplit(" · variation ", 1)[0] if was else title
    chain = [*((was or {}).get("chain") or []), source_.id]
    video, frames = _copy(db, user, source_, f"{_short(base)} · variation {letter}", clips)
    line = _new_words(db, user, video, option, clips, asked["note"])
    told, seen = (_newest(db, source_, step) for step in ("treatment", "review_stills"))
    _job(db, user, video, told, {SOURCE: {"id": source_.id, "letter": letter, "chain": chain}},
         {**told.output, asked["part"]: option.direction})  # its new hook or ending  # fmt: skip
    if seen is not None:  # the stills it keeps were looked at: their review stands
        _job(db, user, video, seen, {"seen": {str(frames[int(f)]): file for f, file in
                                              seen.input.get("seen", {}).items()
                                              if int(f) in frames}}, seen.output)  # fmt: skip
    which = " and ".join(c.removeprefix("c") for c in clips)
    note = NOTE.format(letter=letter, title=title, direction=option.direction.rstrip(".") + ".",
                       part="opening" if asked["part"] == "hook" else "ending",
                       clips=f"clip{'s' if len(clips) > 1 else ''} {which}",
                       note=option.note.rstrip(".") + ".")  # fmt: skip
    note += f" {line_change.WROTE.format(n=line)}" if line else ""  # as Change the line says it
    video.director_chat = [{"text": note, "by": user.id, "at": utcnow().isoformat()}]
    db.commit()
    return video


def _copy(db: Session, user: User, src: Project, name: str,
          remade: list[str]) -> tuple[Project, dict[int, int]]:  # fmt: skip
    """The source as a new video in its folder: its settings, words, newest plan, stills,
    clips and takes (the same files), and its host. The `remade` clips keep their prompt and
    no take. Nothing is charged. With each still's frame: the source's id to its copy's."""
    from app.clip_prompts import newest

    keep = {c.key: copy.deepcopy(getattr(src, c.key)) for c in Project.__table__.columns
            if c.key != "id" and c.key not in FRESH}  # fmt: skip
    ok = {k: v for k, v in (src.cast_ok or {}).items() if k != "asked"} or None
    video = Project(**keep, name=name, created_by_id=user.id, cast_ok=ok)
    db.add(video)
    db.flush()
    for v in db.scalars(select(ScriptVersion).where(ScriptVersion.project_id == src.id)):
        db.add(ScriptVersion(project_id=video.id, version=v.version, text=v.text,
                             source=v.source, created_by_id=v.created_by_id))  # fmt: skip
    bd = newest(db, src)
    plan = _row(db, bd, project_id=video.id)
    frames = {f.id: _row(db, f, project_id=video.id, breakdown_id=plan.id).id
              for f in db.scalars(select(StoryboardFrame).where(
                  StoryboardFrame.breakdown_id == bd.id))}  # fmt: skip
    for c in db.scalars(select(ProjectClip).where(ProjectClip.breakdown_id == bd.id)):
        gone = c.clip_id in remade
        row = _row(db, c, project_id=video.id, breakdown_id=plan.id, picked_take_id=None,
                   **({"file_id": None, "approved": False} if gone else {}))  # fmt: skip
        for t in [] if gone else db.scalars(select(ClipTake).where(ClipTake.clip_id == c.id)):
            take = _row(db, t, clip_id=row.id)
            row.picked_take_id = take.id if c.picked_take_id == t.id else row.picked_take_id
    for h in db.scalars(select(HostPiece).where(HostPiece.project_id == src.id)):
        _row(db, h, project_id=video.id)
    db.flush()
    return video, frames


def _short(title: str, most: int = 100) -> str:
    """The title, cut at a word to fit beside " · variation A1" (a name holds 120)."""
    if len(title) <= most:
        return title
    return title[: most - 1].rsplit(" ", 1)[0].rstrip(" ,·—-") + "…"


def _newest(db: Session, project: Project, step: str) -> Job | None:
    return db.scalar(select(Job).where(Job.project_id == project.id,
                                       Job.input["step"].as_string() == step,
                                       Job.status == JobStatus.succeeded)
                     .order_by(Job.id.desc()).limit(1))  # fmt: skip


def _job(db: Session, user: User, video: Project, job: Job, more: dict, output: dict) -> Job:
    """The source's treatment or stills review, as this video's own: free, by the server."""
    now = utcnow()
    return _row(db, job, project_id=video.id, created_by_id=user.id, kind="director_step",
                provider="server", provider_ref=None, credits=0, input={
                "step": job.input["step"], "project_id": video.id, **more}, output=output,
                started_at=now,
                finished_at=now, approved_by_id=None, retry_of_id=None)  # fmt: skip


def _row(db: Session, row, **changed):
    """A copy of `row` with `changed`, added and flushed (its new id)."""
    cols = {c.key: copy.deepcopy(getattr(row, c.key)) for c in type(row).__table__.columns
            if c.key not in ("id", "created_at")}  # fmt: skip
    new = type(row)(**{**cols, **changed})
    db.add(new)
    db.flush()
    return new


def _new_words(db: Session, user: User, video: Project, option: VideoVariation,
               clips: list[str], note: str) -> int | None:  # fmt: skip
    """The owner's own new words for the opening (or closing) line, quoted in their note,
    made as Change the line makes them (`line_change.replan`): a new version of the script
    for this video only, and the plan on it, whose clips saying that line are left stale, so
    their prompts are written again with the new words before their takes (after Make it).
    Else nothing changes. Never on a song or narrated video, whose words time every clip."""
    from app import line_change, plans
    from app.locked_line import QUOTE
    from app.narration import video_kind
    from app.prompts import without_notes

    words, n = option.words.strip(), option.line
    quoted = {(a or b).strip() for a, b in QUOTE.findall(note)}  # only words it puts in quotes
    if not (user.is_owner and words in quoted and video_kind(db, video) == "story"):
        return None
    saying = line_change.clips_of(db, video, n) if n > 0 else []
    if not saying or not set(saying) <= set(clips):  # every clip that says it is made again
        return None
    line = plans.script(db, video).text.splitlines()[n - 1]
    said = line.split(":", 1)[-1].strip()
    heard = without_notes(said)  # as the shot's line reads it (#1490): "[quietly] Nate…"
    found = {"line": n, "old": heard if heard in line else said, "new": words, "clips": saying}
    line_change.replan(db, user, video, found, heard)  # a note before the words stays
    return n
