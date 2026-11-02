"""The site's director, first slice (docs/next/director-chat.md): from a published script it
builds the whole video with the site's own actions, each checked as the editor's own press;
its turns are its log. All on the stand-ins: the fake Claude answers each turn with
`director.choose` (no paid call)."""

import json

from app import director
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.providers import get_providers
from app.providers.fake_local import _tag
from app.worker import run_once
from tests.helpers import with_sheet
from tests.test_cast_roles import _video


def _run(app, db, ticks=60):
    """Run the worker until the director's run ends (or `ticks` passes)."""
    providers = get_providers(app.state.settings, app.state.storage)
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
    assert "final_cut" in tools and tools[-1] == "deliver"
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
    cut = [t for t in out["turns"] if t["tool"] == "final_cut"][-1]
    assert out["turns"][-1]["tool"] == "deliver"
    assert "is clean: its newest is used." in cut["why"]  # said in the log


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
    providers = get_providers(app.state.settings, app.state.storage)
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
    providers = get_providers(app.state.settings, app.state.storage)
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


def test_it_watches_the_cut_fixes_what_it_found_and_cuts_again(app, db, owner, editor):
    """Reed, 1 Nov: "watch and make those fixes". On the stand-ins a watch finds a rushed line
    in clip 1 (redo) and an extra word in the last clip (mute): it redoes, mutes for free,
    cuts again and watches again, 3 times at most, and the delivery note says what it muted."""
    from app import director_tools
    from app.models.accounts import User
    from app.models.clips import ClipTake, ProjectClip

    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=120)
    out = editor.get(f"/projects/{pid}/director").json()
    tools = [t["tool"] for t in out["turns"]]
    assert out["status"] == "delivered", (out["ended"], tools)
    assert tools.count("watch_cut") == 2  # the stand-in watches twice (the server allows 3)
    redos = [t for t in out["turns"] if t["tool"] == "make_take" and "watch found" in t["why"]]
    assert len(redos) == 1  # the stand-in remakes a clip once for a watch
    assert tools.count("final_cut") == 3 and tools[-2:] == ["final_cut", "deliver"]
    last = db.query(ProjectClip).filter_by(project_id=pid).order_by(ProjectClip.id.desc()).first()
    muted = f"Muted a stretch of clip {last.clip_id.removeprefix('c')} instead of remaking it."
    assert [t["result"] for t in out["turns"] if t["tool"] == "mute"] == [muted]
    ((start, end),) = db.get(ClipTake, last.picked_take_id).made_with["mutes"]
    assert round(end - start, 2) == 0.5  # the half second the watch found, nothing more
    assert out["ended"].endswith(muted)  # named in the delivery note
    assert out["turns"][-1]["why"].endswith(muted)  # the deliver turn's note, as the page shows it
    user = db.query(User).filter_by(email="ed@example.com").one()
    again = director_tools.run(db, user, db.get(Project, pid), {"tool": "mute", "clip_id": "c1"},
                               None)  # fmt: skip
    assert again == "Refused: nothing to mute in clip 1."  # only what was found is silenced


def test_it_never_watches_before_a_cut_or_the_same_cut_twice(app, db, owner, editor, monkeypatch):
    from app import director_tools
    from app.models.accounts import User

    pid = _made(app, owner, editor, db)
    project = db.get(Project, pid)
    user = db.query(User).filter_by(email="ed@example.com").one()
    said = director_tools.run(db, user, project, {"tool": "watch_cut"}, None, {})
    assert said == "Refused: Make the cut first."
    prompt = director.turn_input(db, project, {"id": "r", "turn": 0, "redos": {}})["prompt"]
    assert '"watches_left": 3' in prompt and '"watch": {' in prompt
    db.commit()
    real, asked = director.choose, []

    def watch_again(state):  # once it has watched, it asks twice to watch the same cut again
        out = real(state)
        again = out["tool"] in ("make_take", "mute") and state["watch"].get("current")
        if again and len(asked) < 2:
            asked.append(state["allowed"]["watches_left"])
            return {**out, "tool": "watch_cut"}
        return out

    monkeypatch.setattr("app.director.choose", watch_again)
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", (out["ended"], out["turns"])  # the run went on
    again = [t for t in out["turns"] if t["result"] == director.WATCHED_AGAIN]
    assert len(again) == 2 and asked == [2, 2]  # refused twice, and neither counted as a watch


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
    from app.credits import COUNTED

    own = [
        j
        for j in db.query(Job).filter(Job.project_id == pid)
        if director.RUN in j.input and j.status in COUNTED
    ]  # turns, watches, and this one
    assert len(own) > len(turns)  # its watches of the cut count too
    assert got["director_credits"] == float(sum(j.credits for j in own))
    project, ed = db.get(Project, pid), db.query(User).filter_by(email="ed@example.com").one()
    budget = credits.credits_used(db, project) - credits.director_credits(db, project)
    assert float(budget) == pytest.approx(got["credits_used"] - got["director_credits"])
    room = project.budget_credits - budget  # what the hold still lets through
    assert not credits.needs_approval(db, ed, project, room)  # exactly fits
    assert credits.needs_approval(db, ed, project, room + Decimal("0.01"))  # one cent past
    db.commit()


def test_every_budget_check_counts_as_the_hold_does(app, db, owner, editor, monkeypatch):
    """QA-6: the hold left the director's spend out, but the take retry's check (fits), the
    settings preview and the cost bar's percent still counted it. All read budget_used now;
    the per-video cap still counts everything."""
    from decimal import Decimal

    from app import credits
    from app.models.accounts import User

    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    project, ed = db.get(Project, pid), db.query(User).filter_by(email="ed@example.com").one()
    used = credits.budget_used(db, project)
    assert credits.director_credits(db, project) > 0 and used < credits.credits_used(db, project)
    room, cent = project.budget_credits - used, Decimal("0.01")
    assert credits.fits(db, project, ed, room) == ""
    assert credits.fits(db, project, ed, room + cent) == "would go over this video's budget."
    got = editor.get(f"/projects/{pid}").json()
    assert got["budget_pct"] == round(float(used / project.budget_credits * 100), 1)
    db.commit()
    for cost, over in ((room, False), (room + cent, True)):
        monkeypatch.setattr("app.video_settings.to_finish", lambda db, p, cost=cost: cost)
        seen = editor.post(f"/projects/{pid}/settings/preview", json={"aspect_ratio": "1:1"})
        assert seen.json()["over_budget"] is over, (cost, seen.json())


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


def _stop_during(monkeypatch, editor, pid, where: str, before: bool = False) -> list:
    """Stop is pressed once, while `where` (the turn being asked, or its tool) runs; `before`:
    just as it starts (the worker took the turn, then Stop came)."""
    module, name = where.rsplit(".", 1)
    import importlib

    real, pressed = getattr(importlib.import_module(module), name), []

    def midway(*args, **kwargs):
        out = None if before else real(*args, **kwargs)
        if not pressed:
            args[0].commit()  # as the worker's own session would be, mid-step
            pressed.append(editor.post(f"/projects/{pid}/director/stop").json())
            pressed.append(args[0].query(Job).count())  # every job there is when it stops
        return real(*args, **kwargs) if before else out

    monkeypatch.setattr(where, midway)
    return pressed


def test_a_stop_while_a_turn_or_its_tool_runs_holds(app, db, owner, editor, monkeypatch):
    """QA on #1087: Stop pressed mid-turn was overwritten when the worker recorded that turn
    (from what it read before), and the run went on to deliver."""
    cases = [("app.director.refresh", True), ("app.director.refresh", False),
             ("app.director_tools.run", False)]  # fmt: skip
    for n, (where, before) in enumerate(cases):
        pid = _made(app, owner, editor, db) if n == 0 else _made_again(app, owner, editor, db)
        pressed = _stop_during(monkeypatch, editor, pid, where, before)
        editor.post(f"/projects/{pid}/director")
        _run(app, db)
        out = editor.get(f"/projects/{pid}/director").json()
        assert pressed and pressed[0]["status"] == "ended", where
        assert (out["status"], out["ended"]) == ("ended", "Stopped."), (where, out["turns"])
        assert len(out["turns"]) == 1, where  # no turn after the stop
        assert db.query(Job).count() == pressed[1], where  # nor any job: nothing more charged
        monkeypatch.undo()


def _second_turn(app, db, owner, editor, monkeypatch, when: str):
    """A run whose second turn meets Stop: `before` its call (while its prompt is built, as
    slowly as QA-7's), or `after` its call went out (the answer is back, then Stop)."""
    from decimal import Decimal

    from app.providers import Result, UsageItem

    pid, calls = _made(app, owner, editor, db), []
    providers = get_providers(app.state.settings, app.state.storage)
    real_input, real_run = director.turn_input, providers["claude"].run

    def building(db, project, run, job_id=None):  # QA-7: Stop lands while the prompt is being built
        if when == "before" and run["turn"] == 2 and calls:
            editor.post(f"/projects/{pid}/director/stop")
        return real_input(db, project, run, job_id)

    def asked(kind, input):
        out = real_run(kind, input)
        if input.get("step") == director.STEP:
            calls.append(input[director.RUN]["turn"])
            if when == "after" and len(calls) == 2:
                editor.post(f"/projects/{pid}/director/stop")
            usage = [UsageItem(units=Decimal(1), unit="call", cost_usd=Decimal("0.01"))]
            return Result(out.state, output=out.output, usage=usage)  # a paid call, logged
        return out

    monkeypatch.setattr("app.director.turn_input", building)
    providers["claude"].run = asked
    editor.post(f"/projects/{pid}/director")
    for _ in range(30):
        run_once(db, providers, app.state.storage)
        db.expire_all()
    return pid, calls


def test_a_stop_before_a_turns_call_means_no_call_and_no_charge(app, db, owner, editor,
                                                                monkeypatch):  # fmt: skip
    from app.models.jobs import Usage

    pid, calls = _second_turn(app, db, owner, editor, monkeypatch, "before")
    out = editor.get(f"/projects/{pid}/director").json()
    assert (out["status"], out["ended"]) == ("ended", "Stopped."), out["turns"]
    assert calls == [1]  # the second turn's call was never made
    second = director.turns(db, db.get(Project, pid))[-1]
    assert second.status == JobStatus.cancelled
    assert db.query(Usage).filter(Usage.job_id == second.id).count() == 0  # nothing charged


def test_a_stop_after_a_turns_call_records_and_charges_it_and_stays_stopped(
    app, db, owner, editor, monkeypatch
):
    from app.models.jobs import Usage

    pid, calls = _second_turn(app, db, owner, editor, monkeypatch, "after")
    out = editor.get(f"/projects/{pid}/director").json()
    assert (out["status"], out["ended"]) == ("ended", "Stopped."), out["turns"]
    assert calls == [1, 2] and len(out["turns"]) == 2  # no turn after it
    second = director.turns(db, db.get(Project, pid))[-1]
    assert second.status == JobStatus.succeeded  # its call went out: kept, logged, charged
    assert db.query(Usage).filter(Usage.job_id == second.id).count() == 1
    assert not second.input.get("result")  # nothing it said was done


def test_a_stop_while_the_next_turn_is_made_holds(app, db, owner, editor, monkeypatch):
    """QA-7, round 3: Stop ended the last turn while the next one was being made, and that
    new turn carried the run on to deliver. Now a run is over once ANY of its turns says so:
    the new turn makes no call, and "Stopped." stays."""
    pid, made, calls = _made(app, owner, editor, db), [], []
    real_turn, providers = director._turn, get_providers(app.state.settings, app.state.storage)
    real_run = providers["claude"].run

    def turn(db, user, project, run):  # the next turn is made just as Stop lands
        if run["turn"] == 1 and not made:
            made.append(editor.post(f"/projects/{pid}/director/stop").json()["status"])
        return real_turn(db, user, project, run)

    def asked(kind, input):
        if input.get("step") == director.STEP:
            calls.append(input[director.RUN]["turn"])
        return real_run(kind, input)

    monkeypatch.setattr("app.director._turn", turn)
    providers["claude"].run = asked
    editor.post(f"/projects/{pid}/director")
    for _ in range(30):
        run_once(db, providers, app.state.storage)
        db.expire_all()
    out = editor.get(f"/projects/{pid}/director").json()
    assert made == ["ended"] and calls == [1]  # no call after the stop
    assert (out["status"], out["ended"]) == ("ended", "Stopped."), out["turns"]
    second = director.turns(db, db.get(Project, pid))[-1]
    assert second.input[director.RUN]["turn"] == 2 and second.status == JobStatus.cancelled


def test_the_production_page_counts_the_budget_as_the_hold_does(app, db, owner, editor):
    """Owner's Production page: each row carries director_credits, and "Closest to budget"
    sorts by what the budget counts, the director's own spend left out (QA-6)."""
    from decimal import Decimal

    from app import credits

    app.state.settings.fake_providers = True
    ran, plain = _made_again(app, owner, editor, db), _made_again(app, owner, editor, db)
    a, b = db.get(Project, ran), db.get(Project, plain)

    def spend(project, cost, **input):
        db.add(Job(workspace_id=project.workspace_id, created_by_id=project.created_by_id,
                   kind="write-claude", provider="claude", input=input, project_id=project.id,
                   credits=Decimal(cost), status=JobStatus.succeeded))  # fmt: skip
        db.commit()

    budget = a.budget_credits
    spend(a, budget * Decimal("0.8"), step="director", director_run={"id": "r"})  # its own
    spend(a, budget * Decimal("0.1"))  # the budget's share: 10%
    spend(b, budget * Decimal("0.5"))  # 50%: closer to its budget, though less spent in all
    rows = {r["project_id"]: r for r in owner.get("/production").json()}
    assert rows[ran]["director_credits"] == float(credits.director_credits(db, a)) > 0
    assert rows[plain]["director_credits"] == 0
    order = [r["project_id"] for r in owner.get("/production?sort=budget").json()]
    assert order.index(plain) < order.index(ran)  # counting all spend would put ran first


def test_chat_a_change_after_delivery_and_it_delivers_again(app, db, owner, editor):
    """Director chat (director-chat.md §1 item 4): after a delivery, the editor asks for a
    change; it starts a revision run that reads it, remakes that clip, cuts and delivers
    again. The thread has both people's words and every move, oldest first."""
    pid = _made(app, owner, editor, db)
    url = f"/projects/{pid}/director"
    editor.post(url)
    _run(app, db)
    assert editor.get(url).json()["status"] == "delivered"
    sent = editor.post(f"{url}/messages", json={"text": "Make clip 1 slower and warmer."})
    assert sent.status_code == 201, sent.text
    assert (sent.json()["status"], sent.json()["unread"]) == ("delivered", 1)  # never starts one
    _run(app, db)
    assert editor.get(url).json()["status"] == "delivered"
    assert editor.post(url).status_code == 201  # Make it again: it reads the note
    assert editor.get(url).json()["unread"] == 0
    _run(app, db)
    out = editor.get(url).json()
    assert out["status"] == "delivered", (out["ended"], [t["tool"] for t in out["turns"]])
    remade = next(t for t in out["turns"] if t["tool"] == "make_take")
    assert remade["why"] == "You asked: Make clip 1 slower and warmer."
    note = out["turns"][-1]["why"]  # the revision names the ask, fixes nothing it wasn't asked
    assert "You asked: Make clip 1 slower and warmer. Done." in note
    project = db.get(Project, pid)
    run = director.turns(db, project)
    touched = {(j.output or {}).get("clip_id") for j in run
               if (j.output or {}).get("tool") in ("make_take", "mute", "pick_take")}  # fmt: skip
    assert touched <= {"c1"}, touched
    assert "Muted" not in note and "I also noticed:" in note and "Want me to fix it?" in note
    kinds = [m["kind"] for m in out["thread"]]
    said = kinds.index("message")
    assert "move" in kinds[:said] and "move" in kinds[said + 1 :]  # between the two runs
    assert out["thread"][said] == {
        **out["thread"][said],
        "who": "Ed",
        "text": "Make clip 1 slower and warmer.",
        "status": None,
        "why": "",
    }
    asked = next(m for m in out["thread"] if m["why"].startswith("You asked:"))
    assert asked["kind"] == "move" and asked["text"]  # each move keeps its reason
    assert out["thread"][-1]["why"] == ""  # the delivery's reason is its text
    assert [m["at"] for m in out["thread"]] == sorted(m["at"] for m in out["thread"])
    ids = [m["id"] for m in out["thread"]]
    assert len(set(ids)) == len(ids) and out["thread"][said]["id"] == "m0"
    assert out["thread"][-1]["text"] == out["turns"][-1]["why"]  # ends on the new delivery note


def test_chat_while_it_runs_is_read_at_its_next_turn_and_only_the_maker_may(app, db, owner, editor):
    from fastapi.testclient import TestClient

    from tests.conftest import PASSWORD

    pid = _made(app, owner, editor, db)
    url = f"/projects/{pid}/director"
    editor.post(url)
    editor.post(f"{url}/messages", json={"text": "Keep the end line short."})
    project = db.get(Project, pid)
    db.refresh(project)
    run = director.turns(db, project)[-1].input[director.RUN]
    assert director.chat(project, run["id"]) == [{"text": "Keep the end line short."}]
    asked = director.turn_input(db, project, run)["prompt"]
    assert "<chat>" in asked and "Keep the end line short." in asked
    assert editor.post(f"{url}/messages", json={"text": "   "}).status_code == 422
    db.commit()
    token = owner.post("/team/invites", json={"email": "bo@example.com"}).json()["token"]
    with TestClient(app) as other:  # another editor may read the video but not direct it
        other.post("/auth/accept-invite", json={"token": token, "name": "Bo", "password": PASSWORD})
        assert other.post(f"{url}/messages", json={"text": "Hi"}).status_code == 403


def test_a_note_sent_during_the_last_turn_waits_for_the_next_make_it(
    app, db, owner, editor, monkeypatch
):
    """The Producer: a note sent while the run's last turn delivers is never lost and never
    starts a run. It stays unread; the next Make it reads it, once."""
    pid = _made(app, owner, editor, db)
    url = f"/projects/{pid}/director"
    act, sent = director._act, []

    def deliver_with_a_message(db_, job, storage):
        if (job.output or {}).get("tool") == "deliver" and not sent:
            sent.append(editor.post(f"{url}/messages", json={"text": "Make clip 1 brighter."}))
        return act(db_, job, storage)

    monkeypatch.setattr(director, "_act", deliver_with_a_message)
    editor.post(url)
    _run(app, db)
    assert sent[0].status_code == 201, sent[0].text
    out = editor.get(url).json()
    assert (out["status"], out["unread"]) == ("delivered", 1)
    steps = lambda: [j for j in db.query(Job).filter_by(project_id=pid)  # noqa: E731
                     if j.input.get("step") == director.STEP]  # fmt: skip
    first = len(steps())
    _run(app, db, ticks=5)
    assert len(steps()) == first  # it started nothing by itself
    assert editor.post(url).status_code == 201
    _run(app, db)
    out = editor.get(url).json()
    assert (out["status"], out["unread"]) == ("delivered", 0), out["ended"]
    assert [t["why"] for t in out["turns"]].count("You asked: Make clip 1 brighter.") == 1
    assert not any(
        "c1" in m["text"] + m["why"] for m in out["thread"]
    )  # "clip 1", as people see it


def test_notes_one_every_3_seconds_a_person_and_30_a_run(app, db, owner, editor, monkeypatch):
    from datetime import timedelta

    pid = _made(app, owner, editor, db)
    url = f"/projects/{pid}/director"
    editor.post(url)
    assert editor.post(f"{url}/messages", json={"text": "One"}).status_code == 201
    r = editor.post(f"{url}/messages", json={"text": "Two"})
    assert r.status_code == 429 and r.json()["detail"] == "Too many messages; wait a moment."
    monkeypatch.setattr(director, "GAP", timedelta(0))
    codes = [editor.post(f"{url}/messages", json={"text": f"Ask {n}"}).status_code
             for n in range(30)]  # fmt: skip
    assert codes.count(201) == 29 and codes[-1] == 429  # 30 a run at most
    project = db.get(Project, pid)
    db.refresh(project)
    assert len(project.director_chat) == 30
    assert db.query(Job).filter(Job.kind != "write-claude").count() == 0  # nothing charged


def test_each_note_is_new_to_exactly_one_turn_and_one_paid_redo(app, db, owner, editor):
    """The Producer: a note is shown as new once, on the first turn after it arrives; later
    turns see it as handled. A note asking for a redo makes exactly one redo."""
    pid = _made(app, owner, editor, db)
    url = f"/projects/{pid}/director"
    editor.post(url)
    providers = get_providers(app.state.settings, app.state.storage)
    sent = False
    for _ in range(60):  # the note lands mid-run, once clip 1 has its prompt
        run_once(db, providers, app.state.storage)
        db.expire_all()
        if not sent and any(t["tool"] == "make_take" for t in editor.get(url).json()["turns"]):
            r = editor.post(f"{url}/messages", json={"text": "Make clip 1 brighter."})
            assert r.status_code == 201
            sent = True
    assert sent
    assert editor.get(url).json()["status"] == "delivered"
    steps = sorted((j for j in db.query(Job).filter_by(project_id=pid)
                    if j.input.get("step") == director.STEP), key=lambda j: j.id)  # fmt: skip
    chats = [json.loads(_tag(j.input["prompt"], "chat") or "[]") for j in steps]
    new = [c for c in chats if any(m["new"] for m in c)]
    assert new == [[{"text": "Make clip 1 brighter.", "new": True}]]  # new to one turn only
    later = chats[chats.index(new[0]) + 1 :]
    assert later and all(c == [{"text": "Make clip 1 brighter.", "new": False}] for c in later)
    redos = [j for j in steps if (j.output or {}).get("why") == "You asked: Make clip 1 brighter."]
    assert len(redos) == 1
