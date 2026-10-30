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
    said = still.input["input"]["prompt"]  # who Mia is, never how she's drawn (#1009)
    assert "Mia, the same person as in [Image1]" in said and "exactly as" not in said
    assert clip.input["input"]["duration"] == 5 and clip.input["files"]
    assert clip.input["input"]["generate_audio"] is False  # no sound to be refused (Zack D)

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
    assert owner.get(f"/looks/claymation/sample?brand_id={brand}").json()["characters"] == [
        {"id": mia, "name": "Mia"}
    ]
    stranger = owner.post("/looks/claymation/sample", json={"brand_id": brand, "character_id": 999})
    assert (stranger.status_code, stranger.json()["detail"]) == (422, look_samples.NOT_THEIRS)
    picked = owner.post("/looks/claymation/sample", json={"brand_id": brand, "character_id": mia})
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
    again = db.query(Job).order_by(Job.id.desc()).first()
    assert again.input["files"] == {"reference_images": [kept]}  # from the kept still
    assert again.input["input"]["generate_audio"] is False  # silent, as every sample clip
    db.expire_all()
    _work(app, db, ticks=3)
    ready = owner.get(url).json()
    assert ready["status"] == "ready" and ready["still_id"] == kept and ready["clip_id"]


def test_a_still_with_no_picture_says_so_and_can_be_made_again(app, db, owner):
    from app.steps import save_step_result

    app.state.settings.fake_providers = True
    brand = _brand(owner)
    owner.post("/looks/zack-d/sample", json={"brand_id": brand})
    still = db.query(Job).filter(Job.input["step"].as_string() == look_samples.STILL).one()
    still.status, still.output = "succeeded", {"file_ids": []}  # finished with no picture
    save_step_result(db, still)
    db.commit()
    shown = owner.get(f"/looks/zack-d/sample?brand_id={brand}").json()
    assert (shown["status"], shown["reason"]) == ("failed", look_samples.NO_STILL)
    assert owner.post("/looks/zack-d/sample", json={"brand_id": brand}).status_code == 201
    assert db.query(Job).filter(Job.input["step"].as_string() == look_samples.STILL).count() == 2


def test_real_samples_on_the_test_site_go_real_until_the_budget(app, db, owner, monkeypatch):
    """Reed, 2026-10-29: with the stand-ins on, only a look's sample goes to real Replicate
    (still, then its clip), and only while it fits the test budget; nothing is sent here."""
    from app import providers as lanes
    from app.providers import REAL_SAMPLES, get_providers, samples_on
    from app.settings import Settings
    from app.steps import save_step_result

    real = object()  # a stub: a real provider is never built in tests (the proxy adds a key)
    monkeypatch.setattr(lanes, "_replicate", lambda settings: real)
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-token")
    assert not samples_on(Settings(fake_providers=True))  # off until switched on
    assert not samples_on(Settings(real_look_samples=True))  # live: everything is real anyway
    providers = get_providers(Settings(fake_providers=True, real_look_samples=True))
    assert providers[REAL_SAMPLES] is real and not providers["replicate"].paid  # rest: stand-ins

    settings = app.state.settings
    settings.fake_providers, settings.real_look_samples = True, True
    settings.look_samples_budget_usd = 0.6  # one sample (a still and a 5 s clip, about $0.55)
    brand = _brand(owner)
    url = f"/looks/zack-d/sample?brand_id={brand}"
    assert owner.get(url).json()["test_site"] == look_samples.REAL_NOTE  # said before the press
    owner.post("/looks/zack-d/sample", json={"brand_id": brand})
    still = db.query(Job).filter(Job.input["step"].as_string() == look_samples.STILL).one()
    assert still.provider == REAL_SAMPLES
    still.status, still.output = "succeeded", {"file_ids": [upload(owner)]}
    save_step_result(db, still)
    db.commit()
    clip = db.query(Job).filter(Job.input["step"].as_string() == look_samples.CLIP).one()
    assert clip.provider == REAL_SAMPLES  # the clip follows its still, already paid for
    shown = owner.get(f"/looks/skeleton/sample?brand_id={brand}").json()
    assert shown["test_site"] == look_samples.USED_UP
    owner.post("/looks/skeleton/sample", json={"brand_id": brand})  # past the budget
    newest = db.query(Job).order_by(Job.id.desc()).first()
    assert newest.input["look_id"] == "skeleton" and newest.provider == "replicate"  # stand-in


def test_with_real_samples_on_only_a_sample_goes_real_and_no_key_means_a_stand_in(
    app, db, owner, monkeypatch
):
    """QA-4 on #970: every other image or video job stays a stand-in while the switch is on;
    switched on without the key, the sample's lane makes a stand-in, never a failed job."""
    from app.providers import REAL_SAMPLES, get_providers
    from app.providers.fake_local import FakeMedia
    from tests.test_song_takes import _work

    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    settings = app.state.settings
    settings.fake_providers, settings.real_look_samples = True, True
    settings.look_samples_budget_usd = 6
    assert isinstance(get_providers(settings)[REAL_SAMPLES], FakeMedia)
    brand = _brand(owner)
    clip = owner.post("/clips", json={"brand_id": brand, "prompt": "A dog runs on a beach"})
    assert clip.status_code == 201, clip.text
    assert db.get(Job, clip.json()["id"]).provider == "replicate"  # a Quick clip: stand-in
    owner.post("/looks/zack-d/sample", json={"brand_id": brand})
    _work(app, db, ticks=4)
    ready = owner.get(f"/looks/zack-d/sample?brand_id={brand}").json()
    assert ready["status"] == "ready" and ready["clip_id"]  # made, as stand-ins


def test_two_presses_before_the_first_still_is_back_never_pass_the_budget(app, db, owner):
    """QA-3 on #970: a queued still counts with the clip it holds, so a second quick press
    is a stand-in when both samples together would pass the budget."""
    from app.providers import REAL_SAMPLES

    settings = app.state.settings
    settings.fake_providers, settings.real_look_samples = True, True
    settings.look_samples_budget_usd = 1.0  # one sample is about $0.55
    brand = _brand(owner)
    owner.post("/looks/disney-pixar/sample", json={"brand_id": brand})
    shown = owner.get(f"/looks/zack-d/sample?brand_id={brand}").json()
    assert shown["test_site"] == look_samples.USED_UP  # said before the second press
    owner.post("/looks/zack-d/sample", json={"brand_id": brand})
    lanes = {j.input["look_id"]: j.provider for j in db.query(Job).all()}
    assert lanes == {"disney-pixar": REAL_SAMPLES, "zack-d": "replicate"}


def test_a_look_with_its_own_sample_person_never_draws_the_hero(app, db, owner):
    """The Director on #1009: Skeleton brings its own sample person (`own_sample: yes`), so its
    sample sends no picture of the brand's hero and uses the look's own `## sample` person."""
    from app import prompts

    app.state.settings.fake_providers = True
    brand = _brand(owner)
    owner.patch(f"/brands/{brand}", json={"default_cast": [_mia(owner, db, brand)]})
    card = owner.get(f"/looks/skeleton/sample?brand_id={brand}").json()
    assert (card["hero"], card["characters"]) == (None, [])  # never "of Mia", no pick (Flow-QA)
    assert card["look"]["own_sample"]  # the card shows no "Who's in the sample?"
    assert owner.get(f"/looks/claymation/sample?brand_id={brand}").json()["hero"]["name"] == "Mia"
    owner.post("/looks/skeleton/sample", json={"brand_id": brand})
    job = db.query(Job).filter(Job.input["step"].as_string() == look_samples.STILL).one()
    said = job.input["input"]["prompt"]
    assert not job.input.get("files") and "[Image1]" not in said and "Mia" not in said
    assert prompts.look_sample("skeleton").rstrip(".") in said
