"""Import from website (flows BR2): owner only, on the stand-ins (no fetch, no Claude call),
nothing saved until ticked, the price shown is the most charged, and Undo."""

import pytest

from app import site_read as sr
from app.models.brands import Brand
from app.models.files import StoredFile
from app.models.jobs import Job
from app.models.library import Kind, LibraryItem
from app.providers.fake_local import FakeWriter
from app.providers.local import LocalProvider
from tests.test_song_takes import _work


@pytest.fixture
def site(app, owner, db):
    app.state.settings.fake_providers = True
    brand = owner.get("/brands").json()[0]["id"]
    return brand, f"/brands/{brand}/site-read"


def _read(app, db, owner, url, address="https://ironpaws.example/"):
    started = owner.post(url, json={"url": address})
    assert started.status_code == 201, started.text
    _work(app, db)
    return started.json()["id"], owner.get(f"{url}/{started.json()['id']}").json()


def test_only_the_owner_reads_a_site(owner, editor, site):
    brand, url = site
    assert owner.get(f"{url}/estimate").json() == {"credits": 3.0}  # "about 3 credits"
    for answer in (editor.get(f"{url}/estimate"), editor.post(url, json={"url": "https://a.b/"}),
                   editor.get(f"{url}/1"), editor.post(f"{url}/1/save", json={})):  # fmt: skip
        assert answer.status_code == 403
    assert owner.post(url, json={"url": "ftp://a.b/"}).status_code == 422  # http(s) only


def test_a_read_shows_what_it_found_and_saves_only_the_ticked(app, db, owner, site):
    brand_id, url = site
    brand = db.get(Brand, brand_id)
    brand.colours = ["#2299cc"]
    bag = LibraryItem(workspace_id=1, kind=Kind.prop, name="peanut butter chews", brands=[brand])
    db.add(bag)
    db.commit()
    job_id, seen = _read(app, db, owner, url)
    assert seen["status"] == "done" and seen["have_colours"] == ["#2299cc"]
    found = seen["found"]
    assert found["colours"] == ["#e4572e", "#2299cc"]
    assert found["logo_url"] == "https://ironpaws.example/logo.png"
    assert [p["name"] for p in found["products"]] == ["Chicken bites", "Peanut butter chews"]
    assert db.get(Brand, brand_id).logo_file_id is None  # nothing saved before Save
    read = db.query(Job).filter(Job.input["step"].as_string() == "site_read").one()
    assert (read.credits, db.get(Job, job_id).credits) == (3, 0)  # only the read is paid

    saved = owner.post(f"{url}/{job_id}/save", json={"logo": True, "colours": ["#e4572e",
                       "#2299cc"], "products": [0, 1]})  # fmt: skip
    assert saved.json() == {"colours_added": 1, "logo": True, "products_made": 1,
                            "products_filled": 1, "problems": []}  # fmt: skip
    db.expire_all()
    brand = db.get(Brand, brand_id)
    assert brand.colours == ["#2299cc", "#e4572e"]  # added, never replaced
    assert brand.logo_file_id is not None
    made = db.query(LibraryItem).filter_by(name="Chicken bites").one()
    assert made.kind == Kind.prop and [b.id for b in made.brands] == [brand_id]
    assert db.get(LibraryItem, bag.id).short_description == "Soft chews with real peanut butter."
    assert owner.get(f"{url}/{job_id}").json()["status"] == "saved"
    assert owner.post(f"{url}/{job_id}/save", json={}).status_code == 409  # once

    brand.colours = [*brand.colours, "#111111"]  # an edit after Save stays (Flow-QA)
    db.commit()
    assert owner.post(f"{url}/{job_id}/undo").status_code == 204
    db.expire_all()
    brand = db.get(Brand, brand_id)
    assert (brand.colours, brand.logo_file_id) == (["#2299cc", "#111111"], None)
    assert (
        db.get(LibraryItem, made.id).archived and not db.get(LibraryItem, bag.id).short_description
    )
    again = owner.post(f"{url}/{job_id}/save", json={"products": [1]})
    assert again.json()["products_filled"] == 1  # the read can be saved again


def test_an_existing_description_is_never_overwritten(app, db, owner, site):
    brand_id, url = site
    brand = db.get(Brand, brand_id)
    db.add(LibraryItem(workspace_id=1, kind=Kind.prop, name="Chicken Bites", brands=[brand],
                       short_description="Our best seller."))  # fmt: skip
    db.commit()
    job_id, _ = _read(app, db, owner, url)
    saved = owner.post(f"{url}/{job_id}/save", json={"products": [0]}).json()
    assert (saved["products_made"], saved["products_filled"]) == (0, 0)
    assert db.query(LibraryItem).filter_by(name="Chicken Bites").one().short_description == (
        "Our best seller."
    )


def test_a_site_that_cant_be_read_or_has_nothing_is_free(app, db, owner, site, monkeypatch):
    _, url = site
    job_id, seen = _read(app, db, owner, url, "https://fail.example/")
    assert (seen["status"], seen["reason"]) == ("failed", sr.FAILED)
    _, seen = _read(app, db, owner, url, "https://empty.example/")
    assert (seen["status"], seen["reason"]) == ("empty", sr.EMPTY)
    assert db.query(Job).filter(Job.input["step"].as_string() == "site_read").count() == 0

    monkeypatch.setattr(
        FakeWriter,
        "_site_read",
        lambda self, p: {"products": [], "colours": ["#123456"], "logo": False},
    )  # not on the page: dropped
    job_id, seen = _read(app, db, owner, url)
    assert (seen["status"], seen["reason"]) == ("empty", sr.EMPTY)
    read = db.query(Job).filter(Job.input["step"].as_string() == "site_read").one()
    assert read.credits == 0  # found nothing, so nothing was charged
    assert owner.post(f"{url}/{job_id}/save", json={}).status_code == 409


def test_undo_keeps_a_logo_changed_since(app, db, owner, site):
    brand_id, url = site
    job_id, _ = _read(app, db, owner, url)
    owner.post(f"{url}/{job_id}/save", json={"logo": True})
    brand = db.get(Brand, brand_id)
    db.refresh(brand)
    other = StoredFile(workspace_id=1, key="1/other", filename="other.png",
                       content_type="image/png", size=1, sha256="0")  # fmt: skip
    db.add(other)
    db.flush()
    assert brand.logo_file_id is not None
    brand.logo_file_id = other.id  # the owner picked another logo since
    db.commit()
    owner.post(f"{url}/{job_id}/undo")
    db.expire_all()
    assert db.get(Brand, brand_id).logo_file_id == other.id


def test_a_logo_that_cant_be_fetched_saves_the_rest(app, db, owner, site):
    brand_id, url = site
    job_id, seen = _read(app, db, owner, url, "https://nologo.example/")
    saved = owner.post(f"{url}/{job_id}/save", json={"logo": True, "colours": ["#e4572e"]})
    assert saved.json()["problems"] == [sr.NO_LOGO] and saved.json()["colours_added"] == 1
    assert db.get(Brand, brand_id).logo_file_id is None


def test_real_reading_is_off_unless_switched_on(tmp_path):
    local = LocalProvider(storage=None)  # the real providers' default: BS_SITE_READ_REAL off
    done = local.run("site_fetch", {"url": "https://ironpaws.example/"})
    assert done.output == {"problem": "Reading websites is switched off."}
