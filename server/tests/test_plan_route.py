"""A video's scene plan (flows 1b, P1/P2), on the free stand-in writer."""

from datetime import timedelta

from app.db import utcnow
from app.models.jobs import Job
from app.models.projects import Project
from app.providers.fake_local import FakeWriter
from app.worker import run_once
from tests.test_breakdown import BREAKDOWN
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture


def _write(app, db):
    run_once(db, {"claude": FakeWriter()}, app.state.storage, only={"claude"})


def test_make_check_edit_and_approve_the_plan(app, db, editor, setup):  # noqa: F811
    pid = setup["project"]
    url = f"/projects/{pid}/plan"
    assert editor.get(url).status_code == 404  # E: no plan yet
    assert editor.get(f"/projects/{pid}").json()["plan_status"] == "none"
    price = editor.get(f"/projects/{pid}").json()["plan_credits"]
    job = editor.post(url, json={}).json()
    assert job["credits"] == price == 3  # the price shown is the price charged
    assert editor.get(url).json()["job"]["status"] == "queued"
    assert editor.post(url, json={}).status_code == 409  # one at a time
    _write(app, db)
    plan = editor.get(url).json()
    assert plan["status"] == "ready" and plan["source"] == "claude" and plan["job"] is None
    assert [x["n"] for s in plan["scenes"] for x in s["lines"]] == [2, 3, 4]  # each line once
    assert plan["scenes"][0]["lines"][1]["text"] == "MOM: Nate, where is all your money?"
    assert plan["scenes"][0]["place"] == "SCENE 1 — INT. KITCHEN" and plan["scenes"][0]["time"]
    assert any(a["kind"] == "no_product" for a in plan["advice"])  # Advice, never a block

    scenes = [{**s, "lines": [{**x, "star": x["n"] == 3} for x in s["lines"]]}
              for s in plan["scenes"]]  # fmt: skip
    starred = editor.put(url, json={"scenes": scenes}).json()
    assert starred["scenes"][0]["lines"][1]["star"] is True
    assert not any(a["kind"] == "no_product" for a in starred["advice"])
    split = [{**scenes[0], "lines": scenes[0]["lines"][:1]},
             {**scenes[0], "lines": scenes[0]["lines"][1:]}]  # Split here  # fmt: skip
    assert len(editor.put(url, json={"scenes": split}).json()["scenes"]) == 2
    lost = [{**scenes[0], "lines": scenes[0]["lines"][1:]}]  # a line dropped: never saved
    assert editor.put(url, json={"scenes": lost}).status_code == 422

    done = editor.post(f"{url}/approve").json()
    assert done["plan"]["status"] == "approved" and done["job"]["step"] == "breakdown"
    assert done["job"]["credits"] == done["plan"]["approve_credits"]
    queued = db.get(Job, done["job"]["id"])
    assert "<plan>" in queued.input["prompt"] and queued.input["plan_version"] == 3
    assert editor.get(f"/projects/{pid}").json()["plan_status"] == "approved"
    assert editor.post(f"{url}/approve").status_code == 409
    _run(app, db, FakeClaude(BREAKDOWN))
    shots = editor.get(f"/projects/{pid}/breakdown").json()
    assert shots["breakdown"].get("plan_version") is None or shots["older_plan"] is False
    editor.put(url, json={"scenes": split[::1]})  # an edit after: the shots are older
    assert editor.get(f"/projects/{pid}/breakdown").json()["older_plan"] is True
    assert editor.get(url).json()["status"] == "ready"


def test_an_old_video_is_planned_from_its_breakdown_free(app, db, editor, setup):  # noqa: F811
    pid = setup["project"]
    editor.post(f"/projects/{pid}/breakdown")  # made before plans existed
    _run(app, db, FakeClaude(BREAKDOWN))
    db.get(Project, pid).plan = None
    db.commit()
    assert editor.get(f"/projects/{pid}").json()["plan_status"] == "approved"  # never opened
    plan = editor.get(f"/projects/{pid}/plan").json()
    assert (plan["status"], plan["source"]) == ("approved", "breakdown")
    assert editor.get(f"/projects/{pid}/breakdown").json()["older_plan"] is False


def test_write_it_myself_earlier_plans_stop_and_the_time_limit(app, db, editor, setup):  # noqa: F811
    pid = setup["project"]
    url = f"/projects/{pid}/plan"
    mine = editor.post(f"{url}/by-hand").json()
    assert mine["source"] == "hand"
    assert [x["action"] for x in mine["scenes"][0]["lines"]] == [""] * 3  # cards to fill in
    assert editor.post(f"{url}/approve").json()["detail"] == "Give every line an action first."
    job = editor.post(url, json={"note": "funnier"}).json()
    assert "<note>funnier</note>" in db.get(Job, job["id"]).input["prompt"]
    assert editor.post(f"{url}/stop").status_code == 204  # nothing charged, the plan stays
    assert db.get(Job, job["id"]).status == "cancelled"
    assert editor.get(url).json()["source"] == "hand"
    assert editor.post(f"{url}/stop").status_code == 409

    job = editor.post(url, json={}).json()
    _write(app, db)
    assert editor.get(url).json()["source"] == "claude"
    back = editor.post(f"{url}/earlier/0/use").json()  # Earlier plans: one press, free
    assert back["source"] == "hand" and back["earlier"][0]["source"] == "claude"
    versions = [back["version"], *(e["version"] for e in back["earlier"])]
    assert back["version"] == max(versions) and len(set(versions)) == len(versions)  # Flow-QA

    slow = editor.post(url, json={}).json()
    row = db.get(Job, slow["id"])
    row.status, row.started_at = "running", utcnow() - timedelta(minutes=11)
    db.commit()
    said = editor.get(url).json()["job"]
    assert (said["status"], said["reason"]) == ("failed", "The plan took too long and was "
                                                "stopped. Nothing was charged.")  # fmt: skip
    db.expire_all()
    assert db.get(Job, slow["id"]).status == "cancelled"  # never counted
