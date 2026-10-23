from tests.conftest import upload
from tests.helpers import MP4, assert_hidden, assert_no_dollars


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


def test_editor_sees_no_dollars(editor):
    item = editor.post("/library/place", json={"name": "Gym"}).json()
    assert_no_dollars(editor, ["/library/place", f"/library/place/{item['id']}"])


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
