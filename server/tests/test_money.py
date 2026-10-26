"""Money findings from the live test (2026-10-26): no paid work without a price, release
stops a version's work, a shown price is at least the charge, and every charge is listed."""

from decimal import Decimal

from app.credits import credits_used
from app.models.jobs import Job, JobStatus, Usage
from app.models.projects import Project
from app.providers import Result
from app.providers.fake import FakeProvider
from app.routes.jobs import enqueue
from app.worker import run_once
from tests.test_breakdown import BREAKDOWN
from tests.test_credits import _run, ed, project  # noqa: F401 - fixtures
from tests.test_script_produce import _published


def test_make_this_version_shows_its_price_first(owner, editor, db):
    planned, _ = _published(owner, db, breakdown=BREAKDOWN)
    assert editor.get(f"{planned}/drafts/0/produce/estimate").json() == {"credits": 0}
    unplanned, _ = _published(owner, db)  # no saved plan: the breakdown starts with it
    assert editor.get(f"{unplanned}/drafts/0/produce/estimate").json() == {"credits": 3}


def test_a_charge_is_never_more_than_the_price_shown(editor, ed, db, project):  # noqa: F811
    _, model = project
    job = enqueue(db, ed, "video-480p", {"seconds": 10}, units=5, project=model)  # shown: 5
    _run(db)  # the provider says 10 s, $1.028
    db.refresh(job)
    assert (job.status, job.credits) == ("succeeded", Decimal(5))  # charged what was shown
    assert db.query(Usage).one().cost_usd == Decimal("1.028")  # the dollars as they were


class Silent(FakeProvider):
    """An image or video model that doesn't say what it cost."""

    def poll(self, ref):
        done = super().poll(ref)
        return Result(done.state, output=done.output) if done.state == "succeeded" else done


def test_every_paid_job_is_listed_as_a_charge(owner, editor, ed, db, project):  # noqa: F811
    _, model = project
    job = enqueue(db, ed, "video-480p", {}, units=4, project=model)
    _run(db, Silent())
    (row,) = owner.get("/usage/charges").json()["items"]
    assert (row["credits"], row["estimated"]) == (4, True)
    assert row["cost_usd"] == float(Decimal(4) * Decimal("0.1028"))
    assert db.query(Usage).one().job_id == job.id


def test_releasing_a_version_stops_its_running_work(owner, editor, db):
    """The live test: after release, the breakdown went on running and charged 3.92."""
    base, _ = _published(owner, db)
    made = editor.post(f"{base}/drafts/0/produce").json()
    fake = FakeProvider()
    job = db.get(Job, made["breakdown_job_id"])
    job.provider = "fake"
    db.commit()
    run_once(db, {"fake": fake})  # handed to the provider: running
    db.refresh(job)
    assert job.status == JobStatus.running
    assert editor.post(f"/projects/{made['project_id']}/release").status_code == 200
    db.expire_all()  # the worker reads fresh each tick
    run_once(db, {"fake": fake})  # it lands at the provider after the release
    db.refresh(job)
    assert job.status == JobStatus.cancelled and job.output is None  # nothing saved from it
    assert credits_used(db, db.get(Project, made["project_id"])) == 0  # the credits are back
    assert db.query(Usage).filter_by(job_id=job.id).count() == 1  # its dollars, for Reed


def test_a_released_job_from_a_silent_provider_is_listed_and_keeps_no_files(app, owner, editor, db):
    """QA on #419: a discarded job whose provider reports no cost still shows its spend, and
    what it made is never downloaded into storage."""
    from app.models.files import StoredFile

    class Silent(FakeProvider):  # an image model: files, no reported cost
        def poll(self, ref):
            return Result("succeeded", output={}, files=["https://example.com/a.png"])

    base, _ = _published(owner, db)
    made = editor.post(f"{base}/drafts/0/produce").json()
    job = db.get(Job, made["breakdown_job_id"])
    job.provider, job.credits = "fake", Decimal(2)
    db.commit()
    silent = Silent(polls_until_done=1)
    run_once(db, {"fake": silent})
    editor.post(f"/projects/{made['project_id']}/release")
    db.expire_all()
    files = db.query(StoredFile).count()
    run_once(db, {"fake": silent}, app.state.storage)
    db.refresh(job)
    assert job.status == JobStatus.cancelled
    assert db.query(StoredFile).count() == files  # nothing downloaded
    charge = db.query(Usage).filter_by(job_id=job.id).one()
    assert charge.estimated and charge.cost_usd == Decimal("0.2056")  # 2 credits' worth
