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


def _made(app, owner, editor, db) -> int:
    app.state.settings.fake_providers = True
    pid, _, kid = _video(owner, editor, db)
    with_sheet(db, kid)
    return pid


def test_it_builds_the_video_from_a_published_script_and_logs_every_turn(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    url = f"/projects/{pid}/director"
    started = editor.post(url)
    assert started.status_code == 201, started.text
    assert started.json()["status"] == "running"
    assert editor.post(url).status_code == 409  # one run at a time
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
    assert out["spent_usd"] == 0  # the stand-ins cost nothing


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
    assert approved >= 5  # its own turns and its presses each waited for the owner's OK


def test_only_a_published_script_and_stop_ends_the_run(app, db, owner, editor):
    from tests.test_enhance import SCRIPT

    fomo = owner.get("/brands").json()[0]["id"]
    loose = editor.post("/projects", json={"brand_id": fomo, "name": "V", "planned_seconds": 30})
    loose = loose.json()["id"]
    editor.put(f"/projects/{loose}/script", json={"text": SCRIPT})
    refused = editor.post(f"/projects/{loose}/director")
    assert (refused.status_code, refused.json()["detail"]) == (409, director.NOT_PUBLISHED)

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
