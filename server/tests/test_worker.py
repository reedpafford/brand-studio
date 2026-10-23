from decimal import Decimal

import pytest

from app.models.accounts import User
from app.models.jobs import JobStatus, Usage
from app.providers.fake import FakeProvider
from app.routes.jobs import enqueue
from app.worker import UNSURE, check_running, recover, run_once


@pytest.fixture
def user(owner, db):
    return db.query(User).one()


def _run(db, provider, job):
    run_once(db, {"fake": provider})
    db.refresh(job)
    return job


def test_job_runs_to_success_and_records_usage(db, user):
    fake = FakeProvider(polls_until_done=1)
    job = enqueue(db, user, "video", {"seconds": 5})
    assert _run(db, fake, job).status == JobStatus.running  # submitted
    assert _run(db, fake, job).status == JobStatus.running  # still working
    assert _run(db, fake, job).status == JobStatus.succeeded
    assert job.output == {"url": "fake://fake-1"}
    usage = db.query(Usage).one()
    assert (usage.units, usage.unit, usage.cost_usd) == (5, "second", Decimal("0.5140"))


def test_provider_failure_marks_job_failed_without_retry(db, user):
    fake = FakeProvider(fail=True)
    job = enqueue(db, user, "video", {})
    _run(db, fake, job)
    assert _run(db, fake, job).status == JobStatus.failed
    assert job.error == "fake failure" and len(fake.submitted) == 1


def test_network_error_while_checking_is_retried(db, user):
    fake = FakeProvider()
    job = enqueue(db, user, "video", {})
    _run(db, fake, job)
    fake.network_errors_on_poll = 1
    assert _run(db, fake, job).status == JobStatus.running
    assert _run(db, fake, job).status == JobStatus.succeeded


def test_paid_submit_is_never_retried(db, user):
    fake = FakeProvider(paid=True)
    fake.network_errors_on_submit = 1
    job = enqueue(db, user, "video", {})
    assert _run(db, fake, job).status == JobStatus.failed
    assert job.error == UNSURE
    _run(db, fake, job)
    assert fake.submitted == {}


def test_free_submit_retries_network_errors_on_later_ticks(db, user):
    fake = FakeProvider(paid=False)
    fake.network_errors_on_submit = 2
    job = enqueue(db, user, "write", {})
    assert _run(db, fake, job).status == JobStatus.queued
    assert _run(db, fake, job).status == JobStatus.queued
    assert _run(db, fake, job).status == JobStatus.running
    assert job.attempts == 3


def test_restart_rechecks_running_jobs_and_fails_unsure_paid_ones(db, user):
    fake = FakeProvider()
    handed_over = enqueue(db, user, "video", {})
    _run(db, fake, handed_over)
    crashed = enqueue(db, user, "video", {})
    crashed.status = JobStatus.running  # crash between marking running and submitting
    db.commit()
    recover(db, {"fake": fake})
    db.refresh(crashed)
    assert crashed.status == JobStatus.failed and crashed.error == UNSURE
    assert _run(db, fake, handed_over).status == JobStatus.succeeded


def test_two_workers_record_usage_once(app, db, user):
    fake = FakeProvider()
    job = enqueue(db, user, "video", {})
    _run(db, fake, job)
    real_poll = fake.poll

    def poll_while_other_worker_finishes(ref):
        result = real_poll(ref)
        fake.poll = real_poll
        with app.state.sessionmaker() as other:
            check_running(other, {"fake": fake})  # finishes first
        return result

    fake.poll = poll_while_other_worker_finishes
    check_running(db, {"fake": fake})
    assert db.query(Usage).count() == 1
