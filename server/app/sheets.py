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
    if known is not None:  # a role with no look yet (Reed, 2026-10-27: never drawn without one)
        require_looks([[i for i in ids if i]], known)


def lookless(shots: list[list[str]], known: dict) -> list[str]:
    """The names of the roles in these shots (each a list of character ids) that have no
    approved look yet, each once."""
    out = [r.partition(":")[2] for ids in shots for r in ids if r.startswith("unroled:")]
    for ref in (r for ids in shots for r in ids if r.startswith("slot:")):
        if ref in known and not known[ref][-1]:
            parts = known[ref][0].split(" | ")
            out.append(parts[2].split(",")[0].strip() if len(parts) > 2 else "A character")
    return list(dict.fromkeys(out))


def require_looks(shots: list[list[str]], known: dict, status: int = 422) -> None:
    """Refuse while a role in the shots has no approved look (Reed, 2026-10-27: nothing
    reaches Storyboard or Clips without a sheet for every character in it), naming them and
    pointing to Assets, where their looks are made."""
    if names := lookless(shots, known):
        if len(names) == 1:
            raise HTTPException(
                status, f"{names[0]} has no approved look yet. Approve one in Assets."
            )
        who = f"{', '.join(names[:-1])} and {names[-1]}"
        raise HTTPException(status, f"{who} have no approved look yet. Approve them in Assets.")


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
