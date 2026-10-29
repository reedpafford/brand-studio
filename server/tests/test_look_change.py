"""Changing a look once looks exist (flows ST1): on an unpublished script, the confirm says
how many of its roles need a new look and what making them costs; on a video, VS1's
confirm says the same and its to-finish price includes them. Free and read only."""

from app.models.library import LibraryItem
from app.models.projects import Project
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_breakdown import BREAKDOWN
from tests.test_script_produce import SCRIPT, _make, _published

LOOK = "disney-pixar"


def _script_with_mia(owner, db):
    made = _make(owner, text=SCRIPT, reference_id="fomo-DehudnaAmce")
    base = f"/scripts/{made['id']}"
    mia = owner.post("/library/character", json={"name": "Mia", "image_file_ids": [upload(owner)]})
    with_sheet(db, mia.json()["id"])
    slot = owner.post(f"{base}/cast", json={"role": "Mom"}).json()[0]["id"]
    owner.post(f"{base}/cast/{slot}/lock", json={"library_item_id": mia.json()["id"]})
    return base, mia.json()["id"]


def test_a_scripts_look_change_counts_the_roles_that_need_a_new_look(owner, db):
    base, mia = _script_with_mia(owner, db)
    seen = owner.get(f"{base}/look-change?look={LOOK}").json()
    assert seen["roles"] == ["Mom"] and seen["to_finish_credits"] > 0 and seen["was_credits"] == 0
    assert seen["over_budget"] is False  # the owner has no budget on a script
    assert owner.get(f"{base}/look-change?look=house").json()["roles"] == []
    item = db.get(LibraryItem, mia)
    item.look_sheets = {LOOK: {"file_id": item.sheet_file_id, "approved": True}}  # ST2's sheet
    db.commit()
    assert owner.get(f"{base}/look-change?look={LOOK}").json()["roles"] == []
    assert owner.get(f"{base}/look-change?look=claymation-x").status_code == 422


def test_a_published_scripts_look_cant_be_previewed_either(owner, db):
    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    assert owner.get(f"{base}/look-change?look={LOOK}").status_code in (403, 409)


def test_a_videos_look_switch_names_the_roles_and_prices_them(owner, editor, db):
    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    url = f"/projects/{pid}/settings/preview"
    seen = owner.post(url, json={"look": LOOK}).json()
    assert seen["roles_needing_look"] == ["Mom"]
    same = owner.post(url, json={"look": "house"}).json()
    assert (
        same["roles_needing_look"] == [] and seen["to_finish_credits"] > same["to_finish_credits"]
    )
    assert db.get(Project, pid).look == "house"  # a preview never switches
