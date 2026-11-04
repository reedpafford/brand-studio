"""New video (v6 S2): the format and style cards from the guides with their test samples, the
open folder and the brand's saved cast filled in, Song off while its music provider is, and an
editor's send from a published script starting at once inside its video's budget (S2-06) and
waiting for the owner past it (S2-05)."""

from decimal import Decimal

from app import director, guides, looks
from app.models.brands import Brand
from app.models.jobs import Job, JobStatus
from app.models.library import LibraryItem
from app.models.projects import Project
from app.routes import freestyles
from tests.conftest import first_brand, upload
from tests.test_freestyle_dialogue import BODY, SCRIPT, _run
from tests.test_script_library import _make


def test_the_cards_come_from_the_guides_with_their_test_samples(owner, monkeypatch):
    looks = {x["id"]: x for x in owner.get("/looks").json()}
    assert looks["claymation"]["test_clip"] and looks["claymation"]["test_still"]
    assert looks["house"]["test_still"] and not looks["house"]["test_clip"]  # a site still only
    assert {"card", "broll"} <= set(looks["house"])
    clip = owner.get("/looks/claymation/test-sample.mp4")
    assert clip.status_code == 200 and clip.headers["content-type"] == "video/mp4"
    assert owner.get("/looks/house/test-sample.jpg").headers["content-type"] == "image/jpeg"
    assert owner.get("/looks/house/test-sample.mp4").status_code == 404
    assert owner.get("/looks/claymation/test-sample.gif").status_code == 404
    assert owner.get("/looks/nope/test-sample.mp4").status_code == 422
    hidden = [{**s, "hidden": s["id"] == "paper"} for s in guides.styles()]
    monkeypatch.setattr("app.prompts.styles", lambda: hidden)  # Reed: "do not build it"
    assert "paper" not in {x["id"] for x in owner.get("/looks").json()}


def test_song_is_off_while_its_music_provider_is_and_says_why(owner, app):
    formats = {f["id"]: f for f in owner.get("/formats").json()}
    assert formats["song"]["off"] == "its music provider isn't switched on for this site yet"
    assert formats["dialogue"]["off"] is None and formats["dialogue"]["test_still"]
    assert formats["zack-d"]["off"] == "off"  # off in its guide
    assert owner.get("/formats/dialogue/test-sample.jpg").status_code == 200
    assert owner.get("/formats/nope/test-sample.jpg").status_code == 404
    sent = owner.post("/freestyles", json={**BODY, "type": "song", "brand_id": first_brand(owner)})
    assert sent.status_code == 409 and "music provider" in sent.text
    app.state.settings.kie_suno = True
    try:
        assert owner.get("/formats").json()[1]["off"] is None
    finally:
        app.state.settings.kie_suno = False


def test_it_lands_in_the_open_folder_with_the_brands_saved_cast(owner, db):
    brand_id = first_brand(owner)
    folder = owner.post(f"/brands/{brand_id}/folders", json={"name": "Week of 3 Nov"}).json()
    hero = LibraryItem(workspace_id=db.get(Brand, brand_id).workspace_id, kind="character",
                       name="Dr. Pickle")  # fmt: skip
    db.add(hero)
    db.flush()
    hero.brands.append(db.get(Brand, brand_id))
    db.get(Brand, brand_id).default_cast = [hero.id]
    db.commit()
    body = {**BODY, "brand_id": brand_id, "folder_id": folder["id"]}
    fs = owner.post("/freestyles", json=body).json()
    video = db.get(Project, fs["project_id"])
    assert video.folder_id == folder["id"] and video.cast_ids == [hero.id]
    picked = owner.post("/freestyles", json={**body, "text": SCRIPT + "\nMIA: No one.",
                                             "cast_ids": []}).json()  # fmt: skip
    assert db.get(Project, picked["project_id"]).cast_ids == []
    unsorted = owner.post("/freestyles", json={**BODY, "text": "A new idea.",
                                               "brand_id": brand_id}).json()  # fmt: skip
    assert db.get(Project, unsorted["project_id"]).folder_id is None  # Unsorted
    other = owner.post("/brands", json={"name": "Resilia"}).json()["id"]
    wrong = owner.post("/freestyles", json={**body, "brand_id": other, "text": "Elsewhere."})
    assert wrong.status_code == 422 and wrong.json()["detail"] == freestyles.OTHER_BRAND


def _published(owner, text):
    made = _make(owner, text=text)
    owner.post(f"/scripts/{made['id']}/drafts/0/approve")
    assert owner.post(f"/scripts/{made['id']}/publish").status_code == 200
    return made["id"]


def _first_turn(db, project_id):
    return db.query(Job).filter_by(project_id=project_id).order_by(Job.id).first()


def test_an_editors_published_script_starts_at_once_inside_its_budget(
    owner, editor, db, monkeypatch
):
    pick = {"shape": "9:16", "script_id": _published(owner, SCRIPT)}
    monkeypatch.setattr(freestyles, "budget", lambda db, project: Decimal(10_000))
    est = editor.get("/freestyles/estimate", params=pick).json()
    assert est["held"] == "" and est["budget"] == 10_000 and est["usd"] is None  # credits only
    usd = owner.get("/freestyles/estimate", params=pick).json()
    assert usd["usd"] >= usd["credits"] * 0.1028 and usd["usd"] - usd["credits"] * 0.1028 < 0.01
    sent = editor.post("/freestyles", json=pick)
    assert sent.status_code == 201, sent.text
    fs = sent.json()
    assert fs["status"] == "working"  # S2-06: no wait for the owner
    assert _first_turn(db, fs["project_id"]).status != JobStatus.needs_owner_approval
    assert fs["project_id"] in [p["id"] for p in editor.get("/projects").json()]  # shown


def test_an_editors_published_script_past_its_budget_waits_and_says_by_how_much(
    app, owner, editor, db, monkeypatch
):
    pick = {"shape": "9:16", "script_id": _published(owner, SCRIPT)}
    monkeypatch.setattr(freestyles, "budget", lambda db, project: Decimal("1.2"))
    est = editor.get("/freestyles/estimate", params=pick).json()
    words = est["held"]
    assert words.startswith("Waiting for the owner's OK: up to ") and est["budget"] == 1.2
    assert words.endswith(" credits is past this video's budget of 2.")
    fs = editor.post("/freestyles", json=pick).json()
    _run(app, db, ticks=4, start=False)  # its plan first (Reed, 4 Nov), then its start card
    fs = editor.get(f"/freestyles/{fs['id']}").json()
    assert fs["status"] == "waiting" and fs["make_it"] is None  # S2-05: no generation starts
    (card,) = db.query(Job).filter_by(project_id=fs["project_id"],
                                      status=JobStatus.needs_owner_approval).all()  # fmt: skip
    assert card.input["held"] == words  # its start card, waiting for the owner, says why
    pasted = editor.get("/freestyles/estimate", params={**BODY, "shape": "9:16"}).json()
    assert pasted["held"] == freestyles.HELD and pasted["budget"] is None  # S2-04
    assert owner.get("/freestyles/estimate", params=pick).json()["held"] == ""  # the owner's


def test_pictures_attached_stay_with_the_video_and_the_director_is_told(owner, db, monkeypatch):
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)
    pic = upload(owner)
    sound = upload(owner, "a.mp3", b"ID3" + b"\0" * 40, "audio/mpeg")
    body = {**BODY, "brand_id": first_brand(owner), "attachments": [pic]}
    refused = owner.post("/freestyles", json={**body, "attachments": [sound]})
    assert refused.status_code == 422 and refused.json()["detail"] == freestyles.NOT_ATTACHABLE
    fs = owner.post("/freestyles", json=body).json()
    video = db.get(Project, fs["project_id"])
    assert video.attachments == [pic]  # with the video, never the brand's (rule 12)
    assert fs["thread"][0]["files"] == [pic]  # thumbnails on the first message
    said = director.turn_input(db, video, {"id": "r", "turn": 0, "redos": {}})
    assert said["files"] == {"reference_images": [pic]}  # it sees them (piece B)
    assert '"Image 1: attached in New video"' in said["prompt"].split("<seen>")[1]


def test_a_presenters_b_roll_look_is_set_from_new_video_and_only_with_a_host(owner, db):
    brand = first_brand(owner)
    sent = {**BODY, "type": "presenter", "brand_id": brand, "broll_look": "skeleton"}
    est = owner.get("/freestyles/estimate", params={**sent, "text": SCRIPT}).json()
    assert est["credits"] > 0
    fs = owner.post("/freestyles", json=sent).json()
    assert db.get(Project, fs["project_id"]).broll_look == "skeleton"
    flat = owner.post("/freestyles", json={**sent, "type": "dialogue", "text": "Another."})
    assert flat.status_code == 409 and flat.json()["detail"] == looks.BROLL_HOSTED


def test_the_estimate_is_never_below_what_the_send_approves(owner, editor, db):
    brand = first_brand(owner)
    sent = {**BODY, "brand_id": brand, "text": SCRIPT + "\nLEO: And the estimate holds."}
    est = owner.get("/freestyles/estimate", params=sent).json()
    fs = owner.post("/freestyles", json=sent).json()
    assert est["credits"] >= fs["up_to"]  # rule 36: "up to" never under what it can charge
    many = owner.post("/freestyles", json={**sent, "text": "More.", "attachments": [1] * 3})
    assert many.status_code in (404, 422)  # an unknown file is refused, a repeat counted once
    files = [upload(owner, f"{n}.png") for n in range(freestyles.MAX_FILES + 1)]
    too_many = owner.post("/freestyles", json={**sent, "text": "Most.", "attachments": files})
    assert too_many.status_code == 422 and too_many.json()["detail"] == freestyles.TOO_MANY_FILES
