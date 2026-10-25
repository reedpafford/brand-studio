"""Producing a library version: its project, once, with the saved breakdown or a new one."""

from app.models.jobs import Job
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_breakdown import BREAKDOWN
from tests.test_script_library import SCRIPT, _make


def _published(owner, db, *, breakdown=None, target=None):
    made = _make(owner, text=SCRIPT, reference_id="fomo-DehudnaAmce")
    base = f"/scripts/{made['id']}"
    if target:
        owner.put(f"{base}/drafts/0", json={"text": SCRIPT, "target_seconds": target})
    mia = owner.post("/library/character", json={"name": "Mia", "image_file_ids": [upload(owner)]})
    with_sheet(db, mia.json()["id"])
    slot = owner.post(f"{base}/cast", json={"role": "Mom"}).json()[0]["id"]
    owner.post(f"{base}/cast/{slot}/lock", json={"library_item_id": mia.json()["id"]})
    if breakdown:
        owner.put(f"{base}/drafts/0/breakdown", json=breakdown)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    return base, mia.json()["id"]


def test_produce_with_the_saved_breakdown_is_free_and_once(owner, editor, db):
    base, mia = _published(owner, db, breakdown=BREAKDOWN)
    made = editor.post(f"{base}/drafts/0/produce")
    assert made.status_code == 201, made.text
    assert made.json()["breakdown_job_id"] is None and db.query(Job).count() == 0
    project = editor.get(f"/projects/{made.json()['project_id']}").json()
    assert project["cast_ids"] == [mia] and project["planned_seconds"] is None
    assert project["reference_breakdown"]["source_id"] == "fomo-DehudnaAmce"
    assert (project["breakdown_seconds"], project["budget_credits"]) == (5, 10)
    pid = project["id"]
    assert editor.get(f"/projects/{pid}/script").json()["text"] == SCRIPT
    bd = editor.get(f"/projects/{pid}/breakdown").json()
    assert bd["source"] == "library" and bd["breakdown"]["clips"] == BREAKDOWN["clips"]
    again = owner.post(f"{base}/drafts/0/produce")
    assert (
        again.status_code == 409 and again.json()["detail"] == "This version already has a video."
    )
    library = owner.get(base).json()
    assert library["versions"][0]["status"] == "in_production" and library["versions_left"] == 0
    assert library["versions"][0]["project_id"] == pid


def test_produce_without_a_saved_breakdown_runs_one(owner, editor, db):
    base, _ = _published(owner, db, target=40)
    made = editor.post(f"{base}/drafts/0/produce").json()
    job = db.get(Job, made["breakdown_job_id"])
    assert job.input["step"] == "breakdown" and job.project_id == made["project_id"]
    project = editor.get(f"/projects/{made['project_id']}").json()
    assert (project["planned_seconds"], project["budget_credits"]) == (40, 80)  # Reed's target


def test_only_approved_versions_of_published_scripts(owner, editor):
    made = _make(owner, text=SCRIPT)
    url = f"/scripts/{made['id']}/drafts/0/produce"
    assert owner.post(url).json()["detail"] == "Publish this script first."
    owner.put(f"/scripts/{made['id']}/drafts/1", json={"text": SCRIPT + "\nMOM: Fine."})
    assert editor.post(url).status_code == 404  # private until published
