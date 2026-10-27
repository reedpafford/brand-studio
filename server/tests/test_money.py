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
from tests.test_credits import _run, ed, project  # noqa: F401 - fixtures
from tests.test_script_produce import _published


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


def test_restoring_a_video_never_leaves_stopped_work_running(owner, editor, db):
    """QA on #419: work a release stopped shows as stopped straight away, and stays stopped
    after Restore (it isn't brought back); its cost is still recorded once when it lands."""
    base, _ = _published(owner, db)
    made = editor.post(f"{base}/drafts/0/produce").json()
    pid = made["project_id"]
    fake = FakeProvider(polls_until_done=1)
    job = db.get(Job, made["breakdown_job_id"])
    job.provider = "fake"
    db.commit()
    run_once(db, {"fake": fake})  # at the provider
    editor.post(f"/projects/{pid}/release")
    db.expire_all()
    assert db.get(Job, job.id).status == JobStatus.cancelled  # stopped, not "running"
    assert editor.post(f"/projects/{pid}/restore").status_code == 200
    db.expire_all()
    assert db.get(Job, job.id).status == JobStatus.cancelled  # not brought back
    for _ in range(3):  # it lands at the provider; later ticks change nothing
        run_once(db, {"fake": fake})
        db.expire_all()
    stopped = db.get(Job, job.id)
    assert stopped.finished_at is not None and stopped.output is None
    assert db.query(Usage).filter_by(job_id=job.id).count() == 1
    assert credits_used(db, db.get(Project, pid)) == 0


def test_deleting_a_script_stops_its_work_and_restore_doesnt_start_it(owner, editor, ed, db):  # noqa: F811
    """Producer, after the live test: a deleted script's running Write, its held cast read and
    its own look's sheet stop, as on Release; another script's work goes on."""
    from app.credits import credits_left
    from app.models.library import LibraryItem
    from tests.test_script_library import SCRIPT, _make

    sid, other = _make(editor, text=SCRIPT)["id"], _make(editor, text=SCRIPT)["id"]
    look = editor.post(
        "/library/character", json={"name": "Bo", "notes": "a pug", "owner_script_id": sid}
    ).json()["id"]
    assert db.get(LibraryItem, look).owner_script_id == sid

    def job(**input):
        made = Job(workspace_id=ed.workspace_id, created_by_id=ed.id, kind="write-claude",
                   provider="fake", input=input, credits=Decimal(1))  # fmt: skip
        db.add(made)
        db.commit()
        return made

    write = job(step="script_draft", script_id=sid, then_cast=True)
    fake = FakeProvider(polls_until_done=1)
    run_once(db, {"fake": fake})  # the Write is at the provider
    sheet = job(step="sheet", library_item_id=look)
    elsewhere = job(step="script_draft", script_id=other)
    db.refresh(write)
    assert write.status == JobStatus.running
    before = credits_left(db, ed)

    assert editor.delete(f"/scripts/{sid}").status_code == 204
    db.expire_all()
    assert db.get(Job, write.id).status == JobStatus.cancelled  # stopped at once
    assert db.get(Job, sheet.id).status == JobStatus.cancelled
    assert db.get(Job, elsewhere.id).status == JobStatus.queued  # not this script's
    assert credits_left(db, ed) > before  # the Write, its held cast read and the sheet are back

    assert editor.post(f"/scripts/{sid}/restore").status_code == 200
    for _ in range(3):  # the Write lands; nothing is saved and no cast read starts
        run_once(db, {"fake": fake})
        db.expire_all()
    stopped = db.get(Job, write.id)
    assert (stopped.status, stopped.output) == (JobStatus.cancelled, None)
    assert db.query(Usage).filter_by(job_id=write.id).count() == 1  # its dollars, once
    assert not [j for j in db.query(Job).all() if j.input.get("step") == "cast_slots"]


def test_a_script_says_its_own_work_is_being_made(owner, editor, ed, db, project):  # noqa: F811
    """Producer, for the Delete and Archive confirm (spec #468): Reed sees an editor's running
    work on the script; its videos' jobs aren't the script's."""
    from tests.test_script_library import SCRIPT, _make

    sid = _make(editor, text=SCRIPT)["id"]

    def running():
        row = next(r for r in owner.get("/scripts").json() if r["id"] == sid)
        assert owner.get(f"/scripts/{sid}").json()["running"] == row["running"]
        return row["running"]

    assert running() is False
    video = Job(workspace_id=ed.workspace_id, created_by_id=ed.id, kind="image", provider="fake",
                input={"script_id": sid}, project_id=project[1].id)  # fmt: skip
    write = Job(workspace_id=ed.workspace_id, created_by_id=ed.id, kind="write-claude",
                provider="fake", input={"step": "script_draft", "script_id": sid})  # fmt: skip
    db.add(video)
    db.commit()
    assert running() is False  # a video's job never counts
    db.add(write)
    db.commit()
    assert running() is True  # the editor's Write, seen by Reed
    write.status = JobStatus.running
    db.commit()
    assert running() is True
    write.status = JobStatus.succeeded
    db.delete(video)
    db.commit()
    assert running() is False
