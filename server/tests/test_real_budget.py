"""The test site's real-AI budget (Producer, 1 Nov): with the stand-ins off on the test site,
every paid call counts against BS_REAL_BUDGET_USD from BS_REAL_BUDGET_SINCE. Past it, a press
is refused in plain words and queued work isn't sent (failed, uncharged). Live is never
capped here. No paid calls: the providers are the tests' fakes."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.credits import NO_START, REAL_DONE, USD_PER_CREDIT, real_budget_refusal
from app.db import utcnow
from app.models.accounts import User
from app.models.jobs import Job, JobStatus
from app.providers.fake import FakeProvider
from app.routes.jobs import enqueue
from app.settings import Settings
from app.worker import run_once

SINCE = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def real(monkeypatch):
    """The test site on real providers, with a budget of 1.5 five-second takes."""
    settings = Settings(env="next", fake_providers=False, real_budget_since=SINCE,
                        real_budget_usd=float(5 * USD_PER_CREDIT * Decimal("1.5")))  # fmt: skip
    for where in ("app.settings.get_settings", "app.routes.jobs.get_settings"):
        monkeypatch.setattr(where, lambda: settings)
    return settings


def _take(db, user):
    return enqueue(db, user, "video-480p", {}, units=5, provider="replicate")


def test_presses_run_within_the_budget_then_are_refused_in_plain_words(owner, db, real):
    boss = db.query(User).one()
    first = _take(db, boss)
    first.provider_ref, first.started_at = "sent", utcnow()  # what counts is what was sent
    db.commit()
    with pytest.raises(HTTPException) as no:
        _take(db, boss)
    assert (
        no.value.detail
        == REAL_DONE.format(real.real_budget_usd)
        == "The test site's real-AI budget ($0.77) is used up. Nothing was charged."  # not "$1"
    )
    assert db.query(Job).count() == 1  # nothing reserved


def test_queued_work_past_it_isnt_sent_and_charges_nothing(owner, db, real):
    boss = db.query(User).one()
    jobs = [_take(db, boss), _take(db, boss)]  # both fit when pressed: nothing sent yet
    provider = FakeProvider()  # paid, like the real lane
    run_once(db, {"replicate": provider})
    db.expire_all()
    assert db.get(Job, jobs[0].id).status == JobStatus.running  # sent
    second = db.get(Job, jobs[1].id)
    assert (second.status, second.error) == (
        JobStatus.failed,
        REAL_DONE.format(real.real_budget_usd),
    )
    assert second.provider_ref is None  # never sent


def test_no_budget_or_start_on_the_test_site_runs_nothing_paid_and_live_is_never_capped(db):
    on_test = Settings(env="next", fake_providers=False)
    assert real_budget_refusal(db, on_test, "replicate", Decimal(1)) == NO_START
    no_start = Settings(env="next", fake_providers=False, real_budget_usd=50)  # not set up
    assert real_budget_refusal(db, no_start, "replicate", Decimal(1)) == NO_START
    assert "start time not set" in NO_START and "used up" not in NO_START
    no_budget = Settings(env="next", fake_providers=False, real_budget_since=SINCE)
    assert real_budget_refusal(db, no_budget, "replicate", Decimal(1)) == REAL_DONE.format(0)
    assert real_budget_refusal(db, on_test, "local", Decimal(1)) == ""  # our own server: free
    live = Settings(env="production", fake_providers=False)
    assert real_budget_refusal(db, live, "replicate", Decimal(10**6)) == ""
    stand_ins = Settings(env="next", fake_providers=True)
    assert real_budget_refusal(db, stand_ins, "replicate", Decimal(10**6)) == ""


def test_the_budget_shows_its_cents(db):
    cents = Settings(env="next", fake_providers=False, real_budget_since=SINCE, real_budget_usd=2.5)
    no = real_budget_refusal(db, cents, "replicate", Decimal(10**6))
    assert no == "The test site's real-AI budget ($2.50) is used up. Nothing was charged."


def test_the_owner_reads_what_is_spent_so_far(app, owner, editor, db):
    app.state.settings.env, app.state.settings.fake_providers = "next", False
    app.state.settings.real_budget_usd, app.state.settings.real_budget_since = 20.0, SINCE
    boss = db.query(User).filter_by(email="reed@example.com").one()
    job = enqueue(db, boss, "video-480p", {}, units=5, provider="replicate")
    job.provider_ref, job.started_at = "sent", utcnow()
    db.commit()
    got = owner.get("/credits/real-budget").json()
    assert (got["on"], got["budget_usd"], got["since"]) == (True, 20.0, "2026-01-01T00:00:00Z")
    assert got["spent_usd"] == float(job.credits * USD_PER_CREDIT)
    assert editor.get("/credits/real-budget").status_code == 403


def test_stand_in_work_never_counts_against_the_real_budget(app, owner, db):
    """The dry run: the counter counted the stand-ins' clips (fake://) as spent."""
    from app.models.jobs import Job as J
    from app.providers import get_providers

    app.state.settings.real_budget_since = SINCE
    app.state.settings.fake_providers = True
    boss = db.query(User).filter_by(email="reed@example.com").one()
    _take(db, boss)
    run_once(db, get_providers(app.state.settings, app.state.storage))
    assert db.query(J).one().provider_ref  # sent to the stand-in, at its price
    assert owner.get("/credits/real-budget").json()["spent_usd"] == 0
