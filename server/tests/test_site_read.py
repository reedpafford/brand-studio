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
    assert [p["mark"] for p in found["products"]] == ["new", "fills"]  # an empty description
    assert (seen["id"], seen["url"]) == (job_id, "https://ironpaws.example/")
    assert owner.get(f"{url}/latest").json()["id"] == job_id  # Import reopens on it
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
    job_id, seen = _read(app, db, owner, url)
    assert seen["found"]["products"][0]["mark"] == "have"  # "Already in your products"
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


def test_the_found_logo_is_shown_once_fetched_and_save_uses_that_file(app, db, owner, site):
    brand_id, url = site
    job_id, _ = _read(app, db, owner, url)
    shown = owner.get(f"{url}/{job_id}/logo")
    assert shown.status_code == 200 and shown.headers["content-type"] == "image/png"
    files = db.query(StoredFile).count()
    assert owner.get(f"{url}/{job_id}/logo").content == shown.content
    assert db.query(StoredFile).count() == files  # fetched once, kept on the read
    owner.post(f"{url}/{job_id}/save", json={"logo": True})
    db.expire_all()
    kept = db.get(Job, job_id).output["logo_file_id"]
    assert db.get(Brand, brand_id).logo_file_id == kept and db.query(StoredFile).count() == files
    assert db.get(Brand, brand_id).logo_file_id is not None


def test_a_logo_that_cant_be_fetched_saves_the_rest(app, db, owner, site):
    brand_id, url = site
    job_id, seen = _read(app, db, owner, url, "https://nologo.example/")
    shown = owner.get(f"{url}/{job_id}/logo")
    assert (shown.status_code, shown.json()["detail"]) == (404, sr.NO_LOGO)
    saved = owner.post(f"{url}/{job_id}/save", json={"logo": True, "colours": ["#e4572e"]})
    assert saved.json()["problems"] == [sr.NO_LOGO] and saved.json()["colours_added"] == 1
    assert db.get(Brand, brand_id).logo_file_id is None


def test_real_reading_is_off_unless_switched_on(tmp_path):
    local = LocalProvider(storage=None)  # the real providers' default: BS_SITE_READ_REAL off
    done = local.run("site_fetch", {"url": "https://ironpaws.example/"})
    assert done.output == {"problem": "Reading websites is switched off."}


def test_a_new_brand_with_a_website_is_made_and_its_site_read(app, db, owner, editor, site):
    """F_BrandNew: Name, Website, Colour and Logo; the site is read once the brand is made,
    and the brand page opens on that read's review."""
    assert owner.get("/brands/site-read/estimate").json() == {"credits": 3.0}
    assert editor.get("/brands/site-read/estimate").status_code == 403
    bad = owner.post("/brands", json={"name": "Calm Co", "website": "ftp://calm.example/"})
    assert bad.status_code == 422 and "Paste a web address (https://…)" in bad.text
    made = owner.post("/brands", json={"name": "Calm Co", "website": "https://calm.example/",
                                       "colours": ["#112233"]})  # fmt: skip
    assert made.status_code == 201 and made.json()["colours"] == ["#112233"]
    job_id = made.json()["site_read_job_id"]
    _work(app, db)
    url = f"/brands/{made.json()['id']}/site-read"
    seen = owner.get(f"{url}/latest").json()
    assert (seen["id"], seen["status"], seen["url"]) == (job_id, "done", "https://calm.example/")
    assert db.get(Brand, made.json()["id"]).logo_file_id is None  # nothing saved before Save

    plain = owner.post("/brands", json={"name": "Quiet Co"}).json()
    assert plain["site_read_job_id"] is None
    assert owner.get(f"/brands/{plain['id']}/site-read/latest").status_code == 404
    app.state.settings.fake_providers = False
    app.state.settings.generation_enabled = False  # the read can't start: the brand is made
    off = owner.post("/brands", json={"name": "Still Co", "website": "https://still.example/"})
    assert off.status_code == 201 and off.json()["site_read_job_id"] is None
    assert off.json()["site_read_problem"] == "Generation is switched off on this server."


def test_the_logo_waits_for_the_read_and_a_broken_start_still_makes_one_brand(
    app, db, owner, site, monkeypatch
):
    """QA-13 on #1222: the logo row says it's still reading, not "Couldn't get the logo"; and
    a read that fails to start for any reason answers with the made brand, never a 500, so a
    second press can't make a second brand."""
    _, url = site
    started = owner.post(url, json={"url": "https://ironpaws.example/"}).json()
    still = owner.get(f"{url}/{started['id']}/logo")
    assert (still.status_code, still.json()["detail"]) == (409, "Still reading the site.")

    def broken(*args):
        raise RuntimeError("the queue is down")

    monkeypatch.setattr("app.site_read.start", broken)
    made = owner.post("/brands", json={"name": "Calm Co", "website": "https://calm.example/"})
    assert made.status_code == 201 and made.json()["site_read_job_id"] is None
    assert made.json()["site_read_problem"].startswith("The brand is made, but reading its site")
    assert db.query(Brand).filter_by(name="Calm Co").count() == 1
