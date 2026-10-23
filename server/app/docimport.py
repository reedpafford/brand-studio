"""Turn an uploaded script document (txt, docx, pdf) into plain text."""

import io
import re
import zipfile
from xml.etree.ElementTree import ParseError

from defusedxml import ElementTree  # safe against entity-expansion tricks
from pypdf import PdfReader

WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MAX_UNZIPPED = 20 * 1024 * 1024
KINDS = {
    "text/plain": "txt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/pdf": "pdf",
}


class DocumentError(ValueError):
    """The document couldn't be read; the message is safe to show."""


def kind_of(filename: str, content_type: str | None) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    kind = KINDS.get(content_type or "") or (ext if ext in KINDS.values() else "")
    if not kind:
        raise DocumentError("Upload a .txt, .docx or .pdf file.")
    return kind


def to_text(data: bytes, kind: str) -> str:
    try:
        if kind == "txt":
            text = data.decode("utf-8-sig")
        elif kind == "docx":
            text = _docx(data)
        else:
            text = "\n".join(
                page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages
            )
    except (UnicodeDecodeError, zipfile.BadZipFile, KeyError, ParseError) as exc:
        raise DocumentError(
            "That file couldn't be read. Try saving it again or paste the text."
        ) from exc
    except Exception as exc:  # noqa: BLE001 - pypdf raises many kinds on broken files
        raise DocumentError("That PDF couldn't be read. Try pasting the text instead.") from exc
    text = re.sub(r"[ \t]+\n", "\n", text.replace("\r\n", "\n")).strip()
    if not text:
        raise DocumentError("No text found in that file (scanned PDFs aren't supported yet).")
    return text


def _docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if z.getinfo("word/document.xml").file_size > MAX_UNZIPPED:  # zip bomb guard
            raise DocumentError("That document is too big to read.")
        root = ElementTree.fromstring(z.read("word/document.xml"))
    paragraphs = []
    for p in root.iter(f"{WORD}p"):
        paragraphs.append("".join(t.text or "" for t in p.iter(f"{WORD}t")))
    return "\n".join(paragraphs)
