"""Reading the cast: Claude lists the roles; existing slots stay, new ones are added."""

from app.models.jobs import Job
from app.models.script_library import Script
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_script_library import SCRIPT, _make
from tests.test_script_preview import _work


def test_reading_keeps_locked_slots_and_adds_new_roles(app, db, owner):
    made = _make(owner, title="Dip", description="Mom finds the wallet", text=SCRIPT)
    base = f"/scripts/{made['id']}"
    url = f"{base}/cast/read"
    assert owner.post(url).json()["detail"] == "Approve the original first."
    mia = owner.post("/library/character", json={"name": "Mia", "image_file_ids": [upload(owner)]})
    with_sheet(db, mia.json()["id"])
    owner.post(f"{base}/cast", json={"role": "Coach"})
    mom = owner.post(f"{base}/cast", json={"role": "Mom"}).json()[1]["id"]
    owner.post(f"{base}/cast/{mom}/lock", json={"library_item_id": mia.json()["id"]})
    owner.post(f"{base}/drafts/0/approve")

    job = owner.post(url)
    assert job.status_code == 201, job.text
    assert owner.post(url).status_code == 409  # one at a time
    assert owner.get(url).json() == {"running": True, "problems": []}
    prompt = db.get(Job, job.json()["id"]).input["prompt"]
    assert "<brief>Dip: Mom finds the wallet</brief>" in prompt
    assert f"char:{mia.json()['id']} Mia (Mom)" in prompt and '<version slot="0">' in prompt
    _work(app, db)
    cast = owner.get(base).json()["cast"]
    assert [(s["role"], s["locked"], s["kind"], s["appears_in"]) for s in cast] == [
        ("Mom", True, "Main", [0]),  # found and already there: kept, still locked
        ("Nate", False, "Main", [0]),  # new (recurring: Main)
        ("Coach", False, "Main", []),  # not in the script any more: kept, flagged by []
    ]
    assert cast[1]["description"] == "A practice look."
    found = owner.get(url).json()
    assert found["running"] is False
    assert all(p.startswith("Advice: ") for p in found["problems"])


def test_reading_follows_the_script_rules(owner, editor):
    made = _make(owner, text=SCRIPT)
    url = f"/scripts/{made['id']}/cast/read"
    assert editor.post(url).status_code == 404  # private until published
    owner.post(f"/scripts/{made['id']}/drafts/0/approve")
    owner.post(f"/scripts/{made['id']}/publish")
    assert editor.get(url).status_code == 200
    assert editor.post(url).status_code in (403, 409)  # published: final


def test_publish_waits_for_a_read_and_a_late_result_is_dropped(app, db, owner):
    made = _make(owner, text=SCRIPT)
    base = f"/scripts/{made['id']}"
    owner.post(f"{base}/drafts/0/approve")
    assert owner.post(f"{base}/cast/read").status_code == 201
    assert owner.post(f"{base}/publish").status_code == 409  # still writing
    db.query(Script).filter_by(id=made["id"]).update({"published": True})
    db.commit()
    _work(app, db)
    assert owner.get(base).json()["cast"] == []
