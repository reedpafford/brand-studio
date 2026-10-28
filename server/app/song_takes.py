"""Song takes (song ads): making them, their state, Try again, Preferred and delete.

A take is one music job (paid, about 1.5 credits), then a free timing read on our server
(app/song_timing.py). Takes belong to a script version, or to one video when it makes its own
(rule 31: a published script stays as it is). In each, one take is Preferred: the first one
ready, until someone picks another. Every failure says why and offers the press that helps
(rule 22); nothing failed is charged."""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import music
from app.credits import estimate
from app.db import utcnow
from app.models.accounts import User
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.models.songs import SongTake

WAITING = (JobStatus.queued, JobStatus.running)
GUESSED = "Timing guessed: the lines are spread evenly over the song, so check the shot times."
OLDER_WORDS = "This take sings older words. Make 2 takes of the lyrics as they are now."


def price(db: Session, user: User, count: int) -> Decimal:
    job = music.SERVICES[music.DEFAULT].job("la", "")  # the price doesn't depend on the words
    return estimate(db, user.workspace_id, "music", Decimal(count), job)


def takes(db: Session, draft: ScriptDraft, project: Project | None = None) -> list[SongTake]:
    """A version's own takes, or one video's, oldest first (removed ones left out)."""
    return list(
        db.scalars(
            select(SongTake)
            .where(
                SongTake.draft_id == draft.id,
                SongTake.project_id == (project.id if project else None),
                SongTake.deleted_at.is_(None),
            )
            .order_by(SongTake.id)
        )
    )


def make(
    db: Session, user: User, draft: ScriptDraft, count: int, project: Project | None = None
) -> list[SongTake]:
    """Queue `count` takes of the version's lyrics and style line. A request that can't be
    made says why (422); past an allowance or budget, enqueue declines with the reason."""
    from app.routes.jobs import enqueue

    service = music.SERVICES[music.DEFAULT]
    try:
        job_input = service.job(draft.text, draft.style_line)
    except music.NotReady as no:
        raise HTTPException(422, str(no)) from None
    each = price(db, user, 1)
    numbered = select(func.max(SongTake.number)).where(
        SongTake.draft_id == draft.id, SongTake.project_id == (project.id if project else None)
    )
    number = db.scalar(numbered) or 0
    made = []
    for k in range(count):  # the later takes are checked together with the first
        job = enqueue(db, user, "music", {**job_input, "step": "song_take"},
                      project=project, provider=service.provider,
                      hold=each * (count - k - 1))  # fmt: skip
        take = SongTake(draft_id=draft.id, project_id=project.id if project else None,
                        number=number + k + 1, job_id=job.id, created_by_id=user.id,
                        **_sings(job_input))  # fmt: skip
        db.add(take)
        db.commit()
        made.append(take)
    return made


def _sings(job_input: dict) -> dict:
    return {"lyrics": job_input["input"]["lyrics"], "style_line": job_input["input"]["prompt"]}


def _by_job(db: Session, column, job: Job) -> SongTake | None:
    return db.scalar(select(SongTake).where(column == job.id))


def save_take(db: Session, job: Job) -> None:
    """A song arrived: keep its file and read its timing (free, on our server)."""
    take = _by_job(db, SongTake.job_id, job)
    if take is None:
        return
    take.file_id = job.output["file_ids"][0]
    _time(db, take, db.get(User, job.created_by_id))


def _time(db: Session, take: SongTake, user: User, spread: bool = False) -> None:
    """Read the take's timing (free). `spread`: don't listen for the words, share the lines
    evenly over the song ("Use timing spread evenly" when reading failed)."""
    from app.models.files import StoredFile
    from app.routes.jobs import enqueue

    song = db.get(StoredFile, take.file_id)
    job = enqueue(db, user, "song_timing",
                  {"song_key": song.key, "lyrics": take.lyrics, "step": "song_timing",
                   "spread": spread},
                  units=0, provider="local", prepaid=True)  # fmt: skip
    take.timing_job_id = job.id
    db.commit()


def save_timing(db: Session, job: Job) -> None:
    """The take's timing is read: it's ready, and Preferred if its group has none yet."""
    take = _by_job(db, SongTake.timing_job_id, job)
    if take is None:
        return
    timing = job.output["timing"]
    take.timing, take.seconds = timing, timing["seconds"]
    take.timing_guessed = bool(job.input.get("spread"))
    take.advice = [GUESSED] if take.timing_guessed else advice(timing)
    draft = db.get(ScriptDraft, take.draft_id)
    project = db.get(Project, take.project_id) if take.project_id else None
    current = not out_of_date(take, draft)
    if current and not any(t.preferred for t in takes(db, draft, project)):
        take.preferred = True
    if current and project and project.song_take_id is None:  # a video's first song
        project.song_take_id = take.id


def advice(timing: dict) -> list[str]:
    """What the timing heard that differs from the lyrics. Advice only: it never blocks."""
    said = []
    for n, line in enumerate(timing["lines"], 1):
        if line["heard"] == 0:
            said.append(f"Timing guessed: line {n} (“{line['text']}”) wasn't heard in this take.")
        elif line.get("times_sung", 1) > 1:
            said.append(f"Line {n} (“{line['text']}”) is sung {line['times_sung']} times.")
    return said


def state(db: Session, take: SongTake) -> tuple[str, str | None, bool]:
    """(status, plain reason, whether Try again can help). Status: making, timing, ready,
    failed (the song wasn't made) or timing_failed."""
    song = db.get(Job, take.job_id)
    if song.status in WAITING:
        return "making", None, False
    if song.status != JobStatus.succeeded:
        reason = song.error or music.FAILED
        if take.project_id and reason == music.REFUSED:  # a video can't change the words
            reason = music.REFUSED_IN_VIDEO
        return "failed", reason, True
    timing = db.get(Job, take.timing_job_id) if take.timing_job_id else None
    if take.timing is not None:
        return "ready", None, False
    if timing is None or timing.status in WAITING:
        return "timing", None, False
    reason = timing.error or music.TIMING_FAILED
    return "timing_failed", reason, reason != music.TIMING_UNREADABLE


def out_of_date(take: SongTake, draft: ScriptDraft) -> bool:
    """Sings other words, or in another style line, than the version has now."""
    now = (music.clean(draft.text).text, draft.style_line.strip())
    return (take.lyrics, take.style_line) != now


def try_again(db: Session, user: User, take: SongTake) -> None:
    """A failed song is asked for again with the version's lyrics and style line as they are
    now (a refusal says to change them first); charged only if it's made. A failed timing is
    read again (free)."""
    from app.routes.jobs import enqueue

    status, _, helps = state(db, take)
    if status == "timing_failed" and helps:
        _time(db, take, user)
        return
    if status != "failed":
        raise HTTPException(409, "This take isn't failed, so there's nothing to try again.")
    draft = db.get(ScriptDraft, take.draft_id)
    service = music.SERVICES[music.DEFAULT]
    try:
        job_input = service.job(draft.text, draft.style_line)
    except music.NotReady as no:
        raise HTTPException(422, str(no)) from None
    project = db.get(Project, take.project_id) if take.project_id else None
    job = enqueue(db, user, "music", {**job_input, "step": "song_take"}, project=project,
                  provider=service.provider)  # fmt: skip
    take.job_id = job.id
    take.lyrics, take.style_line = _sings(job_input).values()
    db.commit()


def spread(db: Session, user: User, take: SongTake) -> None:
    """Timing couldn't be heard: time the lines evenly instead (free, Advice says so)."""
    status, _, helps = state(db, take)
    if status != "timing_failed" or not helps:
        raise HTTPException(409, "Only a take whose timing couldn't be heard can be spread.")
    _time(db, take, user, spread=True)


def prefer(db: Session, take: SongTake) -> int | None:
    """Make this take Preferred; returns the one that was (for Undo)."""
    if state(db, take)[0] != "ready":
        raise HTTPException(409, "Only a finished take can be Preferred.")
    draft = db.get(ScriptDraft, take.draft_id)
    if out_of_date(take, draft):
        raise HTTPException(409, OLDER_WORDS)
    project = db.get(Project, take.project_id) if take.project_id else None
    was = next((t.id for t in takes(db, draft, project) if t.preferred), None)
    for t in takes(db, draft, project):
        t.preferred = t.id == take.id
    db.commit()
    return was


def preferred(db: Session, draft: ScriptDraft) -> SongTake | None:
    """The version's Preferred take of its current words: a new video starts on it."""
    found = [t for t in takes(db, draft) if t.preferred and not out_of_date(t, draft)]
    return found[0] if found else None


def for_video(db: Session, project: Project) -> list[SongTake]:
    """The takes a video can use: its version's, then its own."""
    draft = db.get(ScriptDraft, project.script_draft_id)
    return [*takes(db, draft), *takes(db, draft, project)]


def use_in_video(db: Session, project: Project, take: SongTake) -> int | None:
    """Time this video to `take` (its version's or its own); returns the one before (Undo).
    Shots keep their lines and Sung marks; their times follow the new take for free once
    song breakdowns land (V2a)."""
    if take.id not in {t.id for t in for_video(db, project)}:
        raise HTTPException(404, "No such take for this video.")
    if state(db, take)[0] != "ready":
        raise HTTPException(409, "Only a finished take can be this video's song.")
    if out_of_date(take, db.get(ScriptDraft, take.draft_id)):
        raise HTTPException(409, OLDER_WORDS)
    was, project.song_take_id = project.song_take_id, take.id
    db.commit()
    return was


IN_USE = "This take is the video's song. Pick another take for the video first."


def remove(db: Session, take: SongTake) -> None:
    """Remove a take (Undo brings it back). A removed Preferred hands the mark to the newest
    other finished take, so a video always has one to time to when there is one."""
    if state(db, take)[0] in ("making", "timing"):
        raise HTTPException(409, "This take is still being made. Remove it once it's done.")
    if db.scalar(select(Project.id).where(Project.song_take_id == take.id)):
        raise HTTPException(409, IN_USE)
    take.deleted_at = utcnow()
    if take.preferred:
        draft = db.get(ScriptDraft, take.draft_id)
        project = db.get(Project, take.project_id) if take.project_id else None
        ready = [t for t in takes(db, draft, project)
                 if t.id != take.id and t.timing and not out_of_date(t, draft)]  # fmt: skip
        if ready:
            ready[-1].preferred = True
    db.commit()


def restore(db: Session, take: SongTake) -> None:
    """Undo a remove; if it was Preferred, it is again."""
    draft = db.get(ScriptDraft, take.draft_id)
    project = db.get(Project, take.project_id) if take.project_id else None
    take.deleted_at = None
    if take.preferred:
        for t in takes(db, draft, project):
            t.preferred = t.id == take.id
    db.commit()
