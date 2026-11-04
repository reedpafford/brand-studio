from tests.conftest import upload
from tests.helpers import MP4, assert_hidden


def _brands(client) -> dict[str, int]:
    return {b["slug"]: b["id"] for b in client.get("/brands").json()}


def test_character_in_two_brands_shows_in_both_filters(editor):
    b = _brands(editor)
    sheet, voice = upload(editor), upload(editor, "v.mp3", b"ID3", "audio/mpeg")
    r = editor.post(
        "/library/character",
        json={
            "name": "Max",
            "brand_ids": [b["fomo"], b["iron-paws"]],
            "image_file_ids": [sheet],
            "outfits": [{"name": "Gym kit", "file_ids": [sheet]}],
            "voice_file_id": voice,
        },
    )
    assert r.status_code == 201, r.text
    editor.post("/library/character", json={"name": "Rex", "brand_ids": [b["iron-paws"]]})

    def names(brand):
        r = editor.get("/library/character", params={"brand_id": brand})
        return [c["name"] for c in r.json()]

    assert names(b["fomo"]) == ["Max"]
    assert names(b["iron-paws"]) == ["Max", "Rex"]


def test_kinds_are_separate(owner):
    owner.post("/library/place", json={"name": "Trading floor"})
    owner.post("/library/prop", json={"name": "Phone"})
    assert [p["name"] for p in owner.get("/library/place").json()] == ["Trading floor"]
    assert owner.get("/library/character").json() == []


def test_only_characters_have_outfits_or_voice(owner):
    r = owner.post("/library/prop", json={"name": "Cup", "outfits": [{"name": "x"}]})
    assert r.status_code == 422


def test_unknown_brand_or_file_rejected(owner):
    assert owner.post("/library/prop", json={"name": "A", "brand_ids": [999]}).status_code == 404
    r = owner.post("/library/prop", json={"name": "A", "image_file_ids": [999]})
    assert r.status_code == 404


def test_edit_keeps_history_and_restore_brings_it_back(owner):
    item = owner.post("/library/character", json={"name": "Max", "notes": "v1"}).json()
    url = f"/library/character/{item['id']}"
    edited = owner.patch(url, json={"notes": "v2"}).json()
    assert edited["version"] == 2 and edited["name"] == "Max"
    versions = owner.get(f"{url}/versions").json()
    assert [(v["version"], v["snapshot"]["notes"]) for v in versions] == [(1, "v1")]
    restored = owner.post(f"{url}/versions/1/restore").json()
    assert restored["notes"] == "v1" and restored["version"] == 3


def test_archive_hides_item(owner):
    item = owner.post("/library/place", json={"name": "Gym"}).json()
    assert owner.delete(f"/library/place/{item['id']}").status_code == 204
    assert owner.get("/library/place").json() == []


def test_other_workspace_cannot_touch_items(owner, outsider):
    item = owner.post("/library/character", json={"name": "Max", "notes": "v1"}).json()
    url = f"/library/character/{item['id']}"
    owner.patch(url, json={"notes": "v2"})
    assert outsider.get("/library/character").json() == []
    assert_hidden(
        outsider,
        [
            ("GET", url),
            ("PATCH", url, {"notes": "x"}),
            ("GET", f"{url}/versions"),
            ("POST", f"{url}/versions/1/restore"),
            ("DELETE", url),
        ],
    )
    owner.delete(url)  # archived: the archive routes must hide it from outsiders too
    assert_hidden(outsider, [("POST", f"{url}/unarchive"), ("DELETE", f"{url}/permanent")])


def test_cannot_attach_another_workspaces_brand_or_file(owner, outsider):
    brand = owner.get("/brands").json()[0]["id"]
    r = outsider.post("/library/prop", json={"name": "A", "brand_ids": [brand]})
    assert r.status_code == 404
    r = outsider.post("/library/prop", json={"name": "A", "image_file_ids": [upload(owner)]})
    assert r.status_code == 404


def test_file_kinds_are_checked(owner):
    video = upload(owner, "v.mp4", MP4, "video/mp4")
    image = upload(owner)
    r = owner.post("/library/prop", json={"name": "A", "image_file_ids": [video]})
    assert r.status_code == 422
    r = owner.post("/library/character", json={"name": "A", "voice_file_id": image})
    assert r.status_code == 422
    outfit = {"name": "Kit", "file_ids": [video]}
    assert (
        owner.post("/library/character", json={"name": "A", "outfits": [outfit]}).status_code == 422
    )


def test_restore_skips_brands_archived_since(owner):
    b = _brands(owner)
    item = owner.post(
        "/library/prop", json={"name": "Cup", "brand_ids": [b["fomo"], b["iron-paws"]]}
    )
    url = f"/library/prop/{item.json()['id']}"
    owner.patch(url, json={"notes": "edited"})
    owner.delete(f"/brands/{b['iron-paws']}")
    r = owner.post(f"{url}/versions/1/restore")
    assert r.status_code == 200 and r.json()["brand_ids"] == [b["fomo"]]


def test_null_brand_ids_leaves_brands_and_empty_list_clears(owner):
    b = _brands(owner)
    item = owner.post("/library/prop", json={"name": "Cup", "brand_ids": [b["fomo"]]}).json()
    url = f"/library/prop/{item['id']}"
    assert owner.patch(url, json={"brand_ids": None}).json()["brand_ids"] == [b["fomo"]]
    assert owner.patch(url, json={"brand_ids": []}).json()["brand_ids"] == []


def test_archive_is_reversible_by_editors(editor):
    item = editor.post("/library/place", json={"name": "Gym"}).json()
    url = f"/library/place/{item['id']}"
    editor.delete(url)
    archived = editor.get("/library/place", params={"archived": True}).json()
    assert [i["name"] for i in archived] == ["Gym"]
    assert editor.post(f"{url}/unarchive").json()["name"] == "Gym"
    assert [i["name"] for i in editor.get("/library/place").json()] == ["Gym"]


def test_permanent_delete_is_owner_only_and_needs_archive_first(owner, editor):
    item = editor.post("/library/prop", json={"name": "Cup"}).json()
    url = f"/library/prop/{item['id']}"
    editor.patch(url, json={"notes": "v2"})
    assert owner.delete(f"{url}/permanent").status_code == 404  # not archived yet
    editor.delete(url)
    assert editor.delete(f"{url}/permanent").status_code == 403
    assert owner.delete(f"{url}/permanent").status_code == 204
    assert owner.post(f"{url}/unarchive").status_code == 404


def test_an_item_says_who_made_it_and_when_it_was_archived(owner, editor):
    """S8-03 "Came from": who made it; S8-08 "Archived 20 Oct"; Undo clears the date."""
    me = editor.get("/auth/me").json()["id"]
    item = editor.post("/library/character", json={"name": "Dana"}).json()
    assert item["created_by_id"] == me and item["archived_at"] is None and item["created_at"]
    editor.delete(f"/library/character/{item['id']}")
    gone = editor.get("/library/character", params={"archived": True}).json()
    assert [g["archived_at"] is not None for g in gone] == [True]
    back = editor.post(f"/library/character/{item['id']}/unarchive").json()
    assert back["archived_at"] is None


def test_a_presenter_and_a_usual_place_are_a_characters_and_keep_its_sheet(owner, db):
    """S8-04, S-gaps-05 L3: a presenter is a face and a voice (how they appear is each video's
    pick); S8-03: the usual place. Neither makes a new version or needs the sheet approved."""
    from app.models.library import LibraryItem

    kitchen = owner.post("/library/place", json={"name": "Mark's kitchen"}).json()["id"]
    mark = owner.post("/library/character", json={"name": "Mark", "presenter": True}).json()
    assert mark["presenter"] is True and mark["product_type"] is None
    db.get(LibraryItem, mark["id"]).sheet_approved = True
    db.commit()
    url = f"/library/character/{mark['id']}"
    r = owner.patch(url, json={"presenter": False, "place_id": kitchen}).json()
    assert (r["presenter"], r["place_id"], r["version"]) == (False, kitchen, mark["version"])
    db.expire_all()
    assert db.get(LibraryItem, mark["id"]).sheet_approved
    assert owner.patch(url, json={"place_id": None}).json()["place_id"] is None
    assert owner.patch(url, json={"place_id": mark["id"]}).status_code == 404  # not a place
    prop = owner.post("/library/prop", json={"name": "Bag"}).json()
    assert prop["product_type"] == "physical"  # unless it's an app
    assert owner.patch(f"/library/prop/{prop['id']}", json={"presenter": True}).status_code == 422
    assert owner.patch(url, json={"product_type": "app"}).status_code == 422


def test_a_products_pictures_are_its_brand_screens(owner, editor):
    """S8-06: a product is the record; its real photos are brand screens linked to it, each
    with its flavour. A product from another brand can't be linked."""
    b = _brands(owner)
    bag = owner.post("/library/prop", json={"name": "Bag", "brand_ids": [b["iron-paws"]]}).json()
    assert bag["pictures"] == []
    screens = f"/brands/{b['iron-paws']}/screens"
    body = {"name": "Chicken bag", "file_id": upload(editor), "product_id": bag["id"],
            "variant": "Chicken"}  # fmt: skip
    pic = editor.post(screens, json=body).json()
    assert pic["product"] == "Bag" and pic["product_id"] == bag["id"]
    got = owner.get("/library/prop", params={"brand_id": b["iron-paws"]}).json()[0]["pictures"]
    assert [(p["screen_id"], p["name"], p["variant"]) for p in got] == [
        (pic["id"], "Chicken bag", "Chicken")]  # fmt: skip
    other = f"/brands/{b['fomo']}/screens"
    r = owner.post(other, json={"name": "X", "file_id": upload(owner), "product_id": bag["id"]})
    assert r.status_code == 404
    kept = owner.patch(f"{screens}/{pic['id']}", json={"product_id": 0}).json()
    assert kept["product_id"] == bag["id"]  # a picture always stays a product's
    owner.delete(f"{screens}/{pic['id']}")
    assert owner.get(f"/library/prop/{bag['id']}").json()["pictures"] == []


def test_prices_say_up_to_in_dollars_for_the_owner_and_credits_for_an_editor(owner, editor):
    """S8-02 "Make one · up to $0.08", S8-03 "Change this… · up to $0.08"; editors see credits."""
    from tests.helpers import assert_no_dollars

    new = owner.get("/library/character/price").json()
    assert new["credits"] >= 1 and new["usd"] >= 0.01
    assert editor.get("/library/character/price").json() == {"credits": new["credits"], "usd": None}
    assert owner.get("/library/prop/price").status_code == 404
    item = owner.post("/library/character", json={"name": "Dana", "notes": "late 30s"}).json()
    mine = owner.get(f"/library/character/{item['id']}").json()
    assert mine["change_credits"] >= 1 and mine["usd"]["change"] >= 0.01
    assert owner.get("/library/character").json()[0]["usd"]["sheet"] >= 0.01
    assert_no_dollars(editor, [f"/library/character/{item['id']}", "/library/character"])
    assert editor.get(f"/library/character/{item['id']}").json()["usd"] is None


def test_an_app_is_a_product_whose_pictures_are_its_screens(owner):
    """S-gaps-05 L1: a screen added with no product is one of the brand's app's screens (made
    once, "<brand> app"); an app's screen isn't a pack, so it names no physical product."""
    b = _brands(owner)
    screens = f"/brands/{b['fomo']}/screens"
    one = owner.post(screens, json={"name": "Home", "file_id": upload(owner)}).json()
    two = owner.post(screens, json={"name": "Chart", "file_id": upload(owner)}).json()
    assert one["product_id"] == two["product_id"] and one["product"] == ""
    app = owner.get(f"/library/prop/{one['product_id']}").json()
    assert (app["name"], app["product_type"]) == ("fomo app", "app")
    assert [p["name"] for p in app["pictures"]] == ["Home", "Chart"]


def test_an_archived_products_pictures_are_not_offered_to_new_work(owner, db):
    from app.enhance import screens_of
    from app.models.brands import Brand

    b = _brands(owner)["iron-paws"]
    bag = owner.post("/library/prop", json={"name": "Bag", "brand_ids": [b]}).json()["id"]
    pic = owner.post(f"/brands/{b}/screens", json={"name": "Bag", "file_id": upload(owner),
                                                   "product_id": bag}).json()["id"]  # fmt: skip
    assert pic in [s.id for s in screens_of(db, db.get(Brand, b))]
    owner.delete(f"/library/prop/{bag}")
    db.expire_all()
    assert pic not in [s.id for s in screens_of(db, db.get(Brand, b))]


def test_each_version_says_which_sheet_it_had(owner, db):
    """S8-03's v3 · v2 · v1: the versions list carries each one's sheet."""
    from app.models.library import LibraryItem

    item = owner.post("/library/character", json={"name": "Mia"}).json()
    db.get(LibraryItem, item["id"]).sheet_file_id = upload(owner)
    db.commit()
    sheet = db.get(LibraryItem, item["id"]).sheet_file_id
    owner.patch(f"/library/character/{item['id']}", json={"notes": "older"})
    (v1,) = owner.get(f"/library/character/{item['id']}/versions").json()
    assert (v1["version"], v1["sheet_file_id"]) == (1, sheet)
