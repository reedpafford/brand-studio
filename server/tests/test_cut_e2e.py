"""The real E2E run (video 233): a free edit is never held back for want of a watch, and
each cut keeps its file's own length. On the stand-ins."""

from app import cut_render, director
from app.models.clips import FinalVideo
from app.models.files import StoredFile
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from tests.test_run_progress import _done


def test_a_free_edit_goes_through_with_no_watches_left(app, db, owner, editor, monkeypatch):
    """233: "Refused: no watches are left this run to check an edit", for a free trim of a
    1.6 s silent tail. The edit is made; with no watch left it's delivered as not watched."""
    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    last = director.turns(db, project)[-1]
    run = {**last.input[director.RUN], "id": "after", "watches": director.MAX_WATCHES}
    move = {"tool": "edit_cut", "why": "b4: end on the dare",
            "edit": {"kind": "trim", "piece": "c1", "start": None, "end": 4.0}}  # fmt: skip
    turn = Job(workspace_id=project.workspace_id, project_id=pid, kind="write-claude",
               provider="claude", status=JobStatus.succeeded, output=move,
               input={"step": director.STEP, director.RUN: run})  # fmt: skip
    db.add(turn)
    db.commit()
    made = []
    monkeypatch.setattr("app.director_tools.run", lambda *a, **k: made.append(a[3]) or "Trimmed.")
    director._act(db, turn, app.state.storage)
    assert made and made[0]["tool"] == "edit_cut"  # it reached the cut editor
    db.expire_all()
    assert db.get(Job, turn.id).input["result"] == "Trimmed."  # never "no watches are left"


def test_a_cut_keeps_its_files_own_length(app, db, owner, editor):
    """233: the Cut tab said 0:18 (the plan's) for a 16.7 s file."""
    pid = _done(app, db, owner, editor)
    video = db.query(FinalVideo).filter_by(project_id=pid).order_by(FinalVideo.id.desc()).first()
    data = app.state.storage.get(db.get(StoredFile, video.file_id).key)
    assert video.seconds == round(cut_render.seconds(data), 2)
    cut = owner.get(f"/projects/{pid}/cut").json()
    assert cut["seconds"] == video.seconds == cut["versions"][-1]["seconds"]


def test_a_cut_made_again_under_its_number_says_so(app, db, owner, editor):
    """233: "Making Cut 1" four times. S3-12 keeps a cut's number until it's handed over, so
    the chat says it plainly: "Making Cut 1 again (2nd try)"."""
    from app import director_tools
    from app.models.accounts import User

    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    made = db.query(FinalVideo).filter_by(project_id=pid, number=1).count()
    user = db.get(User, project.created_by_id)
    last = director.turns(db, project)[-1].input[director.RUN]
    said = director_tools.run(db, user, project, {"tool": "final_cut"}, app.state.storage, last)
    assert said == f"Making Cut 1 again ({director_tools._nth(made + 1)} try).", said
    assert [director_tools._nth(n) for n in (2, 3, 4, 11, 12, 21, 22)] == [
        "2nd", "3rd", "4th", "11th", "12th", "21st", "22nd"]  # fmt: skip


def test_a_trim_of_the_ending_says_what_it_ends_on_and_the_next_watch_checks_it(app, db, owner,
                                                                               editor):  # fmt: skip
    """Video 271: the trim "about 0.7 s after 'two a day'" said it kept his satisfied look at
    the pouch, and cut it away: the cut ended mid-drink. A trim of the ending now says what its
    last frame shows, and the next watch of the cut is told it, to check the last frames."""
    from types import SimpleNamespace

    from app import cut_edits, director_tools, watch_cut
    from app.models.accounts import User
    from app.models.checks import ItemCheck
    from app.models.clips import CutEdit, ProjectClip

    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    user = db.get(User, project.created_by_id)
    for row in db.query(ProjectClip).filter_by(project_id=pid):  # its words heard: a trim may
        db.add(ItemCheck(project_id=pid, target="words", target_id=row.picked_take_id,
                         status="done", findings=[]))  # fmt: skip
    db.commit()
    run = director.turns(db, project)[-1].input[director.RUN]
    last = cut_edits.for_director(db, project)["pieces"][-1]
    shows = "his satisfied smile at the pouch"
    move = {"tool": "edit_cut", "why": "b6: end on his smile",
            "edit": {"kind": "trim", "piece": last["piece"], "end": last["end"] - 0.5,
                     "shows": shows}}  # fmt: skip
    said = director_tools.run(db, user, project, move, app.state.storage, run)
    assert said.startswith("Ending trimmed"), said
    edit = db.get(CutEdit, run["edit_id"])
    assert edit.data["shows"] == shows
    assert watch_cut.ending_shows(db, SimpleNamespace(edit_ids=[edit.id])) == shows
    cut_edits.undo(db, project, edit.id)
    db.commit()
    assert watch_cut.ending_shows(db, SimpleNamespace(edit_ids=[edit.id])) == ""
