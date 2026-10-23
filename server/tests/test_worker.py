from decimal import Decimal

import pytest

from app.models.accounts import User
from app.models.jobs import JobStatus, Usage
from app.providers.fake import FakeProvider
from app.routes.jobs import enqueue
from app.worker import FAILED, UNKNOWN, UNSURE, check_running, recover, run_once


@pytest.fixture
def user(owner, db):
    return db.query(User).one()


def _run(db, provider, job):
    run_once(db, {"fake": provider})
    db.refresh(job)
    return job


def test_job_runs_to_success_and_records_usage(db, user):
    fake = FakeProvider(polls_until_done=1)
    job = enqueue(db, user, "video-480p", {"seconds": 5})
    assert _run(db, fake, job).status == JobStatus.running  # submitted
    assert _run(db, fake, job).status == JobStatus.running  # still working
    assert _run(db, fake, job).status == JobStatus.succeeded
    assert job.output == {"url": "fake://fake-1"}
    usage = db.query(Usage).one()
    assert (usage.units, usage.unit, usage.cost_usd) == (5, "second", Decimal("0.5140"))


def test_provider_failure_marks_job_failed_without_retry(db, user):
    fake = FakeProvider(fail=True)
    job = enqueue(db, user, "video-480p", {})
    _run(db, fake, job)
    assert _run(db, fake, job).status == JobStatus.failed
    assert job.error == FAILED and job.error_detail == "fake failure"
    assert len(fake.submitted) == 1


def test_network_error_while_checking_is_retried(db, user):
    fake = FakeProvider()
    job = enqueue(db, user, "video-480p", {})
    _run(db, fake, job)
    fake.network_errors_on_poll = 1
    assert _run(db, fake, job).status == JobStatus.running
    assert _run(db, fake, job).status == JobStatus.succeeded


def test_paid_submit_is_never_retried(db, user):
    fake = FakeProvider(paid=True)
    fake.network_errors_on_submit = 1
    job = enqueue(db, user, "video-480p", {})
    assert _run(db, fake, job).status == JobStatus.failed
    assert job.error == UNSURE
    _run(db, fake, job)
    assert fake.submitted == {}


def test_free_submit_retries_network_errors_on_later_ticks(db, user):
    fake = FakeProvider(paid=False)
    fake.network_errors_on_submit = 2
    job = enqueue(db, user, "video-480p", {})
    assert _run(db, fake, job).status == JobStatus.queued
    assert _run(db, fake, job).status == JobStatus.queued
    assert _run(db, fake, job).status == JobStatus.running
    assert job.attempts == 3


def test_restart_rechecks_running_jobs_and_fails_unsure_paid_ones(db, user):
    fake = FakeProvider()
    handed_over = enqueue(db, user, "video-480p", {})
    _run(db, fake, handed_over)
    crashed = enqueue(db, user, "video-480p", {})
    crashed.status = JobStatus.running  # crash between marking running and submitting
    db.commit()
    recover(db, {"fake": fake})
    db.refresh(crashed)
    assert crashed.status == JobStatus.failed and crashed.error == UNSURE
    assert _run(db, fake, handed_over).status == JobStatus.succeeded


def test_two_workers_record_usage_once(app, db, user):
    fake = FakeProvider()
    job = enqueue(db, user, "video-480p", {})
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


def test_unknown_provider_fails_the_job_and_others_still_run(db, user):
    bad = enqueue(db, user, "video-480p", {}, provider="nope")
    good = enqueue(db, user, "video-480p", {})
    fake = FakeProvider()
    _run(db, fake, bad)
    db.refresh(good)
    assert (bad.status, bad.error) == (JobStatus.failed, UNKNOWN)
    assert good.status == JobStatus.running


def test_unknown_provider_on_restart_fails_instead_of_crashing(db, user):
    job = enqueue(db, user, "video-480p", {}, provider="nope")
    job.status = JobStatus.running
    db.commit()
    recover(db, {"fake": FakeProvider()})
    db.refresh(job)
    assert job.status == JobStatus.failed


def _claude(handler):
    import httpx2 as httpx
    from anthropic import DefaultHttpxClient

    from app.claude import make_client
    from app.providers.claude import ClaudeProvider

    client = make_client("k", DefaultHttpxClient(transport=httpx.MockTransport(handler)))
    return {"claude": ClaudeProvider("k", client)}


def _claude_job(db, user):
    return enqueue(
        db,
        user,
        "write-claude",
        {"step": "enhance", "system": ["Rules."], "prompt": "<script>1| Hi</script>"},
        provider="claude",
    )


def test_claude_job_end_to_end_records_a_refusal_cost(db, user):
    import httpx2 as httpx

    from tests.helpers import claude_stream

    def refuse(request):
        body = claude_stream(
            "",
            "refusal",
            {"type": "refusal", "category": "cyber"},
            {"input_tokens": 1000, "output_tokens": 0},
        )
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    job = _claude_job(db, user)
    run_once(db, _claude(refuse))
    db.refresh(job)
    assert (job.status, job.provider_ref, job.error) == (JobStatus.failed, "sync", FAILED)
    assert "declined" in job.error_detail
    usage = db.query(Usage).one()  # refused answers are billed, so they're recorded
    assert (usage.unit, usage.cost_usd) == ("call", Decimal("0.0040"))


def test_claude_busy_is_retried_and_lost_contact_is_unsure(db, user):
    import httpx2 as httpx

    calls = []

    def busy_then_drop(request):
        calls.append(request)
        if len(calls) <= 3:  # the SDK itself tries 3 times
            busy = {"type": "error", "error": {"type": "overloaded_error"}}
            return httpx.Response(529, json=busy)
        raise httpx.ConnectError("dropped")

    job = _claude_job(db, user)
    providers = _claude(busy_then_drop)
    run_once(db, providers)
    db.refresh(job)
    assert job.status == JobStatus.queued and job.attempts == 1  # busy: not started, retry
    run_once(db, providers)
    db.refresh(job)
    assert (job.status, job.error) == (JobStatus.failed, UNSURE)
    assert db.query(Usage).count() == 0


def test_claude_answers_lose_stray_control_characters():
    from app.providers.claude import clean

    answer = {"clips": [{"prompt": "Shot 1 | 0\ty1 s.\nKeep: x\x00", "seconds": 5}]}
    assert clean(answer) == {"clips": [{"prompt": "Shot 1 | 0y1 s.\nKeep: x", "seconds": 5}]}
