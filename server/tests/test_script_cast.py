"""A script's cast slots: shared roles, optional, locked to one approved look."""

from tests.conftest import upload
from tests.helpers import assert_hidden, with_sheet
from tests.test_script_library import SCRIPT, _make


def test_slots_add_rename_lock_and_unlock(app, db, owner):
    made = _make(owner, text=SCRIPT)
    url = f"/scripts/{made['id']}/cast"
    owner.post(url, json={"role": "Nate", "description": "teen trader"})
    slots = owner.post(url, json={"role": "Mom"}).json()
    assert [(s["role"], s["position"], s["locked"]) for s in slots] == [
        ("Nate", 1, False),
        ("Mom", 2, False),
    ]
    assert owner.post(url, json={"role": "nate"}).status_code == 409  # one slot per role
    nate = slots[0]["id"]
    renamed = owner.patch(f"{url}/{nate}", json={"role": "Nate (groom)"}).json()
    assert renamed[0]["role"] == "Nate (groom)"

    mia = owner.post("/library/character", json={"name": "Mia", "image_file_ids": [upload(owner)]})
    mia = mia.json()["id"]
    locked = owner.post(f"{url}/{nate}/lock", json={"library_item_id": mia})
    assert locked.status_code == 422 and "sheet" in locked.json()["detail"]  # approved looks only
    with_sheet(db, mia)
    locked = owner.post(f"{url}/{nate}/lock", json={"library_item_id": mia}).json()
    assert (locked[0]["locked"], locked[0]["library_item_id"]) == (True, mia)
    assert locked[0]["sheet_file_id"]  # the look at lock time, kept
    assert owner.get(f"/scripts/{made['id']}").json()["cast"][0]["locked"] is True
    unlocked = owner.delete(f"{url}/{nate}/lock").json()
    assert unlocked[0]["locked"] is False and unlocked[0]["sheet_file_id"] is None
    assert len(owner.delete(f"{url}/{slots[1]['id']}").json()) == 1

    copy = owner.post(f"/scripts/{made['id']}/duplicate").json()
    assert [s["role"] for s in copy["cast"]] == ["Nate (groom)"]


def test_published_cast_is_final_and_others_are_kept_out(owner, editor, outsider):
    made = _make(owner, text=SCRIPT)
    url = f"/scripts/{made['id']}/cast"
    slot = owner.post(url, json={"role": "Nate"}).json()[0]["id"]
    assert_hidden(outsider, [("GET", url), ("POST", url, {"role": "x"})])
    assert editor.get(url).status_code == 404  # not published: private
    owner.post(f"/scripts/{made['id']}/drafts/0/approve")
    owner.post(f"/scripts/{made['id']}/publish")
    assert [s["role"] for s in editor.get(url).json()] == ["Nate"]
    assert editor.post(url, json={"role": "Mom"}).status_code == 403
    assert owner.patch(f"{url}/{slot}", json={"role": "x"}).status_code == 409  # final
