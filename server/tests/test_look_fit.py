"""Looks must fit the role (Reed, 2026-10-26; Director's #480): a sheet drawn from a
description is checked once by a cheap Claude look; one that doesn't read as its role is
redone once by itself, then shown with advice. Claude is mocked: no paid calls."""

import math

import pytest

from app.models.accounts import User
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.routes.sheets import save_sheet
from tests.conftest import upload
from tests.test_enhance import FakeClaude, _run

TEACHER = "Mid-40s woman, a primary-school teacher; curly hair, green cardigan"
CHILD = {"fits": False, "seen": "girl of about 10", "problem": "draw an adult woman in her 40s"}


def _look(editor, db, **extra):
    made = editor.post("/library/character", json={"name": "Ms Ade", "notes": TEACHER, **extra})
    return db.get(LibraryItem, made.json()["id"])


def _landed(db, item, sheet_job):
    """The sheet's image job finished with a new picture."""
    sheet_job.output = {"file_ids": [item.image_file_ids[0] if item.image_file_ids else 1]}
    sheet_job.status = "succeeded"
    save_sheet(db, sheet_job)
    db.commit()


def _waiting(db, item, step):
    queued = db.query(Job).filter_by(status="queued").all()
    return [
        j
        for j in queued
        if (j.input.get("library_item_id"), j.input.get("step")) == (item.id, step)
    ]


def test_a_look_that_reads_wrong_is_redone_once_then_advised(app, db, editor):
    item = _look(editor, db, image_file_ids=[upload(editor)])
    url = f"/library/character/{item.id}"
    sheet = db.get(Job, editor.post(f"{url}/sheet", json={}).json()["id"])
    _landed(db, item, sheet)
    (check,) = _waiting(db, item, "look_fit")
    assert (check.input["effort"], check.input["redo"], check.input["fit_images_to"]) == (
        "low", True, 1024
    )  # fmt: skip
    assert check.input["files"] == {"reference_images": [item.sheet_file_id]}
    assert editor.get(url).json()["sheet_status"] == "drawing"  # never shown before the check

    fake = FakeClaude(CHILD)
    _run(app, db, fake)  # the check: a child for a teacher
    sent = fake.requests[0]["messages"][0]["content"]
    assert sent[0]["type"] == "image" and TEACHER in sent[1]["text"]
    db.expire_all()
    (redo,) = _waiting(db, item, "sheet")  # redone once, by itself, with the check's note
    assert (
        redo.input["changed"] is True and "adult woman in her 40s" in redo.input["input"]["prompt"]
    )
    assert editor.get(url).json()["look_fit"] is None

    _landed(db, item, redo)
    (again,) = _waiting(db, item, "look_fit")
    assert again.input["redo"] is False  # checked again, never redone again
    _run(app, db, FakeClaude(CHILD))
    db.expire_all()
    shown = editor.get(url).json()
    assert shown["look_fit"] == {"seen": "girl of about 10", "problem": CHILD["problem"]}
    assert shown["sheet_status"] == "needs_approval" and not _waiting(db, item, "sheet")


def test_a_look_that_fits_says_nothing_and_a_persons_change_is_never_redone(app, db, editor):
    item = _look(editor, db, image_file_ids=[upload(editor)])
    url = f"/library/character/{item.id}"
    _landed(db, item, db.get(Job, editor.post(f"{url}/sheet", json={}).json()["id"]))
    _run(app, db, FakeClaude({"fits": True, "seen": "woman in her 40s", "problem": ""}))
    db.expire_all()
    assert editor.get(url).json()["look_fit"] is None
    changed = db.get(Job, editor.post(f"{url}/sheet", json={"change": "Shorter hair"}).json()["id"])
    _landed(db, item, changed)
    (check,) = _waiting(db, item, "look_fit")
    assert check.input["redo"] is False  # the person asked for this change: advice only


def test_a_sheet_from_a_photo_is_never_checked(db, editor):
    photo = upload(editor)
    item = _look(editor, db, source_photo_file_id=photo, image_file_ids=[photo])
    _landed(db, item, db.get(Job, editor.post(f"/library/character/{item.id}/sheet",
                                              json={}).json()["id"]))  # fmt: skip
    assert not _waiting(db, item, "look_fit")


def test_a_look_shows_its_whole_price_and_is_never_refused_for_the_week(owner, db, editor):
    """The price shown covers the sheet, its check and the one redo. One allowance (Reed,
    30 Oct): a look is a brand's work, so the week never refuses it."""
    from app.sheets import look_price, sheet_price

    item = _look(editor, db, image_file_ids=[upload(editor)])
    url = f"/library/character/{item.id}"
    shown = editor.get(url).json()
    whole = look_price(db, item.workspace_id)
    assert (
        shown["sheet_credits"] == math.ceil(whole) > math.ceil(sheet_price(db, item.workspace_id))
    )
    limits = owner.get("/credits/limits").json()
    owner.put("/credits/limits", json={**limits, "weekly_quick_clip_credits": 0})
    assert editor.post(f"{url}/sheet", json={}).status_code in (200, 201)


def test_the_check_and_redo_spend_what_the_press_held(owner, app, db, editor):
    """Spent within the price shown: the sheet, its check, the redo and its check all run."""
    from app.sheets import look_price

    item = _look(editor, db, image_file_ids=[upload(editor)])
    url = f"/library/character/{item.id}"
    whole = look_price(db, item.workspace_id)
    sheet = db.get(Job, editor.post(f"{url}/sheet", json={}).json()["id"])
    _landed(db, item, sheet)
    _run(app, db, FakeClaude(CHILD))  # the check fails: the redo is held, so it goes ahead
    db.expire_all()
    (redo,) = _waiting(db, item, "sheet")
    _landed(db, item, redo)
    _run(app, db, FakeClaude(CHILD))
    db.expire_all()
    assert editor.get(url).json()["look_fit"]["seen"] == "girl of about 10"
    spent = [j for j in db.query(Job).all() if j.input.get("library_item_id") == item.id]
    assert [j.input["step"] for j in spent] == ["sheet", "look_fit", "sheet", "look_fit"]
    assert sum(j.credits for j in spent) <= whole  # never above the price shown


def test_a_look_that_fits_gives_back_what_the_redo_held(owner, app, db, editor):
    """Spec #488: "Usually 2. Anything not used comes back." On a video's budget, a look that
    fits first time costs its sheet and check; the rest is released."""
    from app.credits import credits_used
    from app.models.projects import Project
    from app.sheets import check_price, look_price, sheet_price
    from tests.test_video_looks import _row, _video

    fits = {"fits": True, "seen": "woman in her 40s", "problem": ""}
    item = _look(editor, db, image_file_ids=[upload(editor)])
    ws = item.workspace_id
    used = sheet_price(db, ws) + check_price(db, ws)
    shown = editor.get(f"/library/character/{item.id}").json()
    assert (shown["sheet_credits"], shown["sheet_usual_credits"]) == (
        math.ceil(look_price(db, ws)), math.ceil(used)
    )  # fmt: skip

    _, pid, nate = _video(owner, editor, db)
    project = db.get(Project, pid)
    row = _row(editor, pid, nate)
    assert (row["look_credits"], row["look_usual_credits"]) == (
        math.ceil(look_price(db, ws)), math.ceil(used)
    )  # fmt: skip
    editor.post(f"/projects/{pid}/assets/slots/{nate}/make-look")
    look = db.get(LibraryItem, _row(editor, pid, nate)["own_look_id"])
    (sheet,) = _waiting(db, look, "sheet")
    sheet.output, sheet.status = {"file_ids": [upload(editor)]}, "succeeded"
    save_sheet(db, sheet)
    db.commit()
    _run(app, db, FakeClaude(fits))
    db.expire_all()
    assert credits_used(db, project) == used  # the video's budget pays only what was made


def test_made_looks_say_what_they_really_cost(owner, app, db, editor):
    """Spec #488: after Make all, "Made 3 looks · 7 credits": the real spend of the looks Assets
    made by itself (sheet, check, any redo); a card's own Make a look isn't counted."""
    from app.sheets import check_price, sheet_price
    from tests.test_video_looks import _row, _video

    _, pid, nate = _video(owner, editor, db)
    url = f"/projects/{pid}/assets"
    assert editor.get(f"{url}/missing-looks").json()["made"] is None
    assert editor.post(f"{url}/make-missing").status_code == 200
    made = editor.get(f"{url}/missing-looks").json()["made"]
    assert (made["looks"], made["drawing"]) == (1, True)
    look = db.get(LibraryItem, _row(editor, pid, nate)["own_look_id"])
    (sheet,) = _waiting(db, look, "sheet")
    assert sheet.input["auto_made"] is True
    sheet.output, sheet.status = {"file_ids": [upload(editor)]}, "succeeded"
    save_sheet(db, sheet)
    db.commit()
    (check,) = _waiting(db, look, "look_fit")
    assert check.input["auto_made"] is True
    _run(app, db, FakeClaude({"fits": True, "seen": "teen boy", "problem": ""}))
    db.expire_all()
    ws = look.workspace_id
    made = editor.get(f"{url}/missing-looks").json()["made"]
    spent = math.ceil(sheet_price(db, ws) + check_price(db, ws))
    assert made == {"looks": 1, "drawing": False, "credits_used": spent}

    _, other, slot = _video(owner, editor, db)
    editor.post(f"/projects/{other}/assets/slots/{slot}/make-look")  # the card's own press
    assert editor.get(f"/projects/{other}/assets/missing-looks").json()["made"] is None


def test_one_credit_is_said_as_one_credit(owner, editor, db):
    """QA nit on #487: "this week's 1 credit", never "1 credits" (now on a Quick clip)."""
    from fastapi import HTTPException

    from app.routes.jobs import enqueue

    limits = owner.get("/credits/limits").json()
    owner.put("/credits/limits", json={**limits, "weekly_quick_clip_credits": 1})
    me = db.query(User).filter_by(email=editor.get("/auth/me").json()["email"]).one()
    with pytest.raises(HTTPException) as refused:
        enqueue(db, me, "video-480p", {}, units=2)
    assert "this week's 1 credit (" in refused.value.detail
