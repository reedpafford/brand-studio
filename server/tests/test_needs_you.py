"""The Videos home's Needs you group (audit M6): each video says what waits on its editor,
first thing first, and ?status=needs_you lists only those. Free and read-only."""

from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.jobs import JobStatus
from app.models.storyboards import StoryboardFrame
from tests.conftest import upload
from tests.test_production import _job, _video


def _row(editor, pid):
    return next(p for p in editor.get("/projects").json() if p["id"] == pid)


def test_a_video_says_what_waits_on_its_editor_first_thing_first(owner, editor, db):
    pid = _video(owner, editor, db)
    assert (_row(editor, pid)["needs_you"], _row(editor, pid)["waiting_on"]) == (False, None)
    bd = db.query(BreakdownVersion).filter_by(project_id=pid).one()
    for shot in ("s1", "s2"):
        db.add(StoryboardFrame(project_id=pid, breakdown_id=bd.id, clip_id="c1", shot_id=shot,
                               prompt="p", file_id=upload(editor)))  # fmt: skip
    db.commit()
    assert _row(editor, pid)["waiting_on"] == "2 stills ready to check"
    db.add(ProjectClip(project_id=pid, breakdown_id=bd.id, clip_id="c1", seconds=5, prompt="p",
                       picked_take_id=None))  # fmt: skip
    db.commit()
    _job(db, pid, JobStatus.failed, step="frame")  # the newest run didn't finish: first
    row = _row(editor, pid)
    assert row["needs_you"] and row["waiting_on"] == "A still didn't finish"
    assert [p["id"] for p in editor.get("/projects?status=needs_you").json()] == [pid]

    _job(db, pid, JobStatus.succeeded, step="frame")  # tried again: back to the stills
    for frame in db.query(StoryboardFrame):
        frame.approved = True
    db.commit()
    assert _row(editor, pid)["waiting_on"] is None
    assert editor.get("/projects?status=needs_you").json() == []


def test_work_made_for_an_older_plan_says_changes_are_waiting(owner, editor, db):
    pid = _video(owner, editor, db)
    bd = db.query(BreakdownVersion).filter_by(project_id=pid).one()
    db.add(StoryboardFrame(project_id=pid, breakdown_id=bd.id, clip_id="c1", shot_id="s1",
                           prompt="p", file_id=upload(editor), approved=True))  # fmt: skip
    db.add(BreakdownVersion(project_id=pid, script_version=bd.script_version, source="edit",
                            data=bd.data, created_by_id=bd.created_by_id))  # fmt: skip
    db.commit()
    assert _row(editor, pid)["waiting_on"] == "Changes are waiting: bring it up to date"


def test_an_advisory_check_or_an_unknown_step_never_hides_what_waits(owner, editor, db):
    from app.models.jobs import Job
    from app.models.projects import Project

    pid = _video(owner, editor, db)
    bd = db.query(BreakdownVersion).filter_by(project_id=pid).one()
    db.add(StoryboardFrame(project_id=pid, breakdown_id=bd.id, clip_id="c1", shot_id="s1",
                           prompt="p", file_id=upload(editor)))  # fmt: skip
    project = db.get(Project, pid)
    db.add(Job(workspace_id=project.workspace_id, kind="check-claude", provider="claude",
               input={"step": "item_check"}, project_id=pid, credits=0,
               status=JobStatus.failed))  # fmt: skip
    db.commit()
    assert _row(editor, pid)["waiting_on"] == "1 still ready to check"
    _job(db, pid, JobStatus.failed, step="something_new")
    assert _row(editor, pid)["waiting_on"] == "1 still ready to check"
    _job(db, pid, JobStatus.failed, step="song_timing")
    assert _row(editor, pid)["waiting_on"] == "The song's timing didn't finish"


def test_a_failed_narration_is_named_as_the_narration(owner, editor, db):
    from app.models.jobs import Job
    from app.models.projects import Project

    pid = _video(owner, editor, db)
    ws = db.get(Project, pid).workspace_id
    for kind, step in (("narration_timing", "song_timing"), ("speech", "song_take")):
        db.add(Job(workspace_id=ws, kind=kind, provider="replicate", input={"step": step},
                   project_id=pid, credits=0, status=JobStatus.failed))  # fmt: skip
        db.commit()
        name = "The narration's timing" if kind == "narration_timing" else "The narration"
        assert _row(editor, pid)["waiting_on"] == f"{name} didn't finish"
