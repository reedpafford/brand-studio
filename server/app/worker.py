"""Background worker: a separate process that polls the jobs table. Run: `python -m app.worker`.

Rules
- Network errors while checking on work are retried (checking is free).
- A paid submit is never retried automatically: if we can't tell whether the provider
  started (and charged for) the work, the job fails with a note and a person decides.
- After a restart, running jobs with a provider reference are simply checked again.
- `only` (BS_WORKER_PROVIDERS) splits the queue: a worker handles only those providers' jobs
  and leaves the rest to another worker (e.g. slow local reel prep in a worker of its own).
"""

import base64
import hashlib
import logging
import time
import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.credits import usd_to_credits
from app.db import make_sessionmaker, utcnow
from app.filetypes import ALLOWED_TYPES, matches
from app.models.files import StoredFile
from app.models.jobs import Job, JobStatus, Usage
from app.providers import NetworkError, NotStarted, Provider, Result, get_providers
from app.references import fit_image
from app.steps import save_step_result
from app.storage import LocalStorage, Storage

log = logging.getLogger("worker")
MAX_SUBMIT_TRIES = 3
# Messages everyone sees. Raw provider text can hold balances or URLs, so it goes only
# into `error_detail` (owner-only) and the log.
UNSURE = "Lost contact while starting paid work. Check the provider before retrying."
FAILED = "The service couldn't finish this. Ask the owner for details."
EXTENSIONS = {"video/mp4": ".mp4", "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
# Provider output links expire (Replicate: 1 hour); stop retrying downloads after that.
DOWNLOAD_GIVE_UP = timedelta(hours=1)
UNKNOWN = "This job names a service we don't have."


def _move(db: Session, job: Job, old: JobStatus, new: JobStatus, **values) -> bool:
    """Change status only if nobody else did first (safe with several workers)."""
    done = db.execute(
        update(Job).where(Job.id == job.id, Job.status == old).values(status=new, **values)
    )
    return done.rowcount == 1


def _fail(db: Session, job: Job, message: str, detail: str = "") -> None:
    if detail:
        log.warning("job %s failed: %s", job.id, detail)
    _move(
        db,
        job,
        JobStatus.running,
        JobStatus.failed,
        error=message,
        error_detail=detail[:2000],
        finished_at=utcnow(),
    )


def _actual_credits(job: Job, result: Result) -> Decimal:
    """Real cost converted to credits; the queue-time estimate if the provider didn't say."""
    if not result.usage:
        return job.credits
    return usd_to_credits(sum((i.cost_usd for i in result.usage), Decimal(0)))


def _mine(query, only: set[str] | None):
    return query.where(Job.provider.in_(only)) if only else query


def recover(db: Session, providers: dict[str, Provider], only: set[str] | None = None) -> None:
    """On boot: jobs marked running but never handed to the provider."""
    query = select(Job).where(Job.status == JobStatus.running, Job.provider_ref.is_(None))
    for job in db.scalars(_mine(query, only)).all():
        if job.provider not in providers:
            _fail(db, job, UNKNOWN, job.provider)
        elif providers[job.provider].paid:
            _fail(db, job, UNSURE)
        else:
            _move(db, job, JobStatus.running, JobStatus.queued)
    db.commit()


def _download(job: Job, provider: Provider, urls: list[str], storage: Storage) -> list[StoredFile]:
    """Copy the provider's output files into our storage (they expire on the provider)."""
    files = []
    for url in urls:
        data, content_type = provider.fetch(url)
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
    db: Session, job: Job, provider: Provider, result: Result, storage: Storage | None
) -> bool:
    """Record a finished job: outputs, status, real credits and usage, then the step's own
    saving (e.g. Enhance suggestions). Returns False to try again on the next tick."""
    files: list[StoredFile] = []
    if result.state == "succeeded" and result.files:
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
        output=result.output,
        error=FAILED if new == JobStatus.failed else "",
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
        db.add_all(
            Usage(
                workspace_id=job.workspace_id,
                job_id=job.id,
                provider=job.provider,
                kind=job.kind,
                units=item.units,
                unit=item.unit,
                cost_usd=item.cost_usd,
                estimated=item.estimated,
            )
            for item in result.usage
        )
        if new == JobStatus.succeeded and job.input.get("step"):
            db.refresh(job)
            save_step_result(db, job)
    db.commit()
    return True


def check_running(
    db: Session,
    providers: dict[str, Provider],
    storage: Storage | None = None,
    only: set[str] | None = None,
) -> None:
    query = select(Job).where(Job.status == JobStatus.running, Job.provider_ref.is_not(None))
    for job in db.scalars(_mine(query, only)).all():
        if job.provider not in providers:
            _fail(db, job, UNKNOWN, job.provider)
            db.commit()
            continue
        try:
            result = providers[job.provider].poll(job.provider_ref)
        except NetworkError:
            log.warning("job %s: network error while checking; will retry", job.id)
            continue
        except Exception as exc:  # noqa: BLE001 - a broken answer fails the job, not the worker
            _fail(db, job, FAILED, repr(exc))
            db.commit()
            continue
        if result.state == "running":
            continue
        if not _finish(db, job, providers[job.provider], result, storage):
            continue


def _stored(db: Session, storage: Storage | None, job: Job, file_id: int) -> StoredFile:
    stored = db.get(StoredFile, file_id)
    if storage is None or not stored or stored.workspace_id != job.workspace_id:
        raise RuntimeError(f"Reference file {file_id} is missing.")
    return stored


def _files_as_data(db: Session, storage: Storage | None, job: Job, provider=None) -> dict:
    """The job's input with its file ids (job.input["files"]) turned into data URLs. With
    `fit_images_to`, reference images are scaled down to that long side; `exact_file_ids`
    (brand screens, products) stay lossless. Files too big for a data URL (a reel's video,
    job.input["uploads"]) go up through the provider's own file upload first."""
    payload = dict(job.input)
    for key, ids in (job.input.get("uploads") or {}).items():
        urls = []
        for file_id in ids:
            stored = _stored(db, storage, job, file_id)
            try:
                urls.append(provider.upload(storage.get(stored.key), stored.content_type))
            except NetworkError as exc:  # nothing was started, so trying again is safe
                raise NotStarted(f"Upload failed: {exc!r}") from exc
        payload["input"] = {**payload["input"], key: urls}
    max_side = job.input.get("fit_images_to")
    exact = set(job.input.get("exact_file_ids") or [])
    for key, ids in (job.input.get("files") or {}).items():
        urls = []
        for file_id in ids:
            stored = _stored(db, storage, job, file_id)
            data, content_type = storage.get(stored.key), stored.content_type
            if max_side and key == "reference_images":
                data, content_type = fit_image(data, content_type, max_side, file_id in exact)
            urls.append(f"data:{content_type};base64,{base64.b64encode(data).decode()}")
        payload["input"] = {**payload["input"], key: urls}
    return payload


def start_next(
    db: Session,
    providers: dict[str, Provider],
    storage: Storage | None = None,
    allow_paid: bool = True,
    only: set[str] | None = None,
) -> bool:
    """Hand the oldest queued job to its provider. Returns False if the queue is empty.
    With `allow_paid` off (generation switched off), paid providers' jobs are left queued."""
    query = _mine(select(Job).where(Job.status == JobStatus.queued), only)
    if not allow_paid:
        paid = [name for name, p in providers.items() if p.paid]
        query = query.where(Job.provider.not_in(paid))
    job = db.scalar(query.order_by(Job.id).limit(1))
    if not job:
        return False
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
    if getattr(provider, "sync", False):  # answers in the same call (e.g. Claude)
        return _run_sync(db, job, provider, storage)
    try:
        ref = provider.submit(job.kind, _files_as_data(db, storage, job, provider))
    except NotStarted as exc:
        db.refresh(job)
        if job.attempts < MAX_SUBMIT_TRIES:
            _move(db, job, JobStatus.running, JobStatus.queued)
        else:
            _fail(db, job, FAILED, repr(exc))
    except NetworkError:
        db.refresh(job)
        if provider.paid:
            _fail(db, job, UNSURE)
        elif job.attempts < MAX_SUBMIT_TRIES:
            _move(db, job, JobStatus.running, JobStatus.queued)
        else:
            _fail(db, job, FAILED, "Provider unreachable.")
    except Exception as exc:  # noqa: BLE001 - any other provider error fails the job
        _fail(db, job, FAILED, repr(exc))
    else:
        db.execute(update(Job).where(Job.id == job.id).values(provider_ref=ref))
    db.commit()
    return True


def _run_sync(db: Session, job: Job, provider: Provider, storage: Storage | None) -> bool:
    try:
        result = provider.run(job.kind, job.input)
    except NotStarted as exc:
        db.refresh(job)
        if job.attempts < MAX_SUBMIT_TRIES:
            _move(db, job, JobStatus.running, JobStatus.queued)
        else:
            _fail(db, job, FAILED, repr(exc))
        db.commit()
        return True
    except NetworkError:
        _fail(db, job, UNSURE)
        db.commit()
        return True
    except Exception as exc:  # noqa: BLE001 - any other provider error fails the job
        _fail(db, job, FAILED, repr(exc))
        db.commit()
        return True
    db.execute(update(Job).where(Job.id == job.id).values(provider_ref="sync"))
    _finish(db, job, provider, result, storage)
    return True


def run_once(
    db: Session,
    providers: dict[str, Provider],
    storage: Storage | None = None,
    allow_paid: bool = True,
    only: set[str] | None = None,
) -> None:
    check_running(db, providers, storage, only)
    # At most one start per queued job per tick, so a requeued job waits for the next tick.
    queued = db.scalar(
        _mine(select(func.count(Job.id)).where(Job.status == JobStatus.queued), only)
    )
    for _ in range(queued):
        if not start_next(db, providers, storage, allow_paid, only):
            break


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
    while True:
        try:
            with sessions() as db:
                run_once(db, providers, storage, settings.generation_enabled, only)
        except Exception:  # keep the worker alive through e.g. a database hiccup
            log.exception("worker tick failed; trying again next tick")
        time.sleep(settings.worker_poll_seconds)


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
