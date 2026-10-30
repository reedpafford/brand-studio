"""Brand setup (flows BR1): voice and tone, CTA lines with one Default (Undo), the default
cast, music style, language and look, and a product's description and claim. Editors change a
brand's setup too (Reed's item 1); nothing already made changes. main's `never_say` and
`end_line` are kept in step (data.md n08)."""

from app import brand_setup
from app.routes.library import NO_CLAIM
from tests.conftest import upload


def _brand(owner):
    return owner.get("/brands").json()[0]


def test_editors_change_brand_setup_too_and_read_it(owner, editor):
    brand = _brand(owner)
    url = f"/brands/{brand['id']}"
    body = {"audience": "Dog owners over 40", "do_list": ["Warm", "Plain words", "Warm"],
            "dont_list": ["guaranteed"], "music_style": "breezy pop, 100 BPM",
            "default_language": "es"}  # fmt: skip
    assert editor.patch(url, json={"colours": ["#112233"]}).status_code == 200  # as before BR1
    saved = owner.patch(url, json=body).json()
    assert saved["audience"] == "Dog owners over 40" and saved["do_list"] == ["Warm", "Plain words"]
    assert saved["music_style"] == "breezy pop, 100 BPM" and saved["default_language"] == "es"
    assert editor.get(url).json()["dont_list"] == ["guaranteed"]  # editors read it


def test_never_say_and_dont_list_stay_in_step(owner):
    url = f"/brands/{_brand(owner)['id']}"
    got = owner.patch(url, json={"dont_list": ["cure", "guaranteed"]}).json()
    assert got["never_say"] == ["cure", "guaranteed"]
    got = owner.patch(url, json={"never_say": ["vet-approved"]}).json()  # main's field
    assert got["dont_list"] == ["vet-approved"] and got["never_say"] == ["vet-approved"]


def test_cta_lines_one_default_delete_promotes_and_undo(owner, db):
    brand = _brand(owner)
    url = f"/brands/{brand['id']}"
    first = brand["cta_lines"][0]  # the seeded end line is the Default
    assert first["default"] and brand["end_line"] == first["text"]
    two = owner.post(f"{url}/cta-lines", json={"text": "Shop Iron Paws, link in bio"}).json()
    second = two["cta_lines"][1]
    assert not second["default"] and two["end_line"] == first["text"]

    gone = owner.delete(f"{url}/cta-lines/{first['id']}").json()
    assert gone["promoted_id"] == second["id"]
    assert gone["brand"]["end_line"] == "Shop Iron Paws, link in bio"  # main reads the Default
    assert [x["id"] for x in gone["brand"]["cta_lines"]] == [second["id"]]
    back = owner.post(f"{url}/cta-lines/{first['id']}/restore").json()  # Undo
    assert [(x["id"], x["default"]) for x in back["cta_lines"]] == [
        (first["id"], True),
        (second["id"], False),
    ]
    assert back["end_line"] == first["text"]

    made = owner.patch(f"{url}/cta-lines/{second['id']}", json={"default": True}).json()
    assert made["end_line"] == "Shop Iron Paws, link in bio"
    owner.delete(f"{url}/cta-lines/{first['id']}")
    last = owner.delete(f"{url}/cta-lines/{second['id']}").json()["brand"]
    assert last["cta_lines"] == [] and last["end_line"] == ""
    assert last["advice"] == [brand_setup.NO_CTA]  # Advice, never a block (rule 18)
    assert owner.patch(f"{url}/cta-lines/nope", json={"text": "x"}).status_code == 404


def test_main_writing_end_line_moves_the_default_line(owner):
    url = f"/brands/{_brand(owner)['id']}"
    got = owner.patch(url, json={"end_line": "Download fomo, link in bio"}).json()
    assert [x["text"] for x in got["cta_lines"] if x["default"]] == ["Download fomo, link in bio"]
    cleared = owner.patch(url, json={"end_line": ""}).json()
    assert cleared["end_line"] == "" and not any(x["default"] for x in cleared["cta_lines"])


def test_default_cast_marks_a_deleted_pick(owner):
    url = f"/brands/{_brand(owner)['id']}"
    dog = owner.post("/library/character", json={"name": "Biscuit"}).json()["id"]
    place = owner.post("/library/place", json={"name": "Kitchen"}).json()["id"]
    assert owner.patch(url, json={"default_cast": [place]}).status_code == 422
    got = owner.patch(url, json={"default_cast": [dog, dog]}).json()
    assert got["default_cast"] == [dog] and got["cast"] == [
        {"id": dog, "name": "Biscuit", "deleted": False}
    ]
    owner.delete(f"/library/character/{dog}")
    assert owner.get(url).json()["cast"][0]["deleted"]  # "Deleted: pick another"


def test_new_scripts_start_on_the_brands_look_and_music_style(owner, editor):
    brand = _brand(owner)
    url = f"/brands/{brand['id']}"
    assert owner.patch(url, json={"default_look": "nope"}).status_code == 422
    owner.patch(url, json={"default_look": "disney-pixar", "music_style": "laid-back pop"})
    song = owner.post("/scripts", json={"brand_id": brand["id"], "title": "S", "kind": "song",
                                        "text": "la"}).json()  # fmt: skip
    assert song["look"] == "disney-pixar"
    version = owner.get(f"/scripts/{song['id']}").json()["versions"][0]
    assert version["style_line"] == "laid-back pop"
    story = editor.post("/scripts", json={"brand_id": brand["id"], "title": "T"}).json()
    assert story["look"] == "house"  # off for editors: House

    owner.patch(url, json={"music_style": "rock", "default_look": "house",
                           "dont_list": ["x"], "end_line": "New end"})  # fmt: skip
    after = owner.get(f"/scripts/{song['id']}").json()  # nothing already made changes (S)
    assert after["look"] == "disney-pixar" and after["versions"][0]["style_line"] == "laid-back pop"


def test_a_products_description_and_claim(owner, editor):
    bag = owner.post("/library/prop", json={"name": "Iron Paws bag"}).json()
    assert bag["advice"] == [NO_CLAIM]
    url = f"/library/prop/{bag['id']}"
    mine = editor.patch(url, json={"main_claim": "Gut health in 14 days"})  # editors too (item 1)
    assert mine.status_code == 200 and mine.json()["main_claim"] == "Gut health in 14 days"
    assert editor.patch(url, json={"notes": "chicken"}).status_code == 200
    got = owner.patch(url, json={"short_description": "Daily gut scoop",
                                 "main_claim": "Gut health in 14 days"}).json()  # fmt: skip
    assert got["main_claim"] == "Gut health in 14 days" and got["advice"] == []
    dog = owner.post("/library/character", json={"name": "Rex"}).json()["id"]
    assert owner.patch(f"/library/character/{dog}", json={"main_claim": "x"}).status_code == 422
    assert (
        editor.patch(url, json={"main_claim": "Gut health in 14 days"}).status_code == 200
    )  # same


def test_a_brand_with_no_lines_upload_still_works(owner):
    url = f"/brands/{_brand(owner)['id']}"
    assert owner.patch(url, json={"logo_file_id": upload(owner)}).status_code == 200


def test_an_editor_editing_never_say_or_end_line_changes_dont_and_the_default(owner, editor):
    """The one path from an editor into the new sections (Next-Lead): they edit these two
    today, and they write through. Reed's open "editor brand edits" question may close it."""
    url = f"/brands/{_brand(owner)['id']}"
    got = editor.patch(url, json={"never_say": ["cure"], "end_line": "Find us, link in bio"})
    assert got.status_code == 200
    got = got.json()
    assert got["dont_list"] == ["cure"]
    assert [x["text"] for x in got["cta_lines"] if x["default"]] == ["Find us, link in bio"]


def test_an_editor_saves_every_setup_field_and_the_cta_lines(owner, editor, db):
    """Reed's item 1: editors fill in the Brand page. Creating, archiving and restoring a brand
    and the paid site read stay the owner's."""
    from app.models.brands import Brand
    from app.models.library import LibraryItem

    brand = _brand(owner)
    url = f"/brands/{brand['id']}"
    mia = owner.post("/library/character", json={"name": "Mia"}).json()["id"]
    db.get(LibraryItem, mia).brands = [db.get(Brand, brand["id"])]
    db.commit()
    body = {"audience": "Dog owners", "do_list": ["Warm"], "dont_list": ["cure"],
            "music_style": "breezy pop", "default_language": "es", "default_look": "house",
            "default_cast": [mia]}  # fmt: skip
    saved = editor.patch(url, json=body)
    assert saved.status_code == 200, saved.text
    assert {k: saved.json()[k] for k in body if k != "default_cast"} == {
        k: v for k, v in body.items() if k != "default_cast"}  # fmt: skip
    added = editor.post(f"{url}/cta-lines", json={"text": "Link in bio"})
    assert added.status_code == 201
    line = next(x for x in added.json()["cta_lines"] if x["text"] == "Link in bio")["id"]
    assert editor.patch(f"{url}/cta-lines/{line}", json={"text": "Tap the link"}).status_code == 200
    assert editor.delete(f"{url}/cta-lines/{line}").status_code == 200
    assert editor.post(f"{url}/cta-lines/{line}/restore").status_code == 200
    assert (
        editor.post("/brands", json={"name": "Night Owl"}).status_code == 403
    )  # still the owner's
    assert editor.delete(url).status_code == 403
