"""Replicate adapter against a mocked Replicate API (no real or paid calls)."""

import json
from decimal import Decimal

import httpx2 as httpx
import pytest

from app.catalogue import get_model
from app.models.accounts import User
from app.models.jobs import Job, Usage
from app.providers.replicate import ReplicateProvider
from app.routes.jobs import enqueue
from app.worker import UNSURE, run_once
from tests.helpers import MP4

BASE = "https://replicate.test/v1"
SEEDANCE = get_model("seedance-2.5")
VIDEO_INPUT = {"prompt": "a cat trades", "duration": 5, "resolution": "480p"}


class FakeReplicate:
    """Answers like Replicate: one prediction that finishes on the second check."""

    def __init__(self, final: dict | None = None, submit_status: int = 201):
        self.final = final or {}
        self.submit_status = submit_status
        self.requests: list[httpx.Request] = []
        self.checks = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        if request.method == "POST" and url == f"{BASE}/predictions":
            body = json.loads(request.content)
            assert body["version"] == SEEDANCE.provider_version
            if self.submit_status != 201:
                return httpx.Response(self.submit_status, text="nope")
            return httpx.Response(201, json={"id": "p1", "status": "starting"})
        if url == f"{BASE}/predictions/p1":
            self.checks += 1
            if self.checks == 1:
                return httpx.Response(200, json={"id": "p1", "status": "processing"})
            done = {
                "id": "p1",
                "status": "succeeded",
                "version": SEEDANCE.provider_version,
                "input": VIDEO_INPUT,
                "output": "https://replicate.delivery/out.mp4",
                "metrics": {"predict_time": 40.1, "video_output_duration_seconds": 5},
            }
            return httpx.Response(200, json={**done, **self.final})
        if url == "https://replicate.delivery/page.html":  # claims video, is a web page
            return httpx.Response(200, content=b"<html>", headers={"content-type": "video/mp4"})
        if url == "https://replicate.delivery/out.mp4":
            return httpx.Response(200, content=MP4, headers={"content-type": "video/mp4"})
        return httpx.Response(404)


@pytest.fixture
def fake():
    return FakeReplicate()


def _providers(fake):
    client = httpx.Client(transport=httpx.MockTransport(fake))
    return {"replicate": ReplicateProvider(BASE, client)}


def _job(db):
    user = db.query(User).first()
    input = {"model": "seedance-2.5", "input": VIDEO_INPUT}
    return enqueue(db, user, "video", input, units=5, provider="replicate")


def _tick(app, db, fake, job, times=1):
    for _ in range(times):
        run_once(db, _providers(fake), app.state.storage)
    db.refresh(job)
    return job


def test_video_runs_downloads_output_and_records_real_cost(app, owner, editor, db, fake):
    job = _job(db)
    assert job.credits == 5  # catalogue: 1 credit per 480p second
    assert _tick(app, db, fake, job).status == "running"
    assert _tick(app, db, fake, job, 2).status == "succeeded"
    file_id = job.output["file_ids"][0]
    assert editor.get(f"/files/{file_id}").content == MP4
    usage = db.query(Usage).one()
    assert (usage.units, usage.cost_usd, usage.estimated) == (5, Decimal("0.5140"), False)
    assert job.credits == 5
    assert all("authorization" not in r.headers for r in fake.requests)  # proxy adds it


def test_missing_metrics_falls_back_to_request_and_is_marked_estimate(app, owner, db):
    fake = FakeReplicate(final={"metrics": {"predict_time": 3}})
    job = _tick(app, db, fake, _job(db), 3)
    assert job.status == "succeeded"
    assert db.query(Usage).one().estimated is True


def test_failed_prediction_gives_plain_message_and_frees_credits(app, owner, editor, db):
    fake = FakeReplicate(final={"status": "failed", "error": "NSFW detected; balance $3.20"})
    job = _tick(app, db, fake, _job(db), 3)
    assert job.status == "failed" and "3.20" not in editor.get(f"/jobs/{job.id}").text
    assert "NSFW" in owner.get(f"/jobs/{job.id}/detail").json()["error_detail"]
    assert db.query(Usage).count() == 0


def test_rate_limited_submit_is_retried_later(app, owner, db):
    fake = FakeReplicate(submit_status=429)
    job = _tick(app, db, fake, _job(db))
    assert job.status == "queued"  # Replicate said "busy": nothing started, safe to retry


def test_server_error_on_paid_submit_is_not_retried(app, owner, db):
    job = _tick(app, db, FakeReplicate(submit_status=502), _job(db))
    assert (job.status, job.error) == ("failed", UNSURE)


def test_rejected_input_fails_the_job(app, owner, db):
    job = _tick(app, db, FakeReplicate(submit_status=422), _job(db))
    assert job.status == "failed" and "422" in job.error_detail


def test_bad_output_file_fails_job_but_keeps_its_cost(app, owner, db, fake):
    fake.final = {"output": "https://replicate.delivery/page.html"}
    job = _tick(app, db, fake, _job(db), 3)
    assert job.status == "failed"
    assert db.query(Usage).count() == 1  # the generation was paid for


def test_base_url_is_configurable(app, owner, db):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(201, json={"id": "x"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ReplicateProvider("https://proxy.internal/replicate/v1/", client)
    provider.submit("video", {"model": "seedance-2.5", "input": {}})
    assert seen == ["https://proxy.internal/replicate/v1/predictions"]


def test_unknown_model_never_reaches_replicate(app, owner, db, fake):
    user = db.query(User).first()
    job = enqueue(db, user, "video", {"model": "nope", "input": {}}, provider="replicate")
    assert _tick(app, db, fake, job).status == "failed"
    assert fake.requests == []
    assert db.query(Job).count() == 1


def test_watch_model_text_output_and_call_price():
    gemini = get_model("gemini-3.5-flash")

    def handler(request):
        return httpx.Response(
            200,
            json={
                "id": "g1",
                "status": "succeeded",
                "version": gemini.provider_version,
                "input": {"prompt": "what happens?"},
                "output": ["A cat ", "buys the dip."],
            },
        )

    provider = ReplicateProvider(BASE, httpx.Client(transport=httpx.MockTransport(handler)))
    result = provider.poll("g1")
    assert result.output == {"text": "A cat buys the dip."} and result.files == []
    assert (result.usage[0].unit, result.usage[0].estimated) == ("call", True)
