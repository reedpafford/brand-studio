"""Who plays whom (Reed, "Turned down in Paris"): after Nate was cast at Assets and the
breakdown redone, the rich older man showed up in Nate's shot. Every cast line now names the
role; a swapped shot is a problem that stops stills; a free fix puts the right cast back."""

import copy

from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from tests.conftest import upload
from tests.helpers import approved_plan, with_sheet
from tests.test_breakdown import BREAKDOWN
from tests.test_script_library import SCRIPT, _make


def _video(owner, editor, db):
    """Mom locked to Mia; Nate cast at Assets to Kid (as Carl was in Reed's video)."""
    made = _make(owner, text=SCRIPT)
    base = f"/scripts/{made['id']}"
    mia = owner.post("/library/character", json={"name": "Mia", "image_file_ids": [upload(owner)]})
    mia = mia.json()["id"]
    with_sheet(db, mia)
    mom = owner.post(f"{base}/cast", json={"role": "Mom"}).json()[0]["id"]
    nate = owner.post(f"{base}/cast", json={"role": "Nate", "description": "teen"}).json()[1]["id"]
    owner.post(f"{base}/cast/{mom}/lock", json={"library_item_id": mia})
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][0]["character_ids"] = [f"char:{mia}", f"slot:{nate}"]
    bd["scenes"][0]["shots"][1]["character_ids"] = [f"slot:{nate}"]
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    kid = editor.post(
        "/library/character", json={"name": "Kid", "image_file_ids": [upload(editor)]}
    )
    kid = kid.json()["id"]
    editor.put(f"/projects/{pid}/assets/slots/{nate}", json={"library_item_id": kid})
    return pid, mia, kid


def test_cast_lines_name_the_role_each_character_plays(owner, editor, db):
    pid, mia, kid = _video(owner, editor, db)
    approved_plan(db, f"/projects/{pid}")  # shots come from a plan (1b)
    job = editor.post(f"/projects/{pid}/breakdown").json()
    prompt = db.get(Job, job["id"]).input["prompt"]
    assert f"char:{kid} | Kid | plays Nate" in prompt  # cast at Assets
    assert "teen" not in prompt.split("</cast>")[0]  # the look's own notes say how he looks
    assert f"char:{mia} | Mia | plays Mom" in prompt  # locked
    assert "slot:" not in prompt.split("</cast>")[0]  # both roles are cast


def test_a_filled_slot_is_one_asset_line_the_looks_own(owner, editor, db):
    """Director (video 7): Omar, locked to Carl, was listed twice (char:3 and slot:N, two
    names, two outfits). Now the slot is the look's line, printed once."""
    from app.storyboard import assets, job_input

    pid, mia, kid = _video(owner, editor, db)
    project = db.get(Project, pid)
    known = assets(db, project)
    slots = [k for k in known if k.startswith("slot:")]
    assert len(slots) == 2 and {known[k][0] for k in slots} == {
        known[f"char:{mia}"][0],
        known[f"char:{kid}"][0],
    }  # either id still works
    assert known[f"char:{kid}"][0] == f"char:{kid} | character | Kid | plays Nate"
    bd = db.query(BreakdownVersion).filter_by(project_id=pid).first()
    lines = job_input(db, project, bd, False)["prompt"].split("<assets>")[1]
    assert lines.count("plays Nate") == 1 and "slot:" not in lines.split("</assets>")[0]


def test_a_redone_breakdown_with_the_wrong_person_stops_stills_and_is_fixed_for_free(
    owner, editor, db
):
    """The regression: Nate cast at Assets, then a new breakdown puts Mom's look in Nate's
    shot. Stills stop with the reason; Put the right cast in each shot fixes it, no model call."""
    pid, mia, kid = _video(owner, editor, db)
    url = f"/projects/{pid}/breakdown"
    wrong = copy.deepcopy(BREAKDOWN)
    wrong["scenes"][0]["shots"][0]["character_ids"] = [f"char:{mia}", f"char:{kid}"]
    wrong["scenes"][0]["shots"][1]["character_ids"] = [f"char:{mia}"]  # Nate's line, Mom's look
    saved = editor.put(url, json=wrong).json()
    problem = (
        "Check the cast: shot 1.2: the script has Nate here, but the shot shows Mia (Mom)"
        " instead of Kid"
    )
    assert problem in saved["problems"]
    assert not [p for p in saved["problems"] if "shot 1.1" in p]  # both named there, both shown

    row = db.query(BreakdownVersion).filter_by(id=saved["id"]).one()
    frame = StoryboardFrame(
        project_id=pid, breakdown_id=row.id, clip_id="c1", shot_id="1.2", prompt="p"
    )
    db.add(frame)
    db.commit()
    stopped = editor.post(f"/projects/{pid}/storyboard/frames/{frame.id}/render")
    assert (
        stopped.status_code == 409
        and "Put the right cast in each shot first" in stopped.json()["detail"]
    )
    assert editor.post(f"{url}/keep", json={"problem": problem}).json()["kept"] == [problem]
    kept = editor.post(f"/projects/{pid}/storyboard/frames/{frame.id}/render")
    assert "right cast" not in kept.text  # kept anyway: no longer stops the still
    editor.delete(f"{url}/keep", params={"problem": problem})

    jobs = db.query(Job).count()
    fixed = editor.post(f"{url}/fix-cast")
    assert fixed.status_code == 200 and db.query(Job).count() == jobs  # free: no model call
    body = fixed.json()
    assert body["source"] == "edit" and body["id"] != saved["id"]  # a new version
    assert body["breakdown"]["scenes"][0]["shots"][1]["character_ids"] == [f"char:{kid}"]
    assert not [p for p in body["problems"] if p.startswith("Check the cast")]
    assert editor.post(f"{url}/fix-cast").status_code == 409  # nothing left to fix


def _still(db, editor, pid, kid):
    """A frame on Nate's shot with its still already drawn."""
    from app.models.breakdowns import BreakdownVersion as BV

    newest = db.query(BV).filter_by(project_id=pid).order_by(BV.id.desc()).first()
    frame = StoryboardFrame(project_id=pid, breakdown_id=newest.id, clip_id="c1", shot_id="1.2",
                            prompt="Kid at the table, eyes down.", reference_ids=[f"char:{kid}"],
                            file_id=upload(editor), approved=True)  # fmt: skip
    db.add(frame)
    db.commit()
    return frame


def _recast(owner, editor, db, pid, name):
    other = editor.post(
        "/library/character", json={"name": name, "image_file_ids": [upload(editor)]}
    )
    other = other.json()["id"]
    with_sheet(db, other)
    slot = next(r for r in editor.get(f"/projects/{pid}/assets").json() if r["role"] == "Nate")
    editor.put(f"/projects/{pid}/assets/slots/{slot['slot_id']}", json={"library_item_id": other})
    return other


def test_a_recast_rewrites_the_frames_for_free_and_redraws_the_stills_within_budget(
    owner, editor, db
):
    pid, _, kid = _video(owner, editor, db)
    with_sheet(db, kid)
    frame = _still(db, editor, pid, kid)
    jobs = db.query(Job).count()
    leo = _recast(owner, editor, db, pid, "Leo")
    db.expire_all()
    frame = db.get(StoryboardFrame, frame.id)
    assert frame.reference_ids == [f"char:{leo}"] and frame.prompt == "Leo at the table, eyes down."
    stills = editor.get(f"/projects/{pid}/storyboard").json()
    assert stills[0]["stale"] is False  # the frame follows the new breakdown version
    assert (stills[0]["redrawn"], stills[0]["approved"]) == (True, False)  # needs Approve again
    redraws = db.query(Job).filter(Job.kind == "image").all()
    assert db.query(Job).count() == jobs + 1 and redraws[-1].input["frame_id"] == frame.id
    note = editor.get(f"/projects/{pid}").json()["cast_redraw"]["redrawn_for_cast"]
    assert note["count"] == 1 and note["credits"] > 0
    assert "usd" not in str(note)  # credits, never dollars


def test_a_recast_past_the_budget_redraws_nothing_and_says_why(owner, editor, db):
    pid, _, kid = _video(owner, editor, db)
    with_sheet(db, kid)
    frame = _still(db, editor, pid, kid)
    project = db.get(Project, pid)
    db.add(Job(workspace_id=project.workspace_id, kind="image", provider="fake", input={},
               project_id=pid, credits=project.budget_credits, status="succeeded"))  # fmt: skip
    db.commit()  # the video's budget is all spent
    jobs = db.query(Job).count()
    _recast(owner, editor, db, pid, "Leo")
    assert db.query(Job).count() == jobs  # nothing charged
    refused = editor.get(f"/projects/{pid}").json()["cast_redraw"]["redraw_refused"]
    assert refused["count"] == 1 and "would go over this video's budget" in refused["reason"]
    assert "1 still shows the old cast: redrawing it (" in refused["reason"]
    assert "(0 credits)" not in refused["reason"]  # a small price rounds up, never to nothing
    still = next(f for f in editor.get(f"/projects/{pid}/storyboard").json() if f["id"] == frame.id)
    assert still["still_stale"] is True  # "Out of date"


def test_a_new_still_keeps_the_old_one_as_an_earlier_version(owner, editor, db):
    from app.storyboard import save_still

    pid, _, kid = _video(owner, editor, db)
    frame = _still(db, editor, pid, kid)
    old = frame.file_id
    job = Job(workspace_id=1, kind="image", provider="fake", input={"frame_id": frame.id},
              output={"file_ids": [upload(editor)]}, status="succeeded")  # fmt: skip
    save_still(db, job)
    assert frame.earlier == [{"file_id": old, "prompt": "Kid at the table, eyes down."}]
    assert frame.still_stale is False


def test_a_plan_with_the_wrong_person_is_flagged_and_fixed_for_free(owner, db):
    made = _make(owner, text=SCRIPT)
    base = f"/scripts/{made['id']}"
    mia = owner.post("/library/character", json={"name": "Mia", "image_file_ids": [upload(owner)]})
    mia = mia.json()["id"]
    with_sheet(db, mia)
    mom = owner.post(f"{base}/cast", json={"role": "Mom"}).json()[0]["id"]
    nate = owner.post(f"{base}/cast", json={"role": "Nate"}).json()[1]["id"]
    owner.post(f"{base}/cast/{mom}/lock", json={"library_item_id": mia})
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][0]["character_ids"] = [f"char:{mia}", f"slot:{nate}"]
    bd["scenes"][0]["shots"][1]["character_ids"] = [f"char:{mia}"]  # Nate's line, Mom's look
    url = f"{base}/drafts/0/breakdown"
    problems = owner.put(url, json=bd).json()["problems"]
    assert (
        "Check the cast: shot 1.2: the script has Nate here, but the shot shows Mia (Mom)"
        in problems
    )
    fixed = owner.post(f"{url}/fix-cast").json()
    assert fixed["breakdown"]["scenes"][0]["shots"][1]["character_ids"] == [f"slot:{nate}"]
    assert fixed["changed_shots"] == [
        {"shot_id": "1.2", "before": [f"char:{mia}"], "after": [f"slot:{nate}"]}
    ]
    assert not [p for p in fixed["problems"] if p.startswith("Check the cast")]
    assert owner.post(f"{url}/fix-cast").status_code == 409


def test_a_shot_names_the_role_never_the_look(owner, editor, db):
    """Live test: locking Omar to the look "Carl" turned him into Carl in the breakdown."""
    pid, mia, _ = _video(owner, editor, db)
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][0]["speaker"] = "Mia"  # the look's name, not the role's
    saved = editor.put(f"/projects/{pid}/breakdown", json=bd).json()
    assert saved["breakdown"]["scenes"][0]["shots"][0]["speaker"] == "Mom"


def test_a_name_said_in_dialogue_doesnt_put_them_in_the_shot():
    """The fake run's altar reel: NATE: "Where's the bride?" doesn't need the bride on screen,
    and "Nate, the teen groom" is labelled NATE."""
    from app.cast_roles import named, on_screen

    text = on_screen(["NATE: Where's the bride?", "Nate looks around the empty altar."])
    assert named("Nate, the teen groom", text) and not named("The bride", text)
    assert named("The bride", on_screen(["EX-BRIDE: Huh?!"]))


def test_a_refused_redraw_never_breaks_the_cast(owner, editor, db, monkeypatch):
    from fastapi import HTTPException

    from app.routes import jobs

    pid, _, kid = _video(owner, editor, db)
    with_sheet(db, kid)
    _still(db, editor, pid, kid)

    def refuse(*a, **k):
        raise HTTPException(409, "That's more than one video can cost.")

    monkeypatch.setattr(jobs, "enqueue", refuse)
    leo = _recast(owner, editor, db, pid, "Leo")  # the cast still happens
    slot = next(r for r in editor.get(f"/projects/{pid}/assets").json() if r["role"] == "Nate")
    assert slot["library_item_id"] == leo
    refused = editor.get(f"/projects/{pid}").json()["cast_redraw"]["redraw_refused"]
    assert refused["reason"] == "That's more than one video can cost."


def test_every_check_the_cast_line_comes_with_its_one_click_fix(owner, editor, db):
    """QA-Live (rule 22): a blocking cast line lists its fix, and Fix applies it, free."""
    pid, mia, kid = _video(owner, editor, db)
    url = f"/projects/{pid}/breakdown"
    wrong = copy.deepcopy(BREAKDOWN)
    wrong["scenes"][0]["shots"][0]["character_ids"] = [f"char:{mia}", f"char:{kid}"]
    wrong["scenes"][0]["shots"][1]["character_ids"] = [f"char:{mia}"]
    saved = editor.put(url, json=wrong).json()
    (line,) = [p for p in saved["problems"] if p.startswith("Check the cast")]
    assert {"problem": line, "kind": "fix_cast", "label": "Put the right cast in each shot"} in (
        saved["fixes"]
    )
    jobs = db.query(Job).count()
    done = editor.post(f"{url}/fix", json={"problems": [line]}).json()
    assert done["fixed"] == ["Put the right cast in each shot."]
    assert done["breakdown"]["scenes"][0]["shots"][1]["character_ids"] == [f"char:{kid}"]
    assert db.query(Job).count() == jobs


def test_a_reaction_shot_to_someone_elses_line_is_never_a_cast_problem(owner, editor, db):
    """QA-Live, video 16: the boss's line over "Lexi takes the hit" isn't a swap, and the free
    fix never puts the speaker into the reaction shot."""
    pid, mia, kid = _video(owner, editor, db)
    url = f"/projects/{pid}/breakdown"
    react = copy.deepcopy(BREAKDOWN)
    react["scenes"][0]["shots"][0]["character_ids"] = [f"char:{mia}", f"char:{kid}"]
    react["scenes"][0]["shots"][1].update(character_ids=[f"char:{mia}"],
                                          action="Mom takes the hit.")  # Nate's line  # fmt: skip
    saved = editor.put(url, json=react).json()
    assert not [p for p in saved["problems"] if p.startswith("Check the cast")]
    assert editor.post(f"{url}/fix-cast").status_code == 409  # nothing to change
    editor.get(f"/projects/{pid}/assets")  # nor does filling the roles in their shots
    shots = editor.get(url).json()["breakdown"]["scenes"][0]["shots"]
    assert shots[1]["character_ids"] == [f"char:{mia}"]


def test_a_new_version_saved_for_the_editor_keeps_what_they_kept_anyway():
    """QA-Live, video 16: a look made at Assets saved a new plan that dropped the Keep anyway
    choices. A kept line stays kept, and so does a cast line on the same shot that now names
    the new look; a new shot's line doesn't."""
    from app.breakdown import carry_kept

    kept = ["Check the cast: shot 1.11: the script has Boss here, but the shot shows Lexi (Lexi)",
            "Advice: shot 1.3: a montage shot without the main character"]  # fmt: skip
    problems = [
        "Check the cast: shot 1.11: the script has Boss here, but the shot shows Lexi (Lexi)"
        " instead of Boss look",
        "Advice: shot 1.3: a montage shot without the main character",
        "Check the cast: shot 1.12: the script has Boss here, but the shot shows Lexi (Lexi)",
    ]
    assert carry_kept(kept, problems) == problems[:2]


def test_an_approved_sheet_beats_the_role_text_in_stills_and_clips(owner, editor, db):
    """Reed, Iron Paws "Pitbull 1 POV": Biscuit's approved sheet is a French bulldog, but the
    role says "Biscuit, the golden dog" and the look's notes a golden retriever; stills and
    clips drew golden. Beside a sheet, no role description and no notes reach the prompts."""
    from app import prompts
    from app.models.library import LibraryItem
    from app.models.script_library import ScriptCastSlot
    from app.storyboard import SHEET_SETS, assets

    pid, mia, kid = _video(owner, editor, db)
    db.get(LibraryItem, mia).notes = "Golden retriever, thick golden coat, friendly face"
    slot = db.query(ScriptCastSlot).filter_by(library_item_id=mia).one()
    slot.role = "Biscuit, the golden dog"
    db.commit()
    line = assets(db, db.get(Project, pid))[f"char:{mia}"][0]
    assert line == f"char:{mia} | character | Mia | plays Biscuit | {SHEET_SETS}"
    assert "golden" not in line.lower()
    assert assets(db, db.get(Project, pid))[f"char:{kid}"][0].endswith("plays Nate")  # no sheet
    assert "is a French bulldog" in prompts.system("storyboard")
    assert 'never "golden coat"' in prompts.system("clip_prompts")
    redo = prompts.sheet_prompt(  # a redraw keeps the sheet's dog, whatever the role says
        "character",
        "Golden retriever, thick golden coat",
        change="Bigger ears.",
        role="Biscuit, the golden dog",
    )
    assert "even where the words above describe them differently" in redo


def test_an_insert_shot_is_never_a_cast_problem(owner, db):
    """Reed's song pilot: a close-up of a thing (the vacuum's canister), with no speaker and no
    one named in its action, raised "Check the cast" and needed "Keep anyway"."""
    made = _make(owner, text=SCRIPT)
    base = f"/scripts/{made['id']}"
    mia = owner.post("/library/character", json={"name": "Mia", "image_file_ids": [upload(owner)]})
    mia = mia.json()["id"]
    with_sheet(db, mia)
    mom = owner.post(f"{base}/cast", json={"role": "Mom"}).json()[0]["id"]
    owner.post(f"{base}/cast", json={"role": "Nate"})
    owner.post(f"{base}/cast/{mom}/lock", json={"library_item_id": mia})
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][1].update(
        character_ids=[f"char:{mia}"], speaker=None, line=None,
        action="Extreme close-up: the vacuum's canister fills with a fur mountain.",
    )  # fmt: skip
    problems = owner.put(f"{base}/drafts/0/breakdown", json=bd).json()["problems"]
    assert not [p for p in problems if p.startswith("Check the cast")]
