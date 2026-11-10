"""Story cards (New video's front door, Reed 10 Nov): a preset brief a person may start a video
from. Each is one file, app/guides/cards/<id>.md (`guides.card` reads it): `key: value` lines
(title, subtitle, style, format, seconds, order; `shape` and `on: no` are optional), a blank
line, then the brief. The web sends only the card's id; its brief goes to the models
(`context`), never to people."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import guides, looks
from app.enhance import escape
from app.models.library import LibraryItem

UNKNOWN = "There's no such story card."
OFF = "That story card isn't available right now. Pick another, or start without one."


def find(card_id: str | None) -> dict | None:
    return next((c for c in guides.cards() if c["id"] == card_id), None)


def on(db: Session, workspace_id: int, card: dict) -> bool:
    """A card can be started from: not `on: no`, its style shown and switched on for this
    workspace, and that style made in its format."""
    return (card["on"] and not looks.get(card["style"])["hidden"]
            and looks.is_on(db, workspace_id, card["style"])
            and not looks.format_refusal(card["style"], card["format"]))  # fmt: skip


def pick(db: Session, workspace_id: int, card_id: str) -> dict:
    """The card a send starts from, or a plain 422."""
    card = find(card_id)
    if card is None:
        raise HTTPException(422, UNKNOWN)
    if not on(db, workspace_id, card):
        raise HTTPException(422, OFF)
    return card


def context(db: Session, project) -> str:
    """What New video's picks add to the treatment's and the idea writer's input: the card's
    brief as <card>, and the brand's products picked for this video as <products>, each by
    the id its real picture is attached under. "" with neither."""
    out = ""
    if card := find(project.card):
        out += f"\n<card>\n{escape(card['brief'])}\n</card>"
    items = [db.get(LibraryItem, i) for i in project.product_ids or []]
    lines = "\n".join(
        " | ".join(x for x in (f"prop:{i.id}", i.name, i.short_description,
                               i.main_claim and f"claim: {i.main_claim}") if x)
        for i in items if i is not None and not i.archived)  # fmt: skip
    if lines:
        out += ("\n<products>\nThe person picked these products of the brand: this ad is about "
                f"them.\n{escape(lines)}\n</products>")  # fmt: skip
    return out
