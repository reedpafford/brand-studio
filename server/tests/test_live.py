"""Push updates (app/live.py): an open video page hears the moment one of its jobs finishes, and
only someone who may read the video may listen."""

import threading

from app.models.jobs import Job
from app.models.projects import Project
from app.providers.fake import FakeProvider
from app.routes import live
from app.worker import run_once
from tests.conftest import first_brand


def _video(db, brand: int) -> int:
    video = Project(workspace_id=1, brand_id=brand, name="V", created_by_id=1)
    db.add(video)
    db.commit()
    return video.id


def test_a_job_finishing_reaches_its_open_page(app, owner, db, monkeypatch):
    monkeypatch.setattr(live, "LIFETIME", 1.5)  # the stream ends, so the test client can read it
    video = _video(db, first_brand(owner))
    db.add(Job(workspace_id=1, project_id=video, kind="video-480p", provider="fake",
               input={"seconds": 5}))  # fmt: skip
    db.commit()

    def work():  # the worker, in its own session, while the page listens
        with app.state.sessionmaker() as worker:
            for _ in range(2):  # sent, then done
                run_once(worker, {"fake": FakeProvider(polls_until_done=0)})

    threading.Timer(0.5, work).start()
    r = owner.get(f"/projects/{video}/live")
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "no-transform" in r.headers["cache-control"]  # Caddy passes it on uncompressed
    assert "data: jobs\n\n" in r.text  # it started
    assert "data: made\n\n" in r.text  # it finished
    assert r.text.endswith("event: bye\ndata: bye\n\n")  # the page opens a new one at once


def test_only_who_may_read_the_video_may_listen(owner, outsider, db):
    video = _video(db, first_brand(owner))
    assert outsider.get(f"/projects/{video}/live").status_code == 404  # another workspace
    owner.post("/auth/logout")
    assert owner.get(f"/projects/{video}/live").status_code == 401
