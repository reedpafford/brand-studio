"""S3-08's "Start the plan again": after a person's Stop, a new run that writes its treatment,
waits for Make it, then plans the whole video again (a new plan, new shots, every clip made
anew) instead of carrying on from its shots. What was made stays, as earlier plans and takes.
All on the stand-ins (no paid call)."""

import json
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app import asks, director
from app.db import utcnow
from app.models.asks import Ask
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job, JobStatus
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
    run = director.turns(db, project)[-1].input[director.RUN]
    mine = db.query(Job).filter(Job.input["step"].as_string() == "treatment",
                                Job.input[director.RUN]["id"].as_string() == run["id"],
                                Job.status == JobStatus.succeeded)  # fmt: skip
    assert mine.count() == 1  # its own new treatment
    card = db.query(Ask).filter_by(project_id=pid, kind="start", run=run["id"]).one()
    assert asks.state(db, card) == "open"  # and its own start card, waiting for Make it
    _run(app, db, ticks=150)
    db.expire_all()
    project = db.get(Project, pid)
    said = _results(db, pid)
    assert "Made the cut." in said  # (a remake past the budget then waits for the owner)
    assert said.index(AGAIN) < said.index("Drawing the stills.") < said.index("Made the cut.")
    assert project.plan["made_at"] > plan_before  # a new plan, the old one in Earlier plans
    assert db.query(BreakdownVersion).filter_by(project_id=pid).count() > versions  # new shots
    pressed = datetime.fromisoformat(run[director.FRESH])
    for row in db.query(ProjectClip).filter_by(project_id=pid):  # every clip made again
        assert db.get(ClipTake, row.picked_take_id).created_at > pressed
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
    assert all(picked.values())
    run = {"id": "r", "turn": 1, "redos": {}, director.FRESH: "2999-01-01T00:00:00"}  # pressed
    # after all of it was made: no plan, shots or takes of its own yet
    assert director.fresh(db, project, run) == (True, True)
    video = director.turn_input(db, project, run)["prompt"]
    assert '"plan": "none"' in video and '"shots": "none"' in video
    director.unpick_old_takes(db, project, run)  # its new shots aren't made yet: nothing goes
    assert _picked(db, pid) == picked and director.UNPICKED not in run
    assert director.fresh(db, project, {}) == (False, False)  # Carry on: as it was
    assert '"set_aside": true' not in director.turn_input(db, project, {**run, director.FRESH: ""})[
        "prompt"]  # fmt: skip


def test_once_its_new_shots_are_made_every_take_from_before_is_set_aside(app, db, owner, editor):
    """Once the new plan's shots are made, every clip's take from before the press stays only as
    an earlier take: the director reads it `set_aside`, a pick of it is refused, and the clip
    gets a take of its own."""
    pid = _stopped(app, db, owner, editor)
    project = db.get(Project, pid)
    picked = _picked(db, pid)
    run = {"id": "r", "turn": 1, "redos": {}, director.FRESH: utcnow().isoformat()}
    later = utcnow() + timedelta(seconds=1)  # its plan and shots made after the press
    project.plan = {**project.plan, "made_at": later.isoformat()}
    old = db.query(BreakdownVersion).filter_by(project_id=pid).order_by(BreakdownVersion.id)
    old = old.all()[-1]
    db.add(BreakdownVersion(project_id=pid, script_version=old.script_version, source="claude",
                            data=old.data, created_at=later))  # fmt: skip
    db.commit()
    video = json.loads(director.turn_input(db, project, run)["prompt"].split("<video>")[1]
                       .split("</video>")[0])  # fmt: skip
    takes = [t for c in video["clips"] for t in c["takes"]]
    assert takes and all(t["set_aside"] for t in takes)
    clip, take = next(iter(picked.items()))
    said = director._aside(db, project, run, {"tool": "pick_take", "take_id": take})
    assert said.startswith("Refused: take 1 of") and "Make a new take" in said
    director.unpick_old_takes(db, project, run)
    db.expire_all()
    assert all(t is None for t in _picked(db, pid).values()) and run[director.UNPICKED]
    assert set(picked.values()) <= {t for ids in _takes(db, pid).values() for t in ids}  # kept


def test_a_take_from_an_earlier_prompt_is_set_aside_in_any_run(app, db, owner, editor):
    """A clip whose prompt was written again (a re-plan, a split) never has its take from the
    earlier prompt picked: the stand-in makes it a take from its prompt now."""
    pid = _stopped(app, db, owner, editor)
    project = db.get(Project, pid)
    row = db.query(ProjectClip).filter_by(project_id=pid).first()
    take = db.get(ClipTake, row.picked_take_id)
    take.prompt = (take.prompt or row.prompt) + " (earlier)"
    db.commit()
    state = director.video_state(db, project)
    (mine,) = [c for c in state["clips"] if c["clip_id"] == row.clip_id]
    assert all(t["set_aside"] for t in mine["takes"] if t["id"] == take.id)
    state = {**state, "allowed": {}, "treatment": "written", "started": True,
             "stills_review": {"state": "done"}}  # fmt: skip
    assert [c["clip_id"] for c in state["clips"]] == [row.clip_id]
    made = director.choose(state)
    assert (made["tool"], made["clip_id"]) == ("make_take", row.clip_id)


def _picked(db, pid: int) -> dict[str, int | None]:
    return {r.clip_id: r.picked_take_id for r in db.query(ProjectClip).filter_by(project_id=pid)}
