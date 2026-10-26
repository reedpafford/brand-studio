"""Which pictures of a library item may go into a generation (Reed, 2026-10-23): for
characters and places only the approved house-style sheet, never the uploaded photo; props
use their pictures as before."""

from decimal import Decimal

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


def require_cast_sheets(db, breakdown_data: dict, shot_ids: list[str], known=None) -> None:
    """Every character and place a shot names needs an approved sheet, whether or not the
    frame or clip attaches it, so editors find out before spending on anything. One the
    video's pictures (`known`) already have, e.g. a locked role's sheet, is fine."""
    ids = []
    for scene in breakdown_data.get("scenes", []):
        for shot in scene.get("shots", []):
            if shot["id"] in shot_ids:
                ids += [*shot.get("character_ids", []), shot.get("place_id")]
    for ref in dict.fromkeys(i for i in ids if i and i.startswith(("char:", "place:"))):
        if known and known.get(ref) and known[ref][-1]:
            continue
        item = db.get(LibraryItem, int(ref.split(":")[1]))
        if item:
            require_sheet(item)


SHEET_MODEL, RESOLUTION = "nano-banana-pro", "2K"  # what Make a look and Make sheet draw with


def sheet_price(db, workspace_id: int, model: str = SHEET_MODEL) -> Decimal:
    """One sheet with the given model, as it's drawn."""
    from app.credits import estimate

    job = {"model": model, "input": {"resolution": RESOLUTION}}
    return estimate(db, workspace_id, "image", Decimal(1), job)


def check_price(db, workspace_id: int) -> Decimal:
    """One look-fit check (a small Claude call)."""
    from app.credits import estimate

    return estimate(db, workspace_id, "check-claude", Decimal(1))


def is_checked(item: LibraryItem) -> bool:
    """Sheets of a character drawn from a description get the look-fit check; one from an
    uploaded photo doesn't (the photo is the truth), nor do places."""
    return item.kind == Kind.character and not item.source_photo_file_id


def worst(sheet: Decimal, check: Decimal, checked: bool, change: bool) -> Decimal:
    """What one press can spend at most, so the price shown is never below the charge: the
    sheet, its check, and (unless the press is the person's own change) the one automatic
    redo with its check."""
    if not checked:
        return sheet
    return (sheet + check) * (1 if change else 2)


def usual(sheet: Decimal, check: Decimal, checked: bool) -> Decimal:
    """What a press usually costs: the sheet and its check, no redo ("Usually 2")."""
    return sheet + (check if checked else Decimal(0))


def press_price(db, item: LibraryItem, change: bool = False) -> Decimal:
    ws = item.workspace_id
    return worst(sheet_price(db, ws), check_price(db, ws), is_checked(item), change)


def press_usual(db, item: LibraryItem) -> Decimal:
    ws = item.workspace_id
    return usual(sheet_price(db, ws), check_price(db, ws), is_checked(item))


def look_usual(db, workspace_id: int) -> Decimal:
    return usual(sheet_price(db, workspace_id), check_price(db, workspace_id), True)


def look_price(db, workspace_id: int) -> Decimal:
    """Make a look: a new character from its role's description, checked."""
    return worst(sheet_price(db, workspace_id), check_price(db, workspace_id), True, False)
