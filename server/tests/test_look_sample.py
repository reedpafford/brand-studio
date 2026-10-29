"""A look's sample (flows ST3, owner only): Make a sample makes one still and one 5 s clip of
the brand's hero in the look; with no hero, a picked character or the look's own; then the
look can be switched on for editors. All on the free stand-ins (no paid calls)."""

from app import look_samples
from app.models.jobs import Job
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_song_takes import _work


def _brand(owner):
    return owner.get("/brands").json()[0]["id"]


def _mia(owner, db, brand):
    made = owner.post("/library/character", json={"name": "Mia", "brand_ids": [brand],
                                                   "image_file_ids": [upload(owner)]})  # fmt: skip
    with_sheet(db, made.json()["id"])
    return made.json()["id"]


def test_a_sample_of_the_brands_hero_is_made_then_the_look_switched_on(app, db, owner, editor):
    app.state.settings.fake_providers = True
    brand = _brand(owner)
    mia = _mia(owner, db, brand)
    owner.patch(f"/brands/{brand}", json={"default_cast": [mia]})
    url = f"/looks/zack-d/sample?brand_id={brand}"
    shown = owner.get(url).json()
    assert shown["status"] == "none" and shown["hero"]["name"] == "Mia" and shown["credits"] > 0
    assert editor.get(url).status_code == 403  # the owner's page
    no = owner.patch("/looks/zack-d", json={"on": True})
    assert no.status_code == 409  # no sample yet

    made = owner.post("/looks/zack-d/sample", json={"brand_id": brand})
    assert made.status_code == 201, made.text
    assert made.json()["status"] == "making"
    again = owner.post("/looks/zack-d/sample", json={"brand_id": brand})
    assert (again.status_code, again.json()["detail"]) == (409, look_samples.ALREADY)
    _work(app, db, ticks=4)
    ready = owner.get(url).json()
    assert ready["status"] == "ready" and ready["still_id"] and ready["clip_id"]
    still, clip = (db.query(Job).filter(Job.input["step"].as_string() == s).one()
                   for s in (look_samples.STILL, look_samples.CLIP))  # fmt: skip
    assert "Mia, exactly as in [Image1]" in still.input["input"]["prompt"]
    assert clip.input["input"]["duration"] == 5 and clip.input["files"]

    on = owner.patch("/looks/zack-d", json={"on": True})
    assert on.status_code == 200 and on.json()["on"]  # Switch on for editors
    assert not owner.patch("/looks/zack-d", json={"on": False}).json()["on"]  # Switch off


def test_with_no_hero_the_owner_picks_one_or_the_look_brings_its_own(app, db, owner):
    app.state.settings.fake_providers = True
    brand = _brand(owner)
    shown = owner.get(f"/looks/disney-pixar/sample?brand_id={brand}").json()
    assert shown["hero"] is None and shown["characters"] == []  # "Who's in the sample?"
    owner.post("/looks/disney-pixar/sample", json={"brand_id": brand})  # its own character
    job = db.query(Job).filter(Job.input["step"].as_string() == look_samples.STILL).one()
    assert "[Image1]" not in job.input["input"]["prompt"] and not job.input.get("files")
    mia = _mia(owner, db, brand)
    assert owner.get(f"/looks/skeleton/sample?brand_id={brand}").json()["characters"] == [
        {"id": mia, "name": "Mia"}
    ]
    stranger = owner.post("/looks/skeleton/sample", json={"brand_id": brand, "character_id": 999})
    assert (stranger.status_code, stranger.json()["detail"]) == (422, look_samples.NOT_THEIRS)
    picked = owner.post("/looks/skeleton/sample", json={"brand_id": brand, "character_id": mia})
    assert picked.status_code == 201
    house = owner.post("/looks/house/sample", json={"brand_id": brand})
    assert (house.status_code, house.json()["detail"]) == (409, look_samples.HOUSE)


def test_after_a_clip_that_didnt_finish_only_the_clip_is_made_again(app, db, owner):
    from app.credits import estimate, price
    from app.models.looks import LookSwitch

    app.state.settings.fake_providers = True
    brand = _brand(owner)
    owner.post("/looks/zack-d/sample", json={"brand_id": brand})
    _work(app, db, ticks=4)
    clip = db.query(Job).filter(Job.input["step"].as_string() == look_samples.CLIP).one()
    clip.status, clip.error = "failed", "The clip didn't finish. Nothing was charged."
    row = db.query(LookSwitch).one()
    kept, row.sample_clip_id = row.sample_still_id, None
    db.commit()
    url = f"/looks/zack-d/sample?brand_id={brand}"
    shown = owner.get(url).json()
    assert shown["status"] == "failed" and shown["still_id"] == kept
    ws = owner.get("/auth/me").json()["workspace_id"]
    assert shown["credits"] == price(estimate(db, ws, "video", 5, clip.input))  # the clip alone
    jobs = db.query(Job).count()
    assert owner.post("/looks/zack-d/sample", json={"brand_id": brand}).status_code == 201
    assert db.query(Job).count() == jobs + 1  # only the clip, no new still
    db.expire_all()
    _work(app, db, ticks=3)
    ready = owner.get(url).json()
    assert ready["status"] == "ready" and ready["still_id"] == kept and ready["clip_id"]
