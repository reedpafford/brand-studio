import pytest

from app.models.files import StoredFile
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


def test_other_workspace_cannot_read_file(owner, outsider):
    file_id = upload(owner)
    assert outsider.get(f"/files/{file_id}").status_code == 404


def test_unknown_file_is_404(owner):
    assert owner.get("/files/999").status_code == 404


def test_contents_must_match_declared_type(owner):
    r = owner.post("/files", files={"upload": ("a.png", b"<html><script>", "image/png")})
    assert r.status_code == 415


@pytest.mark.parametrize(
    ("content_type", "head"),
    [
        ("image/jpeg", b"\xff\xd8\xff\xe0"),
        ("image/gif", b"GIF89a"),
        ("image/webp", b"RIFF\0\0\0\0WEBP"),
        ("audio/wav", b"RIFF\0\0\0\0WAVE"),
        ("audio/mpeg", b"\xff\xfb\x90"),
        ("video/mp4", b"\0\0\0\x18ftypmp42"),
        ("video/webm", b"\x1a\x45\xdf\xa3"),
    ],
)
def test_known_signatures_accepted(owner, content_type, head):
    upload(owner, "f", head + b"0" * 16, content_type)


def test_oversize_content_length_refused_before_reading(app, owner):
    limit = app.state.settings.max_upload_mb * 1024 * 1024
    r = owner.post("/files", content=b"x", headers={"content-length": str(limit * 2)})
    assert r.status_code == 413


def test_missing_bytes_on_disk_is_404(app, owner, db):
    file_id = upload(owner)
    app.state.storage.delete(db.get(StoredFile, file_id).key)
    assert owner.get(f"/files/{file_id}").status_code == 404
