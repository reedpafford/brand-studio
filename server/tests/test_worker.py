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

    answer = {"clips": [{"prompt": "Shot\x1b 1 | 0–1 s.\tA\r\nKeep: x\x00", "seconds": 5}]}
    assert clean(answer) == {"clips": [{"prompt": "Shot 1 | 0–1 s.\tA\r\nKeep: x", "seconds": 5}]}


def test_a_claude_check_sees_its_picture(app, db, editor):
    """A Claude job with files gets them as image blocks before its prompt, scaled down."""
    from app.models.accounts import User
    from app.models.jobs import Job
    from tests.conftest import upload
    from tests.test_enhance import FakeClaude, _run

    me = db.query(User).filter_by(email=editor.get("/auth/me").json()["email"]).one()
    job = Job(workspace_id=me.workspace_id, created_by_id=me.id, kind="write-claude",
              provider="claude", input={"step": "change", "system": ["Check it."],
              "prompt": "Does it fit?", "files": {"reference_images": [upload(editor)]},
              "fit_images_to": 64})  # fmt: skip
    db.add(job)
    db.commit()
    fake = FakeClaude({"prompt": "fits"})
    _run(app, db, fake)
    content = fake.requests[0]["messages"][0]["content"]
    assert [b["type"] for b in content] == ["image", "text"]
    assert content[1]["text"] == "Does it fit?"
    assert content[0]["source"]["type"] == "base64"
    assert db.get(Job, job.id).output == {"prompt": "fits"}  # answered (no clip to save it on)


def test_a_job_running_past_its_time_limit_fails_plainly_uncharged_and_is_cancelled(db, user):
    """Producer, 2026-10-28: a running job had no time limit, so "Drawing…" could last
    forever with nothing coming back. Past it, the job is cancelled at the provider and fails
    like any failure, said plainly; a failed job isn't counted against anyone's credits."""
    from datetime import timedelta

    from app.credits import COUNTED
    from app.worker import LIMITS

    fake = FakeProvider(polls_until_done=10**6)  # says "running" for ever
    cancelled = []
    fake.cancel = cancelled.append
    job = enqueue(db, user, "image", {})
    _run(db, fake, job)
    assert _run(db, fake, job).status == JobStatus.running  # within its limit
    job.started_at -= LIMITS["image"] + timedelta(minutes=1)
    db.commit()
    fake.network_errors_on_poll = 1  # checking failing counts too
    assert _run(db, fake, job).status == JobStatus.failed
    assert (
        job.error == "The image service didn't finish this in time. Nothing was charged; try again."
    )
    assert cancelled == [job.provider_ref] and job.status not in COUNTED


def test_a_job_waiting_a_while_to_start_says_why_plainly(db, user, owner):
    from datetime import timedelta

    from app.routes.jobs import WAITING

    job = enqueue(db, user, "image", {})
    assert owner.get(f"/jobs/{job.id}").json()["waiting"] == ""  # just asked
    job.created_at -= timedelta(minutes=11)
    db.commit()
    assert owner.get(f"/jobs/{job.id}").json()["waiting"] == WAITING


class SlowClaude:
    """Claude's place: answers in the same call; records when it was asked."""

    name, paid, sync = "claude", False, True

    def __init__(self):
        self.asked = []

    def run(self, kind, input):
        from app.providers import Result

        self.asked.append(kind)
        return Result("succeeded", output={})


def test_long_claude_jobs_never_hold_up_a_still(db, user):
    """Producer, 2026-10-28: Reed's 9 stills waited 6 minutes behind three Claude breakdowns,
    because one worker ran every job in turn. Claude has its own worker lane, so the stills'
    lane hands them to the image service at once, whatever Claude has queued."""
    claude, images = SlowClaude(), FakeProvider(polls_until_done=10)
    jobs = [enqueue(db, user, "write-claude", {}, provider="claude") for _ in range(2)]
    still = enqueue(db, user, "image", {}, provider="replicate")
    run_once(db, {"claude": claude, "replicate": images}, only={"replicate"})  # stills' lane
    db.refresh(still)
    assert still.status == JobStatus.running and images.submitted  # started at once
    assert claude.asked == [] and all(db.get(type(j), j.id).status == "queued" for j in jobs)
    run_once(db, {"claude": claude, "replicate": images}, only={"claude"})  # Claude's lane
    assert claude.asked == ["write-claude", "write-claude"]


def test_deploy_gives_claude_stills_and_reel_prep_a_worker_each():
    """Each provider is taken by exactly one worker lane, and Claude's is its own."""
    import json
    import re

    from app.settings import REPO_ROOT

    compose = (REPO_ROOT / "deploy/docker-compose.yml").read_text()
    lanes = [json.loads(m) for m in re.findall(r"BS_WORKER_PROVIDERS: '(\[.*?\])'", compose)]
    taken = [p for lane in lanes for p in lane]
    assert sorted(taken) == ["claude", "fake", "local", "replicate"] and ["claude"] in lanes
