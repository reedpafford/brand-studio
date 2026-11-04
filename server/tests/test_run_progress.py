"""v6 pieces C and D (S3-03 to S3-13, S6-01, S6-04, S6-05, P-04, P-05, P-08, P-10): one live
progress record a run, read by GET …/director/progress, with each clip's state and frame,
the steps in plain words and the seen marks; and the delivery note kept on the deliver turn.
All on the stand-ins (no paid call)."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import event
from sqlalchemy.orm.attributes import flag_modified

from app import delivery, director, run_progress
from app.db import utcnow
from app.models.breakdowns import BreakdownVersion
from app.models.checks import ItemCheck
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.prompts.schemas import DirectorTurn
from tests.test_director import _made, _run


def _done(app, db, owner, editor) -> int:
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    assert editor.get(f"/projects/{pid}/director").json()["status"] == "delivered"
    return pid


def _progress(client, pid: int) -> dict:
    r = client.get(f"/projects/{pid}/director/progress")
    assert r.status_code == 200, r.text
    return r.json()


def _clip(db, pid: int, clip_id: str = "c1") -> ProjectClip:
    return db.query(ProjectClip).filter_by(project_id=pid, clip_id=clip_id).one()


def _job(db, row: ProjectClip, status=JobStatus.queued, **extra) -> Job:
    """A take of `row` being made, held or failed: the same press its button makes."""
    first = db.query(Job).filter_by(project_id=row.project_id, kind="video").first()
    job = Job(workspace_id=first.workspace_id, created_by_id=first.created_by_id, kind="video",
              provider=first.provider, project_id=row.project_id, credits=Decimal("3.1"),
              status=status, input={**first.input, "project_clip_id": row.id, **extra})  # fmt: skip
    db.add(job)
    db.commit()
    return job


def _remade(db, row: ProjectClip, kind: str = "face", text: str = "Mia's face drifts") -> ClipTake:
    """Its watch found something on take 1 and the director made take 2, now picked."""
    one = db.get(ClipTake, row.picked_take_id)
    db.add(ItemCheck(project_id=row.project_id, target="take", target_id=one.id, status="done",
                     findings=[{"kind": kind, "role": "", "text": text, "at": 1.5,
                                "change_note": "keep her face"}]))  # fmt: skip
    job = _job(db, row, JobStatus.succeeded, by_director=True)
    two = ClipTake(clip_id=row.id, number=one.number + 1, job_id=job.id, file_id=one.file_id,
                   made_with=one.made_with)  # fmt: skip
    db.add(two)
    db.flush()
    row.picked_take_id = two.id
    db.commit()
    return two


def _going(db, pid: int) -> None:
    """The newest run as it reads while it goes on: its last turn acted on, not yet ended."""
    last = director.turns(db, db.get(Project, pid))[-1]
    last.input = {k: v for k, v in last.input.items() if k not in ("ended", "result")}
    last.input = {**last.input, "result": "Made the cut."}
    last.output = {**last.output, "tool": "make_take"}
    db.commit()


def test_there_is_no_record_before_a_run(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    assert owner.get(f"/projects/{pid}/director/progress").json() is None


def test_a_delivered_run_reads_as_made_with_every_step_done_and_its_note(app, db, owner, editor):
    pid = _done(app, db, owner, editor)
    p = _progress(owner, pid)
    assert (p["status"], p["tone"]) == ("delivered", "done")
    assert p["sub"] == "1 clip · 1 redone after watching"
    assert p["title"].startswith("Made in ") and p["title"].endswith(" min")
    assert p["ended_at"] and p["minutes_left"] is None and p["stopped"] is p["failed"] is None
    assert all(s["state"] == "done" and s["sub"] == "" for s in p["steps"]), p["steps"]
    keys = [s["key"] for s in p["steps"]]
    assert keys[:2] == ["read", "plan"] and keys[-1] == "cut" and "takes" in keys
    assert p["steps"][0]["text"].startswith("Read the script, the ") and "’s brand kit" in (
        p["steps"][0]["text"])  # fmt: skip
    assert p["steps"][1]["text"] == "Treatment and plan: 1 scene, 1 clip, about 5 s"
    (scene,) = p["scenes"]
    assert (scene["name"], scene["total"], scene["done"]) == ("INT. KITCHEN — MORNING", 1, 1)
    (c,) = scene["clips"]
    assert c["frame_file_id"] and c["take_id"] and c["number"] == 1
    assert c["model"] and c["label"] and c["changed"] and c["state"] == "redone"  # its cut's watch
    assert c["note"] and not c["note"].startswith(("The watch", "c1"))
    assert p["spent"] > 0 and p["up_to"] > 0 and p["spent_usd"] == 0  # the stand-ins are free
    assert _progress(editor, pid)["spent_usd"] is None  # editors never see dollars

    mine = next(m for m in owner.get(f"/projects/{pid}/director").json()["thread"]
                if m.get("note"))  # fmt: skip
    note = mine["note"]
    assert note["made"] == "The cut is made with each clip's best take."
    cuts = db.query(FinalVideo).filter_by(project_id=pid).count()  # it cut, watched and cut again
    assert (note["cut"], note["clips"], note["seconds"]) == (cuts, 1, 5) and cuts > 1
    assert note["needs"] == delivery.NOTHING and note["cost"].startswith("$0.00 spent of up to $")
    texts = [r["text"] for r in note["redid"]]  # what it watched and redid, with when
    muted = "Clip 1: a stray sound nobody asked for. Muted a stretch of clip 1 instead of " \
            "remaking it."  # fmt: skip
    assert muted in texts and all(r["at"] == 0 for r in note["redid"])
    assert any(t.startswith("Clip 1: ") and t.endswith(f"Remade on {c['model']}.") for t in texts)
    assert f"0:00 {texts[0]}" in mine["text"].splitlines()  # the plain lines
    theirs = next(m for m in editor.get(f"/projects/{pid}/director").json()["thread"]
                  if m.get("note"))["note"]  # fmt: skip
    assert theirs["spent_usd"] is None and "$" not in theirs["cost"]
    assert theirs["cost"].endswith("% of the budget)") and " credits used of up to " in (
        theirs["cost"])  # fmt: skip
    cards = [m for m in owner.get(f"/projects/{pid}/director").json()["thread"] if m.get("run")]
    assert [(m["status"], m["text"]) for m in cards] == [("done", p["title"])]


def test_the_director_writes_the_notes_words_and_the_server_the_rest(app, db, owner, editor):
    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    two = _remade(db, _clip(db, pid), "text", "c1: garbled words burned in")
    cut = db.query(FinalVideo).filter_by(project_id=pid).order_by(FinalVideo.id.desc()).first()
    cut.take_ids = [two.id]  # the cut made with it
    db.commit()
    deliver = director.turns(db, project)[-1]
    turn = DirectorTurn(tool="deliver", why="b3: done", made="A 0:05 clip in the kitchen.",
                        unsure="The end holds long; say “shorter end”.",
                        needs="Your OK on c1.")  # fmt: skip
    note = delivery.note(db, project, deliver, turn.model_dump())
    assert note["made"] == "A 0:05 clip in the kitchen." and note["needs"] == "Your OK on clip 1."
    assert note["unsure"] == "The end holds long; say “shorter end”."
    texts = [r["text"] for r in note["redid"]]
    assert "Clip 1: garbled words burned in. Remade without them." in texts  # no "c1: " left
    seen = delivery.shown(note, owner=False)
    assert seen["needs"] == "Your OK on clip 1." and seen["spent_usd"] is None


def test_each_clip_says_what_happened_to_it(app, db, owner, editor, monkeypatch):
    """S6-05's row states and S3-09's outline: flagged, redone, text found, seen, waiting and
    failed, each with its line and, for a press, its price as the viewer reads money."""
    pid = _done(app, db, owner, editor)
    row = _clip(db, pid)

    def cell(who=owner):
        return _progress(who, pid)["scenes"][0]["clips"][0]

    picked = db.get(ClipTake, row.picked_take_id)
    db.add(ItemCheck(project_id=pid, target="take", target_id=picked.id, status="done",
                     findings=[{"kind": "voice", "role": "", "text": "Her voice drifts",
                                "change_note": ""}]))  # fmt: skip
    db.commit()
    assert (cell()["state"], cell()["note"]) == ("flagged", "Her voice drifts")
    counts = _progress(owner, pid)["counts"]
    assert (counts["flagged"], counts["needs_you"], counts["redone"]) == (1, 1, 1)

    two = _remade(db, row)  # the director watched it and made it again
    c = cell()
    assert (c["state"], c["note"], c["changed"], c["watched"]) == (
        "redone", "Mia's face drifts", True, False)  # fmt: skip
    assert c["take_id"] == two.id and _progress(owner, pid)["changed"][0]["take_id"] == two.id
    assert owner.post(f"/projects/{pid}/director/seen", json={"take_ids": [two.id, 999999]}
                      ).status_code == 204  # another video's take is ignored  # fmt: skip
    assert cell()["watched"] is True and cell(editor)["watched"] is False  # a mark a person
    assert owner.post(f"/projects/{pid}/director/seen", json={"take_ids": [two.id]}
                      ).status_code == 204  # twice is fine  # fmt: skip

    check = db.query(ItemCheck).filter_by(target="take").order_by(ItemCheck.id.desc()).first()
    check.findings = [{**check.findings[0], "kind": "text", "text": "Garbled words burned in"}]
    flag_modified(check, "findings")
    db.commit()
    assert cell()["state"] == "text"  # words in the picture, found and remade

    held = _job(db, row, JobStatus.needs_owner_approval,
                held="Waiting for the owner's OK: redo past the budget.")  # fmt: skip
    assert (cell()["state"], cell()["note"], cell()["credits"]) == (
        "waiting", "Redo past the budget.", "$0.32")  # fmt: skip
    assert cell(editor)["credits"] == "4 credits"  # an editor reads credits

    held.status, held.error = JobStatus.failed, "The service was busy."
    db.commit()
    assert (cell()["state"], cell()["note"]) == (
        "failed", "The service was busy. Nothing was charged.")  # fmt: skip

    monkeypatch.setattr(run_progress, "median", lambda _: 180)  # a take takes about 3 min
    making = _job(db, row, JobStatus.running)
    making.started_at = utcnow() - timedelta(seconds=90)
    db.commit()
    c = cell()
    assert (c["state"], c["percent"], c["minutes_left"]) == ("making", 50, 2)


def test_while_it_makes_the_clips_the_card_counts_them_by_scene(app, db, owner, editor):
    pid = _done(app, db, owner, editor)
    _going(db, pid)
    bd = db.query(BreakdownVersion).order_by(BreakdownVersion.id.desc()).first()
    bd.data["clips"] = [{**bd.data["clips"][0], "shot_ids": ["1.1"]},
                        {"id": "c2", "shot_ids": ["1.2"], "seconds": 2, "seam": "end"}]  # fmt: skip
    flag_modified(bd, "data")
    one = _clip(db, pid)
    db.add(ProjectClip(project_id=pid, breakdown_id=one.breakdown_id, clip_id="c2", seconds=2,
                       prompt="Nate shrugs."))  # fmt: skip
    db.commit()
    p = _progress(owner, pid)
    assert (p["status"], p["title"], p["sub"], p["tone"]) == (
        "working", "Making the clips", "1 of 2 · scene 1 of 1", "now")  # fmt: skip
    assert [c["state"] for c in p["scenes"][0]["clips"]] == ["redone", "todo"]
    assert p["minutes_left"] >= 1 and p["ended_at"] is None
    takes = next(s for s in p["steps"] if s["key"] == "takes")
    assert (takes["state"], takes["text"]) == ("now", "Making takes: 1 of 2")
    assert [s["state"] for s in p["steps"]][-1] == "todo"
    _job(db, _clip(db, pid, "c2"), JobStatus.running)
    takes = next(s for s in _progress(owner, pid)["steps"] if s["key"] == "takes")
    assert takes["sub"].startswith("Clip 2 · scene 1 · 2 s · about ")
    (card,) = [m for m in owner.get(f"/projects/{pid}/director").json()["thread"] if m.get("run")]
    assert card["status"] == "running"
    assert card["text"] == "Making the clips · 1 of 2 · scene 1 of 1"


def test_waiting_for_an_ok_reads_as_such_to_each_person(app, db, owner, editor):
    pid = _done(app, db, owner, editor)
    _going(db, pid)
    held = "Waiting for the owner's OK: remaking clip 1 goes past the video's budget."
    _job(db, _clip(db, pid), JobStatus.needs_owner_approval, held=held)
    p = _progress(owner, pid)
    assert (p["status"], p["title"], p["tone"]) == ("waiting", "Waiting for your OK", "wait")
    assert p["sub"] == "remaking clip 1 goes past the video's budget"
    assert any(s["state"] == "wait" for s in p["steps"])
    assert _progress(editor, pid)["title"] == "Waiting for the owner’s OK"  # never a name


def test_stopped_by_a_person_says_who_and_what_carrying_on_costs(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    url = f"/projects/{pid}/director"
    owner.post(url)
    _run(app, db, ticks=4)
    assert owner.post(f"{url}/stop").status_code == 200
    p = _progress(owner, pid)
    assert (p["status"], p["title"], p["tone"]) == ("stopped", "Stopped", "stop")
    assert p["sub"] == f"{p['made']} of {p['clips']} clips made"
    assert p["stopped"]["by"] == "Reed" and p["stopped"]["at"]
    assert p["stopped"]["carry_on"].startswith("$")  # "Carry on · up to $10.74 more"
    assert _progress(editor, pid)["stopped"]["carry_on"].endswith("credits")
    (card,) = [m for m in owner.get(url).json()["thread"] if m.get("run")]
    assert (card["status"], card["text"]) == ("done", "Stopped")


def test_a_run_that_stopped_on_a_problem_offers_a_one_click_fix(app, db, owner, editor):
    """S3-11, rule 22: never a dead end. The clip that failed is made again at its own price,
    or the run carries on; with no clip to blame, carrying on is the fix."""
    pid = _done(app, db, owner, editor)
    last = director.turns(db, db.get(Project, pid))[-1]
    last.input = {**last.input, "result": "Stopped.",
                  "ended": "It stopped: c1's take failed 3 times."}  # fmt: skip
    db.commit()
    p = _progress(owner, pid)
    assert (p["status"], p["title"], p["tone"]) == ("needs_fix", "Stopped", "bad")
    assert p["failed"]["title"] == "The director stopped"
    assert p["failed"]["why"] == "It stopped: clip 1's take failed 3 times."
    assert [f["kind"] for f in p["failed"]["fixes"]] == ["carry_on"]
    _job(db, _clip(db, pid), JobStatus.failed).error = "The service was busy."
    db.commit()
    p = _progress(owner, pid)
    assert (p["title"], p["failed"]["title"]) == ("Stopped at clip 1", "Clip 1 couldn’t be made")
    assert p["failed"]["clip"] == _clip(db, pid).id
    assert [(f["kind"], f["price"]) for f in p["failed"]["fixes"]][0] == ("again", "$0.32")
    assert "bad" in [s["state"] for s in p["steps"]]


def test_a_revision_counts_its_changes(app, db, owner, editor):
    pid = _done(app, db, owner, editor)
    url = f"/projects/{pid}/director"
    editor.post(f"{url}/messages", json={"text": "Make clip 1 warmer."})
    editor.post(url)  # Make it again: a revising run
    p = _progress(owner, pid)
    assert (p["status"], p["title"], p["sub"]) == ("revising", "Revising", "0 of 0 changes")
    _job(db, _clip(db, pid), JobStatus.running, by_director=True)
    assert _progress(owner, pid)["sub"] == "0 of 1 change"
    cards = [m for m in owner.get(url).json()["thread"] if m.get("run")]
    assert [m["status"] for m in cards] == ["done", "running"]  # one card a run


def test_a_long_video_reads_in_the_same_queries(app, db, owner, editor):
    """S3-13: a 118-clip Movie is polled like a short one: the record's reads don't grow with
    its clips."""
    pid = _done(app, db, owner, editor)
    one = _clip(db, pid)
    take = db.get(ClipTake, one.picked_take_id)

    def count() -> int:
        n = [0]
        engine = db.get_bind()
        tick = lambda *a, **k: n.__setitem__(0, n[0] + 1)  # noqa: E731
        event.listen(engine, "before_cursor_execute", tick)
        try:
            run_progress.record(db, db.get(Project, pid), None)
        finally:
            event.remove(engine, "before_cursor_execute", tick)
        return n[0]

    few = count()
    for n in range(2, 40):
        row = ProjectClip(project_id=pid, breakdown_id=one.breakdown_id, clip_id=f"c{n}",
                          seconds=4, prompt="More.")  # fmt: skip
        db.add(row)
        db.flush()
        db.add(ClipTake(clip_id=row.id, number=1, job_id=take.job_id, file_id=take.file_id))
    db.commit()
    assert count() == few
    assert _progress(owner, pid)["clips"] == 39


def test_money_reads_as_dollars_to_the_owner_and_credits_to_everyone_else():
    assert run_progress.money(Decimal("3.1"), True) == "$0.32"  # rounded up, never below
    assert run_progress.money(Decimal("3.1"), False) == "4 credits"
    assert run_progress.money(1, False) == "1 credit"
