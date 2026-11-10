"""New video's product picks (Reed, 10 Nov): the brand's products a person picked for a video
(`projects.product_ids`), as the treatment and the idea writer read them."""

from sqlalchemy.orm import Session

from app.enhance import escape
from app.models.library import LibraryItem


def context(db: Session, project) -> str:
    """The <products> block the picks add to the treatment's and the idea writer's input, each
    product by the id its real picture is attached under. "" with none picked."""
    items = [db.get(LibraryItem, i) for i in project.product_ids or []]
    lines = "\n".join(
        " | ".join(x for x in (f"prop:{i.id}", i.name, i.short_description,
                               i.main_claim and f"claim: {i.main_claim}") if x)
        for i in items if i is not None and not i.archived)  # fmt: skip
    if not lines:
        return ""
    return ("\n<products>\nThe person picked these products of the brand: this ad is about "
            f"them.\n{escape(lines)}\n</products>")  # fmt: skip
