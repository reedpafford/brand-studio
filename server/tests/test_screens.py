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
    screens = {s["name"]: s for s in owner.get(f"/brands/{fomo.id}/screens").json()}
    assert screens["home"]["tags"] == ["desktop"]
    assert screens["trading-chart-up-mobile"]["tags"] == ["chart-up", "mobile", "trading"]
    assert screens["trading-chart-up-mobile"]["default_for"] == ["trading"]
    assert owner.get(f"/files/{screens['home']['file_id']}").content == PNG


def _setup_with_screens_dir(app, client, folder):
    app.state.settings.fomo_screens_dir = str(folder)
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


def test_real_fomo_assets_import_with_names_moments_logo_and_style_board(app, owner, db):
    from app.settings import Settings

    folder = Path(Settings().fomo_screens_dir)
    fomo = db.query(Brand).filter_by(slug="fomo").one()
    assert import_screens(db, app.state.storage, fomo, folder) == 4
    screens = {s["name"]: s for s in owner.get(f"/brands/{fomo.id}/screens").json()}
    assert screens["Token chart up"]["default_for"] == ["trading", "win"]
    assert screens["Home"]["tags"] == ["home", "mobile"]
    kit = owner.get(f"/brands/{fomo.id}").json()
    assert kit["logo_file_id"] and kit["style_board_file_id"]
    assert owner.get(f"/files/{kit['logo_file_id']}").headers["content-type"] == "image/png"
