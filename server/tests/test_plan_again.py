"""S3-08's "Start the plan again": after a person's Stop, a new run that writes its treatment,
waits for Make it, then plans the whole video again (a new plan, new shots, every clip made
anew) instead of carrying on from its shots. What was made stays, as earlier plans and takes.
All on the stand-ins (no paid call)."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app import director
from app.db import utcnow
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.projects import Project
from app.providers import get_providers
from app.worker import run_once
from tests.conftest import PASSWORD
from tests.helpers import make_it
from tests.test_director import _made, _run

AGAIN = "Planning the whole video again."


def _stopped(app, db, owner, editor) -> int:
    """A video whose run a person stopped once its first takes were made (S3-08)."""
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    providers = get_providers(app.state.settings, app.state.storage)
    for _ in range(80):
        run_once(db, providers, app.state.storage)
        db.expire_all()
        make_it(db)
        if (
            db.query(ProjectClip)
            .filter(ProjectClip.project_id == pid, ProjectClip.picked_take_id.is_not(None))
            .count()
        ):
            break
    stopped = editor.post(f"/projects/{pid}/director/stop").json()
    assert stopped["ended"] == "Stopped.", stopped
    _run(app, db, ticks=5)  # what it started finishes; no more turns
    return pid


def _results(db, pid: int) -> list[str]:
    rows = director.turns(db, db.get(Project, pid))
    return [t.input.get("result", "") for t in rows]


def _takes(db, pid: int) -> dict[str, list[int]]:
    rows = db.query(ProjectClip).filter_by(project_id=pid).all()
    return {r.clip_id: [t.id for t in db.query(ClipTake).filter_by(clip_id=r.id)] for r in rows}


def test_start_the_plan_again_plans_the_whole_video_again_after_make_it(app, db, owner, editor):
    pid = _stopped(app, db, owner, editor)
    project = db.get(Project, pid)
    plan_before = project.plan["made_at"]
    versions = db.query(BreakdownVersion).filter_by(project_id=pid).count()
    before = {t for ids in _takes(db, pid).values() for t in ids}
    r = editor.post(f"/projects/{pid}/director/plan-again")
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "running"
    assert editor.post(f"/projects/{pid}/director/plan-again").status_code == 409  # one at a time
    assert editor.post(f"/projects/{pid}/director").status_code == 409  # nor Carry on beside it
    _run(app, db, ticks=4, start=False)
    assert AGAIN not in _results(db, pid)  # nothing is planned or made before Make it
    assert director.treatment(db, project)  # its treatment, then its start card
    _run(app, db)
    db.expire_all()
    project = db.get(Project, pid)
    said = _results(db, pid)
    assert said[-1] == "Delivered."
    assert said.index(AGAIN) < said.index("Drawing the stills.")  # then on from the new plan
    assert project.plan["made_at"] > plan_before  # a new plan, the old one in Earlier plans
    assert db.query(BreakdownVersion).filter_by(project_id=pid).count() > versions  # new shots
    for row in db.query(ProjectClip).filter_by(project_id=pid):  # each clip has its take
        assert row.picked_take_id is not None
    assert before <= {t for ids in _takes(db, pid).values() for t in ids}  # what was made stays


def test_carry_on_keeps_the_plan_and_the_shots(app, db, owner, editor):
    pid = _stopped(app, db, owner, editor)
    plan_before = db.get(Project, pid).plan["made_at"]
    versions = db.query(BreakdownVersion).filter_by(project_id=pid).count()
    assert editor.post(f"/projects/{pid}/director").status_code == 201  # Carry on
    _run(app, db)
    db.expire_all()
    assert AGAIN not in _results(db, pid) and _results(db, pid)[-1] == "Delivered."
    assert db.get(Project, pid).plan["made_at"] == plan_before
    assert db.query(BreakdownVersion).filter_by(project_id=pid).count() == versions


def test_the_owner_may_start_the_plan_again_and_another_editor_may_not(app, db, owner, editor):
    pid = _stopped(app, db, owner, editor)
    db.commit()
    token = owner.post("/team/invites", json={"email": "bo@example.com"}).json()["token"]
    with TestClient(app) as other:
        other.post("/auth/accept-invite", json={"token": token, "name": "Bo", "password": PASSWORD})
        assert other.post(f"/projects/{pid}/director/plan-again").status_code == 403
    assert owner.post(f"/projects/{pid}/director/plan-again").status_code == 201


def test_a_fresh_run_reads_no_plan_shots_or_takes_of_its_own_until_it_makes_them(
    app, db, owner, editor
):
    pid = _stopped(app, db, owner, editor)
    project = db.get(Project, pid)
    picked = _picked(db, pid)
    assert any(picked.values())
    run = {"id": "r", "turn": 1, "redos": {}, director.FRESH: "2999-01-01T00:00:00"}  # pressed
    # after all of it was made
    assert director.fresh(db, project, run) == (True, True)
    video = director.turn_input(db, project, run)["prompt"]
    assert '"plan": "none"' in video and '"shots": "none"' in video
    director.unpick_old_takes(db, project, run)  # its new shots aren't made yet: nothing goes
    assert _picked(db, pid) == picked
    assert director.fresh(db, project, {}) == (False, False)  # Carry on: as it was
    old = {"id": "r", director.FRESH: "2000-01-01T00:00:00"}  # its own plan and shots made
    assert director.fresh(db, project, old) == (False, False)
    director.unpick_old_takes(db, project, old)  # takes made after the press stay picked
    assert _picked(db, pid) == picked


def test_once_its_new_shots_have_prompts_each_rewritten_clip_is_made_again(app, db, owner, editor):
    """The new plan's changed shots get new prompts (`clip_prompts`): their takes from before
    the press stay only as earlier takes, so each gets a take from its new prompt. A clip whose
    shots the new plan kept as they were (moved to the new shots, not rewritten) keeps its take."""
    pid = _stopped(app, db, owner, editor)
    project = db.get(Project, pid)
    picked = _picked(db, pid)
    assert all(picked.values())
    run = {"id": "r", director.FRESH: utcnow().isoformat()}  # pressed now
    later = utcnow() + timedelta(seconds=1)  # its plan and shots made after it
    project.plan = {**project.plan, "made_at": later.isoformat()}
    old = db.query(BreakdownVersion).filter_by(project_id=pid).order_by(BreakdownVersion.id)
    old = old.all()[-1]
    new = BreakdownVersion(project_id=pid, script_version=old.script_version, source="claude",
                           data=old.data, created_at=later)  # fmt: skip
    db.add(new)
    db.commit()
    row = db.query(ProjectClip).filter_by(project_id=pid).first()
    was, row.breakdown_id = row.breakdown_id, new.id  # its shots kept as they were: moved over
    db.commit()
    director.unpick_old_takes(db, project, run)
    db.expire_all()
    assert _picked(db, pid) == picked  # it keeps its take
    row = db.query(ProjectClip).filter_by(project_id=pid).first()
    row.breakdown_id = was  # its shots changed: its prompt is being written again
    db.commit()
    director.unpick_old_takes(db, project, run)
    db.expire_all()
    assert all(t is None for t in _picked(db, pid).values())
    there = {t for ids in _takes(db, pid).values() for t in ids}
    assert set(picked.values()) <= there  # still there, as earlier takes


def _picked(db, pid: int) -> dict[str, int | None]:
    return {r.clip_id: r.picked_take_id for r in db.query(ProjectClip).filter_by(project_id=pid)}
