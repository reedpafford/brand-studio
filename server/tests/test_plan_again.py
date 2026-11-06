"""S3-08's "Start the plan again": after a Stop, a new run that writes its treatment, waits
for Make it, then plans the whole video again instead of carrying on from its shots. What was
made stays. All on the stand-ins (no paid call)."""

from app import director
from app.models.breakdowns import BreakdownVersion
from app.models.projects import Project
from tests.test_director import _made, _run


def _stopped(app, db, owner, editor) -> int:
    pid = _made(app, owner, editor, db)
    url = f"/projects/{pid}/director"
    editor.post(url)
    _run(app, db)  # delivered: shots, stills, takes and a cut
    return pid


def _results(db, pid: int) -> list[str]:
    run = director.turns(db, db.get(Project, pid))[-1].input[director.RUN]["id"]
    return [t.input.get("result", "") for t in director.turns(db, db.get(Project, pid))
            if t.input[director.RUN]["id"] == run]  # fmt: skip


def test_start_the_plan_again_plans_the_whole_video_again_after_make_it(app, db, owner, editor):
    pid = _stopped(app, db, owner, editor)
    project = db.get(Project, pid)
    plan_before, versions = project.plan["made_at"], db.query(BreakdownVersion).filter_by(
        project_id=pid).count()  # fmt: skip
    r = editor.post(f"/projects/{pid}/director/plan-again")
    assert r.status_code == 201, r.text
    assert editor.post(f"/projects/{pid}/director/plan-again").status_code == 409  # one at a time
    _run(app, db, ticks=3, start=False)
    assert "Planning the whole video again." not in _results(db, pid)  # nothing before Make it
    _run(app, db)
    db.expire_all()
    project = db.get(Project, pid)
    assert "Planning the whole video again." in _results(db, pid)
    assert project.plan["made_at"] > plan_before  # a new plan, the old one in Earlier plans
    assert db.query(BreakdownVersion).filter_by(project_id=pid).count() > versions  # new shots
    said = _results(db, pid)  # then on from the new plan, as any run goes
    assert said.index("Planning the whole video again.") < said.index("Drawing the stills.")


def test_carry_on_keeps_the_plan(app, db, owner, editor):
    pid = _stopped(app, db, owner, editor)
    plan_before = db.get(Project, pid).plan["made_at"]
    assert editor.post(f"/projects/{pid}/director").status_code == 201  # Carry on / Make it again
    _run(app, db)
    db.expire_all()
    assert "Planning the whole video again." not in _results(db, pid)
    assert db.get(Project, pid).plan["made_at"] == plan_before


def test_a_fresh_run_reads_no_plan_or_shots_of_its_own_until_it_makes_them(app, db, owner, editor):
    pid = _stopped(app, db, owner, editor)
    project = db.get(Project, pid)
    run = {director.FRESH: "2999-01-01T00:00:00"}  # pressed after everything here was made
    assert director.fresh(db, project, run) == (True, True)
    assert director.fresh(db, project, {}) == (False, False)  # Carry on: as it was
    assert director.fresh(db, project, {director.FRESH: "2000-01-01T00:00:00"}) == (False, False)
