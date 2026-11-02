"""A video's locks (director-chat.md §1): choices the owner or editor fixed, which the
director builds around and never changes. People's own presses on the step screens aren't
blocked by them (a later option). Its outfit per character: `outfit`."""

from app.models.projects import Project

LOCKABLE = ("cast", "look", "length", "song", "end_line")  # and "screens": a list of ids
LOCKED = {"cast": "the cast", "look": "the style", "length": "the length", "song": "the song",
          "end_line": "the end line", "screens": "its screens"}  # fmt: skip


def locked(project: Project, choice: str) -> bool:
    return bool((project.locks or {}).get(choice))


def refusal(project: Project, choice: str) -> str:
    """The plain refusal when the director would change a locked choice; "" when it may."""
    return f"Refused: {LOCKED[choice]} is locked for this video." if locked(project, choice) else ""


def outfit(project: Project, item_id: int) -> str:
    """This video's outfit for a character, or "" (the sheet's)."""
    return ((project.outfits or {}).get(f"char:{item_id}") or "").strip()
