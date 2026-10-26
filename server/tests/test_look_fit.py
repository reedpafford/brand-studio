"""Looks must fit the role (Reed, 2026-10-26; Director's #480): a sheet drawn from a
description is checked once by a cheap Claude look; one that doesn't read as its role is
redone once by itself, then shown with advice. Claude is mocked: no paid calls."""

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


def test_past_the_week_the_check_is_skipped_never_held(owner, db, editor):
    item = _look(editor, db, image_file_ids=[upload(editor)])
    sheet = db.get(Job, editor.post(f"/library/character/{item.id}/sheet", json={}).json()["id"])
    limits = owner.get("/credits/limits").json()
    owner.put("/credits/limits", json={**limits, "weekly_quick_clip_credits": 0})
    _landed(db, item, sheet)
    assert not _waiting(db, item, "look_fit")
    assert not db.query(Job).filter_by(status="needs_owner_approval").count()
    db.expire_all()
    shown = editor.get(f"/library/character/{item.id}").json()
    assert shown["sheet_status"] == "needs_approval" and shown["sheet_file_id"]  # kept, unchecked


def test_a_redo_past_the_week_leaves_the_advice(owner, app, db, editor):
    item = _look(editor, db, image_file_ids=[upload(editor)])
    url = f"/library/character/{item.id}"
    _landed(db, item, db.get(Job, editor.post(f"{url}/sheet", json={}).json()["id"]))
    limits = owner.get("/credits/limits").json()
    owner.put("/credits/limits", json={**limits, "weekly_quick_clip_credits": 0.1})
    _run(app, db, FakeClaude(CHILD))  # the check was already queued; the redo doesn't fit
    db.expire_all()
    assert not _waiting(db, item, "sheet")
    assert editor.get(url).json()["look_fit"]["seen"] == "girl of about 10"
    (check,) = [j for j in db.query(Job).all() if j.input.get("step") == "look_fit"]
    assert check.status == "succeeded" and check.output["fits"] is False  # its answer kept
