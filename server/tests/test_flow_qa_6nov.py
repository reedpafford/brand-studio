"""Flow-QA on the test site, 6 Nov (.context/team/flow-qa-6nov): M1 the owner is never held for
his own OK; M4 nothing runs (or is charged) while a send waits for the owner; a revision starts
by talking (S3-12, the leftover Make it again press gone); S7 the header says what the video is
doing. All on the stand-ins (no paid call)."""

from app import credits, director, ideas
from app.models.freestyles import Freestyle
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from tests.conftest import first_brand
from tests.test_director import _made, _run
from tests.test_freestyle_dialogue import BODY
from tests.test_freestyle_dialogue import _run as _fs_run


def _owners_freestyle(app, db, owner) -> tuple[dict, int]:
    app.state.settings.fake_providers = True
    fs = owner.post("/freestyles", json={**BODY, "brand_id": first_brand(owner)}).json()
    _fs_run(app, db, ticks=120)
    assert owner.get(f"/freestyles/{fs['id']}").json()["status"] == "delivered"
    return fs, db.get(Freestyle, fs["id"]).project_id


def test_m1_the_owners_own_start_card_never_holds_him_for_his_own_ok(app, db, owner):
    fs, pid = _owners_freestyle(app, db, owner)
    for press in ("", "/plan-again"):  # Make it again (by talking), Start the plan again
        if press:
            owner.post(f"/projects/{pid}/director/stop")
            assert owner.post(f"/projects/{pid}/director{press}").status_code == 201
        else:
            said = owner.post(f"/projects/{pid}/director/messages",
                              json={"text": "Make clip 1 slower."})  # its card  # fmt: skip
            assert said.json()["status"] == "running"  # a revision starts by talking
        _fs_run(app, db, ticks=6, start=False)  # its plan, then its start card: his own press
        out = owner.get(f"/freestyles/{fs['id']}").json()
        assert out["status"] == "working", press  # never "waiting" for himself (rule 5)
        cards = [a for a in owner.get(f"/projects/{pid}/asks").json()
                 if a["kind"] in ("start", "plan") and a["state"] == "open"]  # fmt: skip
        assert cards, press  # his own card: Make it, or more planning past its allowance
        assert {"make_it", "approve"} & set(cards[-1]["can"]) and "$" in cards[-1]["question"]


def test_m4_a_held_send_plans_within_its_cap_and_no_generation_runs_before_the_yes(
    app, db, owner, editor
):
    """M4 as Reed decided it (4 Nov): an editor's held send gets its plan before the owner's OK
    (a small planning spend, inside the cap); no generation runs until they say yes."""
    held = editor.post("/freestyles", json=BODY).json()  # an editor's New video send
    _fs_run(app, db, ticks=6, start=False)
    pid = db.get(Freestyle, held["id"]).project_id
    charged = {j.input.get("step") for j in db.query(Job).filter(
        Job.project_id == pid, Job.status.in_(credits.COUNTED))}  # fmt: skip
    assert charged <= {"director", "treatment"}  # its plan only: no generation
    (turn,) = db.query(Job).filter(Job.project_id == pid,
                                   Job.status == JobStatus.needs_owner_approval).all()  # fmt: skip
    assert turn.input.get(director.START)  # its start card, for the owner


def test_a_revision_starts_by_talking_and_after_a_stop_the_note_waits(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    url = f"/projects/{pid}/director"
    editor.post(url)
    _run(app, db)
    assert editor.get(url).json()["status"] == "delivered"
    out = editor.post(f"{url}/messages", json={"text": "Make clip 1 slower."}).json()
    assert (out["status"], out["unread"]) == ("running", 0)  # the next run reads it (S3-12)
    editor.post(f"{url}/stop")
    out = owner.post(f"{url}/messages", json={"text": "And warmer."}).json()
    assert out["status"] == "ended" and out["unread"] >= 1  # for Carry on or the next run


def _status(owner, db, pid: int):
    head = owner.get(f"/projects/{pid}/idea").json()["status"]
    return head["kind"], head["reason"]


def test_s7_the_header_says_stopped_after_a_stop_whatever_else_waits(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=12)
    editor.post(f"/projects/{pid}/director/stop")
    _run(app, db, ticks=3, start=False)
    assert _status(owner, db, pid)[0] == "stopped"


def test_s7_a_newer_run_that_ended_on_its_own_never_reads_delivered(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    project = db.get(Project, pid)
    assert _status(owner, db, pid)[0] == "delivered" and project.finished_at
    last = director.turns(db, project)[-1]  # a later run that ended by itself, not delivered
    db.add(Job(workspace_id=project.workspace_id, project_id=pid, kind="write-claude",
               provider="claude",
               status=JobStatus.succeeded, credits=0, created_by_id=last.created_by_id,
               input={**last.input, director.RUN: {**last.input[director.RUN], "id": "later"},
                      "result": "Refused again: no.", "ended": "It stopped: no."}))  # fmt: skip
    db.commit()
    assert _status(owner, db, pid)[0] == "needs_fix"


def test_s7_a_run_waiting_on_the_cast_ok_says_so(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=3)
    project = db.get(Project, pid)
    last = director.turns(db, project)[-1]
    last.input = {**last.input, "result": director.CAST_WAIT}
    db.commit()
    db.query(Job).filter(Job.project_id == pid, Job.status.in_(
        (JobStatus.queued, JobStatus.running))).update(
        {Job.status: JobStatus.succeeded}, synchronize_session=False)  # fmt: skip
    db.commit()
    assert _status(owner, db, pid) == ("needs_you", ideas.CAST_OK)  # never "Working"
