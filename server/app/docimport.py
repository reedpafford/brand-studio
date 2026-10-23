"""Turn an uploaded script document (txt, docx, pdf) into plain text."""

import io
import re
import zipfile
from xml.etree.ElementTree import ParseError

from defusedxml import ElementTree  # safe against entity-expansion tricks
from pypdf import PdfReader

WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MAX_UNZIPPED = 20 * 1024 * 1024
MAX_PAGES = 300
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


def to_text(data: bytes, kind: str, max_chars: int = 50_000) -> str:
    """Plain text from the document. Stops early (and refuses) past `max_chars` or
    `MAX_PAGES`, so a huge file can't tie the server up."""
    too_long = DocumentError(f"That script is too long ({max_chars:,} characters max).")
    try:
        if kind == "txt":
            text = data.decode("utf-8-sig")
        elif kind == "docx":
            text = _docx(data)
        else:
            text = _pdf(data, max_chars, too_long)
    except DocumentError:
        raise
    except UnicodeDecodeError as exc:
        raise DocumentError("Save the file as UTF-8 text, or paste the script.") from exc
    except (zipfile.BadZipFile, KeyError, ParseError) as exc:
        raise DocumentError("That file couldn't be read. Try pasting the text.") from exc
    except Exception as exc:  # noqa: BLE001 - pypdf raises many kinds on broken files
        raise DocumentError("That PDF couldn't be read. Try pasting the text instead.") from exc
    text = re.sub(r"[ \t]+\n", "\n", text.replace("\r\n", "\n")).strip()
    if not text:
        raise DocumentError("No text found in that file (scanned PDFs aren't supported yet).")
    if len(text) > max_chars:
        raise too_long
    return text


def _pdf(data: bytes, max_chars: int, too_long: DocumentError) -> str:
    pages = PdfReader(io.BytesIO(data)).pages
    if len(pages) > MAX_PAGES:
        raise DocumentError(f"That PDF has too many pages ({MAX_PAGES} max).")
    parts, size = [], 0
    for page in pages:
        text = page.extract_text() or ""
        size += len(text)
        if size > max_chars:
            raise too_long
        parts.append(text)
    return "\n".join(parts)


def _docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if z.getinfo("word/document.xml").file_size > MAX_UNZIPPED:  # zip bomb guard
            raise DocumentError("That document is too big to read.")
        root = ElementTree.fromstring(z.read("word/document.xml"))
    paragraphs = []
    for p in root.iter(f"{WORD}p"):
        paragraphs.append("".join(t.text or "" for t in p.iter(f"{WORD}t")))
    return "\n".join(paragraphs)
