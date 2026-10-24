"""Which pictures of a library item may go into a generation (Reed, 2026-10-23): for
characters and places only the approved house-style sheet, never the uploaded photo; props
use their pictures as before."""

from fastapi import HTTPException

from app.models.library import Kind, LibraryItem

SHEET_KINDS = (Kind.character, Kind.place)


def usable_files(item: LibraryItem) -> list[int]:
    if item.kind in SHEET_KINDS:
        return [item.sheet_file_id] if item.sheet_approved and item.sheet_file_id else []
    return list(item.image_file_ids)


def require_sheet(item: LibraryItem) -> None:
    """A plain 422 when a character or place has no approved sheet yet."""
    if item.kind in SHEET_KINDS and not usable_files(item):
        raise HTTPException(422, f"Approve {item.name}'s sheet first.")


def require_cast_sheets(db, breakdown_data: dict, shot_ids: list[str]) -> None:
    """Every character and place a shot names needs an approved sheet, whether or not the
    frame or clip attaches it, so editors find out before spending on anything."""
    ids = []
    for scene in breakdown_data.get("scenes", []):
        for shot in scene.get("shots", []):
            if shot["id"] in shot_ids:
                ids += [*shot.get("character_ids", []), shot.get("place_id")]
    for ref in dict.fromkeys(i for i in ids if i and i.startswith(("char:", "place:"))):
        item = db.get(LibraryItem, int(ref.split(":")[1]))
        if item:
            require_sheet(item)
