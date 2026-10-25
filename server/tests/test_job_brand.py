"""Every charge gets a brand (Usage, DECISIONS #237), or none when it can't belong to one."""

import importlib.util
from pathlib import Path

from sqlalchemy import text

from app.models.accounts import Role, User
from app.models.jobs import Job
from app.models.projects import Project
from app.routes.jobs import enqueue
from tests.conftest import upload
from tests.test_script_library import SCRIPT, _make

MIGRATION = Path(__file__).parents[1] / "migrations/versions/0027_job_brand.py"


def test_a_job_takes_the_brand_of_its_project_request_script_or_item(owner, db):
    me = db.query(User).filter_by(role=Role.owner).one()
    fomo, paws = (b["id"] for b in owner.get("/brands").json()[:2])
    made = owner.post("/projects", json={"brand_id": paws, "name": "Launch"}).json()
    project = db.get(Project, made["id"])
    assert enqueue(db, me, "video-480p", {}, project=project).brand_id == paws
    assert enqueue(db, me, "video-480p", {"brand_id": fomo}).brand_id == fomo  # Quick clip
    script = _make(owner, text=SCRIPT)  # a fomo script
    assert enqueue(db, me, "write-claude", {"script_id": script["id"]}).brand_id == fomo
    draft = db.execute(text("SELECT id FROM script_drafts LIMIT 1")).scalar()
    assert enqueue(db, me, "write-claude", {"script_draft_id": draft}).brand_id == fomo

    def item(brand_ids):
        body = {"name": "Mia", "image_file_ids": [upload(owner)], "brand_ids": brand_ids}
        return owner.post("/library/character", json=body).json()["id"]

    one, shared = item([paws]), item([paws, fomo])
    assert enqueue(db, me, "image", {"library_item_id": one}).brand_id == paws
    assert enqueue(db, me, "image", {"library_item_id": shared}).brand_id is None
    assert enqueue(db, me, "write-claude", {}).brand_id is None


def test_old_jobs_are_backfilled_by_the_same_rule(owner, db):
    me = db.query(User).filter_by(role=Role.owner).one()
    fomo, paws = (b["id"] for b in owner.get("/brands").json()[:2])
    made = owner.post("/projects", json={"brand_id": paws, "name": "Launch"}).json()
    body = {"name": "Mia", "image_file_ids": [upload(owner)], "brand_ids": [paws, fomo]}
    shared = owner.post("/library/character", json=body).json()["id"]
    jobs = [
        enqueue(db, me, "video-480p", {}, project=db.get(Project, made["id"])),
        enqueue(db, me, "video-480p", {"brand_id": fomo}),
        enqueue(db, me, "image", {"library_item_id": shared}),
    ]
    db.query(Job).update({"brand_id": None})  # as before the migration
    db.commit()
    spec = importlib.util.spec_from_file_location("m0027", MIGRATION)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.backfill(db.connection())
    db.commit()
    db.expire_all()
    assert [db.get(Job, j.id).brand_id for j in jobs] == [paws, fomo, None]
