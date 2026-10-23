from tests.conftest import upload


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
