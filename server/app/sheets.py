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
