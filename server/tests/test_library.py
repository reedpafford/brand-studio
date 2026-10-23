from tests.conftest import upload


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
