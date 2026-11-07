"""A brand character with only a House sheet, locked into a video in another style, stopped the
director's run: "Mia has no approved look yet" (found making Movie, 7 Nov; any style but House).
make_looks now makes their look for this video in its style, from their approved sheet, priced
on the missing-looks card and shown in the cast and places OK; made once, never again by
itself. Stand-ins only."""

import copy

import pytest

from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.projects import Project
from app.routes.project_assets import missing_copies
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_breakdown import BREAKDOWN
from tests.test_director import _run
from tests.test_script_library import SCRIPT, _make

DRAMA = """SCENE 1 — INT. DINER — NIGHT
NATE: They laughed at me. The whole table.
MOM: Then give them something else to look at.
NATE: Like what? I've tried everything.
MOM: You haven't tried this."""


def _locked(app, owner, editor, db, look: str, text: str = DRAMA, shots=False) -> tuple[int, int]:
    """A published script in `look` with Mom locked to Mia, who has only a House sheet."""
    app.state.settings.fake_providers = True
    made = _make(owner, text=text, look=look)
    base = f"/scripts/{made['id']}"
    mia = owner.post("/library/character", json={"name": "Mia", "image_file_ids": [upload(owner)]})
    mia = mia.json()["id"]
    with_sheet(db, mia)
    mom = owner.post(f"{base}/cast", json={"role": "Mom"}).json()[0]["id"]
    owner.post(f"{base}/cast/{mom}/lock", json={"library_item_id": mia})
    if shots:  # a breakdown with her in its first shot, as the video's newest
        bd = copy.deepcopy(BREAKDOWN)
        bd["scenes"][0]["shots"][0]["character_ids"] = [f"char:{mia}"]
        owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    return editor.post(f"{base}/drafts/0/produce").json()["project_id"], mia


@pytest.mark.parametrize("look", ["claymation", "skeleton"])
def test_a_locked_house_only_character_gets_its_look_and_the_run_goes_on(
    app, db, owner, editor, look
):
    pid, mia = _locked(app, owner, editor, db, look)
    house = db.get(LibraryItem, mia).sheet_file_id
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    project = db.get(Project, pid)
    made = db.get(LibraryItem, project.look_copies[str(mia)])
    assert (made.owner_project_id, made.sheet_look, made.name) == (pid, look, "Mia")
    assert made.source_photo_file_id == house  # who she is: her approved sheet
    (sheet,) = [j for j in db.query(Job).filter_by(project_id=pid)
                if j.input.get("library_item_id") == made.id]  # fmt: skip
    assert sheet.input["auto_made"] and list(sheet.input["files"].values()) == [[house]]
    prompt = sheet.input["input"]["prompt"]
    assert "approved sheet, drawn in another style" in prompt and "photo of a real" not in prompt
    approved = (project.cast_ok or {}).get("items") or {}
    assert f"char:{made.id}" in approved or f"char:{mia}" in approved  # through the OK (rule 8)
    assert db.get(LibraryItem, mia).look_sheets == {}  # Cast & places untouched (rule 12)
    assert not missing_copies(db, project)  # made once


def test_the_card_prices_it_and_not_now_or_a_made_copy_is_never_made_again(app, db, owner, editor):
    pid, mia = _locked(app, owner, editor, db, "claymation", text=SCRIPT, shots=True)
    url = f"/projects/{pid}/assets"
    card = editor.get(f"{url}/missing-looks").json()
    assert "Mia" in card["roles"] and card["credits"] > 0 and card["usual_credits"] > 0
    project = db.get(Project, pid)
    assert [i.id for i in missing_copies(db, project)] == [mia]
    declined = editor.post(f"{url}/missing-looks/decline").json()
    assert "Mia" not in declined["roles"]  # Not now: never made by itself again
    db.expire_all()
    assert editor.post(f"{url}/make-missing").status_code == 200
    assert db.get(Project, pid).look_copies == {str(mia): None}  # nothing drawn
    made = editor.post(f"{url}/looks/{mia}/copy")  # the editor's own Make a look still works
    assert made.status_code == 200, made.text
    db.expire_all()
    assert db.get(Project, pid).look_copies[str(mia)]


def test_a_house_video_needs_no_copy(app, db, owner, editor):
    pid, _ = _locked(app, owner, editor, db, "house", text=SCRIPT, shots=True)
    assert missing_copies(db, db.get(Project, pid)) == []
