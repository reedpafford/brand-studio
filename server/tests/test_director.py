"""The site's director, first slice (docs/next/director-chat.md): from a published script it
builds the whole video with the site's own actions, each checked as the editor's own press;
its turns are its log. All on the stand-ins: the fake Claude answers each turn with
`director.choose` (no paid call)."""

from app import director
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.providers import get_providers
from app.worker import run_once
from tests.helpers import with_sheet
from tests.test_cast_roles import _video


def _run(app, db, ticks=60):
    """Run the worker until the director's run ends (or `ticks` passes)."""
    providers = get_providers(app.state.settings)
    for _ in range(ticks):
        run_once(db, providers, app.state.storage)
        db.expire_all()


def _made_again(app, owner, editor, db) -> int:
    """A second video from a published script, in the same workspace."""
    from tests.test_script_library import SCRIPT, _make

    made = _make(owner, text=SCRIPT, title="Again")
    base = f"/scripts/{made['id']}"
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    return editor.post(f"{base}/drafts/0/produce").json()["project_id"]


def _made(app, owner, editor, db) -> int:
    app.state.settings.fake_providers = True
    pid, _, kid = _video(owner, editor, db)
    with_sheet(db, kid)
    return pid


def test_it_builds_the_video_from_a_published_script_and_logs_every_turn(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    url = f"/projects/{pid}/director"
    assert editor.get(url).json()["start_blocked"] == ""
    started = editor.post(url)
    assert started.status_code == 201, started.text
    assert started.json()["status"] == "running"
    assert editor.post(url).status_code == 409  # one run at a time
    assert editor.get(url).json()["start_blocked"] == director.RUNNING
    _run(app, db)
    out = editor.get(url).json()
    tools = [t["tool"] for t in out["turns"]]
    assert out["status"] == "delivered", (
        out["ended"],
        [(t["tool"], t["result"]) for t in out["turns"]],
    )
    assert tools[-2:] == ["final_cut", "deliver"]
    assert all(not t["result"].startswith("Refused") for t in out["turns"]), out["turns"]
    assert editor.get(f"/projects/{pid}/video").json()["file_id"]
    assert out["spent_usd"] is None  # editors never see dollars (rule 4)
    assert owner.get(url).json()["spent_usd"] == 0  # the stand-ins cost nothing
    assert out["credits"] > 0  # its turns and every press its tools made, "up to"


def test_a_flagged_take_is_made_again_with_its_notes_at_most_twice(
    app, db, owner, editor, monkeypatch
):
    monkeypatch.setattr("app.item_checks.verdict", lambda checks: "flagged")  # every take
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")  # never held: the limits alone
    _run(app, db)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    redos = [t for t in out["turns"] if t["tool"] == "make_take" and "flagged" in t["why"]]
    clips = {t["why"].split()[-1] for t in redos}
    assert len(redos) == director.MAX_REDOS * len(clips)  # then it cuts with the newest
    assert [t["tool"] for t in out["turns"]][-2:] == ["final_cut", "deliver"]
    assert "is clean: its newest is used." in out["turns"][-2]["why"]  # said in the log


def test_the_server_holds_the_limits_whatever_the_answer(app, db, owner, editor, monkeypatch):
    """A director that keeps asking for a redo of one clip: refused past MAX_REDOS, and the
    run stops at MAX_TURNS."""
    monkeypatch.setattr(director, "MAX_TURNS", 9)
    real = director.choose

    def stubborn(state):
        if state["clips"] and all(c["takes"] for c in state["clips"]):
            return {"tool": "make_take", "clip_id": "c1", "take_id": None, "note": "Again.",
                    "why": "Once more."}  # fmt: skip
        return real(state)

    monkeypatch.setattr(director, "choose", stubborn)
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")  # never held: the limits alone
    _run(app, db)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "ended" and out["ended"] == "It stopped after 9 turns."
    assert len(out["turns"]) == 9
    results = [t["result"] for t in out["turns"] if t["why"] == "Once more."]
    made = [r for r in results if r.startswith("Making")]
    assert len(made) == director.MAX_REDOS
    assert results[len(made) :] and all("made again 2 times" in r for r in results[len(made) :])


def test_past_the_budget_it_waits_for_the_owner_then_goes_on(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    project = db.get(Project, pid)
    db.add(Job(workspace_id=project.workspace_id, kind="image", provider="fake", input={},
               project_id=pid, credits=project.budget_credits, status="succeeded"))  # fmt: skip
    db.commit()  # its budget is all spent: every paid press waits for the owner
    editor.post(f"/projects/{pid}/director")
    approved = 0
    for _ in range(40):
        _run(app, db, ticks=3)
        held = db.query(Job).filter_by(status=JobStatus.needs_owner_approval).all()
        for job in held:
            assert owner.post(f"/jobs/{job.id}/approve").status_code == 200
            approved += 1
        if editor.get(f"/projects/{pid}/director").json()["status"] != "running":
            break
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    assert approved >= 4  # its presses each waited for the owner's OK
    held = db.query(Job).filter(Job.approved_by_id.is_not(None), Job.project_id == pid).all()
    assert all(j.input.get("step") != director.STEP for j in held)  # never its own turns


def test_only_a_published_script_and_stop_ends_the_run(app, db, owner, editor):
    from tests.test_enhance import SCRIPT

    fomo = owner.get("/brands").json()[0]["id"]
    loose = editor.post("/projects", json={"brand_id": fomo, "name": "V", "planned_seconds": 30})
    loose = loose.json()["id"]
    editor.put(f"/projects/{loose}/script", json={"text": SCRIPT})
    refused = editor.post(f"/projects/{loose}/director")
    assert (refused.status_code, refused.json()["detail"]) == (409, director.NOT_PUBLISHED)
    assert editor.get(f"/projects/{loose}/director").json()["start_blocked"] == (
        director.NOT_PUBLISHED
    )

    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    stopped = editor.post(f"/projects/{pid}/director/stop").json()
    assert (stopped["status"], stopped["ended"]) == ("ended", "Stopped.")
    _run(app, db, ticks=5)
    assert len(editor.get(f"/projects/{pid}/director").json()["turns"]) == 1  # no more turns
    assert db.query(Job).filter(Job.project_id == pid).count() == 1  # its turn, cancelled


def test_it_stops_and_says_why_when_it_cant_go_on(app, db, owner, editor, monkeypatch):
    monkeypatch.setattr(director, "choose", lambda state: {
        "tool": "stop", "clip_id": None, "take_id": None, "note": "",
        "why": "The ending needs a story choice: who keeps the money?"})  # fmt: skip
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=3)
    out = editor.get(f"/projects/{pid}/director").json()
    assert (out["status"], out["ended"]) == (
        "ended", "The ending needs a story choice: who keeps the money?")  # fmt: skip
    assert [t["result"] for t in out["turns"]] == ["Stopped."]


def test_a_wait_with_nothing_being_made_reads_the_video_again(app, db, owner, editor, monkeypatch):
    """QA on #1087: started right after a step, its first turn read the video before the step
    saved and answered wait. It reads the video again and goes on (twice in a row: it stops)."""
    real, said = director.choose, []

    def late(state):
        said.append(1)
        return real(state) if len(said) > 1 else {**real(state), "tool": "wait"}

    monkeypatch.setattr(director, "choose", late)
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    assert out["turns"][0]["result"] == director.IDLE

    monkeypatch.setattr(director, "choose", lambda state: {**real(state), "tool": "wait"})
    pid = _made_again(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=4)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["ended"] == "It stopped: it waited twice with nothing being made."


def test_a_video_with_no_shots_gets_its_plan_made_and_approved_first(app, db, owner, editor):
    """QA on #1087: a video whose script has no shots waits on its own plan; `plan` makes the
    plan, then approves it (which makes the shots), as the Plan step does."""
    from tests.test_script_library import SCRIPT, _make

    app.state.settings.fake_providers = True
    made = _make(owner, text=SCRIPT)
    base = f"/scripts/{made['id']}"
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    owner.post(f"/projects/{pid}/director")  # never held: the plan steps alone
    _run(app, db)
    out = editor.get(f"/projects/{pid}/director").json()
    results = [t["result"] for t in out["turns"]]
    assert "Approved the plan; making the shots." in results, results
    assert out["status"] == "delivered", (out["ended"], results)


def test_the_same_refused_tool_again_stops_the_run_with_why(app, db, owner, editor, monkeypatch):
    stuck = {"tool": "pick_take", "clip_id": "c9", "take_id": 1, "note": "", "why": "Pick it."}
    monkeypatch.setattr(director, "choose", lambda state: stuck)
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=4)
    out = editor.get(f"/projects/{pid}/director").json()
    assert [t["result"] for t in out["turns"]] == [
        "Refused: name one clip.", "Refused again: name one clip."]  # fmt: skip
    assert (out["status"], out["ended"]) == ("ended", "It stopped: name one clip.")


def test_a_take_for_a_clip_that_isnt_there_is_refused(db, owner, editor, app):
    from app import director_tools
    from app.models.accounts import User

    pid = _made(app, owner, editor, db)
    project = db.get(Project, pid)
    user = db.query(User).filter_by(email="ed@example.com").one()
    said = director_tools.run(db, user, project, {"tool": "make_take", "clip_id": "c9"}, None)
    assert said == "Refused: there's no clip c9."


def test_its_own_turns_never_use_the_videos_budget_but_the_cap_counts_them(app, db, owner, editor):
    """Next-Lead (DECISIONS #1066): the video's budget, the director's own and the per-video
    cap are three limits. An editor's run is never held for the budget by its own turns."""
    from app.credits import get_limits

    pid = _made(app, owner, editor, db)
    project = db.get(Project, pid)
    earlier = {"step": director.STEP, "ended": "Stopped.",
               director.RUN: {"id": "earlier", "turn": 1, "redos": {}, "by": 1}}  # fmt: skip
    turns = Job(workspace_id=project.workspace_id, kind="write-claude", provider="claude",
                input=earlier, project_id=pid, credits=project.budget_credits,
                status="succeeded")  # fmt: skip
    db.add(turns)  # as if an earlier run's own turns had spent the whole budget
    db.commit()
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    assert not db.query(Job).filter_by(status=JobStatus.needs_owner_approval).count()

    turns.credits = get_limits(db, project.workspace_id).per_video_max_credits
    db.commit()  # its turns alone reach the per-video cap: nothing more, for anyone
    refused = editor.post(f"/projects/{pid}/director")
    assert refused.status_code == 409 and "limit" in refused.json()["detail"]


def test_an_editors_run_approves_its_own_videos_plan(app, db, owner, editor):
    """Producer: an editor's run reaching a ready plan approves it (the Approve button's
    route: the video's maker may), so it never dead-ends on "Approve the plan first."."""
    from app import director_tools, plans
    from app.models.accounts import User

    pid = _made_again(app, owner, editor, db)
    assert plans.status(db, db.get(Project, pid)) == "none"
    app.state.settings.fake_providers = True
    editor.post(f"/projects/{pid}/plan")
    _run(app, db, ticks=3)
    project, ed = db.get(Project, pid), db.query(User).filter_by(email="ed@example.com").one()
    assert plans.status(db, project) == "ready"
    said = director_tools.run(db, ed, project, {"tool": "plan"}, app.state.storage)
    assert said == "Approved the plan; making the shots."
    assert plans.status(db, db.get(Project, pid)) == "approved"


def test_a_job_of_its_own_that_fails_never_leaves_the_run_hanging(app, db, owner, editor):
    """QA on #1087: a still that failed (the provider refused it at once, so the worker never
    reached its finish) left the run "running" forever. Now it goes on: it sees the failure,
    draws the still again and delivers."""
    pid = _made(app, owner, editor, db)
    providers = get_providers(app.state.settings)
    real, failed = providers["replicate"].submit, []

    def once(kind, input):
        if kind == "image" and not failed:
            failed.append(1)
            raise RuntimeError("the still service refused it")
        return real(kind, input)

    providers["replicate"].submit = once
    owner.post(f"/projects/{pid}/director")
    for _ in range(60):
        run_once(db, providers, app.state.storage)
        db.expire_all()
    out = owner.get(f"/projects/{pid}/director").json()
    assert failed and out["status"] == "delivered", (out["ended"], out["turns"])
    assert [t["tool"] for t in out["turns"]].count("stills") == 2  # drawn again after it failed


def test_an_item_that_keeps_failing_is_tried_twice_more_then_the_run_says_so(
    app, db, owner, editor
):
    """Producer: a failed item is retried at most twice; then the run delivers what it has or,
    with no cut yet, stops with that reason (never spending its turns on it)."""
    pid = _made(app, owner, editor, db)
    providers = get_providers(app.state.settings)
    real, tries = providers["replicate"].submit, []

    def never(kind, input):
        if kind == "image":
            tries.append(1)
            raise RuntimeError("the still service refused it")
        return real(kind, input)

    providers["replicate"].submit = never
    owner.post(f"/projects/{pid}/director")
    for _ in range(40):
        run_once(db, providers, app.state.storage)
        db.expire_all()
    out = owner.get(f"/projects/{pid}/director").json()
    assert (out["status"], out["ended"]) == ("ended", "It stopped: Clip 1's still failed 3 times.")
    assert len(tries) == 3 and len(out["turns"]) < 8  # three tries, no turns spent past them


def test_it_keeps_to_the_videos_locks_and_reads_its_outfits(app, db, owner, editor):
    import json

    from app import director_tools
    from app.models.accounts import User

    pid = _made(app, owner, editor, db)
    kid = db.get(Project, pid).cast_ids[-1]
    editor.put(
        f"/projects/{pid}/locks",
        json={"locks": {"cast": True}, "outfits": {f"char:{kid}": "a yellow raincoat"}},
    )
    project = db.get(Project, pid)
    db.refresh(project)
    state = director.video_state(db, project)
    assert state["locked"] == {"cast": True}
    assert state["outfits"] == {f"char:{kid}": "a yellow raincoat"}
    prompt = director.turn_input(db, project, {"id": "r", "turn": 0, "redos": {}})["prompt"]
    assert json.loads(prompt.split("<video>")[1].split("</video>")[0])["locked"] == {"cast": True}
    user = db.query(User).filter_by(email="ed@example.com").one()
    said = director_tools.run(db, user, project, {"tool": "make_looks"}, None)
    assert said == (
        "Refused: the cast is locked for this video. Approve the missing looks in "
        "Cast, or unlock the cast, then start it again."
    )
    db.commit()  # reading the video may save its plan's state: let the requests write
    editor.post(f"/projects/{pid}/director")  # its cast is whole: the lock never stands in the way
    _run(app, db)
    assert editor.get(f"/projects/{pid}/director").json()["status"] == "delivered"


def test_a_locked_cast_with_a_look_missing_stops_saying_what_to_do(
    app, db, owner, editor, monkeypatch
):
    pid = _made(app, owner, editor, db)
    editor.put(f"/projects/{pid}/locks", json={"locks": {"cast": True}})
    real = director.choose
    monkeypatch.setattr(
        "app.director.choose",
        lambda state: {**real(state), "tool": "make_looks", "why": "A look is missing."},
    )  # every turn
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "ended" and len(out["turns"]) == 2  # refused twice, then stops
    assert out["ended"] == (
        "It stopped: the cast is locked for this video. Approve the missing "
        "looks in Cast, or unlock the cast, then start it again."
    )


def test_a_turn_that_fails_inside_the_worker_ends_the_run_and_nothing_more_is_charged(
    app, db, owner, editor, monkeypatch
):
    """An answer that isn't a tool fails the turn before the worker's finish: the run used to
    stay "running" forever. Now it ends, saying so, and nothing more is made."""
    monkeypatch.setattr("app.director.choose", lambda state: {"tool": "dance", "why": "?"})
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db)
    out = editor.get(f"/projects/{pid}/director").json()
    assert (out["status"], out["ended"]) == ("ended", director.TURN_FAILED)
    (turn,) = db.query(Job).filter(Job.project_id == pid).all()  # the failed turn, nothing more
    assert turn.status == JobStatus.failed


def test_its_turns_show_apart_so_the_shown_budget_matches_the_hold(app, db, owner, editor):
    """The cost bar read "Over budget" after one director run: its turns are counted in
    credits_used but the hold leaves them out. director_credits shows them apart."""
    from decimal import Decimal

    import pytest

    from app import credits
    from app.models.accounts import User

    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    turns = director.turns(db, db.get(Project, pid))
    run = turns[-1].input[director.RUN]
    watch = Job(
        workspace_id=turns[-1].workspace_id,
        created_by_id=turns[-1].created_by_id,
        kind="write-claude",
        provider="claude",
        project_id=pid,
        credits=Decimal(3),
        input={"step": "watch_cut", director.RUN: run},
        status=JobStatus.succeeded,
    )  # its look at the cut: its own limit too
    db.add(watch)
    db.commit()
    got = editor.get(f"/projects/{pid}").json()
    assert got["director_credits"] == float(sum(j.credits for j in turns) + 3)
    project, ed = db.get(Project, pid), db.query(User).filter_by(email="ed@example.com").one()
    budget = credits.credits_used(db, project) - credits.director_credits(db, project)
    assert float(budget) == pytest.approx(got["credits_used"] - got["director_credits"])
    room = project.budget_credits - budget  # what the hold still lets through
    assert not credits.needs_approval(db, ed, project, room)  # exactly fits
    assert credits.needs_approval(db, ed, project, room + Decimal("0.01"))  # one cent past


def test_the_owners_release_counts_the_budget_as_the_hold_does(app, db, owner, editor):
    """Approving a video releases its held presses by the same figure the hold uses: the
    director's own turns are left out of both, so they always agree."""
    from decimal import Decimal

    from app import credits
    from app.models.accounts import User
    from app.models.projects import ProjectStatus

    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    project, ed = db.get(Project, pid), db.query(User).filter_by(email="ed@example.com").one()
    assert credits.director_credits(db, project) > 0
    room = project.budget_credits - credits.budget_used(db, project)
    assert not credits.needs_approval(db, ed, project, room)  # the hold lets exactly this in

    def held(cost):
        job = Job(workspace_id=project.workspace_id, created_by_id=ed.id, kind="image",
                  provider="replicate", input={}, project_id=pid, brand_id=project.brand_id,
                  credits=cost, status=JobStatus.needs_owner_approval)  # fmt: skip
        db.add(job)
        return job

    fits, past = held(room), held(Decimal("0.01"))
    project.status = ProjectStatus.needs_owner_approval
    db.commit()
    assert owner.post(f"/projects/{pid}/approve").status_code == 200
    db.expire_all()
    assert db.get(Job, fits.id).status == JobStatus.queued  # released, as the hold allowed
    assert db.get(Job, past.id).status == JobStatus.needs_owner_approval  # a cent past: held
