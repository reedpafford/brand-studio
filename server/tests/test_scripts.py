import io
import zipfile

import pytest

from tests.conftest import upload
from tests.helpers import MP4, assert_hidden, assert_no_dollars


def _docx(*paragraphs: str) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("word/document.xml", xml)
    return out.getvalue()


def _pdf(text: str) -> bytes:
    stream = f"BT /F1 24 Tf 72 700 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = io.BytesIO(b"%PDF-1.4\n"), []
    out.seek(0, 2)
    for i, obj in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + obj + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    out.write(b"".join(b"%010d 00000 n \n" % o for o in offsets))
    out.write(
        b"trailer << /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objects) + 1, xref)
    )
    return out.getvalue()


@pytest.fixture
def project(owner, editor):
    fomo = owner.get("/brands").json()[0]["id"]
    body = {"brand_id": fomo, "name": "Launch", "planned_seconds": 30}
    return editor.post("/projects", json=body).json()["id"]


def _upload(client, project, name, data, ctype):
    return client.post(f"/projects/{project}/script/upload", files={"upload": (name, data, ctype)})


def test_paste_then_upload_keeps_versions(editor, project):
    url = f"/projects/{project}/script"
    assert editor.get(url).status_code == 404
    assert editor.put(url, json={"text": "  Hook: a cat buys the dip.  "}).json()["version"] == 1
    r = _upload(editor, project, "v2.txt", b"Hook: the cat sells.\nEnd card.", "text/plain")
    assert (r.json()["version"], r.json()["source"], r.json()["words"]) == (2, "upload", 6)
    assert editor.get(url).json()["text"].startswith("Hook: the cat sells.")
    assert [v["version"] for v in editor.get(f"{url}/versions").json()] == [2, 1]
    assert editor.get(f"{url}/versions/1").json()["text"] == "Hook: a cat buys the dip."


def test_docx_and_pdf_become_text(editor, project):
    r = _upload(
        editor, project, "s.docx", _docx("Scene one.", "Scene two."), "application/octet-stream"
    )
    assert r.json()["text"] == "Scene one.\nScene two."
    r = _upload(editor, project, "s.pdf", _pdf("Buy the dip"), "application/pdf")
    assert r.status_code == 201, r.text
    assert "Buy the dip" in r.json()["text"]


@pytest.mark.parametrize(
    ("name", "data", "ctype"),
    [
        ("s.rtf", b"{\\rtf1 hi}", "application/rtf"),
        ("s.docx", b"not a zip", "application/octet-stream"),
        ("s.pdf", b"%PDF-1.4 garbage", "application/pdf"),
        ("s.txt", b"\xff\xfe\x00bad", "text/plain"),
        ("s.txt", b"   ", "text/plain"),
        ("s.txt", b"x" * 50_001, "text/plain"),
    ],
)
def test_unreadable_documents_get_a_plain_422(editor, project, name, data, ctype):
    r = _upload(editor, project, name, data, ctype)
    assert r.status_code == 422 and r.json()["detail"]


def test_oversize_document_refused_before_reading(editor, project):
    r = editor.post(
        f"/projects/{project}/script/upload",
        content=b"x",
        headers={"content-length": str(30 * 1024 * 1024)},
    )
    assert r.status_code == 413


def test_brief_fields_are_checked(owner, editor, project):
    character = editor.post("/library/character", json={"name": "Max"}).json()["id"]
    place = editor.post("/library/place", json={"name": "Gym"}).json()["id"]
    video, image = upload(editor, "r.mp4", MP4, "video/mp4"), upload(editor)
    url = f"/projects/{project}"
    brief = {
        "goal": "Sign-ups",
        "platform": "tiktok",
        "aspect_ratio": "16:9",
        "cast_ids": [character],
    }
    r = editor.patch(url, json={**brief, "reference_file_id": video})
    assert {k: r.json()[k] for k in brief} == brief
    assert editor.patch(url, json={"cast_ids": None}).json()["cast_ids"] == [character]
    assert editor.patch(url, json={"cast_ids": [place]}).status_code == 404
    assert editor.patch(url, json={"reference_file_id": image}).status_code == 422
    assert editor.patch(url, json={"aspect_ratio": "2:1"}).status_code == 422
    assert editor.patch(url, json={"reference_file_id": None}).json()["reference_file_id"] is None


def test_other_workspace_is_shut_out(owner, editor, outsider, project):
    editor.put(f"/projects/{project}/script", json={"text": "Hi"})
    url = f"/projects/{project}/script"
    assert_hidden(
        outsider,
        [
            ("GET", url),
            ("PUT", url, {"text": "x"}),
            ("GET", f"{url}/versions"),
            ("GET", f"{url}/versions/1"),
        ],
    )
    character = owner.post("/library/character", json={"name": "Max"}).json()["id"]
    fomo = outsider.post("/brands", json={"name": "Mine"}).json()["id"]
    body = {"brand_id": fomo, "name": "P", "planned_seconds": 10, "cast_ids": [character]}
    assert outsider.post("/projects", json=body).status_code == 404


def test_editor_sees_no_dollars(editor, project):
    editor.put(f"/projects/{project}/script", json={"text": "Hi"})
    url = f"/projects/{project}/script"
    assert_no_dollars(editor, [url, f"{url}/versions", f"/projects/{project}"])
