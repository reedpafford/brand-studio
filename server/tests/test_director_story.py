"""The director rework (Reed's first real run "made no sense"; the Producer, the Director): a
turn reads what the video is, its script, plan beats and each clip's shots, and the whole run
so far; the treatment, when there is one, goes to every step that writes the video; and it
delivers only a cut it has watched."""

from app import director
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from tests.test_director import _made, _run

TREATMENT = {"hook": "A wallet on the kitchen floor.", "logline": "Mom finds the dip.",
             "why_it_holds": "A small mystery, solved in the last line.",
             "beats": [{"id": "b1", "lines": [1], "purpose": "hook", "picture": "the wallet"}],
             "ending": "Download fomo."}  # fmt: skip


def test_a_turn_reads_the_script_the_shots_and_the_whole_run(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    project = db.get(Project, pid)
    run = next(j for j in director.turns(db, project)).input[director.RUN]
    prompt = director.turn_input(db, project, run)["prompt"]
    assert "<script>\n" in prompt and "1| " in prompt  # its words, numbered
    assert '"shots": [' in prompt and '"action":' in prompt  # what each clip shows and says
    acted = [j for j in director.turns(db, project) if "result" in j.input]
    assert len(acted) > 8 and prompt.count('"tool":') >= len(acted)  # the whole run, not 8
    assert '"replans_left": 1' in prompt


def test_the_treatment_goes_to_every_step_that_writes_the_video(app, db, owner, editor):
    from app import breakdown, clip_prompts, plans
    from app.models.accounts import User

    pid = _made(app, owner, editor, db)
    project = db.get(Project, pid)
    assert director.treatment_block(db, project) == ""  # none yet: nothing is added
    user = db.query(User).filter_by(email="ed@example.com").one()
    db.add(Job(workspace_id=project.workspace_id, created_by_id=user.id, kind="write-claude",
               provider="claude", project_id=pid, input={"step": "treatment"},
               output=TREATMENT, status=JobStatus.succeeded, credits=3))  # fmt: skip
    db.commit()
    assert director.treatment(db, project) == TREATMENT
    version = plans.script(db, project)
    assert "<treatment>" in plans.job_input(db, project, version)["prompt"]
    assert "<treatment>" in breakdown.job_input(db, project, version)["prompt"]
    bd = clip_prompts.newest(db, project)
    assert "<treatment>" in clip_prompts.job_input(db, project, bd)["prompt"]
    run = {"id": "r", "turn": 0, "redos": {}}
    assert "Mom finds the dip." in director.turn_input(db, project, run)["prompt"]


def test_it_delivers_only_a_cut_it_watched(app, db, owner, editor, monkeypatch):
    real = director.choose

    def early(state):  # a director that delivers the moment the cut is made
        if state["cut"] == "made" and not (state.get("watch") or {}).get("current"):
            return {"tool": "deliver", "why": "Done.", "clip_id": None, "take_id": None,
                    "note": ""}  # fmt: skip
        return real(state)

    monkeypatch.setattr(director, "choose", early)
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=40)
    results = [t["result"] for t in editor.get(f"/projects/{pid}/director").json()["turns"]]
    assert director.UNWATCHED in results  # "Refused: watch the cut first."


def test_planning_again_takes_the_watchs_note_once_a_run(app, db, owner, editor):
    from app import director_tools, plans
    from app.models.accounts import User

    pid = _made(app, owner, editor, db)
    project = db.get(Project, pid)
    user = db.query(User).filter_by(email="ed@example.com").one()
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    assert plans.status(db, project) != "none"
    note = "Re-plan: b2 lands flat; give the payoff its own shot."
    said = director_tools.run(db, user, project, {"tool": "plan", "note": note}, None, {})
    assert said == f"Planning again: {note}"
    job = db.query(Job).filter(Job.project_id == pid).order_by(Job.id.desc()).first()
    assert job.input["step"] == plans.STEP and "give the payoff its own shot" in job.input["prompt"]


def test_the_treatment_is_the_first_move_and_is_posted_in_the_chat(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=120)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    assert out["turns"][0]["tool"] == "treatment"  # the story first
    (told,) = [m for m in out["thread"] if m.get("treatment")]
    assert told["text"].startswith("The treatment:") and told["treatment"]["beats"]
    steps = [j.input for j in db.query(Job).filter(Job.project_id == pid)]
    written = [i for i in steps if i.get("step") in ("clip_prompts", "watch_cut")]
    assert written and all("<treatment>" in i["prompt"] for i in written)  # each read it
    assert any(i.get("step") == "treatment" and i.get(director.RUN) for i in steps)  # its own
