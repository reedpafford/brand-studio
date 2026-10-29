"""The Assets step: locked slots preloaded, unlocked slots given a character, sheets checked."""

import copy

from app.models.jobs import Job
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_breakdown import BREAKDOWN
from tests.test_script_library import SCRIPT, _make


def test_assets_list_slots_and_cast_an_unlocked_one(owner, editor, db):
    made = _make(owner, text=SCRIPT)
    base = f"/scripts/{made['id']}"
    mia = owner.post("/library/character", json={"name": "Mia", "image_file_ids": [upload(owner)]})
    mia = mia.json()["id"]
    with_sheet(db, mia)
    bo = owner.post("/library/character", json={"name": "Bo", "image_file_ids": [upload(owner)]})
    bo = bo.json()["id"]
    with_sheet(db, bo)
    mom, nate = owner.post(f"{base}/cast", json={"role": "Mom"}).json()[0]["id"], None
    nate = owner.post(f"{base}/cast", json={"role": "Nate", "description": "teen"}).json()[1]["id"]
    owner.post(f"{base}/cast/{mom}/lock", json={"library_item_id": mia})
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][0]["character_ids"] = [f"char:{mia}", f"char:{bo}"]
    bd["scenes"][0]["shots"][1]["character_ids"] = [f"slot:{nate}"]
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    url = f"/projects/{pid}/assets"

    rows = editor.get(url).json()
    assert [(r["role"], r["ref"], r["locked"], r["sheet_status"]) for r in rows] == [
        ("Mom", f"char:{mia}", True, "approved"),
        ("Nate", f"slot:{nate}", False, "missing"),
        ("Bo", f"char:{bo}", False, "approved"),
    ]
    assert [(r["slot_id"], r["description"]) for r in rows] == [
        (mom, ""), (nate, "teen"), (None, "")
    ]  # fmt: skip
    assert [r["shots"] for r in rows] == [1, 1, 1]  # "In 1 shot", a slot:N shot included
    kid = editor.post(
        "/library/character", json={"name": "Kid", "image_file_ids": [upload(editor)]}
    )
    kid = kid.json()["id"]
    cast = editor.put(f"{url}/slots/{nate}", json={"library_item_id": kid}).json()
    assert (cast[1]["ref"], cast[1]["name"], cast[1]["sheet_status"], cast[1]["slot_id"]) == (
        f"char:{kid}",
        "Kid",
        "none",
        nate,
    )
    newest = editor.get(f"/projects/{pid}/breakdown").json()["breakdown"]
    assert newest["scenes"][0]["shots"][1]["character_ids"] == [f"char:{kid}"]
    assert kid in editor.get(f"/projects/{pid}").json()["cast_ids"]
    with_sheet(db, kid)
    assert all(r["ready"] for r in editor.get(url).json())
    locked = editor.put(f"{url}/slots/{mom}", json={"library_item_id": kid})
    assert locked.status_code == 409 and "locked" in locked.json()["detail"]


def test_a_paid_breakdown_names_the_unlocked_slots(owner, editor, db):
    """QA #220: without a saved breakdown, the plan made at produce lists unlocked slots
    (slot:N) so the Assets step has them to cast."""
    made = _make(owner, text=SCRIPT)
    base = f"/scripts/{made['id']}"
    nate = owner.post(f"{base}/cast", json={"role": "Nate", "description": "teen"}).json()[0]
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    job_id = editor.post(f"{base}/drafts/0/produce").json()["plan_job_id"]
    assert f"slot:{nate['id']} | Nate | teen (no look yet)" in db.get(Job, job_id).input["prompt"]


def test_recasting_a_slot_leaves_a_shared_character_alone(owner, editor, db):
    """QA #220: re-casting Nate away from Mia doesn't move Mom's shots when Mia plays both."""
    made = _make(owner, text=SCRIPT)
    base = f"/scripts/{made['id']}"
    mom = owner.post(f"{base}/cast", json={"role": "Mom"}).json()[0]["id"]
    nate = owner.post(f"{base}/cast", json={"role": "Nate"}).json()[1]["id"]
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][0]["character_ids"] = [f"slot:{mom}"]
    bd["scenes"][0]["shots"][1]["character_ids"] = [f"slot:{nate}"]
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    url = f"/projects/{pid}/assets/slots"
    mia, kid = (
        editor.post(
            "/library/character", json={"name": n, "image_file_ids": [upload(editor)]}
        ).json()["id"]
        for n in ("Mia", "Kid")
    )
    editor.put(f"{url}/{mom}", json={"library_item_id": mia})
    editor.put(f"{url}/{nate}", json={"library_item_id": mia})
    editor.put(f"{url}/{nate}", json={"library_item_id": kid})
    shots = editor.get(f"/projects/{pid}/breakdown").json()["breakdown"]["scenes"][0]["shots"]
    assert shots[0]["character_ids"] == [f"char:{mia}"]
    assert mia in editor.get(f"/projects/{pid}").json()["cast_ids"]


def test_assets_list_the_products_and_screens_the_shots_show(owner, editor, db):
    fomo = owner.get("/brands").json()[0]["id"]
    screen = owner.post(f"/brands/{fomo}/screens", json={"name": "Buy", "file_id": upload(owner)})
    bag = owner.post(
        f"/brands/{fomo}/screens",
        json={"name": "Bag", "file_id": upload(owner), "tags": ["product"]},
    )
    made = _make(owner, text="SCENE 1 — INT. KITCHEN — DAY\nThe phone buzzes.")  # no one
    base = f"/scripts/{made['id']}"
    bd = copy.deepcopy(BREAKDOWN)
    ids = [f"screen:{screen.json()['id']}", f"screen:{bag.json()['id']}"]
    bd["scenes"][0]["shots"][0]["screen_ids"] = ids
    bd["scenes"][0]["shots"][1]["screen_ids"] = ids[1:]
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    rows = editor.get(f"/projects/{pid}/assets").json()
    assert [(r["kind"], r["name"], r["shots"], r["ready"]) for r in rows] == [
        ("screen", "Buy", 1, True), ("product", "Bag", 2, True)
    ]  # fmt: skip
    assert rows[0]["file_id"] == screen.json()["file_id"]
