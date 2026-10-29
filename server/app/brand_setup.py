"""Brand setup (flows BR1): voice and tone, CTA lines, default cast and the brand's defaults.
Only the owner changes a brand; editors read it. No change here touches a script, version or
video: later steps read the brand live (BR1's S state).

`never_say` and `end_line` are main's fields. Next keeps them and writes them through on every
change (`sync`): never_say = dont_list, end_line = the default CTA line's text. A write to
either old field (main's code, an old screen) comes back into the new ones (`from_legacy`).
They are dropped at the move to main (ops/NEXT.md)."""

import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models.brands import Brand

NO_CTA = "Videos will end without a saved call to action."
NO_LINE = "No such call to action line."


def live(brand: Brand) -> list[dict]:
    return [x for x in brand.cta_lines or [] if not x.get("deleted_at")]


def default_line(brand: Brand) -> str:
    return next((x["text"] for x in live(brand) if x.get("default")), "")


def _tidy(items: list[str]) -> list[str]:
    """Trimmed, blanks dropped, duplicates dropped (order kept)."""
    return list(dict.fromkeys(x.strip() for x in items if x.strip()))


def sync(brand: Brand) -> None:
    """Exactly one default among the live lines (the first, if none is), then main's fields."""
    lines = [dict(x) for x in brand.cta_lines or []]
    alive = [x for x in lines if not x.get("deleted_at")]
    if alive and sum(bool(x.get("default")) for x in alive) != 1:
        first = next((x for x in alive if x.get("default")), alive[0])
        for x in alive:
            x["default"] = x is first
    for x in lines:
        if x.get("deleted_at"):
            x["default"] = False
    brand.cta_lines = lines
    brand.dont_list = _tidy(brand.dont_list or [])
    brand.do_list = _tidy(brand.do_list or [])
    brand.never_say = list(brand.dont_list)
    brand.end_line = default_line(brand)


def from_legacy(brand: Brand, values: dict) -> None:
    """main's `never_say` / `end_line` written directly: carry them into the new fields."""
    if "never_say" in values and "dont_list" not in values:
        brand.dont_list = list(values["never_say"])
    if "end_line" in values and values["end_line"].strip() != default_line(brand):
        text = values["end_line"].strip()
        if not text:  # cleared: the default line goes (Undo-able like any delete)
            found = next((x for x in live(brand) if x.get("default")), None)
            if found:
                delete_line(brand, found["id"])
            return
        found = next((x for x in live(brand) if x.get("default")), None)
        if found:
            edit_line(brand, found["id"], text=text)
        else:
            add_line(brand, text, default=True)


def _find(brand: Brand, line_id: str, deleted: bool = False) -> dict:
    lines = brand.cta_lines or []
    found = next((x for x in lines if x["id"] == line_id
                  and bool(x.get("deleted_at")) == deleted), None)  # fmt: skip
    if found is None:
        raise HTTPException(404, NO_LINE)
    return found


def add_line(brand: Brand, text: str, default: bool = False) -> dict:
    line = {"id": uuid.uuid4().hex[:12], "text": text.strip(), "default": False,
            "deleted_at": None}  # fmt: skip
    brand.cta_lines = [*(brand.cta_lines or []), line]
    if default or not live(brand)[:-1]:  # the first line is the default
        _make_default(brand, line["id"])
    sync(brand)
    return line


def _make_default(brand: Brand, line_id: str) -> None:
    brand.cta_lines = [{**x, "default": x["id"] == line_id} for x in brand.cta_lines]


def edit_line(brand: Brand, line_id: str, text: str | None = None, default=None) -> None:
    _find(brand, line_id)
    if text is not None:
        brand.cta_lines = [{**x, "text": text.strip()} if x["id"] == line_id else x
                           for x in brand.cta_lines]  # fmt: skip
    if default:
        _make_default(brand, line_id)
    sync(brand)


def delete_line(brand: Brand, line_id: str) -> str | None:
    """Delete a line (Undo: `restore_line`). Deleting the default promotes the next live line
    (or the one before, at the end); returns the promoted line's id."""
    line = _find(brand, line_id)
    alive = live(brand)
    promoted = None
    if line.get("default"):
        at = alive.index(line)
        rest = alive[at + 1 :] + alive[:at][::-1]
        promoted = rest[0]["id"] if rest else None
    stamp = utcnow().isoformat()
    brand.cta_lines = [{**x, "deleted_at": stamp, "was_default": bool(x.get("default"))}
                       if x["id"] == line_id else x for x in brand.cta_lines]  # fmt: skip
    if promoted:
        _make_default(brand, promoted)
    sync(brand)
    return promoted


def restore_line(brand: Brand, line_id: str) -> None:
    """Undo a delete: the line comes back where it was, and the default again if it was."""
    line = _find(brand, line_id, deleted=True)
    was = line.get("was_default")
    brand.cta_lines = [{k: v for k, v in x.items() if k != "was_default"} | {"deleted_at": None}
                       if x["id"] == line_id else x for x in brand.cta_lines]  # fmt: skip
    if was:
        _make_default(brand, line_id)
    sync(brand)


def cast_out(db: Session, brand: Brand) -> list[dict]:
    """The default cast for the page: a picked character later deleted or archived reads
    {id, name, deleted: true}, for "Deleted: pick another" (Pick another / Remove)."""
    from app.models.library import LibraryItem

    out = []
    for item_id in brand.default_cast or []:
        item = db.get(LibraryItem, item_id)
        gone = item is None or item.archived or item.workspace_id != brand.workspace_id
        out.append({"id": item_id, "name": "" if item is None else item.name, "deleted": gone})
    return out


def live_cast(db: Session, brand: Brand) -> list[int]:
    """The default cast still in the library (deleted or archived picks are skipped)."""
    return sorted(x["id"] for x in cast_out(db, brand) if not x["deleted"])


def check_cast(db: Session, brand: Brand, ids: list[int]) -> list[int]:
    """Characters from this workspace's library (not a look made for one video or script)."""
    from app.models.library import Kind, LibraryItem

    for item_id in ids:
        item = db.get(LibraryItem, item_id)
        if (
            item is None
            or item.workspace_id != brand.workspace_id
            or item.archived
            or item.kind != Kind.character
            or item.owner_project_id
            or item.owner_script_id
        ):
            raise HTTPException(422, "Pick characters from Cast & places.")
    return list(dict.fromkeys(ids))


def advice(brand: Brand) -> list[str]:
    """The page's Advice (never a block)."""
    return [] if live(brand) else [NO_CTA]
