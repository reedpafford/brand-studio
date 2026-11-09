"""Session 35's costs (A2, A4, A6, A7): the director is told what's true before it pays, never
limited in what it may choose. On the stand-ins."""

import copy

from sqlalchemy.orm.attributes import flag_modified

from app import director, director_tools, still_review, watch_cut
from app.clip_takes import contradicts
from app.models.accounts import User
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.models.script_library import ScriptCastSlot
from app.prompts import review_stills_input
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_breakdown import BREAKDOWN
from tests.test_freestyle_dialogue import _run as tick
from tests.test_run_progress import _done
from tests.test_script_library import SCRIPT, _make

EXTRAS = ["person:Grant", "person:Crowd", "person:Woman", "person:Dog", "person:Door",
          "person:Zed"]  # fmt: skip


def _video(app, owner, editor, db, script: str, bd: dict, roles=()) -> tuple[int, int]:
    """A published script's video: Mom locked to Mia (with a sheet), Nate not cast yet."""
    app.state.settings.fake_providers = True
    base = f"/scripts/{_make(owner, text=script)['id']}"
    for role in roles:
        owner.post(f"{base}/cast", json={"role": role})
    mia = owner.post("/library/character", json={"name": "Mia", "image_file_ids": [upload(owner)]})
    with_sheet(db, mia.json()["id"])
    mom = owner.post(f"{base}/cast", json={"role": "Mom"}).json()[0]["id"]
    nate = owner.post(f"{base}/cast", json={"role": "Nate"}).json()[1]["id"]
    owner.post(f"{base}/cast/{mom}/lock", json={"library_item_id": mia.json()["id"]})
    bd = copy.deepcopy(bd)
    bd["scenes"][0]["shots"][0]["character_ids"] = [f"char:{mia.json()['id']}", f"slot:{nate}"]
    bd["scenes"][0]["shots"][1]["character_ids"] = [f"slot:{nate}", *EXTRAS]
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    return editor.post(f"{base}/drafts/0/produce").json()["project_id"], mia.json()["id"]


def test_someone_who_never_speaks_is_a_role_and_a_missing_look(app, db, owner, editor):
    """A2 (226's Grant): the shots name him and the script writes his name, so he's a role in
    his shots and the director is told his look is missing. QA on #1405: an extra ("A crowd
    cheers", "a woman walks past with her dog") is never a paid role, nor "Mara, a young woman";
    the director is told who's on screen with no role, and decides."""
    script = (f"{SCRIPT}\nA crowd cheers. A woman walks past with her dog. Mara watches as Grant "
              "stands by the door.")  # fmt: skip
    pid, _ = _video(app, owner, editor, db, script, BREAKDOWN, roles=["Mara, a young woman"])
    project = db.get(Project, pid)
    grant = db.query(ScriptCastSlot).filter_by(role="Grant").one()
    roles = {s.role for s in db.query(ScriptCastSlot).all()}
    assert not roles & {"Crowd", "Woman", "Dog", "Door", "Zed"}
    state = director.video_state(db, project)
    assert "Grant" in state["missing_looks"]
    assert state["no_role"] == ["Crowd", "Woman", "Dog", "Door", "Zed"]
    from app.routes.project_assets import _newest

    shown = _newest(db, project).data["scenes"][0]["shots"][1]["character_ids"]
    mara = db.query(ScriptCastSlot).filter_by(role="Mara, a young woman").one()
    assert f"slot:{grant.id}" in shown and f"slot:{mara.id}" not in shown
    assert not [r for r in shown if r.startswith("person:")]


def test_the_still_review_sees_the_sheets_and_a_sheet_redraw_needs_one(app, db, owner, editor):
    """A2: the review judges against the sheets each still is drawn from, and says who has
    none; a redraw asking to match a sheet the shot lacks is refused with what to do first."""
    pid, mia = _video(app, owner, editor, db, SCRIPT, BREAKDOWN)
    project = db.get(Project, pid)
    from app.routes.project_assets import _newest

    shots = [s for sc in _newest(db, project).data["scenes"] for s in sc["shots"]]
    images, against = still_review._sheets(db, project, shots, [901, 902])
    sheet = images[2]
    assert images == [901, 902, sheet] and against == ["Mia [Image3]; Nate (no sheet)",
                                                       "Nate (no sheet)"]  # fmt: skip
    text = review_stills_input("plan", [(1, "1.1", "Mom asks.", "", against[0])])
    assert "(drawn from: Mia [Image3]; Nate (no sheet))" in text and "against its sheet" in text
    note = "Draw it again with Nate's character sheet attached."
    assert still_review.no_sheet(db, project, "1.2", note) == (
        "Refused: Nate has no sheet in this video yet, so drawing shot 1.2 again can't match "
        "one. Make the look first (ask who plays them, then make_looks), then draw it again."
    )
    assert still_review.no_sheet(db, project, "1.2", "Warmer light.") == ""  # anything else goes
    assert still_review.no_sheet(db, project, "1.2", "Match her sheet.") == ""  # names no one
    assert still_review.no_sheet(db, project, "1.1", "Keep Mia's sheet.") == ""  # hers is there
    assert still_review.no_sheet(db, project, "1.1", "Use Maya's character sheet.").startswith(
        "Refused: Maya has no sheet")  # 233: Maya was no role at all  # fmt: skip
    bd = _newest(db, project)
    bd.data["scenes"][0]["shots"][1]["character_ids"] = [f"char:{mia}"]
    flag_modified(bd, "data")
    db.commit()
    assert still_review.no_sheet(db, project, "1.2", "Match Mia's character sheet.") == ""
    assert still_review.no_sheet(db, project, "1.2", note).startswith("Refused: Nate has no")


def test_a_long_note_is_trimmed_and_one_that_takes_away_what_the_prompt_shows_rewrites_it(
    app, db, owner, editor
):
    """A4: a 543-character note was refused as "name one clip"; now a note past 500 is refused
    in plain words, never cut short (F16: 261's ended "on the pouch held still"). A7: "no
    phone" under a prompt with the phone was appended, both stood, and the $0.82 take raised
    the phone; now the prompt is rewritten with the note (Change it…) first."""
    assert contradicts("His phone lights up in his limp hand.", "No phone in this one.")
    assert contradicts("Two phones glow on the desk.", "without the phone")
    assert not contradicts("A warm kitchen at night.", "No phone, warmer light.")
    assert not contradicts("He smiles at her.", "Warmer light.")
    for prompt, said in (
        ("Her eyes wide, she stares.", "His eyes are not wide enough."),
        ("Warm lamp light on her face.", "too blue, not warm lamp light"),
        ('He sighs "Not again" at the phone.', 'He says "Not again" too fast.'),
        ("She never blinks.", "Never let her blink."),
    ):  # QA on #1405
        assert not contradicts(prompt, said), said
    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    user = db.get(User, project.created_by_id)
    row = db.query(ProjectClip).filter_by(project_id=pid, clip_id="c1").one()
    jobs = db.query(Job).count()
    long = "Warmer light in the kitchen. " * 19 + "End on the pouch held still."  # ~580
    note = {"tool": "make_take", "clip_id": "c1", "note": long}
    said = director_tools.run(db, user, project, note, app.state.storage, {"id": "r"})
    assert said == director_tools.LONG_NOTE.format(what="redo", most=500, n=len(long.strip()))
    assert db.query(Job).count() == jobs  # refused, never cut: 261 lost its note's end (F16)
    note = {**note, "note": long[-200:]}  # said shorter, all of it
    said = director_tools.run(db, user, project, note, app.state.storage, {"id": "r"})
    assert said == "Making 1 take.", said
    job = db.query(Job).order_by(Job.id.desc()).first()
    assert job.kind == "video" and job.input["note"].endswith("End on the pouch held still.")
    db.delete(job)  # as if it were made: the next take may start
    row.prompt = f"{row.prompt}\nHis phone lights up in his limp hand."
    db.commit()
    note = {"tool": "make_take", "clip_id": "c1", "note": "No phone: his hands are empty."}
    said = director_tools.run(db, user, project, note, app.state.storage, {"id": "r"})
    assert said.endswith("The note changes what c1 shows, so its prompt is rewritten with it "
                         "first."), said  # fmt: skip
    job = db.query(Job).order_by(Job.id.desc()).first()
    assert (job.input["step"], job.input["note"]) == ("change", "No phone: his hands are empty.")
    take = db.get(ClipTake, was := row.picked_take_id)  # as watch_cut.redone stamps it
    take.watch = {**(take.watch or {}), "by": "cut", "action": "redo", "remake_job_id": job.id}
    db.commit()
    tick(app, db, ticks=4, start=False)  # the rewrite lands and queues the take
    db.expire_all()
    made = db.get(ProjectClip, row.id).change["made_job_id"]
    assert db.get(ClipTake, was).watch["remake_job_id"] == made != job.id  # the take, its number


def test_a_cut_being_made_and_a_redo_the_server_would_refuse_read_as_such(app, db, owner,
                                                                         editor):  # fmt: skip
    """A6: a cut being made read "out of date" (226 asked for it again), and a redo the rule
    refuses (only a doubt, or no reason at all) was tried, paid turn and all (233 c3, 301 T16,
    294's two). The state says both."""
    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    user = db.get(User, project.created_by_id)
    clip = next(c for c in director.video_state(db, project)["clips"] if c["clip_id"] == "c1")
    assert "redo" not in clip  # the current watch of the cut saw it: a redo is confirmed
    job = watch_cut._newest(db, project)
    job.output = {**job.output, "checked": [{**f, "fix": "keep", "doubt": True}
                                            for f in job.output["checked"]]}  # fmt: skip
    db.commit()
    clip = next(c for c in director.video_state(db, project)["clips"] if c["clip_id"] == "c1")
    assert clip["redo"] == director.REDO_NEEDS
    job.output = {**job.output, "checked": []}  # 301 T16: nothing found, a remake refused
    db.commit()
    clip = next(c for c in director.video_state(db, project)["clips"] if c["clip_id"] == "c1")
    assert clip["redo"] == director.REDO_NEEDS  # said before the turn, as for a doubt
    assert director_tools.run(db, user, project, {"tool": "final_cut"}, app.state.storage, {})
    db.commit()
    assert director.video_state(db, project)["cut"] == "being made"


def test_a_doubt_both_watches_saw_is_a_fault_the_director_may_remake(app, db, owner, editor):
    """276: clip 1's take watch and the watch of the cut both saw its lines on the listener's
    face, and the director's remake was refused as only a doubt. The same kind of doubt on the
    same take, seen by both, is a fault (within the usual 2 redos); a different one isn't."""
    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    job = watch_cut._newest(db, project)
    job.output = {**job.output, "checked": [{**f, "fix": "keep", "doubt": True, "kind": "lipsync"}
                                            for f in job.output["checked"]]}  # fmt: skip
    row = db.query(ProjectClip).filter_by(project_id=pid, clip_id="c1").one()
    take = db.get(ClipTake, row.picked_take_id)
    fault = {"kind": "voice", "at": 3.0, "says": "The voice may thin out", "verified": False}
    take.watch = {**(take.watch or {}), "faults": [fault]}
    db.commit()
    assert director._only_a_doubt(db, project, "c1", "Lines on the wrong faces.")
    take.watch = {**take.watch, "faults": [{**fault, "kind": "lipsync",
                                            "says": "Maya mouths Granny's line"}]}  # fmt: skip
    db.commit()
    clip = next(c for c in director.video_state(db, project)["clips"] if c["clip_id"] == "c1")
    assert "redo" not in clip
    assert not director._only_a_doubt(db, project, "c1", "Lines on the wrong faces.")


def test_no_note_is_cut_short_anywhere_the_director_writes_one(app, db, owner, editor):
    """F16: every note the director writes goes on as written or is refused with its length:
    a still's redraw, a plan, a talker's motion, a card's question, a voice's description."""
    import pytest
    from fastapi import HTTPException

    from app import asks, talker, voices

    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    user = db.get(User, project.created_by_id)
    long, jobs = "x " * 300, db.query(Job).count()
    for tool, what in (("redraw_still", "redraw"), ("plan", "plan"), ("change_look", "change")):
        said = director_tools.run(db, user, project, {"tool": tool, "shot_id": "1.1",
                                                      "note": long}, app.state.storage)  # fmt: skip
        assert said.startswith(f"Refused: a {what} note is at most 500 characters"), said
    motion = "y " * (talker.LONGEST_MOTION // 2 + 5)
    said = director_tools.run(db, user, project, {"tool": "host", "note": motion},
                              app.state.storage)  # fmt: skip
    assert said.startswith("Refused: a motion note is at most 600 characters"), said
    assert db.query(Job).count() == jobs  # nothing made, nothing charged
    move = {"kind": "story", "question": "How should it end? " * 30,
            "choices": [{"title": "A"}, {"title": "B"}], "pick": "A"}  # fmt: skip
    assert asks.asked(db, project, None, move).startswith("Refused: an ask's question is at most")
    with pytest.raises(HTTPException) as no:
        voices.describe(db, user, project.brand_id, "A warm low voice. " * 40)
    assert "500 characters or fewer" in no.value.detail


def test_every_instruction_of_a_note_is_kept_in_the_redo_or_named_as_left_out(app, db, owner,
                                                                              editor):  # fmt: skip
    """F16, video 261: the owner's revision note asked four things; the redo note lost its last
    ("end on the pouch held still for a beat"). The director's redo note keeps each one in its
    own words; what can't be done is its move's `left_out`, and the delivery note names it."""
    from app import delivery
    from app.prompts.schemas import DirectorTurn

    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    user = db.get(User, project.created_by_id)
    redo = {"tool": "make_take", "clip_id": "c1", "why": "Note 1: clip 1, as asked.",
            "note": "Warmer late-sun light; she smiles only at the very end; one mug, hers; "
                    "end on the pouch held still for a beat.",
            "left_out": "Note 1: a 20-second clip 1: the model makes 8 s at most."}  # fmt: skip
    asked = ["Warmer late-sun light", "she smiles only at the very end", "one mug, hers",
             "end on the pouch held still for a beat"]  # fmt: skip
    assert director_tools.run(db, user, project, redo, app.state.storage, {"id": "r"}) == (
        "Making 1 take.")  # fmt: skip
    job = db.query(Job).order_by(Job.id.desc()).first()
    assert all(a in job.input["note"] for a in asked), job.input["note"]
    turns = director.turns(db, project)
    deliver = turns[-1]
    moves = [({**redo, "left_out": "Note 1: the hold: no room."}, "Making 1 take."),  # done later
             ({**redo, "left_out": "Note 1: the whole note: too long."}, "Refused: long"),
             (redo, "Making 1 take.")]  # fmt: skip
    for t, (move, result) in zip(turns[-4:-1], moves, strict=True):
        t.output, t.input = move, {**t.input, "result": result}
        flag_modified(t, "output")
        flag_modified(t, "input")
    db.commit()
    turn = DirectorTurn(tool="deliver", why="Note 1: done.", made="Clip 1 made again.")
    note = delivery.note(db, project, deliver, turn.model_dump())
    assert "Note 1: a 20-second clip 1: the model makes 8 s at most." in note["open"]
    assert not any("too long" in x or "no room" in x for x in note["open"])  # refused; redone
    said = turn.model_copy(update={"needs": "Note 1: a 20-second clip 1: the model makes 8 s "
                                            "at most."}).model_dump()  # fmt: skip
    assert not any("20-second" in x for x in delivery.note(db, project, deliver, said)["open"])


def test_a_change_box_takes_a_whole_note_and_a_short_one_refuses_plainly(app, db, owner, editor):
    """F16 (Reed, 8 Nov): Change this… on a clip read a pasted note cut at 500; it's read whole
    (its prompt is rewritten in its own words). A look's change goes into the picture's own
    words, so past 500 it's refused at send, plainly, never cut."""
    pid = _done(app, db, owner, editor)
    row = db.query(ProjectClip).filter_by(project_id=pid, clip_id="c1").one()
    long = "Warmer light in the kitchen, and she smiles only at the end. " * 30  # ~1,800
    said = owner.post(f"/projects/{pid}/clips/{row.id}/change", json={"note": long})
    assert said.status_code != 422, said.text
    no = owner.post(f"/projects/{pid}/plan/scenes/1/change", json={"note": "x" * 20_001})
    assert no.status_code == 422 and "Send it as two notes." in no.json()["detail"][0]["msg"]
    item = owner.post("/library/character", json={"name": "Ana", "image_file_ids": [upload(owner)]})
    no = owner.post(f"/library/character/{item.json()['id']}/sheet", json={"change": "y" * 501})
    assert no.status_code == 422 and no.json()["detail"][0]["msg"] == (
        "This note is 501 characters; the most is 500. Say it shorter.")  # fmt: skip
