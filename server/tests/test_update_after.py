"""Update everything after this (audit M14 part 2): one press runs the out-of-date later
steps in order on the server (storyboard again, every still, then the clip prompts), its
whole price checked first; all on the stand-ins (no paid calls)."""

from app import update_after
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.providers import get_providers
from tests.test_enhance import setup  # noqa: F401 - fixture
from tests.test_fake_local import _drain


def _made(app, db, editor, url):
    """A video with its shots, stills and clip prompts, then new shots made from it."""
    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings)
    editor.post(f"{url}/breakdown")
    _drain(app, db, providers)
    editor.post(f"{url}/storyboard", json={"per_shot": False})
    _drain(app, db, providers)
    for frame in editor.get(f"{url}/storyboard").json():
        editor.post(f"{url}/storyboard/frames/{frame['id']}/render")
        _drain(app, db, providers)
    editor.post(f"{url}/clips/prompts")
    _drain(app, db, providers)
    old = db.query(BreakdownVersion).one().id
    assert editor.post(f"{url}/breakdown").status_code == 201  # the shots change
    _drain(app, db, providers)
    for clip in db.query(ProjectClip):  # as if their own rewrite hadn't fitted the budget
        clip.breakdown_id = old
    db.commit()
    return providers


def test_the_press_runs_the_storyboard_its_stills_then_the_clip_prompts(app, db, editor, setup):  # noqa: F811
    url = f"/projects/{setup['project']}"
    providers = _made(app, db, editor, url)
    shown = editor.get(f"{url}/update-after").json()
    assert [s["step"] for s in shown["steps"]] == ["storyboard", "clip_prompts"]
    assert shown["steps"][0]["what"].startswith("Make the storyboard again (")
    assert shown["credits"] >= sum(s["credits"] for s in shown["steps"]) - 1
    assert [s["step"] for s in editor.get(f"{url}/update-after?from=clips").json()["steps"]] == [
        "clip_prompts"
    ]

    done = editor.post(f"{url}/update-after")
    assert done.status_code == 202, done.text
    assert [s["status"] for s in done.json()["steps"]] == ["started", "waiting"]
    assert done.json()["running"]
    for _ in range(3):  # the storyboard, its stills, the clip prompts: each follows on its own
        _drain(app, db, providers)
    newest = db.query(BreakdownVersion).order_by(BreakdownVersion.id.desc()).first().id
    frames = db.query(StoryboardFrame).all()
    assert frames and all(f.breakdown_id == newest and f.file_id for f in frames)
    assert all(c.breakdown_id == newest for c in db.query(ProjectClip))
    run = [j for j in db.query(Job).order_by(Job.id) if j.input.get(update_after.RUN)]
    assert [j.input["step"] for j in run] == ["storyboard"] + ["frame"] * len(frames) + [
        "clip_prompts"
    ]
    assert all(j.input.get("prepaid") is None for j in run)  # today's presses, nothing new
    after = editor.get(f"{url}/update-after").json()
    assert (after["steps"], after["credits"], after["running"]) == ([], 0, False)
    assert after["stopped_at"] is None
    again = editor.post(f"{url}/update-after")
    assert (again.status_code, again.json()["detail"]) == (409, update_after.NOTHING)


def test_over_the_videos_budget_nothing_starts(app, db, editor, setup):  # noqa: F811
    url = f"/projects/{setup['project']}"
    _made(app, db, editor, url)
    project = db.get(Project, setup["project"])
    shown = editor.get(f"{url}/update-after").json()
    spent = sum(j.credits for j in db.query(Job).filter(Job.project_id == project.id))
    left = shown["credits"] - shown["steps"][-1]["credits"]  # room for the storyboard only
    db.add(Job(workspace_id=project.workspace_id, kind="image", provider="fake", input={},
               project_id=project.id, status="succeeded",
               credits=project.budget_credits - spent - left))  # fmt: skip
    db.commit()
    before = db.query(Job).count()
    refused = editor.post(f"{url}/update-after")
    assert refused.status_code == 409, refused.text
    assert db.query(Job).count() == before  # nothing half-runs


def test_a_still_that_fails_stops_the_run_and_says_where(app, db, editor, setup):  # noqa: F811
    url = f"/projects/{setup['project']}"
    providers = _made(app, db, editor, url)
    from app.worker import run_once

    editor.post(f"{url}/update-after")
    run_once(db, providers, app.state.storage)  # the storyboard: its stills are queued
    still = db.query(Job).filter(Job.input["step"].as_string() == "frame").all()[-1]
    still.status, still.error = "failed", "The still didn't finish. Nothing was charged."
    db.commit()
    for _ in range(3):
        run_once(db, providers, app.state.storage)
    run = [j.input["step"] for j in db.query(Job) if j.input.get(update_after.RUN)]
    assert "clip_prompts" not in run  # never written from a storyboard missing a still
    shown = editor.get(f"{url}/update-after").json()
    assert (shown["stopped_at"], shown["running"]) == ("stills", False)
    assert shown["reason"] == "The still didn't finish. Nothing was charged."
    assert shown["steps"]  # the press is there again, for what's left


def test_out_of_date_stills_alone_are_drawn_again(app, db, editor, setup):  # noqa: F811
    url = f"/projects/{setup['project']}"
    providers = _made(app, db, editor, url)
    editor.post(f"{url}/update-after")
    _drain(app, db, providers)
    frame = db.query(StoryboardFrame).first()
    was, frame.still_stale = frame.file_id, True  # the cast changed since it was drawn
    db.commit()
    (step,) = editor.get(f"{url}/update-after?from=storyboard").json()["steps"]
    assert (step["step"], step["what"]) == ("stills", "Draw 1 still again")
    assert editor.post(f"{url}/update-after?from=storyboard").status_code == 202
    _drain(app, db, providers)
    db.refresh(frame)
    assert frame.file_id != was and not frame.still_stale
    assert editor.get(f"{url}/update-after").json()["steps"] == []
