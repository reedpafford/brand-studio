"""Video 233 (7 Nov): after a delivery a note asking for a free trim started a run whose first
move, the edit, was refused ("the treatment comes first"), so the director rewrote the story
($0.42, a new hook and ending nobody asked for) and waited on a start card for a free trim.
A revision now reuses the video's treatment and plan: its free changes to the cut it has run
at once, with no start card; only what makes something new (a clip's take) waits for Make it,
and only that clip is made again. A note that asks to change the story still gets its
treatment, then waits for Make it. Stand-ins only."""

from app import asks, director
from app.models.asks import Ask
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from tests.test_director import _made, _run


def _delivered(app, db, owner, editor) -> int:
    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db)
    assert owner.get(f"/projects/{pid}/director").json()["status"] == "delivered"
    return pid


def _since(db, pid, first: int, step: str) -> list[Job]:
    return [j for j in _since_jobs(db, pid, first) if j.input.get("step") == step]


def _since_jobs(db, pid, first: int) -> list[Job]:
    return db.query(Job).filter(Job.project_id == pid, Job.id > first).all()


def _starts(db, pid) -> int:
    return db.query(Ask).filter(Ask.project_id == pid, Ask.kind == "start").count()


def test_a_pacing_note_is_a_free_edit_with_no_new_story_or_start_card(app, db, owner,
                                                                       monkeypatch):  # fmt: skip
    """The video 233 case on a narrated presenter video (its words are heard, so the edit can
    be made): "Tighten it" after the delivery is one free re-time, cut and delivered again."""
    from tests.test_freestyle_dialogue import _run as _fs_run
    from tests.test_freestyle_song import NARRATION, _sent
    from tests.test_host import _video

    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)
    fs = _sent(owner, "presenter", NARRATION)
    _fs_run(app, db, ticks=160)
    video = _video(db, fs)
    pid = video.id
    first, cards = db.query(Job).order_by(Job.id.desc()).first().id, _starts(db, pid)
    said = owner.post(f"/freestyles/{fs['id']}/messages",
                      json={"text": "Tighten it: the middle drags."})  # fmt: skip
    assert said.status_code == 201, said.text
    _fs_run(app, db, ticks=120, start=False)  # nobody presses Make it: none is needed
    turns = director.turns(db, db.get(Project, pid))
    run = turns[-1].input[director.RUN]
    assert run.get(director.REVISION) and not run.get("ok")  # never through a start card
    results = [t.input.get("result") or "" for t in turns]
    assert not any(r in (director.TREATMENT_FIRST, director.START_FIRST) for r in results)
    assert not _since(db, pid, first, "treatment")  # the story stands
    assert _starts(db, pid) == cards  # no start card
    assert not _since(db, pid, first, "clip_take")  # nothing made again
    edits = [t for t in turns if (t.output or {}).get("tool") == "edit_cut"]
    assert edits and not edits[0].input["result"].startswith("Refused"), results
    assert owner.get(f"/freestyles/{fs['id']}").json()["status"] == "delivered", [
        (
            (t.output or {}).get("tool"),
            t.input.get("result"),
            t.status,
            t.input.get("held"),
            t.input.get(director.START),
            t.input.get("plan_ok"),
        )
        for t in turns
    ]
    after = turns[turns.index(edits[0]) + 1 :]  # its cut again and its watch: the server's
    assert [((t.output or {}).get("tool"), t.input.get("server")) for t in after[:2]] == [
        ("final_cut", True), ("watch_cut", True)]  # fmt: skip


def test_a_one_clip_note_remakes_only_that_clip_after_its_start_card(app, db, owner, editor):
    pid = _delivered(app, db, owner, editor)
    first = db.query(Job).order_by(Job.id.desc()).first().id
    owner.post(f"/projects/{pid}/director/messages", json={"text": "Make clip 1 brighter."})
    _run(app, db, ticks=4, start=False)
    assert not _since(db, pid, first, "treatment")  # no new story for one clip
    held = [j for j in db.query(Job).filter(Job.project_id == pid,
                                            Job.status == JobStatus.needs_owner_approval)
            if j.input.get(director.START)]  # fmt: skip
    assert held, "a new take waits for its start card"
    results = [t.input.get("result") for t in director.turns(db, db.get(Project, pid))]
    assert director.TREATMENT_FIRST not in results
    _run(app, db)  # Make it, then the rest
    takes = _since(db, pid, first, "clip_take")
    assert takes and {t.input.get("project_clip_id") for t in takes} == {
        takes[0].input.get("project_clip_id")}  # only clip 1  # fmt: skip
    assert owner.get(f"/projects/{pid}/director").json()["status"] == "delivered"


def test_a_note_that_changes_the_story_rewrites_it_then_waits_for_make_it(app, db, owner,
                                                                         editor):  # fmt: skip
    pid = _delivered(app, db, owner, editor)
    first = db.query(Job).order_by(Job.id.desc()).first().id
    owner.post(f"/projects/{pid}/director/messages",
               json={"text": "Change the ending: he throws the pint away."})  # fmt: skip
    _run(app, db, ticks=6, start=False)
    assert _since(db, pid, first, "treatment")  # asked: the story again
    held = [j for j in db.query(Job).filter(Job.project_id == pid,
                                            Job.status == JobStatus.needs_owner_approval)
            if j.input.get(director.START)]  # fmt: skip
    assert held  # then everything waits for Make it, the free edits too


def test_before_make_it_a_revision_may_edit_the_cut_but_never_make_anything(app, db, owner,
                                                                           editor):  # fmt: skip
    pid = _delivered(app, db, owner, editor)
    project = db.get(Project, pid)
    run = {**director.turns(db, project)[-1].input[director.RUN], "ok": False,
           director.REVISION: True, "id": "rev"}  # fmt: skip
    assert director.REVISE_FREE == ("edit_cut", "final_cut", "mute", "unmute", "pick_take",
                                    "splice_word", "watch_cut", "deliver")  # fmt: skip
    assert director._written(db, run, pid)  # its story is the video's
    assert not director._written(db, {**run, director.REVISION: False}, pid)
    assert not director._own_story(db, run, pid)


def test_an_editors_held_revision_waits_for_the_owners_start_card(app, db, owner, editor,
                                                                  monkeypatch):  # fmt: skip
    """QA (#1412): an editor's video with its budget used: "Tighten it." made a paid watch, a
    new cut and a delivery with no owner's OK. A held revision makes nothing, its free edits
    too, until the owner's Make it."""
    from decimal import Decimal

    pid = _delivered(app, db, owner, editor)
    monkeypatch.setattr("app.credits.budget", lambda db, project: Decimal(0))  # all used
    first = db.query(Job).order_by(Job.id.desc()).first().id
    said = editor.post(f"/projects/{pid}/director/messages", json={"text": "Tighten it."})
    assert said.status_code in (200, 201), said.text
    _run(app, db, ticks=8, start=False)  # the owner hasn't pressed Make it
    turns = director.turns(db, db.get(Project, pid))
    run = turns[-1].input[director.RUN]
    assert run.get(director.REVISION) and run.get("hold")  # its last turn: the held card
    made = {j.input.get("step") for j in _since_jobs(db, pid, first)
            if j.status != JobStatus.needs_owner_approval}  # fmt: skip
    assert not made & {"final_cut", "watch_cut", "clip_take"}, made
    held = [j for j in db.query(Job).filter(Job.project_id == pid,
                                            Job.status == JobStatus.needs_owner_approval)
            if j.input.get(director.START)]  # fmt: skip
    assert held and held[-1].input.get(asks.HOLD) == run["hold"]  # the owner's start card
    assert editor.get(f"/projects/{pid}/director").json()["status"] != "delivered"
    assert not director._free_revision(db, run, pid)
    assert director._free_revision(db, {**run, "hold": ""}, pid)


def test_a_step_held_for_make_it_shows_as_not_made_yet_and_is_made_after_it(app, db, owner,
                                                                           editor):  # fmt: skip
    """QA (#1412): a paid step asked before Make it was read as done after it, and never made.
    <last_actions> marks it "Not made yet", and the stand-in makes it once Make it is pressed."""
    pid = _delivered(app, db, owner, editor)
    owner.post(f"/projects/{pid}/director/messages", json={"text": "Make clip 1 brighter."})
    _run(app, db, ticks=4, start=False)
    project = db.get(Project, pid)
    turns = director.turns(db, project)
    held = [t for t in turns if t.input.get("result") == director.START_FIRST]
    assert held and (held[-1].output or {}).get("tool") == "make_take"
    shown = director.turn_input(db, project, turns[-1].input[director.RUN])["prompt"]
    assert director.NOT_MADE in shown and director.START_FIRST not in shown
    _run(app, db)  # Make it: the stand-in reads it as still to make, and makes it
    assert [t for t in _since(db, pid, held[-1].id, "clip_take")]


def test_a_delivered_revisions_turn_input_reads_its_last_actions(app, db, owner, editor):
    """next, 7 Nov: a second `_shown` in app/director.py replaced the <last_actions> one, so
    every turn's prompt raised. A delivered video's revision builds its prompt, and its held
    step reads "Not made yet"."""
    pid = _delivered(app, db, owner, editor)
    project = db.get(Project, pid)
    run = {**director.turns(db, project)[-1].input[director.RUN], "ok": False,
           director.REVISION: True}  # fmt: skip
    last = director.turns(db, project)[-1]
    last.input = {**last.input, "result": director.START_FIRST}
    db.commit()
    shown = director.turn_input(db, project, run)["prompt"]
    assert "<last_actions>" in shown and '"revision": true' in shown
    assert director.NOT_MADE in shown and director.START_FIRST not in shown


def test_an_owners_long_note_reaches_the_director_whole_and_is_never_cut(app, db, owner,
                                                                         editor):  # fmt: skip
    """F16 (Reed, 8 Nov: "a revision note is never silently cut"). A note past the chat box's
    old 2,000 is read whole in <chat>; past 20,000 it's refused at send, in plain words. The
    stand-in can't say a long note shorter, so it makes nothing for it and names it."""
    import json

    pid = _delivered(app, db, owner, editor)
    first = db.query(Job).order_by(Job.id.desc()).first().id
    sent = f"/projects/{pid}/director/messages"
    no = owner.post(sent, json={"text": "x" * 20_001})
    assert no.status_code == 422 and no.json()["detail"][0]["msg"] == (
        "This note is 20,001 characters; the most is 20,000. Send it as two notes.")  # fmt: skip
    note = ("Clip 1 needs four things. Warmer light, like late sun through the window. She "
            "smiles only at the very end. One mug on the counter, hers. "
            + "Why: the brand wants a calm, honest morning. " * 45
            + "And end on the pouch held still for a beat.")  # fmt: skip
    assert len(note) > 2000
    assert owner.post(sent, json={"text": note}).status_code == 201
    _run(app, db, ticks=4, start=False)
    project = db.get(Project, pid)
    run = director.turns(db, project)[-1].input[director.RUN]
    assert json.dumps(note) in director.turn_input(db, project, run)["prompt"]  # whole
    _run(app, db)
    assert not _since(db, pid, first, "clip_take")  # never made from a cut note
    said = owner.get(f"/projects/{pid}/director").json()["thread"][-1]["text"]
    assert "Note 1: it's longer than one redo note carries (500 characters)" in said, said
