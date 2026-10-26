"""House-style sheets: drawn, approved, and the only picture of a character or place that
generations ever get; the source photo never is. Fake Nano Banana / Seedance, no paid calls."""

import base64
import json

import httpx2 as httpx

from app.models.jobs import Job
from app.providers.replicate import ReplicateProvider
from app.worker import run_once
from tests.conftest import PNG, png, upload
from tests.helpers import assert_hidden
from tests.test_clips import fomo  # noqa: F401 - fixture
from tests.test_replicate import BASE
from tests.test_storyboard import FakeNanoBanana


def _work(app, db, fake=None):
    fake = fake or FakeNanoBanana()
    client = httpx.Client(transport=httpx.MockTransport(fake))
    for _ in range(3):
        run_once(db, {"replicate": ReplicateProvider(BASE, client)}, app.state.storage)
    return [json.loads(q.content)["input"] for q in fake.requests if q.method == "POST"]


def test_sheet_from_notes_then_approve(app, db, editor):
    mia = editor.post(
        "/library/character", json={"name": "Mia", "notes": "teen trader, green hoodie"}
    ).json()
    url = f"/library/character/{mia['id']}"
    assert mia["sheet_status"] == "none"
    job = editor.post(f"{url}/sheet", json={})
    assert job.status_code == 201, job.text
    assert job.json()["credits"] == 1.5  # Nano Banana Pro, 0.1542 USD / 0.1028
    assert (job.json()["step"], job.json()["library_item_id"]) == ("sheet", mia["id"])
    assert editor.get(url).json()["sheet_status"] == "drawing"
    assert editor.post(f"{url}/sheet", json={}).status_code == 409  # one at a time
    (sent,) = _work(app, db)
    assert "green hoodie" in sent["prompt"] and "Mia" not in sent["prompt"]  # no names drawn
    assert sent["aspect_ratio"] == "9:16" and sent["allow_fallback_model"] is False
    assert "image_input" not in sent  # nothing attached
    assert db.get(Job, job.json()["id"]).status == "succeeded"

    item = editor.get(url).json()
    assert item["sheet_status"] == "needs_approval" and item["sheet_file_id"]
    assert editor.get(f"/files/{item['sheet_file_id']}").content == PNG
    approved = editor.post(f"{url}/sheet/approve").json()
    assert approved["sheet_status"] == "approved"
    assert editor.post(f"{url}/sheet/approve").status_code == 409  # nothing new to approve
    assert editor.delete(f"{url}/sheet/approve").json()["sheet_status"] == "needs_approval"
    editor.post(f"{url}/sheet/approve")
    edited = editor.patch(url, json={"notes": "teen trader, red hoodie"}).json()
    assert edited["sheet_status"] == "needs_approval"  # any edit needs approval again


def test_sheet_from_a_photo_and_redo(app, db, editor):
    photo = upload(editor, data=png(30, 30, (1, 2, 3, 255)))
    mia = editor.post(
        "/library/character", json={"name": "Mia", "source_photo_file_id": photo}
    ).json()
    url = f"/library/character/{mia['id']}"
    body = {"model_id": "nano-banana-2.1"}
    assert editor.post(f"{url}/sheet", json=body).json()["credits"] == 0.33
    (first,) = _work(app, db)
    assert len(first["image_input"]) == 1  # the photo, to draw the likeness from
    sheet = editor.get(url).json()["sheet_file_id"]
    editor.post(f"{url}/sheet", json={"change": "Bigger eyes."})
    (redo,) = _work(app, db)
    assert len(redo["image_input"]) == 2 and "Bigger eyes." in redo["prompt"]  # photo, sheet
    item = editor.get(url).json()
    assert item["sheet_file_id"] != sheet and item["source_photo_file_id"] == photo


def test_videos_use_only_the_approved_sheet_never_the_photo(app, db, editor, fomo):  # noqa: F811
    """The photo goes in only as the source of a sheet. Quick clips and stills refuse a
    character without an approved sheet, and with one they get the sheet alone."""
    photo_bytes = png(31, 31, (9, 8, 7, 255))
    photo = upload(editor, data=photo_bytes)
    maya = editor.post(
        "/library/character",
        json={"name": "Maya", "notes": "barista", "source_photo_file_id": photo},
    ).json()
    url = f"/library/character/{maya['id']}"
    clip = {"brand_id": fomo["brand"], "prompt": "Maya pours coffee", "character_ids": [maya["id"]]}
    r = editor.post("/clips", json=clip)
    assert (r.status_code, r.json()["detail"]) == (422, "Approve Maya's sheet first.")

    editor.post(f"{url}/sheet", json={})
    _work(app, db)
    r = editor.post("/clips", json=clip)
    assert r.json()["detail"] == "Approve Maya's sheet first."  # drawn, not approved yet
    editor.post(f"{url}/sheet/approve")
    assert editor.post("/clips", json=clip).status_code == 201
    from tests.test_replicate import FakeReplicate

    sent = _work(app, db, FakeReplicate())
    photo_b64 = base64.b64encode(photo_bytes).decode()
    videos = [j for j in db.query(Job).all() if j.input.get("step") != "sheet"]
    assert videos  # the quick clip
    for job in videos:  # only the sheet job may use the photo, as its source
        attached = [f for ids in (job.input.get("files") or {}).values() for f in ids]
        assert photo not in attached and maya_sheet(db, maya["id"]) in attached
    assert all(photo_b64 not in json.dumps(s) for s in sent)  # never sent as data either


def maya_sheet(db, item_id):
    from app.models.library import LibraryItem

    return db.get(LibraryItem, item_id).sheet_file_id


def test_sheet_rules(app, editor, outsider):
    cafe = editor.post("/library/place", json={"name": "Cafe", "notes": "cosy corner"}).json()
    job = editor.post(f"/library/place/{cafe['id']}/sheet", json={})
    assert job.status_code == 201
    bag = editor.post("/library/prop", json={"name": "Bag", "notes": "a bag"}).json()
    assert editor.post(f"/library/prop/{bag['id']}/sheet", json={}).status_code == 422
    blank = editor.post("/library/character", json={"name": "Nobody"}).json()
    assert editor.post(f"/library/character/{blank['id']}/sheet", json={}).status_code == 422
    assert_hidden(outsider, [("POST", f"/library/place/{cafe['id']}/sheet", {})])
    app.state.settings.generation_enabled = False
    try:
        assert editor.post(f"/library/place/{cafe['id']}/sheet", json={}).status_code == 503
    finally:
        app.state.settings.generation_enabled = True


def test_sheet_past_the_weekly_allowance_is_declined(owner, editor):
    owner.put(
        "/credits/limits", json={"weekly_quick_clip_credits": 1, "per_video_max_credits": 729}
    )
    mia = editor.post("/library/character", json={"name": "Mia", "notes": "teen trader"}).json()
    url = f"/library/character/{mia['id']}"
    declined = editor.post(f"{url}/sheet", json={})
    assert declined.status_code == 409 and "this week's 1 free credits (0 used)" in declined.json()["detail"]
    assert editor.get(url).json()["sheet_status"] == "none"  # nothing queued or held
