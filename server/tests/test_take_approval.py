"""A clean take approves itself (rule 21, take check slice 3), on the free stand-ins."""

import pytest

from app.models.checks import ItemCheck
from app.models.clips import ProjectClip
from app.providers.fake_local import hear_take
from app.providers.local import LocalProvider
from app.take_approval import after_check
from app.worker import run_once
from tests.test_clip_takes import FakeSeedance, _mp4, _work, clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture


@pytest.fixture(autouse=True)
def checks_on(monkeypatch):
    monkeypatch.setattr("app.item_checks.on", lambda: True)  # as on the test site's stand-ins


def _take(app, db, editor, setup, clip, picture="done", heard=""):  # noqa: F811
    """A new take, its picture check ended as `picture` (no findings), then its words heard
    (`heard`: a stand-in marker, e.g. fake:drop-line)."""
    clips = f"/projects/{setup['project']}/clips"
    editor.post(f"{clips}/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    take = editor.get(clips).json()[0]["takes"][-1]
    seen = db.query(ItemCheck).filter_by(target="take", target_id=take["id"]).one()
    seen.status, seen.findings = picture, []
    db.commit()

    def hear(path, job):
        return hear_take(path, {**job, "prompt": heard})

    run_once(db, {"local": LocalProvider(app.state.storage, hear_take=hear)},
             app.state.storage, only={"local"})  # fmt: skip
    return clips, editor.get(clips).json()[0]


def test_a_clean_picked_take_approves_itself_and_says_so(app, db, editor, setup, clip):  # noqa: F811
    clips, shown = _take(app, db, editor, setup, clip)
    assert shown["approved"] is True
    (take,) = shown["takes"]
    assert (take["verdict"], take["approved_by"]) == ("clean", "check")


def test_a_flagged_or_unchecked_take_waits_for_a_person(app, db, editor, setup, clip):  # noqa: F811
    _, shown = _take(app, db, editor, setup, clip, heard="fake:drop-line")
    assert shown["approved"] is False and shown["takes"][0]["verdict"] == "flagged"


def test_a_take_whose_picture_check_was_skipped_isnt_approved(app, db, editor, setup, clip):  # noqa: F811
    _, shown = _take(app, db, editor, setup, clip, picture="skipped")
    assert shown["approved"] is False and shown["takes"][0]["verdict"] == "unchecked"


def test_once_a_person_un_approves_the_check_stays_out(app, db, editor, setup, clip):  # noqa: F811
    clips, shown = _take(app, db, editor, setup, clip)
    back = editor.delete(f"{clips}/{shown['id']}/approve").json()
    assert back["approved"] is False and back["takes"][0]["approved_by"] is None
    after_check(db, shown["takes"][0]["id"])  # a check ending again changes nothing
    db.commit()
    assert db.get(ProjectClip, shown["id"]).approved is False
    again = editor.post(f"{clips}/{shown['id']}/approve").json()  # a person's ✓ is theirs
    assert again["approved"] is True and again["takes"][0]["approved_by"] is None


def test_the_mark_follows_the_approval_and_a_re_pick_approves_again(app, db, editor, setup, clip):  # noqa: F811
    clips, first = _take(app, db, editor, setup, clip)  # clean: approved by the check
    one = first["takes"][0]["id"]
    _, shown = _take(app, db, editor, setup, clip, heard="fake:drop-line")  # flagged, picked
    assert shown["approved"] is False
    assert [t["approved_by"] for t in shown["takes"]] == [None, None]  # not on the old take
    editor.delete(f"{clips}/{shown['id']}/approve")  # a person's no on take 2
    back = editor.post(f"{clips}/{shown['id']}/takes/{one}/pick").json()
    assert back["approved"] is True  # re-picking a clean take approves it (QA-3)
    assert [t["approved_by"] for t in back["takes"]] == ["check", None]
    editor.delete(f"{clips}/{shown['id']}/approve")  # a person's no on take 1
    assert editor.post(f"{clips}/approve-all").json()["approved"] == [shown["id"]]
    (after,) = editor.get(clips).json()
    assert after["approved"] is True  # the person's approval, not the check's
    assert [t["approved_by"] for t in after["takes"]] == [None, None]


def test_a_take_a_person_said_no_to_stays_theirs_when_re_picked(app, db, editor, setup, clip):  # noqa: F811
    clips, first = _take(app, db, editor, setup, clip)
    editor.delete(f"{clips}/{first['id']}/approve")
    _take(app, db, editor, setup, clip)  # take 2: clean, approves itself
    back = editor.post(f"{clips}/{first['id']}/takes/{first['takes'][0]['id']}/pick").json()
    assert back["approved"] is False


def test_looks_fine_on_the_last_note_approves_a_clean_take(app, db, editor, setup, clip):  # noqa: F811
    clips, shown = _take(app, db, editor, setup, clip, heard="fake:drop-line")
    words = shown["takes"][0]["words"]
    assert shown["approved"] is False and words["findings"]
    url = f"/projects/{setup['project']}/checks/{words['id']}/findings"
    for finding in words["findings"]:
        editor.post(f"{url}/{finding['index']}/dismiss")
    (after,) = editor.get(clips).json()
    assert after["approved"] is True and after["takes"][0]["approved_by"] == "check"
