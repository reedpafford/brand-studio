"""The video page stayed on placeholders for about 27 s on Reed's test site (7 Nov): each money
figure the owner's uncapped page showed read every finished video in the workspace one by one
(`scorecard.finished`), several queries each. Now they're read together in a fixed few queries,
with exactly the same figures; and a run's answered notes read only its own video's jobs."""

from decimal import Decimal

from sqlalchemy import event

from app import director, scorecard
from app.db import utcnow
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft
from app.settings import get_settings
from tests.test_director import _made, _run


def _finished(db, n: int, start: int = 0, look: str = "house") -> None:
    """`n` finished videos with clips, takes, a cut and charges (some cut, some not)."""
    for i in range(start, start + n):
        script = Script(workspace_id=1, brand_id=1, title=f"S{i}", kind="story",
                        format="dialogue" if i % 3 else "presenter", created_by_id=1,
                        published=True)  # fmt: skip
        db.add(script)
        db.flush()
        draft = ScriptDraft(script_id=script.id, slot=0, text="NATE: Hi.")
        db.add(draft)
        db.flush()
        video = Project(workspace_id=1, brand_id=1, name=f"V{i}", look=look, created_by_id=1,
                        script_draft_id=draft.id, finished_at=utcnow(),
                        score=(i % 5) or None)  # fmt: skip
        db.add(video)
        db.flush()
        takes = []
        for c in range(1 + i % 3):
            job = Job(workspace_id=1, created_by_id=1, project_id=video.id, kind="video",
                      provider="fake", input={"step": "clip_take"}, credits=Decimal(5 + c),
                      status=JobStatus.succeeded)  # fmt: skip
            own = Job(workspace_id=1, created_by_id=1, project_id=video.id, kind="write-claude",
                      provider="fake", input={"step": "director", "director_run": {"id": "r"}},
                      credits=Decimal("0.7"), status=JobStatus.succeeded)  # fmt: skip
            db.add_all([job, own])
            db.flush()
            row = ProjectClip(project_id=video.id, breakdown_id=1, clip_id=f"c{c + 1}",
                              seconds=4 + c, prompt="p")  # fmt: skip
            db.add(row)
            db.flush()
            for n_ in range(1 + c % 2):
                take = ClipTake(clip_id=row.id, number=n_ + 1, job_id=job.id, file_id=1)
                db.add(take)
                db.flush()
                row.picked_take_id = take.id
            takes.append(row.picked_take_id)
        if i % 2:
            db.add(FinalVideo(project_id=video.id, file_id=1, take_ids=takes[:-1] or takes))
    db.commit()


def _count(db, call):
    seen = []
    engine = db.get_bind()

    def hook(*_):
        seen.append(1)

    event.listen(engine, "before_cursor_execute", hook)
    try:
        out = call()
    finally:
        event.remove(engine, "before_cursor_execute", hook)
    return out, len(seen)


def test_finished_videos_read_together_give_the_same_figures(app, db):
    _finished(db, 12)
    _finished(db, 3, start=50, look="skeleton")
    one_by_one = [f for p in db.query(Project).filter(Project.finished_at.is_not(None),
                                                      Project.look == "house")
                  if (f := scorecard.facts(db, p))]  # fmt: skip
    together, queries = _count(db, lambda: scorecard.finished(db, 1, "house"))
    assert sorted(together, key=repr) == sorted(one_by_one, key=repr) and len(together) == 12
    assert queries <= 8  # a fixed few, however many videos
    assert len(scorecard.finished(db, 1)) == 15  # every look


def test_the_owners_video_page_reads_no_more_for_more_finished_videos(app, db, owner, editor,
                                                                      monkeypatch):  # fmt: skip
    monkeypatch.setattr(get_settings(), "owner_uncapped", True)  # its money figures forecast
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db)
    page = [f"/projects/{pid}", f"/projects/{pid}/director", f"/projects/{pid}/director/progress",
            f"/projects/{pid}/idea"]  # fmt: skip

    def read():
        for url in page:
            assert owner.get(url).status_code == 200

    _finished(db, 4)
    _, few = _count(db, read)
    _finished(db, 40, start=100)
    _, many = _count(db, read)
    assert many - few <= 4, (few, many)  # it no longer grows with the workspace


def test_a_runs_answered_notes_are_the_same_read_from_its_own_video(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db)
    run = director.turns(db, db.get(Project, pid))[-1].input[director.RUN]["id"]
    assert director.answered(db, run, pid) == director.answered(db, run)
