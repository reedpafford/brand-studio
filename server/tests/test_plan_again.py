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
from tests.helpers import make_it, ok_when_asked
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
        ok_when_asked(db)  # the person approves the cast and places when asked
        make_it(db)
        if (
            db.query(ProjectClip)
            .filter(ProjectClip.project_id == pid, ProjectClip.picked_take_id.is_not(None))
            .count()
        ):
            break
    stopped = editor.post(f"/projects/{pid}/director/stop").json()
    assert stopped["ended"] == "Stopped.", stopped
    assert (
        db.query(ProjectClip)
        .filter(ProjectClip.project_id == pid, ProjectClip.picked_take_id.is_not(None))
        .count()
    )
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


def test_on_a_video_never_started_again_an_earlier_take_is_picked_back_as_ever(
    app, db, owner, editor
):
    """QA on f6acbb6d: only a Start the plan again run sets takes aside. On any other video a
    take from an earlier prompt is picked back as before (the watch may say it reads better)."""
    pid = _stopped(app, db, owner, editor)
    project = db.get(Project, pid)
    row = db.query(ProjectClip).filter_by(project_id=pid).first()
    first = db.get(ClipTake, row.picked_take_id)
    first.prompt = row.prompt
    second = ClipTake(clip_id=row.id, number=2, job_id=first.job_id, file_id=first.file_id,
                      prompt=row.prompt + " (a person's change)")  # fmt: skip
    db.add(second)
    db.flush()
    row.prompt, row.picked_take_id = second.prompt, second.id
    db.commit()
    state = director.video_state(db, project)
    assert not any(t["set_aside"] for c in state["clips"] for t in c["takes"])
    run = {"id": "r", "turn": 1, "redos": {}}
    assert director._aside(db, project, run, {"tool": "pick_take", "take_id": first.id}) == ""
    finding = {"clip_id": row.clip_id, "fix": "pick", "take_id": first.id,
               "says": "Take 1 reads better."}  # fmt: skip
    state = {**state, "allowed": {}, "treatment": "written", "started": True, "cut": "made",
             "stills_review": {"state": "done"},
             "watch": {"state": "done", "current": True, "findings": [finding]}}  # fmt: skip
    for c in state["clips"]:
        for t in c["takes"]:
            t["verdict"] = "clean"
    made = director.choose(state)
    assert (made["tool"], made["take_id"]) == ("pick_take", first.id)


def test_a_take_a_person_picks_after_the_press_is_theirs(app, db, owner, editor):
    """In a Start the plan again run, once the old takes are set aside, a person who picks one
    back in Clips keeps it: the director neither refuses it nor makes the clip again."""
    pid = _stopped(app, db, owner, editor)
    project = db.get(Project, pid)
    picked = _picked(db, pid)
    run = {"id": "r", "turn": 1, "redos": {}, director.FRESH: utcnow().isoformat()}
    later = utcnow() + timedelta(seconds=1)
    project.plan = {**project.plan, "made_at": later.isoformat()}
    old = db.query(BreakdownVersion).filter_by(project_id=pid).order_by(BreakdownVersion.id)
    old = old.all()[-1]
    db.add(BreakdownVersion(project_id=pid, script_version=old.script_version, source="claude",
                            data=old.data, created_at=later))  # fmt: skip
    db.commit()
    director.unpick_old_takes(db, project, run)
    clip, take = next(iter(picked.items()))
    row = db.query(ProjectClip).filter_by(project_id=pid, clip_id=clip).one()
    row.picked_take_id = take  # a person picks it back in Clips
    db.commit()
    assert director._aside(db, project, run, {"tool": "pick_take", "take_id": take}) == ""
    clips = director.video_state(db, project)["clips"]
    director.set_aside(db, project, run, clips)
    mine = next(c for c in clips if c["clip_id"] == clip)
    assert not next(t for t in mine["takes"] if t["id"] == take)["set_aside"]


def _picked(db, pid: int) -> dict[str, int | None]:
    return {r.clip_id: r.picked_take_id for r in db.query(ProjectClip).filter_by(project_id=pid)}


def test_carrying_on_a_stopped_plan_again_run_still_makes_every_clip_again(app, db, owner, editor):
    """QA on ceef469c: Stop after Start the plan again set the old takes aside, then Carry on.
    The new run carries the press on, so no take from before it is picked back; and the
    stopped card counts no clip as made while only its old takes are there."""
    pid = _stopped(app, db, owner, editor)
    assert editor.post(f"/projects/{pid}/director/plan-again").status_code == 201
    providers = get_providers(app.state.settings, app.state.storage)
    for _ in range(120):  # until its old takes are set aside, before any new take
        run_once(db, providers, app.state.storage)
        db.expire_all()
        ok_when_asked(db)  # the person approves the cast and places when asked
        make_it(db)
        if director.turns(db, db.get(Project, pid))[-1].input[director.RUN].get(director.UNPICKED):
            break
    run = director.turns(db, db.get(Project, pid))[-1].input[director.RUN]
    assert run.get(director.UNPICKED)
    assert editor.post(f"/projects/{pid}/director/stop").json()["ended"] == "Stopped."
    stopped = editor.get(f"/projects/{pid}/director/progress").json()["stopped"]
    assert stopped["made"] == 0  # its old takes don't count as made
    assert editor.post(f"/projects/{pid}/director").status_code == 201  # Carry on
    carried = director.turns(db, db.get(Project, pid))[-1].input[director.RUN]
    assert carried[director.FRESH] == run[director.FRESH] and carried[director.UNPICKED]
    _run(app, db, ticks=150)
    db.expire_all()
    pressed = datetime.fromisoformat(run[director.FRESH])
    rows = db.query(ProjectClip).filter_by(project_id=pid).all()
    assert rows and all(r.picked_take_id for r in rows)
    for row in rows:  # every clip made again after the press
        assert db.get(ClipTake, row.picked_take_id).created_at > pressed


def test_after_a_plan_again_run_delivers_the_next_run_is_a_normal_one(app, db, owner, editor):
    pid = _stopped(app, db, owner, editor)
    editor.post(f"/projects/{pid}/director/plan-again")
    project = db.get(Project, pid)
    last = director.turns(db, project)[-1]
    last.input = {**last.input, "result": "Delivered."}
    db.commit()
    assert director._replanning(db, project) == {}


def test_a_plan_again_whose_cast_needs_its_ok_again_waits_for_it_beside_set_aside_takes(
    app, db, owner, editor
):
    """A clip whose takes are all set aside and that waits for the cast and places OK waits for
    it (never a take before the OK); the others are made again meanwhile."""
    pid = _stopped(app, db, owner, editor)
    state = director.video_state(db, db.get(Project, pid))
    (c,) = state["clips"][:1]
    base = {**state, "allowed": {}, "treatment": "written", "started": True,
            "stills_review": {"state": "done"}, "being_made": 0, "held_for_owner": []}  # fmt: skip
    aside = [{**t, "set_aside": True} for t in c["takes"]]
    waits = {**c, "takes": aside, "picked_take_id": None, "waits_for_cast": True}
    free = {**c, "clip_id": "c9", "takes": aside, "picked_take_id": None, "waits_for_cast": False}
    made = director.choose({**base, "clips": [waits, free]})
    assert made["tool"] == "make_take" and made["clip_id"] is None  # the one that may be made
    made = director.choose({**base, "clips": [waits]})
    assert made["tool"] == "wait" and "cast and places" in made["why"]
