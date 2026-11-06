"""Board S3-08's Carry on: after a person's Stop, "Carry on · up to $10.74 more" is what's left
of the stopped run's OWN approved price ($16.86 − $6.12; rule 34, Reed 6 Nov: each run its own
price, so a run never spends another's leftover). Inside it the same run goes on under the
owner's existing OK, with no new start card; past it, its steps wait for the owner. An editor
reads credits. All on the stand-ins (no paid call)."""

from decimal import Decimal

from app import asks, director, run_progress
from app.credits import PAST_APPROVED
from app.models.asks import Ask
from app.models.clips import ProjectClip
from app.models.freestyles import Freestyle
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.providers import get_providers
from app.worker import run_once
from tests.conftest import first_brand
from tests.helpers import make_it, ok_when_asked
from tests.test_director import _made, _run


def _until(app, db, pid: int, ticks=120, made=1) -> None:
    """The run goes on until `made` clips have a take, as the person approves when asked."""
    providers = get_providers(app.state.settings, app.state.storage)
    for _ in range(ticks):
        run_once(db, providers, app.state.storage)
        db.expire_all()
        ok_when_asked(db)
        make_it(db)
        picked = db.query(ProjectClip).filter(ProjectClip.project_id == pid,
                                              ProjectClip.picked_take_id.is_not(None))  # fmt: skip
        if picked.count() >= made:
            return


def _stop(client, db, app, pid: int) -> None:
    assert client.post(f"/projects/{pid}/director/stop").json()["ended"] == "Stopped."
    _run(app, db, ticks=4, start=False)  # what it started finishes; no more turns


def _stopped(app, db, owner, editor) -> int:
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _until(app, db, pid)
    _stop(editor, db, app, pid)
    return pid


def _left(db, pid: int) -> Decimal:
    price, spent = asks.approved_run(db, db.get(Project, pid))
    return price - spent


def _starts(db, pid: int) -> int:
    return db.query(Ask).filter_by(project_id=pid, kind="start").count()


def test_the_figure_is_the_rest_of_the_stopped_runs_own_price(app, db, owner, editor):
    pid = _stopped(app, db, owner, editor)
    left = _left(db, pid)
    assert left > 0 and run_progress.carry_left(db, db.get(Project, pid)) == left
    owners = owner.get(f"/projects/{pid}/director/progress").json()["stopped"]["carry_on"]
    editors = editor.get(f"/projects/{pid}/director/progress").json()["stopped"]["carry_on"]
    assert owners == run_progress.money(left, True) and owners.startswith("$")  # dollars
    assert editors == run_progress.money(left, False) and editors.endswith("credits")  # credits
    head = owner.get(f"/projects/{pid}/idea").json()  # one run: the header's sum, to the cent
    diff = Decimal(str(head["up_to"]["usd"])) - Decimal(str(head["spent"]["usd"]))
    assert abs(Decimal(owners[1:]) - diff) <= Decimal("0.01")


def test_inside_it_the_same_run_goes_on_with_no_new_start_card(app, db, owner, editor):
    pid = _stopped(app, db, owner, editor)
    project = db.get(Project, pid)
    stopped = director.turns(db, project)[-1].input[director.RUN]
    cards, card = _starts(db, pid), asks.approved_run(db, project)[0]
    since = len(director.turns(db, project))
    r = editor.post(f"/projects/{pid}/director/carry-on")  # the editor's own video
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "running" and r.json()["started"]  # no Make it again
    assert editor.post(f"/projects/{pid}/director/carry-on").status_code == 409  # one at a time
    run = director.turns(db, project)[-1].input[director.RUN]
    assert run["id"] == stopped["id"] and run["ok"]  # the same run: its counts and notes
    assert run["redos"] == stopped["redos"] and run["turn"] > stopped["turn"]
    out = editor.get(f"/projects/{pid}/director").json()  # the header: "Working", never
    assert out["status"] == "running" and any(t["tool"] for t in out["turns"])  # "· starting"
    assert editor.get(f"/projects/{pid}/director/progress").json()["stopped"] is None
    _run(app, db, ticks=120, start=False)  # nobody presses Make it: none is needed
    db.expire_all()
    assert _starts(db, pid) == cards  # no new start card
    assert asks.approved_run(db, project)[0] == card  # under the same OK
    tools = [(t.output or {}).get("tool") for t in director.turns(db, project)[since:]]
    assert tools and "treatment" not in tools  # it goes on where it left off
    assert director.turns(db, project)[-1].input.get("result") == director.DELIVERED
    held = db.query(Job).filter_by(project_id=pid, status=JobStatus.needs_owner_approval)
    assert held.count() == 0


def test_past_it_a_step_waits_for_the_owner(app, db, owner, editor):
    pid = _stopped(app, db, owner, editor)
    project = db.get(Project, pid)
    card = db.query(Job).filter(Job.project_id == pid, Job.input[asks.START].as_boolean()
                                ).order_by(Job.id.desc()).first()  # fmt: skip
    spent = asks.approved_run(db, project)[1]
    card.input = {**card.input, "price": str(spent + Decimal("0.01"))}  # almost none left
    db.commit()
    assert run_progress.carry_left(db, project) == Decimal("0.01")
    assert editor.post(f"/projects/{pid}/director/carry-on").status_code == 201
    _run(app, db, ticks=20, start=False)
    db.expire_all()
    held = db.query(Job).filter_by(project_id=pid, status=JobStatus.needs_owner_approval).all()
    assert held and held[0].input.get("held") == PAST_APPROVED  # the owner's OK first
    assert [a for a in owner.get(f"/projects/{pid}/asks").json() if a["state"] == "open"]


def test_with_no_make_it_it_is_a_new_run_with_its_start_card(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=3, start=False)  # its plan, then its card: never pressed
    _stop(editor, db, app, pid)
    assert run_progress.carry_left(db, db.get(Project, pid)) is None
    cards = _starts(db, pid)
    assert editor.post(f"/projects/{pid}/director/carry-on").status_code == 201
    run = director.turns(db, db.get(Project, pid))[-1].input[director.RUN]
    assert not run["ok"]  # a new run: its plan, then its own card
    _run(app, db, ticks=6, start=False)  # a new run: its plan waits on the planning cap's OK
    cards_now = db.query(Ask).filter(Ask.project_id == pid, Ask.kind.in_(("start", "plan")))
    assert cards_now.count() > cards  # (or its own start card), never the old run's OK


def test_after_a_delivery_and_a_second_run_it_is_that_runs_own_rest(app, db, owner, editor):
    """Rule 34 per run: once a run delivered, a second run's Carry on is what's left of the
    second run's own price, never the first run's leftover."""
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=120)
    project = db.get(Project, pid)
    assert director.turns(db, project)[-1].input.get("result") == director.DELIVERED
    first = _left(db, pid)
    editor.post(f"/projects/{pid}/director/messages", json={"text": "Make clip 1 slower."})
    assert editor.post(f"/projects/{pid}/director").status_code == 201  # Make it again
    providers = get_providers(app.state.settings, app.state.storage)
    for _ in range(40):  # its own start card pressed, then it works a turn or two
        run_once(db, providers, app.state.storage)
        db.expire_all()
        ok_when_asked(db)
        make_it(db)
        rows = director.turns(db, project)
        if rows[-1].input[director.RUN].get("ok") and len(rows) > 3:
            break
    second = director.turns(db, project)[-1].input[director.RUN]
    assert second["ok"]
    _stop(editor, db, app, pid)
    card = db.query(Job).filter(Job.project_id == pid, Job.input[asks.START].as_boolean()
                                ).order_by(Job.id.desc()).first()  # fmt: skip
    assert card.input[director.RUN]["id"] == second["id"]  # the second run's own Make it
    left = run_progress.carry_left(db, project)
    price, spent = asks.approved_run(db, project)
    assert left == price - spent and price == Decimal(str(card.input["price"]))
    assert left != first  # never the first run's leftover


def test_a_freestyles_carry_on_is_its_runs_own_rest(app, db, owner):
    from tests.test_freestyle_dialogue import BODY

    app.state.settings.fake_providers = True
    fs = owner.post("/freestyles", json={**BODY, "brand_id": first_brand(owner)}).json()
    pid = db.get(Freestyle, fs["id"]).project_id
    _until(app, db, pid)
    _stop(owner, db, app, pid)
    db.expire_all()
    left = _left(db, pid)
    stopped = owner.get(f"/projects/{pid}/director/progress").json()["stopped"]
    assert stopped["carry_on"] == run_progress.money(left, True)
    assert owner.post(f"/projects/{pid}/director/carry-on").status_code == 201
    run = director.turns(db, db.get(Project, pid))[-1].input[director.RUN]
    assert run["ok"] and _starts(db, pid) == 1  # the same run, under its one OK


def test_carrying_on_a_stopped_plan_again_run_keeps_its_press(app, db, owner, editor):
    """#1360: Stop after Start the plan again set the old takes aside, then Carry on: the same
    run goes on, keeping the press, so every clip is still made again."""
    pid = _stopped(app, db, owner, editor)
    assert editor.post(f"/projects/{pid}/director/plan-again").status_code == 201
    providers = get_providers(app.state.settings, app.state.storage)
    project = db.get(Project, pid)
    for _ in range(120):
        run_once(db, providers, app.state.storage)
        db.expire_all()
        ok_when_asked(db)
        make_it(db)
        if director.turns(db, project)[-1].input[director.RUN].get(director.UNPICKED):
            break
    run = director.turns(db, project)[-1].input[director.RUN]
    assert run.get(director.UNPICKED)
    _stop(editor, db, app, pid)
    assert editor.post(f"/projects/{pid}/director/carry-on").status_code == 201
    carried = director.turns(db, project)[-1].input[director.RUN]
    assert carried["ok"] and carried["id"] == run["id"]  # the same run goes on
    assert carried[director.FRESH] == run[director.FRESH] and carried[director.UNPICKED]


def _make_it_again_and_stop_at_its_card(app, db, owner, editor, press: str) -> int:
    """A delivered video, then a second run (Make it again, or Start the plan again) stopped
    while its start card waits: nobody pressed its Make it."""
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=120)
    project = db.get(Project, pid)
    assert director.turns(db, project)[-1].input.get("result") == director.DELIVERED
    assert editor.post(f"/projects/{pid}/director{press}").status_code == 201
    _run(app, db, ticks=6, start=False)  # its plan, then its card waits
    _stop(editor, db, app, pid)
    return pid


def test_a_run_stopped_at_its_start_card_is_never_carried_on_under_an_earlier_ok(
    app, db, owner, editor
):
    """QA on 58cc8940: a second run stopped while its start card waited was carried on under
    the first run's OK. Its own Make it was never pressed: Carry on is a new run's card."""
    for press in ("", "/plan-again"):
        pid = _make_it_again_and_stop_at_its_card(app, db, owner, editor, press)
        project = db.get(Project, pid)
        assert run_progress.carry_left(db, project) is None
        stopped = director.turns(db, project)[-1].input[director.RUN]
        assert editor.post(f"/projects/{pid}/director/carry-on").status_code == 201
        run = director.turns(db, project)[-1].input[director.RUN]
        assert run["id"] != stopped["id"] and not run["ok"]  # a new run, with its own card
        editor.post(f"/projects/{pid}/director/stop")


def test_carrying_on_keeps_the_directors_own_limit_and_its_notes(app, db, owner, editor,
                                                                 monkeypatch):  # fmt: skip
    """QA on 58cc8940: the director's own limit and its real-cost guard are the run's, so a
    step the run would hold before Carry on is still held after it; and the notes from before
    the Stop keep their numbers and read marks."""
    pid = _made(app, owner, editor, db)
    url = f"/projects/{pid}/director"
    editor.post(url)
    _until(app, db, pid)
    editor.post(f"{url}/messages", json={"text": "Make clip 1 slower."})  # a note in the run
    _run(app, db, ticks=2, start=False)
    _stop(editor, db, app, pid)
    project = db.get(Project, pid)
    run = director.turns(db, project)[-1].input[director.RUN]
    before = director.chat(project, run["id"])
    db.expire_all()
    said = owner.post(f"{url}/messages", json={"text": "And end on the capsule."})  # after it
    assert said.status_code == 201, said.text
    charged, _ = director.own_charged(db, run["id"])
    monkeypatch.setattr(director, "OWN_CREDITS", charged + Decimal("0.01"))  # none left
    assert editor.post(f"{url}/carry-on").status_code == 201
    turn = director.turns(db, project)[-1]
    assert turn.status == JobStatus.needs_owner_approval
    assert turn.input.get("held", "").startswith("Waiting for the owner's OK: the director")
    db.expire_all()
    project = db.get(Project, pid)
    notes = director.chat(project, run["id"])
    assert notes[: len(before)] == before and notes[-1]["text"] == "And end on the capsule."


def test_after_the_owners_stop_an_editors_carry_on_waits_for_the_owner(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _until(app, db, pid)
    _stop(owner, db, app, pid)  # the owner stopped it
    left = run_progress.carry_left(db, db.get(Project, pid))
    assert editor.post(f"/projects/{pid}/director/carry-on").status_code == 201
    project = db.get(Project, pid)
    held = director.turns(db, project)[-1]
    assert held.status == JobStatus.needs_owner_approval
    assert held.input.get("held") == director.CARRY_HOLD
    card = next(a for a in owner.get(f"/projects/{pid}/asks").json()
                if a["kind"] == "start" and a["state"] == "open")  # fmt: skip
    assert card["question"] == f"Carry on for up to {run_progress.money(left, True)} more?"
    assert (
        "make_it"
        not in next(a for a in editor.get(f"/projects/{pid}/asks").json() if a["id"] == card["id"])[
            "can"
        ]
    )  # the owner's to press
    assert asks.approved_total(db, project) == asks.approved_run(db, project)[0]  # one price
    r = owner.post(f"/asks/{card['id']}/answer", json={"how": "make_it"})
    assert r.status_code == 200, r.text
    _run(app, db, ticks=80, start=False)
    assert director.turns(db, project)[-1].input.get("result") == director.DELIVERED


def test_after_the_editors_own_stop_they_carry_on_inside_the_rest(app, db, owner, editor):
    pid = _stopped(app, db, owner, editor)  # the editor stopped their own run
    assert editor.post(f"/projects/{pid}/director/carry-on").status_code == 201
    turn = director.turns(db, db.get(Project, pid))[-1]
    assert turn.status != JobStatus.needs_owner_approval


def _held_carry(app, db, owner, editor) -> tuple[int, dict]:
    """The owner stopped the run, the editor pressed Carry on: it waits on the owner's card."""
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _until(app, db, pid)
    _stop(owner, db, app, pid)
    assert editor.post(f"/projects/{pid}/director/carry-on").status_code == 201
    card = next(a for a in owner.get(f"/projects/{pid}/asks").json()
                if a["kind"] == "start" and a["state"] == "open")  # fmt: skip
    return pid, card


def _still_stopped(client, pid: int) -> None:
    out = client.get(f"/projects/{pid}/director").json()
    assert out["status"] == "ended" and out["ended"] == "Stopped."
    stopped = client.get(f"/projects/{pid}/director/progress").json()["stopped"]
    assert stopped and stopped["by"] and stopped["carry_on"]  # its Stop line and its presses
    assert client.get(f"/projects/{pid}/idea").json()["status"]["kind"] == "stopped"


def test_while_the_owners_ok_waits_the_run_stays_stopped(app, db, owner, editor):
    pid, _ = _held_carry(app, db, owner, editor)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["ended"] == "Stopped."  # nothing goes on before the owner says yes
    assert editor.get(f"/projects/{pid}/director/progress").json()["stopped"]["carry_on"] == ""
    again = editor.post(f"/projects/{pid}/director/carry-on")
    assert (again.status_code, again.json()["detail"]) == (409, director.CARRY_WAITING)


def test_a_declined_carry_on_leaves_the_run_stopped(app, db, owner, editor):
    pid, card = _held_carry(app, db, owner, editor)
    r = owner.post(f"/asks/{card['id']}/answer", json={"how": "decline"})
    assert r.status_code == 200, r.text
    _run(app, db, ticks=3, start=False)
    _still_stopped(editor, pid)


def test_a_withdrawn_carry_on_leaves_the_run_stopped(app, db, owner, editor):
    pid, card = _held_carry(app, db, owner, editor)
    r = editor.post(f"/asks/{card['id']}/answer", json={"how": "withdraw"})
    assert r.status_code == 200, r.text
    _run(app, db, ticks=3, start=False)
    _still_stopped(editor, pid)


def test_an_approved_carry_on_goes_on_and_its_later_oks_raise_its_price(app, db, owner, editor):
    pid, card = _held_carry(app, db, owner, editor)
    project = db.get(Project, pid)
    price = asks.approved_run(db, project)[0]
    assert owner.post(f"/asks/{card['id']}/answer", json={"how": "make_it"}).status_code == 200
    _run(app, db, ticks=3, start=False)
    db.expire_all()
    stops = editor.get(f"/projects/{pid}/director/progress").json()["stops"]
    assert len(stops) == 1 and stops[0]["by"] and stops[0]["carried_at"] >= stops[0]["at"]
    later = director.turns(db, project)[-1]  # an OK at the director's own limit, after it
    later.input = {**later.input, director.GRANT: True}
    db.commit()
    assert asks.approved_run(db, project)[0] == price + director.own_limit()


def test_a_carry_on_that_cant_queue_its_turn_takes_everything_back(app, db, owner, editor,
                                                                   monkeypatch):  # fmt: skip
    import pytest

    pid = _stopped(app, db, owner, editor)
    project = db.get(Project, pid)
    before = len(director.turns(db, project))

    def broken(*a, **k):
        raise RuntimeError("the queue is down")

    monkeypatch.setattr(director, "_turn", broken)
    with pytest.raises(RuntimeError):
        editor.post(f"/projects/{pid}/director/carry-on")
    db.expire_all()
    assert len(director.turns(db, project)) == before
    assert editor.get(f"/projects/{pid}/director").json()["ended"] == "Stopped."  # as it was


def test_a_new_run_closes_a_carry_on_still_waiting_for_the_owner(app, db, owner, editor):
    for press in ("/plan-again", ""):
        pid, card = _held_carry(app, db, owner, editor)
        assert editor.post(f"/projects/{pid}/director{press}").status_code == 201  # a new run
        gone = next(a for a in owner.get(f"/projects/{pid}/asks").json() if a["id"] == card["id"])
        assert (gone["state"], gone["closed"], gone["can"]) == ("not_needed", director.NEW_RUN, [])
        late = owner.post(f"/asks/{card['id']}/answer", json={"how": "make_it"})
        assert late.status_code == 409  # never a press that does nothing
        assert director._carry_waiting(db, db.get(Project, pid)) is None
