"""Push updates (app/live.py): an open video page hears the moment one of its jobs moves, by the
worker or by a press, and only someone who may read the video may listen."""

import threading
import time

from app import live as news
from app.models.accounts import User
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.providers.fake import FakeProvider
from app.routes import live
from app.routes.jobs import approve_job
from app.worker import run_once
from tests.conftest import first_brand


def _video(db, brand: int, status: JobStatus = JobStatus.queued) -> tuple[int, int]:
    """A video with one job of its own."""
    video = Project(workspace_id=1, brand_id=brand, name="V", created_by_id=1)
    db.add(video)
    db.flush()
    job = Job(workspace_id=1, project_id=video.id, kind="video-480p", provider="fake",
              input={"seconds": 5}, status=status)  # fmt: skip
    db.add(job)
    db.commit()
    return video.id, job.id


def _heard(app, client, video: int, then) -> str:
    """What the video's open page hears while `then(session)` runs, once the page is listening."""

    def run():
        for _ in range(400):  # a loaded machine: wait however long the stream takes to open
            if video in app.state.live.pages and app.state.live.ready.is_set():
                break
            time.sleep(0.05)
        with app.state.sessionmaker() as db:
            then(db)
        url = app.state.settings.database_url  # after what it said: the stream ends
        with open(news._file(url), "a") as f:
            f.write(f"{video} {news.BYE}\n")

    threading.Thread(target=run).start()
    r = client.get(f"/projects/{video}/live")
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "no-transform" in r.headers["cache-control"]  # Caddy passes it on uncompressed
    return r.text


def test_a_job_the_worker_runs_reaches_its_open_page(app, owner, db, monkeypatch):
    monkeypatch.setattr(live, "LIFETIME", 30)  # the page's own end, should the worker hang
    video, job = _video(db, first_brand(owner))
    fake = FakeProvider(polls_until_done=0)

    def work(worker):
        for _ in range(2):  # sent, then done
            run_once(worker, {"fake": fake})

    said = _heard(app, owner, video, work)
    db.expire_all()
    assert db.get(Job, job).status == JobStatus.succeeded
    assert "data: jobs\n\n" in said  # it started
    assert "data: made\n\n" in said  # it finished
    assert said.endswith("event: bye\ndata: bye\n\n")  # the page opens a new one at once


def test_the_owner_approving_a_held_job_tells_its_page(app, owner, db, monkeypatch):
    monkeypatch.setattr(live, "LIFETIME", 30)
    video, job = _video(db, first_brand(owner), JobStatus.needs_owner_approval)

    def approve(session):  # Reed's press on Needs you, while the editor's page is open
        approve_job(job, session.query(User).one(), session)

    said = _heard(app, owner, video, approve)
    assert "data: jobs\n\n" in said  # queued: its card and live card are read again


def test_only_who_may_read_the_video_may_listen(owner, outsider, db):
    video, _ = _video(db, first_brand(owner))
    assert outsider.get(f"/projects/{video}/live").status_code == 404  # another workspace
    owner.post("/auth/logout")
    assert owner.get(f"/projects/{video}/live").status_code == 401
