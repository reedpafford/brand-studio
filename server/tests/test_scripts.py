import io
import threading
import time
import zipfile

import pytest

from tests.conftest import upload
from tests.helpers import MP4, assert_hidden


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


def _pdf(text: str, pages: int = 1) -> bytes:
    """A small valid PDF with `pages` pages, each showing `text`."""
    stream = f"BT /F1 24 Tf 72 700 Td ({text}) Tj ET".encode()
    kids = " ".join(f"{5 + 2 * n} 0 R" for n in range(pages))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids.encode(), pages),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    for _ in range(pages):
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
            b" /Resources << /Font << /F1 3 0 R >> >> >>"
        )
        objects.append(b"<< >>")  # padding so page ids stay 5, 7, 9, ...
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, obj in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + obj + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    out.write(b"".join(b"%010d 00000 n \n" % o for o in offsets))
    trailer = b"trailer << /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF"
    out.write(trailer % (len(objects) + 1, xref))
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


def test_huge_pdfs_are_refused_quickly(editor, project):
    started = time.monotonic()
    r = _upload(editor, project, "big.pdf", _pdf("x", pages=301), "application/pdf")
    assert r.status_code == 422 and "too many pages" in r.json()["detail"]
    long_page = "word " * 400  # ~2,000 characters a page; 30 pages pass 50,000
    r = _upload(editor, project, "long.pdf", _pdf(long_page, pages=30), "application/pdf")
    assert r.status_code == 422 and "too long" in r.json()["detail"]
    assert time.monotonic() - started < 10


def test_non_utf8_text_gets_a_helpful_hint(editor, project):
    r = _upload(editor, project, "s.txt", "Café olé".encode("cp1252"), "text/plain")
    assert r.status_code == 422 and "UTF-8" in r.json()["detail"]


def test_two_saves_at_once_both_get_a_version(app, editor, project, db):
    from app.models.accounts import User
    from app.models.projects import Project
    from app.routes.scripts import save_version

    barrier, numbers = threading.Barrier(2), []
    ed = db.query(User).filter_by(email="ed@example.com").one()

    def save(text):
        with app.state.sessionmaker() as s:
            barrier.wait()
            numbers.append(
                save_version(s, s.get(User, ed.id), s.get(Project, project), text, "paste").version
            )

    threads = [threading.Thread(target=save, args=(t,)) for t in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(numbers) == [1, 2]
