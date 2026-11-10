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
    assert job.status == JobStatus.queued and job.attempts == 0  # busy: not started, not a try
    job.input = {**job.input, "wait_until": ""}  # its wait is over
    db.commit()
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
    answered = {"prompt": "fits", "edit": False, "why": ""}  # a change's answer, its defaults
    assert db.get(Job, job.id).output == answered  # answered (no clip to save it on)


def test_a_job_running_past_its_time_limit_fails_plainly_and_is_cancelled(db, user):
    """Producer, 2026-10-28: a running job had no time limit, so "Drawing…" could last
    forever with nothing coming back. Past it, the job is cancelled at the provider and fails
    like any failure, said plainly; a failed job isn't counted against anyone's credits. A
    cancelled run may still be billed (Replicate's billing docs), so it never says "Nothing was
    charged", and its price is listed in Usage as an estimate."""
    from datetime import timedelta

    from app.credits import COUNTED
    from app.worker import LIMITS, SLOW

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
    assert job.error == SLOW.format("The image service") and "Nothing" not in job.error
    assert cancelled == [job.provider_ref] and job.status not in COUNTED
    usage = db.query(Usage).one()
    assert (usage.unit, usage.estimated, usage.cost_usd > 0) == ("job", True, True)


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
    """Each provider is taken by exactly one worker lane, and Claude's is its own. Each lets
    its job in hand finish on a deploy (P1: the reel worker had Docker's default 10 s), the
    Claude worker for up to 30 minutes (a full-length song's shots stream for 20-30)."""
    import json
    import re

    from app.settings import REPO_ROOT

    compose = (REPO_ROOT / "deploy/docker-compose.yml").read_text()
    lanes = [json.loads(m) for m in re.findall(r"BS_WORKER_PROVIDERS: '(\[.*?\])'", compose)]
    taken = [p for lane in lanes for p in lane]
    assert sorted(taken) == ["claude", "fake", "heygen", "local", "replicate"]
    assert ["claude"] in lanes
    graces = re.findall(r"stop_grace_period: (\d+m)", compose)  # every lane has one, and
    assert len(graces) == len(lanes) and graces.count("30m") == 1  # Claude's long shots: 30m
    claude = compose[compose.index("claude-worker:") :].split("\n\n")[0]
    assert "stop_grace_period: 30m" in claude


def test_a_restart_asks_the_job_it_cut_off_mid_answer_again_once(db, user, caplog):
    """P1: a deploy failed the Claude call or local job in hand ("The server restarted… try
    again"). It goes back in the queue once (its answer was never kept, so nothing is applied
    twice), logged so a billed call cut off can be found; cut off again, it fails as before."""
    from app.worker import RESTARTED

    providers = {"claude": SlowClaude(), "local": SlowClaude()}
    jobs = [enqueue(db, user, "write-claude", {}, provider=p, units=0) for p in providers]
    for job in jobs:
        job.status = JobStatus.running  # cut off mid-answer: never handed over, nothing kept
    db.commit()
    recover(db, providers)
    assert _statuses(db, jobs) == [JobStatus.queued] * 2
    logged = [m for r in caplog.records if "cut off by a restart" in (m := r.getMessage())]
    assert logged == [f"job {j.id} (write-claude, {j.provider}, video None) was cut off by a "
                      "restart: queued again" for j in jobs]  # fmt: skip
    run_once(db, providers)
    assert [p.asked for p in providers.values()] == [["write-claude"]] * 2
    assert _statuses(db, jobs) == [JobStatus.succeeded] * 2
    for job in jobs:
        job.status, job.provider_ref = JobStatus.running, None  # cut off again
    db.commit()
    recover(db, providers)
    assert _statuses(db, jobs) == [JobStatus.failed] * 2
    assert {job.error for job in jobs} == {RESTARTED}


def test_two_local_lanes_never_take_the_same_job(app, db, user, monkeypatch):
    """S1: local work runs in two lanes (threads, each with its own session). Both reach for
    the oldest job at the same moment; the claim, a conditional update, gives it to one."""
    import threading

    from app import worker

    both = threading.Barrier(2, timeout=10)

    def met(db_, job):  # each lane has picked the job and is about to claim it
        both.wait()
        return False

    monkeypatch.setattr(worker.cast_gate, "job_paused", met)
    local = SlowClaude()
    jobs = [enqueue(db, user, "take_listen", {}, provider="local", units=0) for _ in range(2)]

    def lane():
        with app.state.sessionmaker() as mine:
            worker.start_next(mine, {"local": local}, only={"local"})

    lanes = [threading.Thread(target=lane) for _ in range(2)]
    for t in lanes:
        t.start()
    for t in lanes:
        t.join()
    assert local.asked == ["take_listen"]  # one lane ran it; the other found it taken
    assert _statuses(db, jobs) == [JobStatus.succeeded, JobStatus.queued]


def _statuses(db, jobs) -> list[str]:
    for job in jobs:
        db.refresh(job)
    return [job.status for job in jobs]


def test_each_local_lane_gets_its_own_share_of_the_cpus(monkeypatch):
    """S1: two lanes' whisper reads and ffmpeg encodes never crowd onto the same cores: each
    lane (and what it starts) is pinned to its share, which whisper sizes its threads to. Only
    with 2 CPUs a lane or more: on the 2-CPU server each lane sees both, so a lone cut render
    isn't held to half the machine (QA on #1526)."""
    import os

    from app.worker import shares

    cpus = {0, 1, 2, 3}
    monkeypatch.setattr(os, "sched_getaffinity", lambda pid: cpus, raising=False)
    monkeypatch.setattr(os, "sched_setaffinity", lambda pid, cpus: None, raising=False)
    assert shares(2) == [[0, 2], [1, 3]]
    assert shares(1) == [None] and shares(3) == [None] * 3  # one lane, or under 2 CPUs a lane
    cpus = {0, 1}  # the live server (Hostinger KVM 2)
    assert shares(2) == [None, None]


class Busy(FakeProvider):
    """Says "busy" (a 429: nothing started) to every start; counts how often it was asked."""

    def __init__(self):
        super().__init__()
        self.asked = 0

    def submit(self, kind, input):
        from app.providers import NotStarted

        self.asked += 1
        raise NotStarted("Replicate is rate limiting; try later.")


def test_a_busy_service_waits_longer_each_time_and_a_burst_keeps_its_tries(db, user):
    """FABLE B3: a "busy" answer put the job back, and the same tick picked it again at once, so
    a burst of takes used all their tries in one tick and failed. Now the busy job waits longer
    each time (BUSY_WAITS), the service is left alone for the rest of the tick, a busy answer
    isn't a try, and only a busy that lasts through every wait fails, plainly."""
    from datetime import datetime

    from app.db import utcnow
    from app.worker import BUSY, BUSY_WAITS

    busy = Busy()
    first, *others = [enqueue(db, user, "video-480p", {}) for _ in range(3)]
    run_once(db, {"fake": busy})
    assert busy.asked == 1  # one busy answer: nothing more asked of it this tick
    assert all(db.get(type(j), j.id).status == JobStatus.queued for j in others)
    for j in others:  # the rest of the burst, out of the way
        db.get(type(j), j.id).status = JobStatus.cancelled
    db.commit()
    for n, wait in enumerate(BUSY_WAITS):
        db.refresh(first)
        assert (first.status, first.attempts, first.input["busy"]) == (JobStatus.queued, 0, n + 1)
        left = (datetime.fromisoformat(first.input["wait_until"]) - utcnow()).total_seconds()
        assert wait - 5 < left <= wait  # a longer wait each time
        run_once(db, {"fake": busy})  # still waiting: not asked again
        assert busy.asked == n + 1
        first.input = {**first.input, "wait_until": ""}  # its wait is over
        db.commit()
        run_once(db, {"fake": busy})
    db.refresh(first)
    assert (first.status, first.error) == (JobStatus.failed, BUSY.format("The service"))


def test_a_busy_answer_while_checking_keeps_the_take_running_and_asks_less_often(
    db, user, monkeypatch
):
    """FABLE B4: a 429 while checking on a take that was still rendering (and billing) failed
    it. Busy means still running: that take is checked less often (CHECK_WAIT), the service is
    left alone for the rest of the tick, and the take lands when the service answers again."""
    from app import worker
    from app.providers import NotStarted

    monkeypatch.setattr(worker, "_check_after", {})
    fake = FakeProvider()
    jobs = [enqueue(db, user, "video-480p", {}) for _ in range(2)]
    run_once(db, {"fake": fake})
    refs = [db.get(type(j), j.id).provider_ref for j in jobs]
    answers, asked = fake.poll, []

    def busy(ref):
        asked.append(ref)
        raise NotStarted("Replicate is rate limiting; try later.")

    fake.poll = busy
    run_once(db, {"fake": fake})
    assert asked == refs[:1]  # busy: the second isn't asked this tick
    run_once(db, {"fake": fake})
    assert asked == refs  # the first waits its CHECK_WAIT; the second is asked now
    assert all(db.get(type(j), j.id).status == JobStatus.running for j in jobs)
    fake.poll = answers
    worker._check_after.clear()  # their waits are over
    run_once(db, {"fake": fake})
    assert all(db.get(type(j), j.id).status == JobStatus.succeeded for j in jobs)


def test_a_take_its_service_cant_cancel_is_checked_longer_and_never_made_again_on_its_own(
    db, user, monkeypatch
):
    """FABLE B9: HeyGen has no cancel, yet a timed-out HeyGen piece was made again on its own,
    while the first could still finish and be billed. A paid service that can't cancel gets
    one more limit's time, then fails plainly, and its step isn't tried again on its own."""
    from datetime import timedelta

    from app import worker
    from app.worker import LATE, LIMITS

    told = []
    monkeypatch.setattr(worker, "step_failed", lambda db, job, again=True: told.append(again))
    fake = FakeProvider(polls_until_done=10**6)  # paid, says "running" for ever, can't cancel
    job = enqueue(db, user, "image", {"step": "host_still"})
    _run(db, fake, job)
    job.started_at -= LIMITS["image"] + timedelta(minutes=1)
    db.commit()
    assert _run(db, fake, job).status == JobStatus.running  # checked once more, later
    job.started_at -= LIMITS["image"]
    db.commit()
    assert _run(db, fake, job).status == JobStatus.failed
    assert job.error == LATE.format("The image service")
    assert told == [False] and len(fake.submitted) == 1  # never made again on its own
