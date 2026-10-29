"""Song takes (song ads): making them, their state, Try again, Preferred and remove.

One request to the music service (one paid job) makes 2 takes (app/music.py, A2); each take
then gets a free timing read on our server (app/song_timing.py). Takes belong to a script
version, or to one video when it makes its own (rule 31: a published script stays as it
is). In each, one take is Preferred: the first one ready, until someone picks another. Every
failure says why and offers the press that helps (rule 22); nothing failed is charged."""

import logging
import math
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import music
from app.credits import estimate, get_limits, plan_cost
from app.db import utcnow
from app.models.accounts import User
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft
from app.models.songs import SongTake
from app.prompts.check import sung_lines

log = logging.getLogger(__name__)
WAITING = (JobStatus.queued, JobStatus.running)
GUESSED = "Timing guessed: the lines are spread evenly over the song, so check the shot times."
OVER_CAP = "A video of this whole take would go over the {}-credit cap. {}"
SHORTEN = "Shorten the lyrics, then make 2 more."
UNTRIM_IN_USE = (
    "A video uses this trimmed take as its song, and the whole take is over the cap. Pick "
    "another take for that video first."
)
OLDER_WORDS = "This take sings older words. Make 2 takes of the lyrics as they are now."


def price(db: Session, user: User) -> Decimal:
    """One request (2 takes)."""
    return estimate(db, user.workspace_id, "music", Decimal(1))


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


def _request(
    db: Session,
    user: User,
    draft: ScriptDraft,
    project: Project | None,
    free: bool = False,
    kie: float = 0.0,
) -> Job:
    """One request for 2 songs of the version's words as they are now. One that can't be
    made says why (422); past an allowance or budget, enqueue declines with the reason.
    `free`: a request already paid for (it gave back fewer songs than asked). `kie`: the price
    a real song through KIE counts at (0: not a real one)."""
    from app.routes.jobs import enqueue

    try:
        job_input = music.job(draft.text, draft.style_line)
    except music.NotReady as no:
        raise HTTPException(422, str(no)) from None
    job_input = {**job_input, "step": "song_take", **({"free_retry": True} if free else {}),
                 **({"kie": True} if kie else {})}  # fmt: skip
    job = enqueue(db, user, "music", job_input, project=project,
                  provider=music.PROVIDER, units=0 if free else 1)  # fmt: skip
    if kie:  # each real song, for ops/SPEND.md (CLAUDE.md: every paid call is logged)
        made = sum(1 for j in _real_jobs(db))
        log.warning("Real song request: job %s, about $%.2f, %s so far (about $%.2f)", job.id,
                 kie, made, made * kie)  # fmt: skip
    return job


def make(
    db: Session, user: User, draft: ScriptDraft, project: Project | None = None, kie=0.0
) -> list[SongTake]:
    """Make 2 takes (one request) of the version's lyrics and style line. `kie`: a real
    song through KIE (KieSuno sings only those, never a request queued before)."""
    job = _request(db, user, draft, project, kie=kie)
    numbered = select(func.max(SongTake.number)).where(
        SongTake.draft_id == draft.id, SongTake.project_id == (project.id if project else None)
    )
    number = db.scalar(numbered) or 0
    made = [
        SongTake(draft_id=draft.id, project_id=project.id if project else None,
                 number=number + k + 1, track=k, job_id=job.id, created_by_id=user.id,
                 **_sings(draft))
        for k in range(music.TAKES)
    ]  # fmt: skip
    db.add_all(made)
    db.commit()
    return made


def _sings(draft: ScriptDraft) -> dict:
    """What a take sings, as the person wrote it (Suno gets it with song_request's pacing)."""
    return {"lyrics": draft.text.strip(), "style_line": draft.style_line.strip()}


def _by_job(db: Session, column, job: Job) -> list[SongTake]:
    return list(db.scalars(select(SongTake).where(column == job.id)))


def save_take(db: Session, job: Job) -> None:
    """The songs arrived: each take keeps its file and has its timing read (free)."""
    files = job.output["file_ids"]
    for take in _by_job(db, SongTake.job_id, job):
        if take.track < len(files):  # a song the service didn't give stays failed
            take.file_id = files[take.track]
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
    found = _by_job(db, SongTake.timing_job_id, job)
    if not found:
        return
    take = found[0]
    timing = job.output["timing"]
    take.timing, take.seconds = timing, timing["seconds"]
    take.timing_guessed = bool(job.input.get("spread"))
    take.advice = [GUESSED] if take.timing_guessed else advice(timing)
    draft = db.get(ScriptDraft, take.draft_id)
    project = db.get(Project, take.project_id) if take.project_id else None
    usable = not out_of_date(take, draft) and not over_cap(db, take)
    if usable and project:  # a video picks its song by song_take_id, never Preferred
        if project.song_take_id is None:
            project.song_take_id = take.id
    elif usable and preferred(db, draft) is None:
        for t in takes(db, draft):  # an older take's mark goes: it sings old words
            t.preferred = t.id == take.id


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
    if song.status != JobStatus.succeeded or take.file_id is None:
        reason = music.MISSING if song.status == JobStatus.succeeded else song.error or music.FAILED
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
    """Sings other words, or in another style line, than the version has now. Only the sung
    lines count: adding or removing a tag (e.g. [Lip-sync]) changes nothing that's sung."""
    now = (sung_lines(draft.text), draft.style_line.strip())
    return (sung_lines(take.lyrics), take.style_line) != now


def preferred(db: Session, draft: ScriptDraft, project: Project | None = None):
    """The Preferred take of the current words (a new video starts on it), or None."""
    found = [t for t in takes(db, draft, project) if t.preferred and _fits(db, t, draft)]
    return found[0] if found else None


def _fits(db: Session, take: SongTake, draft: ScriptDraft) -> bool:
    """Sings the current words, and its video is under the cap."""
    return not out_of_date(take, draft) and not over_cap(db, take)


def video_credits(db: Session, take: SongTake, seconds: float | None = None) -> Decimal:
    """About what a video of this take (or its first `seconds`) costs, every step at plan:
    the song decides the video's length (spec §1)."""
    length = seconds or take.trim_to or take.seconds or 0
    script = db.get(Script, db.get(ScriptDraft, take.draft_id).script_id)
    return plan_cost(db, script.workspace_id, math.ceil(length), None, roles=0)


def cap(db: Session, take: SongTake) -> int:
    script = db.get(Script, db.get(ScriptDraft, take.draft_id).script_id)
    return get_limits(db, script.workspace_id).per_video_max_credits


def over_cap(db: Session, take: SongTake) -> bool:
    """Its video (the whole take, or the part it's trimmed to) is over the per-video cap."""
    return bool(take.seconds) and video_credits(db, take) > cap(db, take)


def fits_until(db: Session, take: SongTake) -> float | None:
    """The longest start of the song, ending where a section ends, whose video fits under
    the per-video cap ("Use the first 0:55"); None if not even the first section fits."""
    ends = [s["end"] for s in (take.timing or {}).get("sections", [])]
    fits = [e for e in ends if video_credits(db, take, e) <= cap(db, take)]
    return max(fits, default=None)


def lyrics_estimate(db: Session, draft: ScriptDraft) -> tuple[Decimal, int | None]:
    """Before any take: about what a video of the version's lyrics costs, and if that's over
    the per-video cap, how many sung lines to keep so it fits ("Keep the first N lines"; 0
    when not even one does). None when it fits."""
    script = db.get(Script, draft.script_id)
    ws, lines = script.workspace_id, sung_lines(draft.text)
    limit = get_limits(db, ws).per_video_max_credits

    def cost(n: int) -> Decimal:
        return plan_cost(db, ws, music.guessed_seconds(lines[:n]), None, roles=0)

    whole = cost(len(lines))
    if whole <= limit:
        return whole, None
    return whole, max((n for n in range(len(lines)) if cost(n) <= limit), default=0)


def clock(seconds: float) -> str:
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def _usable(db: Session, take: SongTake, draft: ScriptDraft) -> None:
    """A take that can be Preferred or a video's song: current words, under the cap."""
    if out_of_date(take, draft):
        raise HTTPException(409, OLDER_WORDS)
    if over_cap(db, take):
        fits = fits_until(db, take)
        said = f"Press Use the first {clock(fits)} to keep it under." if fits else SHORTEN
        raise HTTPException(409, OVER_CAP.format(cap(db, take), said))


def trim(db: Session, take: SongTake, on: bool) -> None:
    """Use only the start of the take that fits under the cap; `on=False` is its Undo."""
    if on and (not over_cap(db, take) or fits_until(db, take) is None):
        raise HTTPException(409, "This take doesn't need trimming, or no part of it fits.")
    if on:
        take.trim_to = fits_until(db, take)
        db.commit()
        return
    if db.scalar(select(Project.id).where(Project.song_take_id == take.id)):
        raise HTTPException(409, UNTRIM_IN_USE)
    take.trim_to = None
    if take.preferred:  # the whole take is over the cap: the mark goes to the newest that fits
        draft = db.get(ScriptDraft, take.draft_id)
        project = db.get(Project, take.project_id) if take.project_id else None
        take.preferred = False
        fitting = [t for t in takes(db, draft, project) if t.timing and _fits(db, t, draft)]
        if fitting:
            fitting[-1].preferred = True
    db.commit()


def _free_retry(old: Job) -> bool:
    """A request that came back short is asked again free, once: a free request that comes
    back short again is charged like any (QA: free spend outside credits stays capped)."""
    return old.status == JobStatus.succeeded and not old.input.get("free_retry")


def retry_credits(db: Session, take: SongTake) -> Decimal:
    """What Try again on this take costs: nothing for a timing or for a request that came
    back short (already paid), else a new request."""
    if state(db, take)[0] != "failed" or _free_retry(db.get(Job, take.job_id)):
        return Decimal(0)
    script = db.get(Script, db.get(ScriptDraft, take.draft_id).script_id)
    return estimate(db, script.workspace_id, "music", Decimal(1))


def try_again(db: Session, user: User, take: SongTake, kie: float = 0.0) -> None:
    """A failed request is made again for its takes, with the version's lyrics and style
    line as they are now (a refusal says to change them first); charged only if it's made.
    A request that came back with only one song keeps that one and asks again for the other,
    free (it was paid for both). A failed timing is read again (free)."""
    status, _, helps = state(db, take)
    if status == "timing_failed" and helps:
        _time(db, take, user)
        return
    if status != "failed":
        raise HTTPException(409, "This take isn't failed, so there's nothing to try again.")
    draft = db.get(ScriptDraft, take.draft_id)
    project = db.get(Project, take.project_id) if take.project_id else None
    old = db.get(Job, take.job_id)
    short = old.status == JobStatus.succeeded  # it gave fewer songs than asked
    job = _request(db, user, draft, project, free=_free_retry(old), kie=kie)
    for pair in _by_job(db, SongTake.job_id, old):
        if short and pair.file_id is not None:  # a song that did arrive is kept as it is
            continue
        pair.job_id, pair.file_id = job.id, None
        pair.lyrics, pair.style_line = _sings(draft).values()
    db.commit()


BUDGET_USED = "Real songs for this test are used up, so new takes are free stand-in songs."
NO_MORE_REAL = "Real songs for this test are used up, so no more can be made here."


def real_songs(db: Session, settings) -> float:
    """The price a request counts at if it's a real song through KIE (0: not real). Once the
    next one would take the test site's real-song spend past its budget (Reed's test budget),
    it's a free stand-in song instead (the stand-ins are on there; elsewhere a plain 409).
    Two presses at the same moment can both pass and go one request over (about $0.10): not
    worth a lock at a $5 budget."""
    if not settings.kie_suno:
        return 0.0
    made = len(_real_jobs(db))
    if (made + 1) * settings.kie_usd_per_request > settings.kie_budget_usd:
        log.warning("Real songs stopped at the test budget after %s requests.", made)
        if not settings.fake_providers:
            raise HTTPException(409, NO_MORE_REAL)
        return 0.0
    return settings.kie_usd_per_request


def budget_used(db: Session, settings) -> bool:
    """Real songs are on but used up: new takes are stand-in songs (said on the Song step)."""
    if not settings.kie_suno:
        return False
    return (len(_real_jobs(db)) + 1) * settings.kie_usd_per_request > settings.kie_budget_usd


def _real_jobs(db: Session) -> list[Job]:
    jobs = db.scalars(select(Job).where(Job.provider == music.PROVIDER, Job.kind == "music",
                                        Job.status != JobStatus.cancelled))  # fmt: skip
    return [j for j in jobs if j.input.get("kie")]


def spread(db: Session, user: User, take: SongTake) -> None:
    """Timing couldn't be heard: time the lines evenly instead (free, Advice says so)."""
    status, _, helps = state(db, take)
    if status != "timing_failed" or not helps:
        raise HTTPException(409, "Only a take whose timing couldn't be heard can be spread.")
    _time(db, take, user, spread=True)


def prefer(db: Session, take: SongTake) -> int | None:
    """Make this take Preferred; returns the one that was (for Undo). Only a version's own
    takes: a video's song is its song_take_id (PUT /projects/{id}/song)."""
    if take.project_id:
        raise HTTPException(409, "In a video, press Use in this video to make it the song.")
    if state(db, take)[0] != "ready":
        raise HTTPException(409, "Only a finished take can be Preferred.")
    draft = db.get(ScriptDraft, take.draft_id)
    _usable(db, take, draft)
    project = db.get(Project, take.project_id) if take.project_id else None
    was = next((t.id for t in takes(db, draft, project) if t.preferred), None)
    for t in takes(db, draft, project):
        t.preferred = t.id == take.id
    db.commit()
    return was


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
    _usable(db, take, db.get(ScriptDraft, take.draft_id))
    was, project.song_take_id = project.song_take_id, take.id
    db.commit()
    return was


IN_USE = "This take is the video's song. Pick another take for the video first."
PREFERRED = "This is the Preferred take. Make another take Preferred first, then remove this one."


def remove(db: Session, take: SongTake) -> None:
    """Remove a take (Undo brings it back). Never the Preferred one (flows S4)."""
    if state(db, take)[0] in ("making", "timing"):
        raise HTTPException(409, "This take is still being made. Remove it once it's done.")
    if db.scalar(select(Project.id).where(Project.song_take_id == take.id)):
        raise HTTPException(409, IN_USE)
    if take.preferred:
        raise HTTPException(409, PREFERRED)
    take.deleted_at = utcnow()
    db.commit()


def restore(db: Session, take: SongTake) -> None:
    """Undo a remove."""
    take.deleted_at = None
    db.commit()
