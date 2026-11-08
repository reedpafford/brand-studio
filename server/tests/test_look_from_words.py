"""A look is drawn from what the role is, never from a name alone (video 268: the plan said
Bruno was "a stocky tan clay dog", his look was made from "Bruno" and came out an old man, the
check said it fit, and Change… kept the man under a dog). No paid calls: the stand-ins only."""

import copy

from app import director_tools
from app.models.accounts import User
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.projects import Project
from app.routes.sheets import fresh, save_sheet
from tests.conftest import upload
from tests.test_breakdown import BREAKDOWN
from tests.test_script_library import _make

DOG = "Bruno, a stocky tan clay dog, sniffs his bowl. Lena laughs."
SCRIPT = "SCENE 1 — INT. KITCHEN — DAY\nBruno sniffs his bowl."  # no one speaks


def _bruno(owner, editor, action: str, role="Bruno"):
    """A video whose role Bruno has no description, in a shot that does `action`."""
    base = f"/scripts/{_make(owner, text=SCRIPT)['id']}"
    slot = owner.post(f"{base}/cast", json={"role": role}).json()[-1]["id"]
    bd = copy.deepcopy(BREAKDOWN)
    shot = bd["scenes"][0]["shots"][1]
    shot["character_ids"], shot["action"] = [f"slot:{slot}"], action
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    return editor.post(f"{base}/drafts/0/produce").json()["project_id"], slot


def _make_looks(db, pid, look=None) -> str:
    user = db.query(User).filter_by(email="ed@example.com").one()
    said = director_tools.run(
        db, user, db.get(Project, pid), {"tool": "make_looks", "look": look}, None
    )
    db.commit()
    return said


def _look(db, pid, slot) -> LibraryItem | None:
    db.expire_all()
    return db.get(LibraryItem, db.get(Project, pid).slot_looks.get(str(slot)) or 0)


def test_a_role_is_drawn_from_its_shots_words_or_the_directors_never_its_name(owner, editor, db):
    pid, slot = _bruno(owner, editor, DOG)
    assert _make_looks(db, pid) == "Making the missing looks."
    sheet = next(j for j in db.query(Job).all() if j.input.get("step") == "sheet")
    assert _look(db, pid, slot).notes == "Bruno, a stocky tan clay dog, sniffs his bowl."
    assert "stocky tan clay dog" in sheet.input["input"]["prompt"]

    pid, slot = _bruno(owner, editor, "They argue.")  # nothing anywhere says what he is
    jobs = db.query(Job).count()
    said = _make_looks(db, pid)
    assert said.startswith("Refused: Nothing says what Bruno looks like, so a look would only")
    assert db.query(Job).count() == jobs and _look(db, pid, slot) is None
    for url in (f"slots/{slot}/make-look", "make-missing"):  # a person's press: refused too
        refused = editor.post(f"/projects/{pid}/assets/{url}")
        assert refused.status_code == 409 and refused.json()["detail"].startswith(
            "Nothing says what Bruno looks like"
        )
    assert db.query(Job).count() == jobs
    told = {"name": "Bruno", "description": "a stocky tan clay dog"}
    assert _make_looks(db, pid, told) == "Making the missing looks."
    assert _look(db, pid, slot).notes == "a stocky tan clay dog"

    pid, slot = _bruno(owner, editor, "They argue.", role="Bruno, a stocky tan clay dog")
    assert _make_looks(db, pid) == "Making the missing looks."  # the script's words for him
    assert _look(db, pid, slot).notes == "Bruno, a stocky tan clay dog"


def test_a_sheet_with_nothing_to_check_against_never_fits(owner, editor, db):
    item = LibraryItem(workspace_id=1, kind="character", name="Bruno", notes="Bruno",
                       owner_project_id=None)  # fmt: skip
    db.add(item)
    db.commit()
    landed = {"file_ids": [upload(editor)]}
    job = Job(workspace_id=1, created_by_id=1, kind="image", provider="fake", status="succeeded",
              input={"library_item_id": item.id}, output=landed)  # fmt: skip
    db.add(job)
    db.commit()
    save_sheet(db, job)
    db.commit()
    assert not [j for j in db.query(Job).all() if j.input.get("step") == "look_fit"]  # unpaid
    assert item.look_fit["seen"].startswith("a guess from the name alone: nothing says what Bruno")


def test_a_change_to_what_a_look_is_draws_it_fresh_and_keeps_the_words(owner, editor, db):
    """268 after the fix: Bruno's look (notes "Bruno", the check's finding on it) and the
    owner's Change… with the right words: drawn fresh, never on the old sheet."""
    pid, slot = _bruno(owner, editor, "They argue.")
    _make_looks(db, pid, {"name": "Bruno", "description": "Bruno"})  # as 268 has it: a name
    look = _look(db, pid, slot)
    look.sheet_file_id = old = upload(editor)
    look.look_fit = {"seen": "elderly man in a brown coat", "problem": "draw a dog"}
    for job in db.query(Job).all():
        job.status = "succeeded"
    db.commit()
    note = "Bruno is a dog, not a person: a stocky tan clay dog, the same plasticine look as Lena."
    made = editor.post(f"/library/character/{look.id}/sheet", json={"change": note})
    assert made.status_code == 201, made.text
    sheet = db.get(Job, made.json()["id"])
    assert old not in sheet.input["files"].get("image_input", [])  # not drawn on the old man
    prompt = sheet.input["input"]["prompt"]
    assert f"The character: Bruno. {note}" in prompt and "Keep everything about it" not in prompt
    assert _look(db, pid, slot).notes == f"Bruno. {note}"  # his words from now on

    def item(**o):
        return LibraryItem(name="Nate", notes="Nate, a shy teen", owner_project_id=1, **o)

    assert fresh(item(), "Make him a cat instead.", False)  # a kind of being
    assert fresh(item(look_fit={"seen": "girl", "problem": ""}), "A red cap.", False)
    assert fresh(LibraryItem(name="Ms Ade", notes="A teacher"), "x", True)  # the check's redo
    assert not fresh(item(), "A red cap and a dog-shaped badge.", False)  # an ordinary tweak
    assert not fresh(LibraryItem(name="Nate", notes="Nate, a teen"), "Make him a cat.", False)


def test_approve_asks_again_while_the_check_says_a_look_is_wrong(owner, editor, db):
    pid, slot = _bruno(owner, editor, DOG)
    _make_looks(db, pid)
    look = _look(db, pid, slot)
    look.sheet_file_id, look.sheet_approved = upload(editor), True
    look.look_fit = {"seen": "elderly man in a brown coat", "problem": "draw a dog"}
    for job in db.query(Job).all():
        job.status = "succeeded"
    db.commit()
    shown = editor.get(f"/projects/{pid}/cast").json()
    bruno = next(i for i in shown["items"] if i["name"] == "Bruno")
    assert bruno["look_fit"] == {"seen": "elderly man in a brown coat", "problem": "draw a dog"}
    seen = {i["ref"]: i["sig"] for i in shown["items"]}
    refused = editor.post(f"/projects/{pid}/cast/approve", json={"seen": seen})
    assert refused.json()["detail"] == (
        "The look check says Bruno looks wrong. Change it, or approve anyway."
    )
    done = editor.post(f"/projects/{pid}/cast/approve", json={"seen": seen, "anyway": True})
    assert done.status_code == 200 and done.json()["state"] == "approved", done.text


def test_the_check_reads_the_sheets_look_into_the_words_the_clips_keep(app, owner, editor, db):
    """CRITIQUE-268 cause 2: Bruno was three different dogs. His Keep line could name no breed,
    coat or marking: nothing held them. The check now reads them off the sheet, and the cast
    line gives them; a new sheet drops the old words until its check reads it."""
    from app import prompts, storyboard
    from tests.test_enhance import FakeClaude, _run

    assert "on all fours" in prompts.sheet_prompt("character", "a stocky tan clay dog")
    pid, slot = _bruno(owner, editor, DOG)
    _make_looks(db, pid)
    look = _look(db, pid, slot)
    sheet = next(j for j in db.query(Job).all() if j.input.get("step") == "sheet")
    sheet.output, sheet.status = {"file_ids": [upload(editor)]}, "succeeded"
    save_sheet(db, sheet)
    db.commit()
    anchors = "stocky tan pitbull, white chest blaze, one folded ear"
    _run(app, db, FakeClaude({"fits": True, "seen": "tan dog", "problem": "", "anchors": anchors}))
    db.expire_all()
    assert _look(db, pid, slot).short_description == anchors
    line = storyboard.assets(db, db.get(Project, pid))[f"char:{look.id}"][0]
    assert f"in these words only: {anchors} (in the Keep line too)" in line
    redo = Job(workspace_id=1, created_by_id=sheet.created_by_id, kind="image", provider="fake",
               status="succeeded", input={"library_item_id": look.id, "changed": True},
               output={"file_ids": [upload(editor)]})  # fmt: skip
    db.add(redo)
    db.commit()
    save_sheet(db, redo)
    db.commit()
    assert _look(db, pid, slot).short_description == ""  # until its own check reads it


def test_a_sheets_words_go_with_that_sheet_when_it_comes_back(db, owner):
    """QA on #1451: Use this sheet, or restoring a version, brings back that sheet's own words
    (never the newer sheet's "tan" under a brown dog), and restoring never 422s on them."""
    from app.routes.library import _save_version
    from app.routes.sheets import said_short
    from tests.helpers import with_sheet

    made = {"name": "Rex", "notes": "a dog", "image_file_ids": [upload(owner)]}
    rex = owner.post("/library/character", json=made).json()["id"]
    with_sheet(db, rex)
    item, me = db.get(LibraryItem, rex), db.query(User).filter_by(role="owner").one()
    first, item.short_description = item.sheet_file_id, "brown terrier, heavy brow"
    db.commit()
    _save_version(db, me, item)  # a new sheet, read by its check
    item.sheet_file_id, item.short_description = upload(owner), "tan terrier, white chest blaze"
    db.commit()
    url = f"/library/character/{rex}"
    back = owner.post(f"{url}/sheet/preferred", json={"file_id": first})
    assert back.status_code == 200, back.text
    db.expire_all()
    assert db.get(LibraryItem, rex).short_description == "brown terrier, heavy brow"
    versions = owner.get(f"{url}/versions").json()
    newer = max(v["version"] for v in versions)  # the tan sheet, saved by the press
    restored = owner.post(f"{url}/versions/{newer}/restore")
    assert restored.status_code == 200, restored.text
    db.expire_all()
    assert db.get(LibraryItem, rex).short_description == "tan terrier, white chest blaze"
    assert said_short("a" * 60 + ", " + "b" * 60) == "a" * 60  # cut at a comma for the clips


def test_a_role_is_drawn_from_what_the_brief_says_of_them_never_anothers_sentence(
    owner, editor, db
):
    """Video 284: Maya's look came from a shot's action (average build, a hoodie) though the
    brief said "Maya (30s, heavy-set, satin dress)" and the treatment "Maya, 30s, heavy-set,
    champagne-coloured satin dress", and one sentence about Granny and Maya became both their
    words. A speaker's cue is never a look (QA on #1458)."""
    from app import cast_roles
    from app.models.script_library import ScriptCastSlot, ScriptDraft
    from app.routes.project_assets import role_words

    both = "Granny pats Maya's belly. Granny, in pearl earrings, beams at the guests."
    pid, slot = _bruno(owner, editor, both, role="Granny")
    project = db.get(Project, pid)
    draft = db.get(ScriptDraft, project.script_draft_id)
    db.add(ScriptCastSlot(script_id=draft.script_id, role="Maya", kind="Helper",
                          appears_in=[draft.slot], position=9))  # fmt: skip
    db.commit()
    slots = {s.role: s for s in cast_roles.all_slots(db, project)}

    def maya(*notes: str) -> str:
        project.director_chat = [{"text": n, "run": "r"} for n in notes]
        db.commit()
        return role_words(db, project, slots["Maya"])

    cues = "MAYA (quietly): I'm not pregnant.\nMAYA (ON PHONE): Hi.\nMAYA (whispering)\nOkay."
    assert maya(cues) == ""  # delivery notes, not a look: nothing here says how she looks
    assert maya("Maya is in her 30s, heavy-set, in a satin dress.") == (
        "Maya, in her 30s, heavy-set, in a satin dress"
    )
    assert maya(cues, "Brief: Maya (30s, heavy-set, satin dress) freezes.") == (
        "Maya, 30s, heavy-set, satin dress"
    )
    single = "Close single on Maya, 30s, heavy-set, champagne-coloured satin dress: a smile."
    story = {"hook": "Granny, 70s, plants both hands on Maya's belly.", "logline": "",
             "beats": [{"picture": single}], "ending": ""}  # fmt: skip
    db.add(Job(workspace_id=project.workspace_id, kind="write-claude", provider="fake",
               project_id=pid, status="succeeded", input={"step": "treatment"},
               output=story))  # fmt: skip
    db.commit()
    assert maya(cues) == "Maya, 30s, heavy-set, champagne-coloured satin dress"
    assert role_words(db, project, slots["Granny"]) == (
        "Granny, in pearl earrings, beams at the guests."
    )  # never the sentence with Maya in it


def test_a_named_person_in_two_clips_gets_a_role_and_a_look_a_one_off_doesnt(owner, editor, db):
    """Video 281: Danny, Marcus's brother-in-law, was in four B-roll clips but no role (the
    script names him once, "Danny, you were right"), so no look: his face and sweater drifted.
    Rosa, named in one clip only, is drawn as part of the scene."""
    script = ("MARCUS: Every year I laughed at him, and Rosa laughed too.\n"
              "MARCUS: Danny, you were right.")  # fmt: skip
    base = f"/scripts/{_make(owner, text=script)['id']}"
    bd = copy.deepcopy(BREAKDOWN)
    first, second = bd["scenes"][0]["shots"]
    first["action"] = "At the table, quiet Danny in a grey sweater hunches over his phone."
    second["action"] = "A roll bounces off Danny's shoulder while Rosa laughs."
    first["script_lines"], second["script_lines"] = [1], [2]
    bd["clips"] = [{"id": "c1", "shot_ids": ["1.1"], "seconds": 3, "seam": "Cut."},
                   {"id": "c2", "shot_ids": ["1.2"], "seconds": 2, "seam": "End."}]  # fmt: skip
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    missing = editor.get(f"/projects/{pid}/assets/missing-looks").json()
    assert "Danny" in missing["roles"] and "Rosa" not in missing["roles"]
    rows = {r["role"]: r for r in editor.get(f"/projects/{pid}/assets").json()}
    assert "Danny" in rows and "Rosa" not in rows
    assert _make_looks(db, pid) == "Making the missing looks."
    danny = _look(db, pid, rows["Danny"]["slot_id"])
    assert danny.notes.startswith("At the table, quiet Danny in a grey sweater")  # #1458's words
    shown = editor.get(f"/projects/{pid}/cast").json()
    assert "Danny" in [i["name"] for i in shown["items"]]  # in the cast and places OK
