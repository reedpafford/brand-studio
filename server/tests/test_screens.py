from app.models.brands import Brand
from app.seed import import_screens
from tests.conftest import PNG, upload


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
