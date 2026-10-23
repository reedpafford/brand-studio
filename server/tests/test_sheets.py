"""Character sheets and place stills (fake Nano Banana, no paid calls)."""

import json

import httpx2 as httpx

from app.models.jobs import Job
from app.providers.replicate import ReplicateProvider
from app.worker import run_once
from tests.conftest import PNG, upload
from tests.helpers import assert_hidden
from tests.test_replicate import BASE
from tests.test_storyboard import FakeNanoBanana


def _work(app, db):
    fake = FakeNanoBanana()
    client = httpx.Client(transport=httpx.MockTransport(fake))
    for _ in range(2):
        run_once(db, {"replicate": ReplicateProvider(BASE, client)}, app.state.storage)
    return json.loads(next(q for q in fake.requests if q.method == "POST").content)["input"]


def test_character_sheet_from_notes_becomes_a_new_version(app, db, editor):
    mia = editor.post(
        "/library/character", json={"name": "Mia", "notes": "teen trader, green hoodie"}
    ).json()
    job = editor.post(f"/library/character/{mia['id']}/sheet", json={})
    assert job.status_code == 201, job.text
    assert job.json()["credits"] == 1.5 and job.json()["step"] == "sheet"  # Nano Banana Pro
    sent = _work(app, db)
    assert "green hoodie" in sent["prompt"] and "Mia" not in sent["prompt"]  # no names drawn
    assert sent["aspect_ratio"] == "16:9" and sent["allow_fallback_model"] is False
    assert "image_input" not in sent  # nothing attached: no board, no reel frame
    assert db.get(Job, job.json()["id"]).status == "succeeded"
    item = editor.get(f"/library/character/{mia['id']}").json()
    assert item["version"] == 2 and len(item["image_file_ids"]) == 1
    assert editor.get(f"/files/{item['image_file_ids'][0]}").content == PNG


def test_redo_and_from_photo_attach_only_the_items_own_picture(app, db, editor):
    photo = upload(editor)
    mia = editor.post(
        "/library/character", json={"name": "Mia", "notes": "", "image_file_ids": [photo]}
    ).json()
    url = f"/library/character/{mia['id']}/sheet"
    assert editor.post(url, json={}).status_code == 422  # nothing to draw from
    body = {"from_photo": True, "change": "Bigger eyes.", "model_id": "nano-banana-2.1"}
    assert editor.post(url, json=body).json()["credits"] == 0.33
    sent = _work(app, db)
    assert len(sent["image_input"]) == 1 and "Bigger eyes." in sent["prompt"]
    item = editor.get(f"/library/character/{mia['id']}").json()
    assert item["image_file_ids"][1] == photo  # the new sheet first, the photo kept


def test_place_still_and_rules(app, editor, outsider):
    cafe = editor.post("/library/place", json={"name": "Cafe", "notes": "cosy corner cafe"}).json()
    assert editor.post(f"/library/place/{cafe['id']}/sheet", json={}).status_code == 201
    bag = editor.post("/library/prop", json={"name": "Bag", "notes": "a bag"}).json()
    assert editor.post(f"/library/prop/{bag['id']}/sheet", json={}).status_code == 422
    assert_hidden(outsider, [("POST", f"/library/place/{cafe['id']}/sheet", {})])
    app.state.settings.generation_enabled = False
    try:
        assert editor.post(f"/library/place/{cafe['id']}/sheet", json={}).status_code == 503
    finally:
        app.state.settings.generation_enabled = True
