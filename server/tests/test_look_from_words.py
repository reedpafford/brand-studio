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
