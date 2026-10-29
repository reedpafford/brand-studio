"""Languages (flows VS1): the list, and English the only one on for editors until a sample
test. Free."""

from app import languages


def test_the_list_has_english_on_and_the_rest_off(editor):
    got = editor.get("/languages").json()
    assert got[0] == {"id": "en", "name": "English", "on": True}
    assert {"id": "es", "name": "Spanish", "on": False} in got
    assert [x["id"] for x in got if x["on"]] == ["en"]


def test_scripts_and_brands_take_only_a_listed_language(owner, editor):
    brand = owner.get("/brands").json()[0]["id"]
    bad = owner.patch(f"/brands/{brand}", json={"default_language": "xx"})
    assert (bad.status_code, bad.json()["detail"]) == (422, languages.UNKNOWN)
    no = owner.post("/scripts", json={"brand_id": brand, "title": "Hi", "language": "xx"})
    assert (no.status_code, no.json()["detail"]) == (422, languages.UNKNOWN)
    off = editor.post("/scripts", json={"brand_id": brand, "title": "Hola", "language": "es"})
    assert (off.status_code, off.json()["detail"]) == (409, languages.OFF.format("Spanish"))
    tried = owner.post("/scripts", json={"brand_id": brand, "title": "Hola", "language": "es"})
    assert tried.json()["language"] == "es"  # the owner may try an Off one


def test_an_off_brand_language_starts_an_editors_script_in_english(owner, editor):
    brand = owner.get("/brands").json()[0]["id"]
    assert owner.patch(f"/brands/{brand}", json={"default_language": "es"}).status_code == 200
    mine = editor.post("/scripts", json={"brand_id": brand, "title": "Hi"}).json()
    theirs = owner.post("/scripts", json={"brand_id": brand, "title": "Hola"}).json()
    assert (mine["language"], theirs["language"]) == ("en", "es")
