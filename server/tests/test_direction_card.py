"""The direction card (Reed, 8 Nov): "before any paid stills or takes, the director presents
one card: concept, beats, the look, the clip plan and the estimate. I refine it in chat; nothing
expensive starts until I say go." The start card and the cast and places OK are one stop."""

from app import director
from app.models.jobs import Job
from app.providers import get_providers
from app.worker import run_once
from tests.helpers import ok_when_asked
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


def test_a_plan_first_video_shows_drawn_looks_on_its_card_and_no_cast_stop_after(
    app, db, owner, editor
):
    """QA on #1482: a script whose people weren't cast makes its plan first; the card waited
    for nobody's look (grey boxes), and the cast stop came back after Make it."""
    from tests.test_script_library import SCRIPT, _make

    app.state.settings.fake_providers = True
    base = f"/scripts/{_make(owner, text=SCRIPT)['id']}"
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    pid = owner.post(f"{base}/drafts/0/produce").json()["project_id"]
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=20, start=False)
    cast = owner.get(f"/projects/{pid}/cast").json()
    assert cast["state"] == "ready" and all(i["preview_file_id"] for i in cast["items"]), cast
    assert {i["name"] for i in cast["items"]} >= {"Mom", "Nate"}  # drawn before the card
    card = _card(owner, pid)
    assert owner.post(f"/asks/{card['id']}/answer", json={"how": "make_it"}).is_success
    _run(app, db, ticks=60, start=False)  # nobody approves Cast: none is needed
    out = owner.get(f"/projects/{pid}/director").json()
    assert director.CAST_WAIT not in [t["result"] for t in out["turns"]]
    assert out["status"] == "delivered", out["ended"]


def test_a_new_run_plans_on_its_own_not_the_last_runs_price(app, db, owner, editor):
    """QA on #1482: Start the plan again on a video whose last run used its price was held
    on a budget card before its own direction card."""
    from tests.test_asks import _priced_down

    pid, _ = _video(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=80)  # delivered, Make it pressed
    assert owner.get(f"/projects/{pid}/director").json()["status"] == "delivered"
    _priced_down(db, pid, "20")  # as if it used almost all of its "up to"
    assert owner.post(f"/projects/{pid}/director/plan-again").status_code == 201
    _run(app, db, ticks=20, start=False)
    open_ = [c["kind"] for c in owner.get(f"/projects/{pid}/asks").json() if c["state"] == "open"]
    assert open_ == ["start"]  # its own direction card, no budget card before it


def test_a_wait_with_nothing_left_to_plan_brings_the_card(app, db, owner, editor, monkeypatch):
    real = director.choose
    monkeypatch.setattr(
        director,
        "choose",
        lambda state: (
            real(state)
            if state.get("treatment") == "none" or state["missing_looks"]
            else {**real(state), "tool": "wait"}
        ),
    )
    pid, _ = _video(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=12, start=False)
    out = owner.get(f"/projects/{pid}/director").json()
    said = [t["result"] for t in out["turns"]]
    assert said[-2] == director.START_FIRST, said  # its looks drawn: never an idle stop
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


def test_a_look_that_will_not_draw_is_drawn_again_once_then_the_card_marks_it(
    app, db, owner, editor
):
    """QA on #1482: a look that failed before the card left every move refused ("Nate needs a
    look; wait for it") with nothing drawing, 22 turns. It's drawn again once; then the card
    comes with it undrawn (Cast's Redo is its fix), and Make it still goes."""
    pid, _ = _video(app, owner, editor, db)
    providers = get_providers(app.state.settings, app.state.storage)
    real = providers["replicate"].submit

    def no_sheets(kind, input):
        if input.get("step") == "sheet":
            raise RuntimeError("the picture service refused it")
        return real(kind, input)

    providers["replicate"].submit = no_sheets
    owner.post(f"/projects/{pid}/director")
    for _ in range(20):
        run_once(db, providers, app.state.storage)
        ok_when_asked(db)
        db.expire_all()
    out = owner.get(f"/projects/{pid}/director").json()
    said = [t["result"] for t in out["turns"]]
    assert sum(r.startswith("Drawing again what didn't draw: Nate") for r in said) == 1, said
    assert len(said) <= 6 and not out["ended"], said  # no run of refused turns
    items = owner.get(f"/projects/{pid}/cast").json()["items"]
    assert [i["readiness"] for i in items if i["name"] == "Nate"] == ["needs_look"]  # undrawn
    card = _card(owner, pid)  # the card came anyway
    assert owner.post(f"/asks/{card['id']}/answer", json={"how": "make_it"}).is_success
