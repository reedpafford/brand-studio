import pytest

from app.storage import LocalStorage
from tests.conftest import PNG, upload


def test_upload_then_download(editor):
    file_id = upload(editor)
    r = editor.get(f"/files/{file_id}")
    assert r.content == PNG
    assert r.headers["content-type"] == "image/png"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_rejects_svg(owner):
    r = owner.post("/files", files={"upload": ("x.svg", b"<svg/>", "image/svg+xml")})
    assert r.status_code == 415


def test_rejects_too_big(app, owner):
    app.state.settings.max_upload_mb = 0
    r = owner.post("/files", files={"upload": ("a.png", PNG, "image/png")})
    assert r.status_code == 413


def test_needs_login(client):
    assert client.get("/files/1").status_code == 401


def test_storage_refuses_keys_outside_its_folder(tmp_path):
    with pytest.raises(ValueError):
        LocalStorage(tmp_path).put("../escape", b"x")
