"""Reed, 2026-10-28 (Iron Paws' Biscuit): the approved look is a French bulldog but the role
still said "the golden dog… golden retriever". The look check reads the role's words against
the sheet too; once the look is approved, Assets offers them put right in one click, and a
look approved before that can be Checked at its price. Claude is mocked: no paid calls."""

from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.script_library import ScriptCastSlot
from app.routes.sheets import save_sheet
from tests.conftest import upload
from tests.test_enhance import FakeClaude, _run
from tests.test_video_looks import _row, _video

GOLDEN = "golden retriever, thick golden coat, loyal and goofy"
BULLDOG = {"fits": True, "seen": "a French bulldog", "problem": "",
           "role_name": "Biscuit, the French bulldog",
           "role_description": "French bulldog, short fawn coat, loyal and goofy"}  # fmt: skip


def _biscuit(owner, editor, db):
    """Nate's role becomes Biscuit, with a look made on Assets and its sheet landed."""
    _, pid, slot = _video(owner, editor, db)
    row = db.get(ScriptCastSlot, slot)
    row.role, row.description = "Biscuit, the golden dog", GOLDEN
    db.commit()
    editor.post(f"/projects/{pid}/assets/slots/{slot}/make-look")
    look = _row(editor, pid, slot)["own_look_id"]
    sheet = next(j for j in db.query(Job).all() if j.input.get("library_item_id") == look)
    sheet.output, sheet.status = {"file_ids": [upload(editor)]}, "succeeded"
    save_sheet(db, sheet)
    db.commit()
    return pid, slot, look


def _checks(db, look):
    jobs = db.query(Job).all()
    return [
        j
        for j in jobs
        if (j.input.get("library_item_id"), j.input.get("step")) == (look, "look_fit")
    ]  # noqa: E501


def test_an_approved_look_puts_its_roles_words_right(app, owner, editor, db):
    pid, slot, look = _biscuit(owner, editor, db)
    (check,) = _checks(db, look)
    assert '<role_text name="Biscuit, the golden dog">golden retriever' in check.input["prompt"]
    _run(app, db, FakeClaude(BULLDOG))
    db.expire_all()
    assert _row(editor, pid, slot)["text_fit"] is None  # not until the look is approved
    editor.post(f"/library/character/{look}/sheet/approve")
    row = _row(editor, pid, slot)
    assert row["text_fit"] == {"seen": "The approved look shows a French bulldog.",
                               "name": "Biscuit, the French bulldog",
                               "description": BULLDOG["role_description"]}  # fmt: skip
    assert row["text_check_credits"] is None

    url = f"/projects/{pid}/assets/slots/{slot}"
    put_right = {"role": row["text_fit"]["name"], "description": row["text_fit"]["description"]}
    out = next(r for r in editor.patch(url, json=put_right).json() if r["slot_id"] == slot)
    assert (out["role"], out["description"]) == (put_right["role"], put_right["description"])
    assert out["text_fit"] is None and out["text_check_credits"] is None  # nothing to Check
    assert db.get(ScriptCastSlot, slot).guessed == []
    assert db.get(LibraryItem, look).notes == put_right["description"]  # redraws follow too

    undo = {"role": "Biscuit, the golden dog", "description": GOLDEN}  # the toast's Undo
    out = next(r for r in editor.patch(url, json=undo).json() if r["slot_id"] == slot)
    assert out["text_fit"]["name"] == "Biscuit, the French bulldog"  # offered again

    renamed = editor.patch(url, json={"role": "Rex, the French bulldog"})
    assert renamed.status_code == 422 and "Keep the name Biscuit" in renamed.json()["detail"]
    mine = editor.patch(url, json={"description": "a small dog"}).json()  # their own words
    out = next(r for r in mine if r["slot_id"] == slot)
    assert out["text_fit"] is None and out["text_check_credits"] >= 1  # unread: Check


def test_a_look_approved_before_the_words_were_read_can_be_checked(app, owner, editor, db):
    pid, slot, look = _biscuit(owner, editor, db)
    _run(app, db, FakeClaude({"fits": True, "seen": "a French bulldog", "problem": ""}))
    db.expire_all()
    db.get(LibraryItem, look).text_fit = None  # approved before this check existed
    db.commit()
    editor.post(f"/library/character/{look}/sheet/approve")
    row = _row(editor, pid, slot)
    assert row["text_fit"] is None and row["text_check_credits"] >= 1

    url = f"/projects/{pid}/assets/slots/{slot}/check-text"
    out = next(r for r in editor.post(url).json() if r["slot_id"] == slot)
    assert out["sheet_status"] == "drawing"  # a few seconds, as after any sheet
    check = _checks(db, look)[-1]
    assert check.status == "queued" and check.credits > 0  # paid, within the price shown
    assert editor.post(url).status_code == 409  # one at a time
    _run(app, db, FakeClaude(BULLDOG))
    db.expire_all()
    row = _row(editor, pid, slot)
    assert row["sheet_status"] == "approved" and row["text_fit"]["name"].endswith("bulldog")
    assert editor.post(url).status_code == 409  # read already


def test_words_that_fit_say_nothing_and_a_new_name_keeps_its_label(app, owner, editor, db):
    pid, slot, look = _biscuit(owner, editor, db)
    sneaky = {**BULLDOG, "role_name": "Rex, the French bulldog", "role_description": GOLDEN}
    _run(app, db, FakeClaude(sneaky))  # a renamed role, an unchanged description: nothing
    db.expire_all()
    editor.post(f"/library/character/{look}/sheet/approve")
    row = _row(editor, pid, slot)
    assert row["text_fit"] is None and row["text_check_credits"] is None
