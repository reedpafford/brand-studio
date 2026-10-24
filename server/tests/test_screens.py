from pathlib import Path

from app.models.brands import Brand
from app.seed import import_screens
from tests.conftest import PASSWORD, PNG, SETUP_TOKEN, upload


def _fomo(client) -> int:
    return client.get("/brands").json()[0]["id"]


def test_add_filter_and_delete_screens(editor):
    fomo = _fomo(editor)
    base = f"/brands/{fomo}/screens"
    file_id = upload(editor)
    up = {"name": "Buy screen", "file_id": file_id, "tags": ["trading", "Mobile", "mobile"]}
    r = editor.post(base, json={**up, "default_for": ["trading"]})
    assert r.status_code == 201
    assert r.json()["tags"] == ["mobile", "trading"]
    editor.post(base, json={"name": "Desk", "file_id": file_id, "tags": ["desktop"]})
    assert [s["name"] for s in editor.get(base, params={"tag": "mobile"}).json()] == ["Buy screen"]
    assert [s["name"] for s in editor.get(base, params={"moment": "trading"}).json()] == [
        "Buy screen"
    ]
    assert editor.delete(f"{base}/{r.json()['id']}").status_code == 204
    assert [s["name"] for s in editor.get(base).json()] == ["Desk"]


def test_duplicate_screen_name_rejected(owner):
    base = f"/brands/{_fomo(owner)}/screens"
    body = {"name": "A", "file_id": upload(owner)}
    owner.post(base, json=body)
    assert owner.post(base, json=body).status_code == 409


def test_import_folder_uses_manifest_or_filename(app, owner, db, tmp_path):
    folder = tmp_path / "fomo-ui"
    folder.mkdir()
    (folder / "trading-chart-up-mobile.png").write_bytes(PNG)
    (folder / "home.png").write_bytes(PNG)
    (folder / "notes.txt").write_text("ignored")
    (folder / "screens.json").write_text('{"home.png": {"tags": ["desktop"]}}')
    fomo = db.query(Brand).filter_by(slug="fomo").one()
    assert import_screens(db, app.state.storage, fomo, folder) == 2
    assert import_screens(db, app.state.storage, fomo, folder) == 0  # re-run skips existing
    (folder / "screens.json").write_text(
        '{"home.png": {"tags": ["desktop"], "product": "app", "variant": "Light"}}'
    )
    import_screens(db, app.state.storage, fomo, folder)  # a variant added later is filled in
    home = owner.get(f"/brands/{fomo.id}/screens").json()
    assert [(s["product"], s["variant"]) for s in home if s["name"] == "home"] == [("app", "Light")]
    screens = {s["name"]: s for s in owner.get(f"/brands/{fomo.id}/screens").json()}
    assert screens["home"]["tags"] == ["desktop"]
    assert screens["trading-chart-up-mobile"]["tags"] == ["chart-up", "mobile", "trading"]
    assert screens["trading-chart-up-mobile"]["default_for"] == ["trading"]
    assert owner.get(f"/files/{screens['home']['file_id']}").content == PNG

    # A manifest change reaches screens already imported; a screen it doesn't name is left alone.
    owner.patch(f"/brands/{fomo.id}/screens/{screens['trading-chart-up-mobile']['id']}",
                json={"default_for": ["win"]})  # fmt: skip
    (folder / "screens.json").write_text(
        '{"home.png": {"tags": ["desktop"], "default_for": ["win"]}}'
    )
    import_screens(db, app.state.storage, fomo, folder)
    screens = {s["name"]: s for s in owner.get(f"/brands/{fomo.id}/screens").json()}
    assert (screens["home"]["default_for"], screens["home"]["variant"]) == (["win"], "")
    assert screens["trading-chart-up-mobile"]["default_for"] == ["win"]  # the editor's change


def _setup_with_screens_dir(app, client, folder):
    """`folder` plays fomo's screens folder: <assets>/fomo/screens."""
    assets = folder / "_assets"  # inside the test's own tmp folder
    (assets / "fomo").mkdir(parents=True)
    (assets / "fomo" / "screens").symlink_to(folder, target_is_directory=True)
    app.state.settings.brand_assets_dir = str(assets)
    r = client.post(
        "/auth/setup",
        json={
            "setup_token": SETUP_TOKEN,
            "workspace_name": "S",
            "email": "reed@example.com",
            "name": "Reed",
            "password": PASSWORD,
        },
    )
    assert r.status_code == 201, r.text
    assert client.get("/auth/me").status_code == 200
    fomo = client.get("/brands").json()[0]
    assert fomo["slug"] == "fomo"
    return client.get(f"/brands/{fomo['id']}/screens").json()


def test_setup_imports_fomo_screens_from_folder(app, client, tmp_path):
    (tmp_path / "trading-mobile.png").write_bytes(PNG)
    (tmp_path / "fake.png").write_bytes(b"<html>")  # wrong contents: skipped
    screens = _setup_with_screens_dir(app, client, tmp_path)
    assert [s["name"] for s in screens] == ["trading-mobile"]


def test_setup_still_works_when_screen_import_breaks(app, client, tmp_path):
    (tmp_path / "a.png").write_bytes(PNG)
    (tmp_path / "screens.json").write_text("{not json")
    assert _setup_with_screens_dir(app, client, tmp_path) == []


def test_real_fomo_assets_import_with_names_moments_and_logo(app, owner, db):
    from app.settings import Settings

    folder = Path(Settings().brand_assets_dir) / "fomo" / "screens"
    fomo = db.query(Brand).filter_by(slug="fomo").one()
    assert import_screens(db, app.state.storage, fomo, folder) == 5
    screens = {s["name"]: s for s in owner.get(f"/brands/{fomo.id}/screens").json()}
    assert screens["Token chart up"]["default_for"] == ["trading", "win"]
    assert screens["Home"]["tags"] == ["home", "mobile"]
    assert screens["Home (rich)"]["default_for"] == ["win"]  # the got-rich payoff, not $0.00
    kit = owner.get(f"/brands/{fomo.id}").json()
    assert kit["logo_file_id"] and kit["style_board_file_id"] is None
    assert owner.get(f"/files/{kit['logo_file_id']}").headers["content-type"] == "image/png"


def test_setup_seeds_both_launch_brands_from_repo_assets(app, client):
    from app.settings import Settings

    app.state.settings.brand_assets_dir = Settings().brand_assets_dir
    client.post(
        "/auth/setup",
        json={
            "setup_token": SETUP_TOKEN,
            "workspace_name": "S",
            "email": "reed@example.com",
            "name": "Reed",
            "password": PASSWORD,
        },
    )
    brands = {b["slug"]: b["id"] for b in client.get("/brands").json()}
    fomo = client.get(f"/brands/{brands['fomo']}/screens").json()
    bag = client.get(f"/brands/{brands['iron-paws']}/screens").json()
    assert len(fomo) == 5
    assert [(s["name"], s["tags"]) for s in bag] == [
        ("Chicken bag", ["bag", "product"]),
        ("Peanut butter bag", ["bag", "peanut-butter", "product"]),
    ]
    assert [(s["product"], s["variant"]) for s in bag] == [
        ("bag", "Chicken"),
        ("bag", "Peanut butter"),
    ]
    end = {b["slug"]: b["end_line"] for b in client.get("/brands").json()}
    assert end == {
        "fomo": "Want to trade like me? Download fomo through the link in my bio.",
        "iron-paws": "",
    }
    assert "feeding" in bag[0]["default_for"]
    file = client.get(f"/files/{bag[0]['file_id']}")
    assert file.headers["content-type"] == "image/webp"
    moment = client.get(f"/brands/{brands['iron-paws']}/screens", params={"moment": "feeding"})
    assert [s["name"] for s in moment.json()] == ["Chicken bag", "Peanut butter bag"]
