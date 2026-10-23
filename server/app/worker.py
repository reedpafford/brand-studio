"""Background worker: a separate process that polls the jobs table. Run: `python -m app.worker`.

Rules
- Network errors while checking on work are retried (checking is free).
- A paid submit is never retried automatically: if we can't tell whether the provider
  started (and charged for) the work, the job fails with a note and a person decides.
- After a restart, running jobs with a provider reference are simply checked again.
"""

import logging
import time

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db import make_sessionmaker, utcnow
from app.models.jobs import Job, JobStatus, Usage
from app.providers import NetworkError, Provider, get_providers

log = logging.getLogger("worker")
MAX_SUBMIT_TRIES = 3
UNSURE = "Lost contact while starting paid work. Check the provider before retrying."


def _move(db: Session, job: Job, old: JobStatus, new: JobStatus, **values) -> bool:
    """Change status only if nobody else did first (safe with several workers)."""
    done = db.execute(
        update(Job).where(Job.id == job.id, Job.status == old).values(status=new, **values)
    )
    return done.rowcount == 1


def recover(db: Session, providers: dict[str, Provider]) -> None:
    """On boot: jobs marked running but never handed to the provider."""
    for job in db.scalars(
        select(Job).where(Job.status == JobStatus.running, Job.provider_ref.is_(None))
    ):
        if providers[job.provider].paid:
            _move(db, job, JobStatus.running, JobStatus.failed, error=UNSURE, finished_at=utcnow())
        else:
            _move(db, job, JobStatus.running, JobStatus.queued)
    db.commit()


def check_running(db: Session, providers: dict[str, Provider]) -> None:
    for job in db.scalars(
        select(Job).where(Job.status == JobStatus.running, Job.provider_ref.is_not(None))
    ).all():
        try:
            result = providers[job.provider].poll(job.provider_ref)
        except NetworkError:
            log.warning("job %s: network error while checking; will retry", job.id)
            continue
        if result.state == "running":
            continue
        new = JobStatus.succeeded if result.state == "succeeded" else JobStatus.failed
        moved = _move(
            db,
            job,
            JobStatus.running,
            new,
            output=result.output,
            error=result.error,
            finished_at=utcnow(),
        )
        if moved:  # record usage once, in the same transaction as the status change
            db.add_all(
                Usage(
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    provider=job.provider,
                    kind=job.kind,
                    units=item.units,
                    unit=item.unit,
                    cost_usd=item.cost_usd,
                )
                for item in result.usage
            )
        db.commit()


def start_next(db: Session, providers: dict[str, Provider]) -> bool:
    """Hand the oldest queued job to its provider. Returns False if the queue is empty."""
    job = db.scalar(select(Job).where(Job.status == JobStatus.queued).order_by(Job.id).limit(1))
    if not job:
        return False
    if not _move(
        db, job, JobStatus.queued, JobStatus.running, attempts=job.attempts + 1, started_at=utcnow()
    ):
        db.rollback()
        return True  # another worker took it
    db.commit()  # marked running before the call, so a crash mid-call is visible on boot
    provider = providers[job.provider]
    try:
        ref = provider.submit(job.kind, job.input)
    except NetworkError:
        db.refresh(job)
        if provider.paid:
            _move(db, job, JobStatus.running, JobStatus.failed, error=UNSURE, finished_at=utcnow())
        elif job.attempts < MAX_SUBMIT_TRIES:
            _move(db, job, JobStatus.running, JobStatus.queued)
        else:
            _move(db, job, JobStatus.running, JobStatus.failed, error="Provider unreachable.")
    except Exception as exc:  # noqa: BLE001 - any other provider error fails the job
        _move(db, job, JobStatus.running, JobStatus.failed, error=str(exc)[:2000])
    else:
        db.execute(update(Job).where(Job.id == job.id).values(provider_ref=ref))
    db.commit()
    return True


def run_once(db: Session, providers: dict[str, Provider]) -> None:
    check_running(db, providers)
    # At most one start per queued job per tick, so a requeued job waits for the next tick.
    queued = db.scalar(select(func.count(Job.id)).where(Job.status == JobStatus.queued))
    for _ in range(queued):
        if not start_next(db, providers):
            break


def main() -> None:  # pragma: no cover - the loop itself is trivial
    from app.settings import get_settings

    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    providers = get_providers()
    sessions = make_sessionmaker(settings.database_url)
    with sessions() as db:
        recover(db, providers)
    while True:
        with sessions() as db:
            run_once(db, providers)
        time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()
