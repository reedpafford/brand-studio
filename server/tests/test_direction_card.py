"""The direction card (Reed, 8 Nov): "before any paid stills or takes, the director presents
one card: concept, beats, the look, the clip plan and the estimate. I refine it in chat; nothing
expensive starts until I say go." The start card and the cast and places OK are one stop."""

from app import director
from app.models.jobs import Job
from tests.test_asks import _video
from tests.test_director import _run


def _card(owner, pid: int) -> dict:
    (card,) = [c for c in owner.get(f"/projects/{pid}/asks").json() if c["kind"] == "start"]
    return card


def test_make_it_on_the_direction_card_is_the_cast_and_places_ok_too(app, db, owner, editor):
    pid, _ = _video(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=12, start=False)
    assert owner.get(f"/projects/{pid}/cast").json()["state"] == "ready"  # shown on the card
    card = _card(owner, pid)
    assert owner.post(f"/asks/{card['id']}/answer", json={"how": "make_it"}).status_code == 200
    cast = owner.get(f"/projects/{pid}/cast").json()
    assert cast["state"] == "approved" and cast["approved_by"]  # no second stop in Cast


def test_a_run_held_for_the_owner_draws_nothing_before_the_owners_ok(app, db, owner, editor):
    pid, _ = _video(app, owner, editor, db)  # Ed's run is past what's left of the budget
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=12, start=False)
    out = editor.get(f"/projects/{pid}/director").json()
    assert [t["tool"] for t in out["turns"]] == ["treatment", None]  # its card at once
    made = {j.input.get("step") for j in db.query(Job).filter(Job.project_id == pid)}
    assert made == {"director", "treatment"}  # rule 33: nothing drawn before Reed says yes
    assert _card(owner, pid)["state"] == "open"


def test_a_wait_with_nothing_left_to_plan_brings_the_card(app, db, owner, editor, monkeypatch):
    real = director.choose
    monkeypatch.setattr(director, "choose", lambda state: real(state) if state.get(
        "treatment") == "none" else {**real(state), "tool": "wait"})  # fmt: skip
    pid, _ = _video(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=8, start=False)
    out = owner.get(f"/projects/{pid}/director").json()
    assert out["turns"][1]["result"] == director.START_FIRST  # never an idle stop before Make it
    assert _card(owner, pid)["state"] == "open"


def test_the_step_after_make_it_is_the_servers_with_no_claude_call(app, db, owner, editor):
    """Reed: fewer turns, same quality. The card comes on the director's own ask (no turn to
    reach it), and the storyboard after Make it needs no judgment: the server takes it."""
    pid, _ = _video(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=12, start=False)
    turns = owner.get(f"/projects/{pid}/director").json()["turns"]
    assert director.START_FIRST not in [t["result"] for t in turns]
    assert owner.post(f"/asks/{_card(owner, pid)['id']}/answer", json={"how": "make_it"}).is_success
    _run(app, db, ticks=2, start=False)
    (go,) = db.query(Job).filter(Job.project_id == pid, Job.input["start_run"].as_boolean())
    assert (go.kind, go.output["tool"], go.credits) == ("director_step", "storyboard", 0)
