"""Background worker: a separate process that polls the jobs table. Run: `python -m app.worker`.

Rules
- Network errors while checking on work are retried (checking is free).
- A paid submit is never retried automatically: if we can't tell whether the provider
  started (and charged for) the work, the job fails with a note and a person decides.
- After a restart, running jobs with a provider reference are simply checked again; one cut
  off mid-answer (Claude, or our own server's local work) goes back in the queue once.
- `only` (BS_WORKER_PROVIDERS) splits the queue: a worker handles only those providers' jobs
  and leaves the rest to another worker. Live, Claude (answers in the call, for minutes), the
  image and video service (handed over, then checked on) and reel prep each have their own.
"""

import base64
import hashlib
import logging
import os
import signal
import threading
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import cast_gate, director, hidden, live, locked_line, music, screen_figures
from app.clip_takes import still_wanted
from app.credits import FREE_LANES, USD_PER_CREDIT, usd_to_credits
from app.db import make_sessionmaker, utcnow
from app.filetypes import ALLOWED_TYPES, matches
from app.models.accounts import User
from app.models.files import StoredFile
from app.models.jobs import Job, JobStatus, Usage
from app.providers import (
    STAND_IN,
    UNSAVED,
    NetworkError,
    NotStarted,
    Provider,
    Result,
    UsageItem,
    get_providers,
)
from app.purge import purge_deleted, purge_uploads
from app.references import fit_image
from app.steps import explain, recheck, save_step_result, step_failed
from app.storage import LocalStorage, Storage

log = logging.getLogger("worker")
MAX_SUBMIT_TRIES = 3
# Messages everyone sees. Raw provider text can hold balances or URLs, so it goes only
# into `error_detail` (owner-only) and the log.
UNSURE = "Lost contact while this was starting, so it was stopped. Nothing was charged; try again."
CHECK = "Lost contact while starting paid work: check the provider before retrying."  # owner
RESTARTED = "The server restarted while this was being written. Nothing was charged; try again."
FAILED = "The service couldn't finish this. Nothing was charged; try again."  # never counted
EXTENSIONS = {"video/mp4": ".mp4", "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
              "audio/mpeg": ".mp3", "audio/wav": ".wav"}  # fmt: skip
# Provider output links expire (Replicate: 1 hour); stop retrying downloads after that.
DOWNLOAD_GIVE_UP = timedelta(hours=1)
UNKNOWN = "This job names a service we don't have."
# How long the provider may take once it has the work (Replicate: a still takes seconds to a
# minute, a video take a few minutes); past it the job fails and is cancelled there.
# A song takes a minute or two (Starpop's music stalled for good: never wait past this).
LIMITS = {"image": timedelta(minutes=15), "video": timedelta(minutes=45),
          "music": timedelta(minutes=15), "voice_split": timedelta(minutes=10)}  # fmt: skip
LIMIT = timedelta(hours=1)  # anything else, e.g. a reel's local prep
SLOW = "{} didn't finish this in time, so it was stopped. It may still be charged; try again."
SLOW_FREE = "{} didn't finish this in time. Nothing was charged; try again."  # our own server's
# A provider that can't stop work (HeyGen) gets one more limit's time, then fails without an
# automatic remake: the first may still finish there and be billed (FABLE B9).
LATE = ("{} didn't finish this in time. It can't be stopped there and may still finish and be "
        "charged, so it wasn't made again on its own: making it again could charge "
        "twice.")  # fmt: skip
# "Busy" (a 429) when starting: nothing started. Back in the queue after a wait that grows, not
# counted as a try, and nothing more goes to that provider this tick (FABLE B3: 47 takes in
# one burst used up all their tries in one tick). Still busy after the last wait: it fails.
BUSY_WAITS = (10, 30, 90, 180, 300, 300)  # seconds: about 15 minutes in all
BUSY = "{} stayed too busy to start this. Nothing was charged; try again later."
# "Busy" while checking on running work: it is still running (FABLE B4); that job is checked
# less often, and nothing more is asked of that provider this tick.
CHECK_WAIT = timedelta(seconds=30)
_check_after: dict[int, datetime] = {}  # job id: when to check it again (this process only)
DAY = 24 * 60 * 60


def _move(db: Session, job: Job, old: JobStatus, new: JobStatus, *where, **values) -> bool:
    """Change status only if nobody else did first (safe with several workers); `where`: and
    only while these hold."""
    done = db.execute(
        update(Job).where(Job.id == job.id, Job.status == old, *where).values(status=new, **values)
    )
    if done.rowcount == 1:
        live.note(db, job.project_id, new)
    return done.rowcount == 1


def _stop(db: Session, job: Job) -> bool:
    """A job its video's release stopped (cancelled, or still running if it was mid-call):
    done now. Only once, so its cost is recorded once."""
    done = db.execute(
        update(Job)
        .where(
            Job.id == job.id,
            Job.status.in_((JobStatus.running, JobStatus.cancelled)),
            Job.finished_at.is_(None),
        )
        .values(status=JobStatus.cancelled, finished_at=utcnow())
    )
    if done.rowcount == 1:
        live.note(db, job.project_id, JobStatus.cancelled)
    return done.rowcount == 1


def _plain(job: Job, detail: str) -> str:
    """What everyone sees when a job fails; song steps say their own reason (rule 22)."""
    if job.kind == "music":
        return music.failure(detail, (job.input.get("input") or {}).get("style", ""))
    if job.kind == "narration_timing":  # app/narration.py
        from app import narration

        if detail.startswith("ValueError"):
            return narration.TIMING_UNREADABLE
        return narration.TIMING_FAILED
    if job.kind == "song_timing":  # a ValueError: the file itself (app/song_timing.py)
        if detail.startswith("TooLong"):
            return music.TIMING_TOO_LONG
        return music.TIMING_UNREADABLE if detail.startswith("ValueError") else music.TIMING_FAILED
    from app import song_directions
    from app.clip_takes import REFUSED_SAID, invalid, refusal, refused_how

    if refusal(detail):  # its content refused (video 345: E006): never "try again"
        return REFUSED_SAID.format(refused_how(detail))
    if reason := invalid(detail):  # refused as sent: trying the same again won't help
        return f"The service refused this request as invalid, so nothing was charged: {reason}."
    return song_directions.failure(detail) or FAILED


def _fail(db: Session, job: Job, message: str, detail: str = "") -> None:
    """The job failed before the provider answered (a refusal, a 400, a restart): what waits on
    it is told, as when the provider says it failed (audit 6 Nov: else a take stayed
    "watching", a check "checking" and a run "running"), but nothing is tried again on its
    own: it may already have been charged, or would be refused again."""
    if detail:
        log.warning("job %s failed: %s", job.id, detail)
    if _move(
        db,
        job,
        JobStatus.running,
        JobStatus.failed,
        error=message,
        error_detail=detail[:2000],
        finished_at=utcnow(),
    ):
        db.commit()  # the failure is kept whatever the handlers below do
        db.refresh(job)
        try:  # what waits on it is told; never let that stop the worker (it runs at boot too)
            if job.input.get("step"):
                step_failed(db, job, again=False)
            else:
                explain(db, job)
            db.commit()
        except Exception:
            db.rollback()
            log.exception("job %s: telling what waits on it failed", job.id)
        _then(db, job, None)


def _actual_credits(job: Job, result: Result) -> Decimal:
    """Real cost converted to credits, but never more than the price shown before the press
    (the queue-time estimate): a shown price is at least what's charged (live test: 3 shown,
    3.35 charged). The dollars are recorded as they were."""
    if not result.usage:
        return job.credits
    spent = sum((_seconds(job, i).cost_usd for i in result.usage), Decimal(0))
    return min(job.credits, usd_to_credits(spent))


def _seconds(job: Job, item: UsageItem) -> UsageItem:
    """An Omni edit sends no length (it keeps its take's): when the provider reports none,
    it's its source take's `seconds`, never the model's longest (QA on #1488)."""
    asked = job.input or {}
    seconds = asked.get("seconds") if asked.get("edit") else None
    if not (seconds and item.estimated and item.unit == "second" and item.units):
        return item
    each = item.cost_usd / item.units
    return UsageItem(Decimal(seconds), item.unit, each * seconds, True, item.tokens)


def _usage(job: Job, provider: Provider, result: Result, made: bool = False) -> list[Usage]:
    """What the job cost, for Usage. A paid job whose provider didn't say (image and video
    models, the reel watch) is recorded from its credits, marked estimated, so every charge
    is listed. `made`: the provider finished it, though saving it failed (it was paid)."""
    items = [
        Usage(workspace_id=job.workspace_id, job_id=job.id, provider=job.provider, kind=job.kind,
              units=i.units, unit=i.unit, cost_usd=i.cost_usd, estimated=i.estimated,
              **_tokens(i.tokens))
        for i in (_seconds(job, u) for u in result.usage)
    ]  # fmt: skip
    if not items and provider.paid and job.credits and (made or result.state == "succeeded"):
        items.append(
            Usage(workspace_id=job.workspace_id, job_id=job.id, provider=job.provider,
                  kind=job.kind, units=Decimal(1), unit="job",
                  cost_usd=(job.credits * USD_PER_CREDIT).quantize(Decimal("0.0001")),
                  estimated=True)
        )  # fmt: skip
    return items


def _tokens(counts: dict | None) -> dict:
    """A Claude call's counts as Usage's columns; nothing for any other provider."""
    if not counts:
        return {}
    names = {"input": "input_tokens", "output": "output_tokens", "cache_read": "cache_read_tokens",
             "cache_write": "cache_write_tokens", "images": "images"}  # fmt: skip
    return {column: counts.get(key) for key, column in names.items()}


def _mine(query, only: set[str] | None):
    return query.where(Job.provider.in_(only)) if only else query


RESTART = "restarted"  # in a job's input: put back in the queue after a restart (P1)


def recover(db: Session, providers: dict[str, Provider], only: set[str] | None = None) -> None:
    """On boot: jobs marked running but never handed to the provider. One cut off mid-answer
    by a restart (a deploy) goes back in the queue once: its answer is kept in the same commit
    as its status (`_finish`), so nothing of it was kept and nothing is applied twice. The
    call cut off may have been billed, so a Claude job costs at most one more run of itself
    (clip prompts in parts ask every part again); each is logged so it can go in SPEND.md.
    Cut off a second time, it fails as before."""
    query = select(Job).where(Job.status == JobStatus.running, Job.provider_ref.is_(None))
    for job in db.scalars(_mine(query, only)).all():
        if job.provider not in providers:
            _fail(db, job, UNKNOWN, job.provider)
        elif getattr(providers[job.provider], "sync", False):  # cut off mid-answer by a restart
            if job.input.get("discard"):  # its video was released meanwhile: never asked again
                _stop(db, job)
            elif job.input.get(RESTART):
                _fail(db, job, RESTARTED)
            elif _move(db, job, JobStatus.running, JobStatus.queued,
                       input={**job.input, RESTART: True}):  # fmt: skip
                log.warning("job %s (%s, %s, video %s) was cut off by a restart: queued again",
                            job.id, job.kind, job.provider, job.project_id)  # fmt: skip
        elif providers[job.provider].paid:
            _fail(db, job, UNSURE, CHECK)
        else:
            _move(db, job, JobStatus.running, JobStatus.queued)
    db.commit()


def _download(job: Job, provider: Provider, urls: list[str], storage: Storage) -> list[StoredFile]:
    """Copy the provider's output files into our storage (they expire on the provider)."""
    files = []
    for url in urls:
        data, content_type = provider.fetch(url)
        content_type = {"audio/x-wav": "audio/wav", "audio/wave": "audio/wav"}.get(
            content_type, content_type)  # a WAV by any of its names (Demucs's voice)  # fmt: skip
        if content_type not in ALLOWED_TYPES or not matches(content_type, data[:16]):
            raise RuntimeError(f"Output {url} isn't an allowed file ({content_type!r}).")
        key = f"{job.workspace_id}/{uuid.uuid4().hex}"
        storage.put(key, data)
        files.append(
            StoredFile(
                workspace_id=job.workspace_id,
                key=key,
                filename=f"job-{job.id}-{len(files) + 1}{EXTENSIONS.get(content_type, '')}",
                content_type=content_type,
                size=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
            )
        )
    return files


def _finish(
    db: Session,
    job: Job,
    provider: Provider,
    result: Result,
    storage: Storage | None,
    again: bool = True,
) -> bool:
    """Record a finished job: outputs, status, real credits and usage, then the step's own
    saving (e.g. Enhance suggestions). Returns False to try again on the next tick. `again`
    off: a failed step isn't tried again on its own."""
    if job.input.get("discard"):  # its video was released or archived while it ran: nothing
        moved = _stop(db, job)
        if moved:  # is downloaded or kept, but what it cost the owner is still listed
            db.add_all(_usage(job, provider, result))  # dollars only; no credits
        db.commit()
        return True
    files: list[StoredFile] = []
    made = result.state == "succeeded"  # by the provider (paid), whether or not we save it
    if made and result.files:
        try:
            files = _download(job, provider, result.files, storage)
        except NetworkError as exc:
            if utcnow() - (job.started_at or utcnow()) < DOWNLOAD_GIVE_UP:
                log.warning("job %s: download failed; will retry", job.id)
                return False
            result.state, result.error = "failed", f"Gave up downloading: {exc!r}"
        except Exception as exc:  # noqa: BLE001 - paid work is done: keep its usage
            result.state, result.error = "failed", f"Saving the output failed: {exc!r}"
    new = JobStatus.succeeded if result.state == "succeeded" else JobStatus.failed
    moved = _move(
        db,
        job,
        JobStatus.running,
        new,
        credits=_actual_credits(job, result) if new == JobStatus.succeeded else job.credits,
        output={**(result.output or {}), UNSAVED: True}
        if made and new != JobStatus.succeeded
        else result.output,
        error=_plain(job, result.error) if new == JobStatus.failed else "",
        error_detail=result.error[:2000],
        finished_at=utcnow(),
    )
    if result.error:
        log.warning("job %s: provider said: %s", job.id, result.error)
    if moved:  # record usage once, in the same transaction as the status change
        db.add_all(files)
        if files:
            db.flush()
            output = {**(result.output or {}), "file_ids": [f.id for f in files]}
            db.execute(update(Job).where(Job.id == job.id).values(output=output))
        db.add_all(_usage(job, provider, result, made))
        if new == JobStatus.succeeded and job.input.get("step"):
            db.refresh(job)
            save_step_result(db, job)
        elif new == JobStatus.failed and job.input.get("step"):
            db.refresh(job)
            step_failed(db, job, again=again)
    db.commit()
    if moved:
        _then(db, job, storage)
    return True


def _then(db: Session, job: Job, storage: Storage | None) -> None:
    """The director's turn acted on, or its next turn woken, after the job's own result is
    kept, so nothing here can undo it."""
    if not job.project_id:
        return
    try:
        director.after(db, job, storage or _storage())
        locked_line.after(db, job, storage or _storage())  # S3-14: a choice's take is in
        db.commit()
    except Exception:  # never let the director break the worker
        db.rollback()
        log.exception("job %s: the director couldn't go on", job.id)


def _storage() -> Storage:
    from app.settings import get_settings

    return LocalStorage(get_settings().storage_dir)


def check_running(
    db: Session,
    providers: dict[str, Provider],
    storage: Storage | None = None,
    only: set[str] | None = None,
) -> None:
    stopped = (Job.status == JobStatus.cancelled) & Job.finished_at.is_(None)  # by a release
    query = select(Job).where(
        (Job.status == JobStatus.running) | stopped, Job.provider_ref.is_not(None)
    )
    busy: set[str] = set()  # providers that said "busy" this tick: not asked again in it
    for job in db.scalars(_mine(query, only)).all():
        if job.provider not in providers:
            _stop(db, job) if job.input.get("discard") else _fail(db, job, UNKNOWN, job.provider)
            db.commit()
            continue
        if job.provider in busy or _check_after.get(job.id, datetime.min) > utcnow():
            result = Result("running")  # asked less often while its provider is busy
        else:
            try:
                result = providers[job.provider].poll(job.provider_ref)
                _check_after.pop(job.id, None)
            except NetworkError:
                log.warning("job %s: network error while checking; will retry", job.id)
                result = Result("running")
            except NotStarted:  # busy (a 429) while it renders: it's still running
                log.warning("job %s: %s busy while checking; will retry", job.id, job.provider)
                busy.add(job.provider)
                _check_after[job.id] = utcnow() + CHECK_WAIT
                result = Result("running")
            except Exception as exc:  # noqa: BLE001 - a broken answer fails the job, not the worker
                _stop(db, job) if job.input.get("discard") else _fail(db, job, FAILED, repr(exc))
                db.commit()
                continue
        if result.state == "running":
            if _overdue(job, providers[job.provider]):  # it keeps saying "running", or checking
                _check_after.pop(job.id, None)  # keeps failing
                _time_out(db, job, providers[job.provider])
            continue
        if not _finish(db, job, providers[job.provider], result, storage):
            continue


def _unstoppable(provider: Provider) -> bool:
    """Paid work it can't cancel (HeyGen): it may go on, and be billed, after we give up."""
    return provider.paid and not hasattr(provider, "cancel")


def _limit(job: Job, provider: Provider) -> timedelta:
    limit = LIMITS.get(job.kind, LIMIT)
    return 2 * limit if _unstoppable(provider) else limit  # checked once more, later (B9)


def _overdue(job: Job, provider: Provider) -> bool:
    started = job.started_at or job.created_at
    return utcnow() - started > _limit(job, provider)


def _service(job: Job) -> str:
    return {"image": "The image service", "video": "The video service",
            "music": "The music service"}.get(job.kind, "The service")  # fmt: skip


def _time_out(db: Session, job: Job, provider: Provider) -> None:
    """Still running past its time limit (the provider keeps saying "running", or checking
    keeps failing): cancelled at the provider if it can, then failed like any failure (its
    step's own handling), said plainly (Producer, 2026-10-28). A paid one may still be billed,
    so its price is listed as an estimate; one it can't cancel isn't made again on its own (B9)."""
    try:
        getattr(provider, "cancel", lambda ref: None)(job.provider_ref)
    except Exception:  # noqa: BLE001 - cancelling is a courtesy; the job fails either way
        log.warning("job %s: couldn't cancel it at the provider", job.id, exc_info=True)
    stoppable = not _unstoppable(provider)
    said = f"No answer within {_limit(job, provider)}." + ("" if stoppable else " Not cancellable.")
    # Replicate: "If you cancel a run for an official model, you may still be charged"
    # (replicate.com/docs/topics/billing): listed as an estimate, never under-counted
    maybe = provider.paid and job.credits and not (job.provider_ref or "").startswith(STAND_IN)
    paid = [UsageItem(Decimal(1), "job", (job.credits * USD_PER_CREDIT).quantize(Decimal("0.0001")),
                      estimated=True)] if maybe else []  # fmt: skip
    _finish(db, job, provider, Result("failed", error=said, usage=paid), None, again=stoppable)
    message = LATE if not stoppable else SLOW if provider.paid else SLOW_FREE
    db.execute(update(Job).where(Job.id == job.id, Job.status == JobStatus.failed)
               .values(error=message.format(_service(job))))  # fmt: skip
    db.commit()


def _stored(db: Session, storage: Storage | None, job: Job, file_id: int) -> StoredFile:
    stored = db.get(StoredFile, file_id)
    if storage is None or not stored or stored.workspace_id != job.workspace_id:
        raise RuntimeError(f"Reference file {file_id} is missing.")
    return stored


def _files_as_data(db: Session, storage: Storage | None, job: Job) -> dict:
    """The job's input with its file ids (job.input["files"]) turned into data URLs. With
    `fit_images_to`, reference images are scaled down to that long side; `exact_file_ids`
    (brand screens, products) stay lossless."""
    payload = dict(job.input)
    max_side = job.input.get("fit_images_to")
    exact = set(job.input.get("exact_file_ids") or [])
    for key, ids in (job.input.get("files") or {}).items():
        urls = []
        for file_id in ids:
            stored = _stored(db, storage, job, file_id)
            data, content_type = storage.get(stored.key), stored.content_type
            if figure := (job.input.get("screen_figures") or {}).get(str(file_id)):
                data, content_type = screen_figures.draw(data, figure), "image/png"
            if max_side and key in ("reference_images", "image"):
                data, content_type = fit_image(data, content_type, max_side, file_id in exact)
            urls.append(f"data:{content_type};base64,{base64.b64encode(data).decode()}")
        one = key in ("image", "audio", "video")  # P-Video's and MMAudio's single files
        payload["input"] = {**payload.get("input", {}), key: urls[0] if one else urls}
    for file_id in job.input.get("clip_frames") or []:  # the director's eyes on a clip, after
        stored = _stored(db, storage, job, file_id)  # its pictures (director._eyes)
        frames = [f"data:image/jpeg;base64,{base64.b64encode(f).decode()}"
                  for f in video_frames(storage.get(stored.key), director.FRAMES)]  # fmt: skip
        given = payload.get("input", {})
        payload["input"] = {**given, "reference_images": given.get("reference_images", []) + frames}
    return payload


def video_frames(video: bytes, count: int) -> list[bytes]:
    """`count` JPEG frames of a video, evenly spaced (ffmpeg, free): a clip the director is
    given (director._eyes)."""
    import subprocess
    import tempfile
    from pathlib import Path

    from app import deep_watch

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "clip.mp4"
        src.write_bytes(video)
        length = deep_watch.probe(src)["length"]
        out = []
        for n in range(count):
            dst = Path(tmp) / f"{n}.jpg"
            at = length * (n + 0.5) / count
            subprocess.run(  # noqa: S603
                ["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", str(src),  # noqa: S607
                 "-frames:v", "1", "-q:v", "4", str(dst)], timeout=60, check=True)  # fmt: skip
            out.append(dst.read_bytes())
        return out


def start_next(
    db: Session,
    providers: dict[str, Provider],
    storage: Storage | None = None,
    allow_paid: bool = True,
    only: set[str] | None = None,
    busy: set[str] | None = None,
) -> bool:
    """Hand the oldest queued job to its provider. Returns False if the queue is empty.
    With `allow_paid` off (generation switched off), paid providers' jobs are left queued.
    `busy`: providers that said "busy" this tick, left alone until the next; added to."""
    query = _mine(select(Job).where(Job.status == JobStatus.queued), only)
    if not allow_paid:
        paid = [name for name, p in providers.items() if p.paid]
        query = query.where(Job.provider.not_in(paid))
    if busy:
        query = query.where(Job.provider.not_in(busy))
    now = utcnow().isoformat()  # an automatic retry after a busy service waits a moment (P3)
    job = next((j for j in db.scalars(query.order_by(Job.id))
                if (j.input or {}).get("wait_until", "") <= now), None)  # fmt: skip
    if not job:
        return False
    if job.auto and not still_wanted(db, job):  # its clip changed while it waited: uncharged
        _move(db, job, JobStatus.queued, JobStatus.cancelled, finished_at=utcnow())
        db.commit()
        return True
    if cast_gate.job_paused(db, job):  # its cast or places changed since: never an old look
        _move(db, job, JobStatus.queued, JobStatus.cancelled, finished_at=utcnow(),
              error=cast_gate.PAUSED)  # fmt: skip
        db.commit()
        return True
    if not _move(
        db, job, JobStatus.queued, JobStatus.running, attempts=job.attempts + 1, started_at=utcnow()
    ):
        db.rollback()
        return True  # another worker took it
    db.commit()  # marked running before the call, so a crash mid-call is visible on boot
    provider = providers.get(job.provider)
    if provider is None:
        _fail(db, job, UNKNOWN, job.provider)
        db.commit()
        return True
    if provider.paid and not _within_real_budget(db, job):
        return True
    if getattr(provider, "sync", False):  # answers in the same call (e.g. Claude)
        return _run_sync(db, job, provider, storage, busy)
    try:
        ref = provider.submit(job.kind, _files_as_data(db, storage, job))
    except NotStarted as exc:
        _busy(db, job, exc, busy)
    except NetworkError:
        db.refresh(job)
        if provider.paid:
            _fail(db, job, UNSURE, CHECK)
        elif job.attempts < MAX_SUBMIT_TRIES:
            _move(db, job, JobStatus.running, JobStatus.queued)
        else:
            _fail(db, job, FAILED, "Provider unreachable.")
    except Exception as exc:  # noqa: BLE001 - any other provider error fails the job; a
        _fail(db, job, _plain(job, repr(exc)), repr(exc))  # refusal (4xx) says its reason
    else:
        db.execute(update(Job).where(Job.id == job.id).values(provider_ref=ref))
    db.commit()
    return True


def _within_real_budget(db: Session, job: Job) -> bool:
    """On the test site's real lane: the cap again, right before the call (a queued job, a
    run's next step or a retry can't slip past it). Past it, the job fails uncharged."""
    from app.credits import real_budget_refusal, real_capped, real_spent
    from app.settings import get_settings

    settings = get_settings()
    maker = db.get(User, job.created_by_id) if job.created_by_id else None
    if no := real_budget_refusal(db, settings, job.provider, job.credits,
                                 bool(maker and maker.is_owner)):  # fmt: skip
        _fail(db, job, no, "real budget refused")
        db.commit()
        return False
    if real_capped(settings):  # for the Producer during Reed's test: spent so far
        log.info("real budget: $%.2f of $%.2f since %s", real_spent(db, settings),
                 settings.real_budget_usd, settings.real_budget_since or "the start")  # fmt: skip
    return True


def _busy(db: Session, job: Job, exc: NotStarted, busy: set[str] | None) -> None:
    """The provider said "busy" (nothing started): queued again after the next of BUSY_WAITS,
    not counted as a try; nothing more goes to it this tick. Past the last wait: failed."""
    if busy is not None:
        busy.add(job.provider)
    db.refresh(job)
    times = job.input.get("busy", 0)
    if times >= len(BUSY_WAITS):
        _fail(db, job, BUSY.format(_service(job)), repr(exc))
        return
    later = (utcnow() + timedelta(seconds=BUSY_WAITS[times])).isoformat()
    unstopped = Job.input["ended"].as_string().is_(None)  # a Stop since: kept (director._write)
    if not _move(db, job, JobStatus.running, JobStatus.queued, unstopped,
                 attempts=job.attempts - 1,
                 input={**job.input, "busy": times + 1, "wait_until": later}):  # fmt: skip
        _move(db, job, JobStatus.running, JobStatus.queued, attempts=job.attempts - 1)


def _run_sync(db: Session, job: Job, provider: Provider, storage: Storage | None,
              busy: set[str] | None = None) -> bool:  # fmt: skip
    if job.input.get("step") == director.STEP and not director.refresh(db, job):
        _move(db, job, JobStatus.running, JobStatus.cancelled, finished_at=utcnow())
        db.commit()  # stopped before its call: no call is made, so nothing is charged
        return True
    if job.input.get("step") == "treatment":
        director.read_notes(db, job)  # a brief sent as its turn was answered: read now
    ref = "sync" if provider.paid or job.provider in FREE_LANES else f"{STAND_IN}sync"
    sent = update(Job).where(Job.id == job.id).values(provider_ref=ref)  # a stand-in's: marked
    try:  # a Claude check that looks at a picture gets it as data, like other providers
        result = provider.run(job.kind, _files_as_data(db, storage, job))
        result = recheck(job.input, result, lambda again: provider.run(job.kind, again))
    except NotStarted as exc:
        _busy(db, job, exc, busy)
        db.commit()
        return True
    except NetworkError:  # it left, then the connection dropped or timed out: maybe charged
        db.execute(sent)  # so it counts against the real budget (the audit: it counted $0)
        _fail(db, job, UNSURE, CHECK)
        db.commit()
        return True
    except Exception as exc:  # noqa: BLE001 - any other provider error fails the job; a
        _fail(db, job, _plain(job, repr(exc)), repr(exc))  # refusal (4xx) or ours: not charged
        db.commit()
        return True
    db.execute(sent)
    _finish(db, job, provider, result, storage)
    return True


def run_once(
    db: Session,
    providers: dict[str, Provider],
    storage: Storage | None = None,
    allow_paid: bool = True,
    only: set[str] | None = None,
) -> None:
    hidden.see(db)  # the worker works on every job, a freestyle's hidden video's too
    check_running(db, providers, storage, only)
    # At most one start per queued job per tick; a job its provider called busy waits its
    # `wait_until`, and that provider gets nothing more this tick.
    queued = db.scalar(
        _mine(select(func.count(Job.id)).where(Job.status == JobStatus.queued), only)
    )
    busy: set[str] = set()
    for _ in range(queued):
        if STOP.is_set() or not start_next(db, providers, storage, allow_paid, only, busy):
            break  # stopping: the next start waits for the new worker
    if only and "claude" not in only:
        return  # the director's turns are Claude's: only that lane's worker sweeps
    try:  # a director run whose work ended any other way (failed, cancelled) goes on
        director.sweep(db, storage)
        db.commit()
    except Exception:  # never let the director break the worker
        db.rollback()
        log.exception("the director's sweep failed")


def main() -> None:  # pragma: no cover - the loop itself is trivial
    from app.settings import check_production, get_settings

    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    check_production(settings)
    storage = LocalStorage(settings.storage_dir)
    providers = get_providers(settings, storage)
    only = set(settings.worker_providers) or None
    if (only is None or "local" in only) and not settings.fake_providers:
        warm_speech_model()
    sessions = make_sessionmaker(settings.database_url)
    with sessions() as db:
        recover(db, providers, only)
    if settings.fake_providers:
        log.warning("Using stand-in providers (BS_FAKE_PROVIDERS): nothing real is generated.")
    elif not settings.generation_enabled:
        log.warning("Generation is switched off (BS_GENERATION_ENABLED): paid jobs stay queued.")
    tidied = None  # the reel worker removes long-deleted scripts at start and once a day

    def tick() -> None:
        nonlocal tidied
        if (only is None or "local" in only) and (tidied is None or time.time() - tidied > DAY):
            tidied = time.time()
            try:
                with sessions() as db:
                    purge_deleted(db, storage)
                    purge_uploads(db, storage)  # Bulk create videos never used
            except Exception:  # housekeeping never stops the worker
                log.exception("removing long-deleted scripts failed; trying again tomorrow")
        lane(only)

    def lane(jobs: set[str] | None) -> None:
        try:
            with sessions() as db:
                run_once(db, providers, storage, settings.generation_enabled, jobs)
        except Exception:  # keep the worker alive through e.g. a database hiccup
            log.exception("worker tick failed; trying again next tick")

    # Local work (takes' listens, cuts) runs in more than one lane, each on its own share of
    # the CPUs: a long video's 47 listens took about 55 minutes one at a time (S1).
    lanes = max(1, settings.local_workers) if only is None or "local" in only else 1
    serve([tick] + [lambda: lane({"local"})] * (lanes - 1), settings.worker_poll_seconds)


STOP = threading.Event()


def serve(ticks: list, poll: float) -> None:
    """Run each lane's ticks (the first here, the rest in threads) until the worker is asked to
    stop (SIGTERM: a deploy restarting it). The job in hand always finishes first, so a deploy
    never cuts a Claude call off mid-answer (QA-Live 6: two clip-prompts runs lost to
    deploys); compose waits for it (stop_grace_period)."""

    def stop(*_) -> None:
        log.info("stopping after the job in hand")
        STOP.set()

    def loop(tick, cpus: list[int] | None) -> None:
        if cpus:  # what the lane starts (whisper, ffmpeg) inherits its share and sizes to it
            os.sched_setaffinity(0, cpus)
        while not STOP.is_set():
            tick()
            STOP.wait(poll)

    signal.signal(signal.SIGTERM, stop)
    cpus = shares(len(ticks))  # read before any lane is pinned
    others = [threading.Thread(target=loop, args=(t, c), name=f"lane-{n}")
              for n, (t, c) in enumerate(zip(ticks, cpus, strict=True)) if n]  # fmt: skip
    for t in others:
        t.start()
    try:
        loop(ticks[0], cpus[0])
    finally:  # Ctrl-C, or this lane dying: the others finish their job in hand and stop too
        STOP.set()
        for t in others:
            t.join()


def shares(lanes: int) -> list[list[int] | None]:
    """Each lane's share of the CPUs this process may use (Linux), so two lanes' whisper reads
    and ffmpeg encodes never crowd onto the same cores (app/whisper.threads sizes to it). None
    (no pinning: each sees every CPU) for one lane, off Linux, or with under 2 CPUs a lane: on
    the 2-CPU server, pinning would halve a lone cut render's speed."""
    if lanes < 2 or not hasattr(os, "sched_setaffinity"):
        return [None] * lanes
    cpus = sorted(os.sched_getaffinity(0))
    if len(cpus) < 2 * lanes:
        return [None] * lanes
    return [cpus[n::lanes] for n in range(lanes)]


def warm_speech_model() -> None:  # pragma: no cover - downloads ~460 MB once
    """Fetch the reel transcription model before the first job, so its download never eats
    into a job's time limit. A failure only means the first job downloads it."""
    from app.reel import warm

    try:
        warm()
    except Exception:  # noqa: BLE001 - e.g. offline; reel prep still works, just slower first
        log.warning("Couldn't load the speech model now; the first reel will.", exc_info=True)


if __name__ == "__main__":
    main()
