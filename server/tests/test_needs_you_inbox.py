"""Needs you (S9-01, P-14): what each card says and the one press on it. A stuck video's fix
is the same press, at the same "up to" price, as its own stuck card in the chat (S3-11); a
press held outside any video waits here too. All on the stand-ins."""

from decimal import Decimal

from app import director, run_progress
from app.clip_takes import take_credits
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.routes.jobs import enqueue
from tests.test_asks import _dollars, _video
from tests.test_run_progress import _clip, _done, _job


def _stuck(client, pid: int) -> dict:
    return next(s for s in client.get("/needs-you").json()["stuck"] if s["video"]["id"] == pid)


def test_a_money_card_names_what_it_makes_and_the_video_says_where_it_came_from(
    app, db, owner, editor
):
    pid, _ = _video(app, owner, editor, db)
    project = db.get(Project, pid)
    db.add(Job(workspace_id=project.workspace_id, kind="image", provider="fake", input={},
               project_id=pid, credits=project.budget_credits, status="succeeded"))  # fmt: skip
    db.commit()
    editor.post(f"/projects/{pid}/plan")  # past the budget: held
    (row,) = owner.get("/needs-you").json()["money"]
    assert row["ask"]["money"]["what"] == "Make the scene plan"  # "… · $1.54 past the budget"
    assert row["ask"]["question"].startswith("Make the scene plan? That goes $")
    video = row["video"]
    assert (video["send"], video["made_by"]) == (False, "Ed")
    assert video["about"].startswith("Saved script, ") and " style" in video["about"]


def test_a_stuck_run_offers_its_own_cards_fix_at_its_price(app, db, owner, editor):
    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    last = director.turns(db, project)[-1]
    last.input = {**last.input, "result": "Stopped.",
                  "ended": "It stopped: c1's take failed 3 times."}  # fmt: skip
    _job(db, _clip(db, pid), JobStatus.failed, **{director.RUN: last.input[director.RUN]})
    db.commit()
    row = _stuck(owner, pid)
    said = run_progress.record(db, project, None)["failed"]
    assert (row["what"], row["why"]) == ("Clip 1 couldn’t be made", said["why"])
    again = run_progress.money(take_credits(db, project, _clip(db, pid)), True)
    assert row["fix"] == {"kind": "again", "label": "Try again", "price": again,
                          "clip_id": _clip(db, pid).id, "frame_id": None,
                          "problem": None}  # fmt: skip
    assert _stuck(editor, pid)["fix"]["price"].endswith("credits")  # editors: credits


def test_a_step_that_failed_outside_a_run_is_made_again_at_its_price(app, db, owner, editor):
    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    _job(db, _clip(db, pid), JobStatus.failed).error = "The service was busy."
    db.commit()
    row = _stuck(owner, pid)
    assert (row["what"], row["why"]) == ("Clip 1 couldn’t be made", "The service was busy.")
    price = run_progress.money(take_credits(db, project, _clip(db, pid)), True)
    assert (row["fix"]["kind"], row["fix"]["price"]) == ("again", price)
    project.hidden = True  # an editor's send not yet OK'd: its chat is the way in
    db.commit()
    assert _stuck(owner, pid)["fix"]["kind"] == "chat"


def test_a_press_held_outside_any_video_waits_in_needs_you(app, db, owner, editor):
    from app.models.accounts import Role, User

    them = db.query(User).filter_by(role=Role.editor).one()
    brand = owner.get("/brands").json()[0]["id"]
    script = editor.post("/scripts", json={"brand_id": brand, "title": "Gut"}).json()["id"]
    job = enqueue(db, them, "music", {"step": "song_take", "on_script": script})
    assert job.status == JobStatus.needs_owner_approval
    out = owner.get("/needs-you").json()
    (send,) = out["sends"]
    assert (send["job_id"], send["what"], send["made_by"]) == (job.id, "Gut · song", "Ed")
    assert send["brand"]["id"] == brand and send["script_id"] == script
    assert send["up_to"]["usd"] > 0 and send["held"]
    assert out["total"] == 1 and {b["id"]: b["count"] for b in out["brands"]}[brand] == 1
    other = owner.get("/needs-you", params={"brand_id": brand + 1000}).json()
    assert other["sends"] == [] and other["total"] == 1
    assert _dollars(editor.get("/needs-you").json()) == []  # their own, in credits
    assert owner.post(f"/jobs/{job.id}/approve").status_code == 200
    assert owner.get("/needs-you").json()["sends"] == []
    assert Decimal(str(send["up_to"]["credits"])) >= job.credits  # never below the charge


def test_a_take_that_fails_while_its_run_goes_on_is_the_directors_not_stuck(app, db, owner, editor):
    from tests.test_director import _made, _run

    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=2)
    project = db.get(Project, pid)
    run = director.turns(db, project)[-1].input[director.RUN]
    assert run_progress.record(db, project, None)["ended_at"] is None  # still going
    first = db.query(Job).filter_by(project_id=pid).first()
    db.add(Job(workspace_id=first.workspace_id, created_by_id=first.created_by_id, kind="video",
               provider="fake", project_id=pid, credits=Decimal("3"), status=JobStatus.failed,
               input={"step": "clip_take", director.RUN: run}, error="busy"))  # fmt: skip
    db.commit()
    assert [s for s in owner.get("/needs-you").json()["stuck"] if s["video"]["id"] == pid] == []
