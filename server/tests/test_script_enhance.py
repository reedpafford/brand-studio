"""Directions on a library script version: Enhance's marks, accepted and added as lines,
with Undo. A mocked Claude API (no real or paid calls)."""

from app.models.jobs import Job
from tests.test_enhance import SCRIPT, FakeClaude, _mark, _run
from tests.test_script_library import _make


def test_directions_on_a_version_suggest_accept_add_and_undo(app, owner, editor, db):
    made = _make(owner, text=SCRIPT)
    base = f"/scripts/{made['id']}"
    owner.post(f"{base}/drafts/0/approve")  # Directions comes after the words are approved
    url = f"{base}/drafts/0"
    assert owner.get(f"{url}/enhance/estimate").json() == {"credits": 3}
    assert editor.post(f"{url}/enhance").status_code == 404  # Reed's draft: hidden from them
    job = owner.post(f"{url}/enhance")
    assert job.status_code == 201 and job.json()["step"] == "enhance"
    assert owner.post(f"{url}/enhance").status_code == 409  # one at a time
    assert owner.get(f"/scripts/{made['id']}/drafts/0/breakdown").json()["running"] is False
    fake = FakeClaude(
        {
            "suggestions": [
                _mark("s1", "action", 2, "empty wallet", "after", "She slams it on the table."),
                _mark("s2", "camera", 1, "SCENE 1", "before", "Wide on the kitchen."),
                _mark("s3", "action", 3, "all your money", "after", 'NATE: "Spent it."'),
            ],
            "notes": [{"line": 4, "text": "Nate could smile."}],
        }
    )
    _run(app, db, fake)
    assert db.get(Job, job.json()["id"]).output["kept"] == 2  # spoken words are dropped
    assert "Mom finds the wallet" in fake.requests[0]["messages"][0]["content"]
    assert owner.get(f"{url}/notes").json() == [{"line": 4, "text": "Nate could smile."}]
    marks = {m["key"]: m["id"] for m in owner.get(f"{url}/suggestions").json()}
    assert list(marks) == ["s2", "s1"]  # script order
    assert owner.post(f"{url}/apply").status_code == 409  # nothing accepted yet
    owner.post(f"{url}/suggestions/{marks['s1']}/accept")
    owner.post(f"{url}/suggestions/{marks['s2']}/reject")

    added = owner.post(f"{url}/apply").json()["versions"][0]
    assert added["status"] == "approved"  # only direction lines were added
    text = owner.get(base).json()["versions"][0]["text"]
    assert "Mom storms in holding an empty wallet.\n[Movement] She slams it on the table." in text
    assert owner.get(f"{url}/history").json()[0]["source"] == "enhance"
    assert owner.get(f"{url}/suggestions").json() == []  # on the old words
    assert owner.post(f"{url}/suggestions/{marks['s2']}/accept").status_code == 409

    assert owner.delete(f"{url}/apply").status_code == 200  # Undo
    assert owner.get(base).json()["versions"][0]["text"] == SCRIPT
    assert owner.delete(f"{url}/apply").status_code == 409  # nothing left to undo


def test_directions_on_an_editors_own_script_use_their_allowance(editor, db):
    from app.credits import quick_clip_used
    from app.models.accounts import User

    made = _make(editor, text=SCRIPT)
    assert editor.post(f"/scripts/{made['id']}/drafts/0/enhance").status_code == 201
    assert quick_clip_used(db, db.query(User).filter_by(role="editor").one()) == 3
