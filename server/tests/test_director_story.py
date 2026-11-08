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


def test_the_treatment_is_the_first_move_and_is_posted_in_the_chat(app, db, owner, editor,
                                                                    monkeypatch):  # fmt: skip
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=120)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    assert out["turns"][0]["tool"] == "treatment"  # the story first
    (told,) = [m for m in out["thread"] if m.get("treatment")]
    assert told["text"].startswith("The treatment:") and told["treatment"]["beats"]
    card = told["treatment"]  # as the card draws it (board S3-02): named, each beat at its time
    assert (card["style"], card["format"]) == ("House", "Dialogue")
    times = [(b["start"], b["end"]) for b in card["beats"]]
    assert times[0][0] == 0 and all(a < b for a, b in times)  # each beat at least 1 s, in order
    assert all(times[i][1] == times[i + 1][0] for i in range(len(times) - 1))
    db.expire_all()
    project = db.get(Project, pid)
    beats = [{"id": "b1", "lines": [1, 2], "purpose": "hook", "picture": "x"},
             {"id": "b2", "lines": [3], "purpose": "payoff", "picture": "y"}]  # fmt: skip
    script = "INT. KITCHEN — DAY\nNATE: " + " ".join(["word"] * 24) + "\nA long silent look."
    from app import plans

    monkeypatch.setattr(plans, "script", lambda db, p: type("V", (), {"text": script})())
    shown = director._shown(db, project)({"beats": beats})
    assert [(b["start"], b["end"]) for b in shown["beats"]] == [(0, 5), (5, 6)]  # 24 words: 5 s
    steps = [j.input for j in db.query(Job).filter(Job.project_id == pid)]
    written = [i for i in steps if i.get("step") in ("clip_prompts", "watch_cut")]
    assert written and all("<treatment>" in i["prompt"] for i in written)  # each read it
    assert any(i.get("step") == "treatment" and i.get(director.RUN) for i in steps)  # its own


def test_it_looks_at_its_stills_against_the_treatment_and_redraws_one_before_takes(
    app, db, owner, editor, monkeypatch
):
    import re

    from app import still_review
    from app.providers.fake_local import FakeWriter

    def off_story(self, prompt):  # the first still misses the treatment's hook, once
        first = re.search(r"\[Image1\] shot (\S+):", prompt)[1]
        return {"ready": False, "findings": [{
            "shot_id": first, "problem": "The hook still doesn't show what the treatment opens on.",
            "note": "Open on the treatment's hook: the subject close."}]}  # fmt: skip

    monkeypatch.setattr(FakeWriter, "_review_stills", off_story)

    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=150)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    tools = [t["tool"] for t in out["turns"]]
    assert tools.index("review_stills") < tools.index("redraw_still") < tools.index("make_take")
    (redraw,) = [t for t in out["turns"] if t["tool"] == "redraw_still"]
    assert redraw["result"].startswith("Drawing shot ") and "treatment's hook" in redraw["result"]
    step = Job.input["step"].as_string()
    (review,) = db.query(Job).filter(Job.project_id == pid, step == "review_stills").all()
    drawn = review.input["files"]["reference_images"]
    assert (
        drawn
        and "<treatment>" in review.input["prompt"]
        and "[Image1] shot" in review.input["prompt"]
    )
    assert review.input.get(director.RUN)  # on the director's own limit
    assert still_review.state(db, db.get(Project, pid))["current"] is False  # one was redrawn


def test_a_still_is_redrawn_twice_at_most_a_run(app, db, owner, editor, monkeypatch):
    real = director.choose

    def again(state):  # a director that keeps redrawing the same still
        if state["stills"]["frames"] and state["stills"]["drawn"] == state["stills"]["frames"]:
            if not state["being_made"]:
                return {"tool": "redraw_still", "shot_id": "1.1", "note": "Closer.",
                        "why": "Again.", "clip_id": None, "take_id": None}  # fmt: skip
        return real(state)

    monkeypatch.setattr(director, "choose", again)
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=60)
    results = [t["result"] for t in editor.get(f"/projects/{pid}/director").json()["turns"]
               if t["why"] == "Again."]  # fmt: skip
    assert sum(r.startswith("Drawing shot 1.1") for r in results) == 2
    assert "Refused: shot 1.1 was drawn again 2 times." in results


def test_a_treatment_that_varies_from_the_script_is_made_again_once_with_its_problems(
    app, db, owner, editor, monkeypatch
):
    from app import prompts
    from app.providers.fake_local import FakeWriter
    from app.providers.fake_local import _tag as tag

    made = []

    def first_skips_a_line(self, prompt):
        good = prompts.stand_in_treatment(tag(prompt, "script") or "")
        made.append("<note>" in prompt)
        if len(made) == 1:  # the first leaves its last beat out
            return {**good, "beats": good["beats"][:-1] or good["beats"]}
        return good

    monkeypatch.setattr(FakeWriter, "_treatment", first_skips_a_line)
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=150)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    assert made[:2] == [False, True]  # one redo, told what to fix (<note>)
    redo = db.query(Job).filter(Job.input["step"].as_string() == "treatment",
                                Job.input["redo"].as_boolean()).one()  # fmt: skip
    assert "Fix:" in redo.input["prompt"]
    told = [m for m in out["thread"] if m.get("treatment")]
    assert len(told) == 1 and told[0]["text"].startswith("The treatment:")  # the kept one


def test_a_treatments_one_redo_keeps_the_persons_note(app, db, owner, editor):
    """MAIN's run 276: the note's treatment ("a barn wedding at night") failed its check, and
    the redo was told only what to fix, so the treatment kept went back to the first one's
    kitchen. The redo gets the note with its fix, and keeps it for a redo of its own."""
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=4, start=False)
    first = db.query(Job).filter(Job.project_id == pid,
                                 Job.input["step"].as_string() == "treatment").first()  # fmt: skip
    note = "A barn wedding at night."
    first.input = {**first.input, "note": note}
    first.output = {**(first.output or {}), "beats": []}  # every line left out: it fails
    db.commit()
    assert director._treatment_checked(db, first)
    redo = db.query(Job).filter(Job.input["step"].as_string() == "treatment",
                                Job.input["redo"].as_boolean()).one()  # fmt: skip
    assert note in redo.input["prompt"] and "Fix:" in redo.input["prompt"]
    assert redo.input["note"] == note


def test_a_watch_still_going_is_not_a_watched_cut(app, db, owner, editor, monkeypatch):
    real = director.choose

    def eager(state):  # delivers as soon as the watch has started on this cut
        if state["cut"] == "made" and (state.get("watch") or {}).get("state") == "watching":
            return {"tool": "deliver", "why": "Done.", "clip_id": None, "take_id": None,
                    "note": ""}  # fmt: skip
        return real(state)

    monkeypatch.setattr(director, "choose", eager)
    monkeypatch.setattr("app.watch_cut.state", lambda db, p: {"state": "watching",
                                                              "current": True})  # fmt: skip
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=40)
    results = [t["result"] for t in editor.get(f"/projects/{pid}/director").json()["turns"]]
    assert director.UNWATCHED in results
