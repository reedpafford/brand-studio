"""Flavour from the script (n03): each version's default flavour per product, picked at Publish
or after it, one flavour picked by itself, the rest left on Auto; each new video starts from
them. Free."""

from app.models.brands import BrandScreen
from tests.conftest import upload
from tests.test_script_library import SCRIPT, _make

FLAVOURS = {"bag": ["Chicken", "Peanut butter"], "soda": ["Lime"], "app": ["Light", "Dark"]}


def _brand_flavours(db, owner) -> int:
    brand = owner.get("/brands").json()[0]["id"]
    file_id = upload(owner)
    for product, variants in FLAVOURS.items():
        for variant in variants:
            db.add(BrandScreen(brand_id=brand, name=f"{product} {variant}", file_id=file_id,
                               product=product, variant=variant))  # fmt: skip
    db.commit()
    return brand


def _two_versions(owner) -> str:
    url = f"/scripts/{_make(owner, text=SCRIPT)['id']}"
    owner.put(f"{url}/drafts/1", json={"text": SCRIPT + "\nNATE: Fine."})
    for slot in (0, 1):
        owner.post(f"{url}/drafts/{slot}/approve")
    return url


def _flavours(script: dict) -> list[dict]:
    return [v["flavours"] for v in script["versions"]]


def test_publish_saves_the_picks_fills_one_flavour_and_leaves_the_rest_on_auto(db, owner):
    _brand_flavours(db, owner)
    url = _two_versions(owner)
    before = owner.put(f"{url}/drafts/1/flavours", json={"app": "Dark"})  # before Publish
    assert _flavours(before.json())[1] == {"soda": "Lime", "app": "Dark"}
    bad = owner.post(f"{url}/publish", json={"flavours": {"0": {"bag": "Beef"}}})
    assert (bad.status_code, bad.json()["detail"]) == (422, "bag comes in: Chicken, Peanut butter.")
    assert owner.post(f"{url}/publish", json={"flavours": {"2": {}}}).status_code == 422
    assert not owner.get(url).json()["published"]  # a refused pick publishes nothing

    done = owner.post(f"{url}/publish", json={"flavours": {"0": {"bag": "Chicken"}}}).json()
    assert done["published"]
    assert _flavours(done) == [{"bag": "Chicken", "soda": "Lime"},  # app: Auto
                               {"soda": "Lime", "app": "Dark"}]  # fmt: skip


def test_flavours_change_after_publish_by_the_author_or_owner_only(db, owner, editor):
    _brand_flavours(db, owner)
    url = _two_versions(owner)
    assert _flavours(owner.post(f"{url}/publish").json())[0] == {"soda": "Lime"}  # no body
    later = owner.put(f"{url}/drafts/0/flavours", json={"bag": "Peanut butter"})
    assert _flavours(later.json())[0] == {"soda": "Lime", "bag": "Peanut butter"}  # rule 31
    assert later.json()["versions"][0]["text"] == SCRIPT  # the words never change
    assert editor.put(f"{url}/drafts/0/flavours", json={}).status_code == 403


def test_a_new_video_starts_from_its_versions_flavours_and_the_picks_sent_win(db, owner, editor):
    from app.db import utcnow
    from app.models.projects import Project
    from tests.test_breakdown import BREAKDOWN
    from tests.test_script_produce import _published

    _brand_flavours(db, owner)
    first, _ = _published(owner, db, breakdown=BREAKDOWN)
    owner.put(f"{first}/drafts/0/flavours", json={"bag": "Chicken", "app": "Dark"})
    dark = db.query(BrandScreen).filter_by(product="app", variant="Dark").one()
    dark.deleted_at = utcnow()  # deleted since: that product starts on Auto
    db.commit()
    pid = editor.post(f"{first}/drafts/0/produce").json()["project_id"]
    assert db.get(Project, pid).product_variants == {"bag": "Chicken", "soda": "Lime"}

    second, _ = _published(owner, db, breakdown=BREAKDOWN)
    owner.put(f"{second}/drafts/0/flavours", json={"bag": "Chicken"})
    sent = {"product_variants": {"bag": "Peanut butter", "app": "Light"}}
    pid = editor.post(f"{second}/drafts/0/produce", json=sent).json()["project_id"]
    assert db.get(Project, pid).product_variants == {"bag": "Peanut butter", "soda": "Lime",
                                                      "app": "Light"}  # fmt: skip
