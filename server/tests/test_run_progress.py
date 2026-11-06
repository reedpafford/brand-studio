"""v6 pieces C and D (S3-03 to S3-13, S6-01, S6-04, S6-05, P-04, P-05, P-08, P-10): one live
progress record a run, read by GET …/director/progress, with each clip's state and frame,
the steps in plain words and the seen marks; and the delivery note kept on the deliver turn.
All on the stand-ins (no paid call)."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import event
from sqlalchemy.orm.attributes import flag_modified

from app import delivery, director, run_progress
from app.clip_takes import take_credits
from app.db import utcnow
from app.models.breakdowns import BreakdownVersion
from app.models.checks import ItemCheck
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.prompts.schemas import DirectorTurn
from app.routes.jobs import _with_check
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
    assert all(s["state"] == "done" for s in p["steps"]), p["steps"]
    assert [s["key"] for s in p["steps"] if s["sub"]] == ["prompts"]  # why each model (S3-04)
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
    assert p["spent"] > 0 and p["up_to"] >= p["spent"] and p["spent_usd"] > 0  # as the header
    assert _progress(editor, pid)["spent_usd"] is None  # editors never see dollars

    mine = next(m for m in owner.get(f"/projects/{pid}/director").json()["thread"]
                if m.get("note"))  # fmt: skip
    note = mine["note"]
    assert note["made"] == "The cut is made with each clip's best take."
    cuts = db.query(FinalVideo).filter_by(project_id=pid).count()  # it cut, watched and cut again
    assert (note["cut"], note["clips"], note["seconds"]) == (1, 1, 5) and cuts > 1  # its Cut 1
    assert note["open"] == [  # the stand-in's last watch repeats a finding: still open
        "Clip 1: the opening face changes between shots. Not fixed.",
        "The takes weren't checked one by one.",
    ]  # checks are off here
    assert note["needs"] == delivery.LOOK_FIRST
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
    assert seen["needs"].startswith("Your OK on clip 1. Look at") and seen["spent_usd"] is None


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
    ok = _with_check(db, held)  # what the owner's OK charges: the take and its check (rule 36)
    assert (cell()["state"], cell()["note"], cell()["credits"]) == (
        "waiting", "Redo past the budget.", run_progress.money(ok, True))  # fmt: skip
    assert cell(editor)["credits"] == run_progress.money(ok, False)  # an editor reads credits

    held.status, held.error = JobStatus.failed, "The service was busy."
    db.commit()
    assert (cell()["state"], cell()["note"]) == (
        "failed", "The service was busy. Nothing was charged.")  # fmt: skip
    again = take_credits(db, db.get(Project, pid), row)  # as Make a take quotes it
    assert cell()["credits"] == run_progress.money(again, True)

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
    assert _progress(editor, pid)["title"] == "Waiting for the owner's OK"  # never a name
    (card,) = [m for m in owner.get(f"/projects/{pid}/director").json()["thread"] if m.get("run")]
    assert card["status"] == "held" and card["text"].startswith("Waiting for your OK · ")
    (card,) = [m for m in editor.get(f"/projects/{pid}/director").json()["thread"] if m.get("run")]
    assert card["text"].startswith("Waiting for the owner's OK · ")


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
    again = run_progress.money(take_credits(db, db.get(Project, pid), _clip(db, pid)), True)
    assert [(f["kind"], f["price"]) for f in p["failed"]["fixes"]][0] == ("again", again)
    carry = run_progress.money(run_progress.price_of(db, db.get(Project, pid)), True)
    assert p["failed"]["fixes"][1]["price"] == carry != "$0.00"  # a new run's whole "up to"
    assert "bad" in [s["state"] for s in p["steps"]]
    last.input = {**last.input, "ended": "It stopped: the plan kept being refused."}
    db.commit()
    p = _progress(owner, pid)  # a clip failed earlier, but the stop says why: that's shown
    assert (p["title"], p["failed"]["title"]) == ("Stopped", "The director stopped")
    assert p["failed"]["why"] == "It stopped: the plan kept being refused."


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


def test_another_editor_marks_what_they_watched(app, db, owner, editor):
    """A seen mark is a person's own, not a change to the video: any teammate who can open it
    may mark what they watched, and only for that person."""
    from fastapi.testclient import TestClient

    from tests.conftest import PASSWORD

    pid = _done(app, db, owner, editor)
    two = _remade(db, _clip(db, pid))
    token = owner.post("/team/invites", json={"email": "bo@example.com"}).json()["token"]
    with TestClient(app) as bo:
        bo.post("/auth/accept-invite", json={"token": token, "name": "Bo", "password": PASSWORD})
        url = f"/projects/{pid}/director/seen"
        assert bo.post(url, json={"take_ids": [two.id]}).status_code == 204
        assert _progress(bo, pid)["changed"][0]["watched"] is True
    assert _progress(editor, pid)["changed"][0]["watched"] is False


def test_the_note_says_the_headers_spent_and_keeps_no_dollars(app, db, owner, editor):
    """One spent figure: the owner's note says what the run charged, in dollars at the header's
    rate (not the stand-ins' real $0.00). Any teammate can read a job's output (GET /jobs), so
    the note keeps credits only; the dollars are worked out when the owner reads it."""
    pid = _done(app, db, owner, editor)
    deliver = director.turns(db, db.get(Project, pid))[-1]
    assert "spent_usd" not in str(editor.get(f"/jobs/{deliver.id}").json())
    note = next(m for m in owner.get(f"/projects/{pid}/director").json()["thread"]
                if m.get("note"))["note"]  # fmt: skip
    head = owner.get(f"/projects/{pid}/idea").json()
    assert note["spent"] == head["spent"]["credits"] > 0
    assert note["spent_usd"] == head["spent"]["usd"] > 0
    usd, most = head["spent"]["usd"], head["up_to"]["usd"]
    assert note["cost"] == f"${usd:.2f} spent of up to ${most:.2f}"


def test_a_held_turn_the_owner_declined_reads_as_stopped_with_the_reason(app, db, owner, editor):
    pid = _done(app, db, owner, editor)
    last = director.turns(db, db.get(Project, pid))[-1]
    last.input = {k: v for k, v in last.input.items() if k not in ("ended", "result")}
    last.input = {**last.input, "declined": True}
    last.status, last.error = JobStatus.cancelled, "Not this week."
    db.commit()
    p = _progress(owner, pid)
    assert (p["status"], p["tone"], p["failed"]) == ("stopped", "stop", None)
    (card,) = [m for m in owner.get(f"/projects/{pid}/director").json()["thread"] if m.get("run")]
    assert card["text"] == "The owner declined: Not this week."


def test_a_held_turn_taken_back_reads_as_stopped_not_a_fault(app, db, owner, editor):
    pid = _done(app, db, owner, editor)
    last = director.turns(db, db.get(Project, pid))[-1]
    last.input = {k: v for k, v in last.input.items() if k not in ("ended", "result")}
    last.status = JobStatus.cancelled  # cancelled while it waited for the OK (Jobs' Cancel)
    db.commit()
    p = _progress(owner, pid)
    assert (p["status"], p["sub"], p["failed"]) == ("stopped", "Withdrawn.", None)


def test_ready_to_post_only_when_nothing_is_open(app, db, owner, editor, monkeypatch):
    """Reed, 4 Nov: a cut that exists isn't ready to post. The note says what's still open:
    a cut not watched, a take not checked or with a finding kept, a step waiting for the
    owner; then it never says "ready to post"."""
    from app import watch_cut
    from app.watch_cut import _cut

    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    deliver = director.turns(db, project)[-1]
    cut = _cut(db, project)
    take = db.get(ClipTake, cut.take_ids[0])  # the take in the cut
    note = delivery.note(db, project, deliver, {"made": "A short clip."})
    assert note["open"] == [
        "Clip 1: the opening face changes between shots. Not fixed.",
        "The takes weren't checked one by one.",
    ]  # checks off: said
    monkeypatch.setattr("app.item_checks.on", lambda: True)
    w = {"state": "done", "current": True, "findings": []}  # a clean watch of this cut
    monkeypatch.setattr(watch_cut, "state", lambda db_, p: w)
    db.add(ItemCheck(project_id=pid, target="take", target_id=take.id, status="done"))
    db.commit()
    note = delivery.note(db, project, deliver, {"made": "A short clip."})
    assert note["open"] == [] and delivery.shown(note, True)["needs"] == (
        delivery.NOTHING)  # fmt: skip
    w.clear()
    w["state"] = "none"  # then: a cut no one watched

    db.query(ItemCheck).filter_by(target="take", target_id=take.id).update({"status": "failed"})
    db.add(FinalVideo(project_id=pid, file_id=cut.file_id, take_ids=cut.take_ids))  # not watched
    _job(
        db,
        _clip(db, pid),
        JobStatus.needs_owner_approval,
        held="Waiting for the owner's OK: remaking clip 1 goes past the video's budget.",
    )
    db.commit()
    note = delivery.note(db, project, deliver, {"made": "A short clip."})
    assert note["open"] == [
        "The cut wasn't watched.", "Clip 1's take wasn't checked.",
        "Clip 1's take is waiting for the owner's OK: remaking clip 1 goes past the video's "
        "budget."]  # fmt: skip
    shown = delivery.shown(note, False)
    assert shown["needs"] == delivery.LOOK_FIRST and "ready to post" not in shown["needs"]
    assert "Clip 1's take wasn't checked." in delivery.plain(shown).splitlines()

    db.query(ItemCheck).filter_by(target="take", target_id=take.id).update(
        {"status": "done", "findings": [{"kind": "face", "role": "", "text": "c1: Mia's face "
                                         "drifts", "change_note": ""}]})  # fmt: skip
    db.commit()
    note = delivery.note(db, project, deliver, {"made": "x", "needs": "Your OK on clip 1."})
    assert "Clip 1: Mia's face drifts. Kept as it is." in note["open"]
    assert delivery.shown(note, True)["needs"] == (
        "Your OK on clip 1. Look at what remains uncertain before you post it."
    )  # still open


def test_the_director_md_delivery_lines_are_reeds():
    """Reed's clarifications (4 Nov), as the director reads them."""
    from app import prompts

    text = prompts.system("director")
    for said in ("three separate parts you write", "What remains uncertain",
                 "a cut that exists isn't the same as one that's ready to post",
                 "keeps the script's words and the approved cast, voices included",
                 "trimming or re-rendering the cut is free",
                 "never write or repeat changes, timecodes or money yourself"):  # fmt: skip
        assert said in text, said
    assert "two to four short plain sentences" not in text


def test_what_is_open_never_lists_what_was_fixed_and_names_each_step(
    app, db, owner, editor, monkeypatch
):
    """QA on #1340: a finding already muted or spliced (free) isn't "kept"; a check still
    checking is not checked; the watch of this cut's kept findings are open; an unsure line
    alone keeps it from "ready to post"; each held step is named once."""
    from app import watch_cut
    from app.watch_cut import _cut

    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    deliver = director.turns(db, project)[-1]
    take = db.get(ClipTake, _cut(db, project).take_ids[0])
    monkeypatch.setattr("app.item_checks.on", lambda: True)
    monkeypatch.setattr("app.word_splice.wrong", lambda db_, t: [{"word": "fomo",
                                                                  "at": [2.0, 2.4]}])  # fmt: skip
    found: list[dict] = []
    monkeypatch.setattr(watch_cut, "state", lambda db_, p: {"state": "done", "current": True,
                                                            "findings": found})  # fmt: skip
    take.made_with = {**(take.made_with or {}), "mutes": [[1.0, 1.5]],
                      "splices": [{"word": "fomo", "at": [2.0, 2.4], "from_take": 1}]}  # fmt: skip
    db.add(ItemCheck(project_id=pid, target="take", target_id=take.id, status="done"))
    db.add(ItemCheck(project_id=pid, target="words", target_id=take.id, status="done", findings=[
        {"kind": "extra", "role": "", "text": "“uh” isn't in the script", "at": 1.0,
         "span": [1.0, 1.5], "change_note": ""},
        {"kind": "name", "role": "", "text": "“foma”: fomo may be said wrong", "at": 0.5,
         "change_note": ""}]))  # fmt: skip
    db.commit()
    assert delivery.open_items(db, project, delivery._spans(db, _cut(db, project))) == []

    db.query(ItemCheck).filter_by(target="take", target_id=take.id).update({"status": "checking"})
    found.append({"clip_id": "c1", "says": "The hold at the end runs long", "fix": "keep"})
    held = "Waiting for the owner's OK: remaking clip 1 goes past the video's budget."
    _job(db, _clip(db, pid), JobStatus.needs_owner_approval, held=held)
    _job(db, _clip(db, pid), JobStatus.needs_owner_approval, held=held)  # the same, twice
    db.commit()
    note = delivery.note(db, project, deliver, {"made": "x"})
    assert note["open"] == [
        "Clip 1: The hold at the end runs long. Kept as it is.", "Clip 1's take wasn't checked.",
        "Clip 1's take is waiting for the owner's OK: remaking clip 1 goes past the video's "
        "budget."]  # fmt: skip

    note = {**note, "open": [], "unsure": "The ending may feel long."}
    assert delivery.shown(note, True)["needs"] == delivery.LOOK_FIRST


def test_every_open_problem_is_listed_and_every_check_that_didnt_finish(
    app, db, owner, editor, monkeypatch
):
    """QA round 2 on #1340: a current watch's finding that wasn't fixed is open (not one the
    note already asks about); a words check that didn't finish is a check that didn't run;
    every finding is listed; a held watch is named in plain words."""
    from app import watch_cut
    from app.watch_cut import _cut

    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    take = db.get(ClipTake, _cut(db, project).take_ids[0])
    monkeypatch.setattr("app.item_checks.on", lambda: True)
    monkeypatch.setattr(watch_cut, "state", lambda db_, p: {"state": "done", "current": True,
        "findings": [{"clip_id": "c1", "says": "The jump at 0:02", "fix": "redo"},
                     {"clip_id": "c1", "says": "A stray sound", "fix": "mute"}]})  # fmt: skip
    two = [
        {"kind": "face", "role": "", "text": "Mia's face drifts", "change_note": ""},
        {"kind": "outfit", "role": "", "text": "Her coat changes", "change_note": ""},
    ]
    db.add(ItemCheck(project_id=pid, target="take", target_id=take.id, status="done",
                     findings=two))  # fmt: skip
    db.add(ItemCheck(project_id=pid, target="words", target_id=take.id, status="checking"))
    job = director.turns(db, project)[-1]
    held = Job(workspace_id=job.workspace_id, created_by_id=job.created_by_id, kind="check-claude",
               provider="claude", project_id=pid, status=JobStatus.needs_owner_approval,
               input={"step": "watch_cut", "held": "Waiting for the owner's OK: the director "
                      "has used its own limit."})  # fmt: skip
    db.add(held)
    db.commit()
    spans = delivery._spans(db, _cut(db, project))
    asked = "I also noticed: a stray sound. Want me to fix it?"
    assert delivery.open_items(db, project, spans, asked) == [
        "Clip 1: The jump at 0:02. Not fixed.",
        "Clip 1: Mia's face drifts. Kept as it is.", "Clip 1: Her coat changes. Kept as it is.",
        "Clip 1's take wasn't checked.",
        "The watch of the cut is waiting for the owner's OK: the director has used its own "
        "limit."]  # fmt: skip


def test_the_stand_in_says_watched_only_when_it_watched_this_cut():
    clip = {"clip_id": "c1", "stale": False, "picked_take_id": 1, "muted": [],
            "takes": [{"id": 1, "number": 1, "verdict": "clean", "notes": []}]}  # fmt: skip
    state = {"being_made": False, "held_for_owner": False, "shots": "ready", "missing_looks": [],
             "stills": {"frames": 1, "drawn": 1}, "clips": [clip], "cut": "made",
             "watch": {"state": "failed", "current": True},
             "allowed": {"redos_used": {}, "watches_left": 0}}  # fmt: skip
    out = director.choose(state)
    assert (out["tool"], out["why"]) == ("deliver", "The cut is made.")
    state["watch"] = {"state": "done", "current": True, "findings": []}
    assert director.choose(state)["why"] == "The cut is made and watched."


def test_the_director_never_says_ready_to_post_while_something_is_open():
    """Reed: a cut that exists isn't ready to post. Whatever the director wrote, it never
    reads as ready while something is open or uncertain; its real asks are kept word for word
    (QA on #1355: deleting sentences lost asks)."""
    base = {"made": "x", "redid": [], "unsure": "", "needs": "", "open": [], "spent": 1,
            "up_to": 10, "cut": 1, "seconds": 5, "clips": 1}  # fmt: skip
    shown = lambda **o: delivery.shown({**base, **o}, False)["needs"]  # noqa: E731
    assert shown() == delivery.NOTHING
    assert shown(needs="Nothing. It’s ready to post.") == "Nothing. It’s ready to post."
    for o in ({"open": ["The cut wasn't watched."]}, {"unsure": "The end may feel long."}):
        assert shown(needs="Nothing. It’s ready to post.", **o) == delivery.LOOK_FIRST
        assert shown(**o) == delivery.LOOK_FIRST


def test_every_way_of_saying_ready_is_held_back_and_every_ask_is_kept():
    """QA on #1355: readiness said any way (or a note asking nothing) reads LOOK_FIRST; an
    ask stays whole, after "Not ready to post yet." when it mentions being ready."""
    for said in ("ready for posting", "All set.", "You’re all set!", "You can post it.",
                 "It’s ready.", "The cut is ready.", "Everything’s ready.", "Ready to go.",
                 "Good to post.", "Go ahead and post it.", "Feel free to post it.",
                 "Ready for upload.", "Ready to be shared.", "It is ready to be posted.",
                 "Ready-to-post.", "good-to-go", "ready  to post", "Ready\nto post.",
                 "Nothing else needed.", "No action needed.", "Nothing to approve.",
                 "Nothing at this time.", "N/A", "Nothing. It’s ready to post.",
                 "Nothing to approve."):  # fmt: skip
        assert delivery.needs(said, True) == delivery.LOOK_FIRST, said
    look, yet = delivery.LOOK, delivery.NOT_YET
    for ask in ("Your OK on clip 1, and it’s ready to post.",
                "It’s ready to post, but listen to clip 3 first.",
                'Say "go." Then it’s ready to post.',
                "Confirm the voice — it’s all set apart from that.",
                "Is it ready to share with the client?"):  # fmt: skip
        assert delivery.needs(ask, True) == f"{yet} {ask} {look}", ask
    for ask in ("The final cut is ready.", "Your video is ready.", "Ready whenever you are.",
                "Just post it.", "Nothing needed — post it as is.", "Ready to ship.",
                "Approve it, then post it."):  # fmt: skip  # mentions ready or posting: led
        assert delivery.needs(ask, True) == f"{yet} {ask} {look}", ask
    for ask in ("Approve it.", "Approve it?", "Do you approve?", "Do you want it shorter?",
                "OK it?", "Go ahead?", "Nothing else. Approve it.",
                "No, approve it."):  # fmt: skip  # a short ask is never swallowed
        assert delivery.needs(ask, True) == f"{ask} {look}", ask
    assert delivery.needs("Your OK on clip 1", True) == f"Your OK on clip 1. {look}"
    assert delivery.needs("Check clip 3;", True) == f"Check clip 3. {look}"
    assert delivery.needs("Wait…", True) == f"Wait… {look}"
    assert delivery.needs('Say "go."', True) == f'Say "go." {look}'  # no stray full stop
