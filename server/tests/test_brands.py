from tests.conftest import upload
from tests.helpers import MP3, assert_hidden, assert_no_dollars


def test_launch_brands_exist_after_setup(owner):
    assert [b["slug"] for b in owner.get("/brands").json()] == ["fomo", "iron-paws"]


def test_create_and_edit_kit(editor):
    logo = upload(editor)
    r = editor.post("/brands", json={"name": "Night Owl", "colours": ["#112233"]})
    assert r.status_code == 201
    brand = r.json()
    assert brand["slug"] == "night-owl"
    r = editor.patch(
        f"/brands/{brand['id']}",
        json={
            "logo_file_id": logo,
            "never_say": ["guaranteed returns"],
            "legal_line": "Not advice.",
        },
    )
    kit = r.json()
    assert kit["logo_file_id"] == logo
    assert kit["never_say"] == ["guaranteed returns"]
    assert kit["colours"] == ["#112233"]  # untouched fields stay


def test_bad_colour_and_unknown_file_rejected(owner):
    assert owner.post("/brands", json={"name": "A", "colours": ["red"]}).status_code == 422
    assert owner.post("/brands", json={"name": "A", "logo_file_id": 999}).status_code == 404


def test_duplicate_name_rejected(owner):
    assert owner.post("/brands", json={"name": "FOMO"}).status_code == 409


def test_only_owner_archives(owner, editor):
    brand_id = owner.get("/brands").json()[1]["id"]
    assert editor.delete(f"/brands/{brand_id}").status_code == 403
    assert owner.delete(f"/brands/{brand_id}").status_code == 204
    assert owner.get(f"/brands/{brand_id}").status_code == 404


def test_other_workspace_cannot_touch_brands_or_screens(owner, outsider):
    brand = owner.get("/brands").json()[0]["id"]
    screen = owner.post(
        f"/brands/{brand}/screens", json={"name": "S", "file_id": upload(owner)}
    ).json()["id"]
    assert outsider.get("/brands").json() == []
    assert_hidden(
        outsider,
        [
            ("GET", f"/brands/{brand}"),
            ("PATCH", f"/brands/{brand}", {"tone_notes": "x"}),
            ("GET", f"/brands/{brand}/screens"),
            ("POST", f"/brands/{brand}/screens", {"name": "X", "file_id": upload(outsider)}),
            ("PATCH", f"/brands/{brand}/screens/{screen}", {"name": "Y"}),
            ("DELETE", f"/brands/{brand}/screens/{screen}"),
        ],
    )


def test_cannot_attach_another_workspaces_file(owner, outsider):
    owners_file = upload(owner)
    r = outsider.post("/brands", json={"name": "Mine", "logo_file_id": owners_file})
    assert r.status_code == 404


def test_kit_images_must_be_images(owner):
    song = upload(owner, "a.mp3", MP3, "audio/mpeg")
    assert owner.post("/brands", json={"name": "A", "logo_file_id": song}).status_code == 422
    brand = owner.get("/brands").json()[0]["id"]
    r = owner.post(f"/brands/{brand}/screens", json={"name": "S", "file_id": song})
    assert r.status_code == 422


def test_editor_sees_no_dollars(editor):
    brand = editor.get("/brands").json()[0]["id"]
    assert_no_dollars(editor, ["/brands", f"/brands/{brand}", f"/brands/{brand}/screens"])
